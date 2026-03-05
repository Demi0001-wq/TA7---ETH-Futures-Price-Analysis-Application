import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

# Need this to import from src folder correctly
sys.path.append(os.getcwd())

import pytest
from src.main import app, get_db, analyzer, price_update_callback, save_state
from src.database import Base
from src.analyzer import PriceAnalyzer
from src.streamer import BinanceStreamer
from src.alerts import AlertSystem
from src.auth import create_access_token, get_current_user

# Setup a separate test database so we don't wipe our real data
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_final.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    # Helper to use the test db session instead of the production one
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Override the dependency in FastAPI
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    # Create tables before tests and clean up after
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("test_final.db"):
        os.remove("test_final.db")

# --- Testing the Analyzer logic ---

def test_analyzer_basics():
    # Basic check to see if beta updates when we feed it data
    pa = PriceAnalyzer(alert_threshold=1.0)
    assert pa.alert_threshold == 0.01  # 1% threshold
    
    ts = datetime.now()
    # Feed it some fake linear growth to get a beta
    for i in range(12):
        pa.update_price(40000 + i, 2000 + i * 0.05, ts + timedelta(minutes=i))
    
    assert pa.beta != 1.0  # Should have moved from initial value
    assert pa.beta > 0

def test_analyzer_alert():
    # Testing if we actually get an alert when ETH moves on its own
    pa = PriceAnalyzer(alert_threshold=0.1) # low threshold for testing
    ts = datetime.now()
    pa.update_price(40000, 2000, ts)
    # BTC stays flat, ETH jumps 0.5% - should trigger
    alert = pa.update_price(40000, 2010, ts + timedelta(minutes=1))
    assert alert is not None
    assert "INCREASE" in alert["message"]

def test_analyzer_negative_alert():
    # Same thing but for a price drop
    pa = PriceAnalyzer(alert_threshold=0.1)
    ts = datetime.now()
    pa.update_price(40000, 2000, ts)
    # BTC flat, ETH drops 0.5%
    alert = pa.update_price(40000, 1990, ts + timedelta(minutes=1))
    assert alert is not None
    assert "DECREASE" in alert["message"]

def test_analyzer_edge_cases():
    # Making sure it doesn't crash on bad inputs
    pa = PriceAnalyzer()
    assert pa.update_price(0, 2000, datetime.now()) is None
    assert pa.update_price(40000, -1, datetime.now()) is None

# --- Testing the API endpoints ---

def test_api_root():
    # Basic smoke test for the root endpoint
    response = client.get("/")
    assert response.status_code == 200

def test_api_status():
    # Checking the /status response
    from src.main import analyzer as main_analyzer
    main_analyzer.history = main_analyzer.history.iloc[0:0] # clear history
    assert client.get("/status").json()["status"] == "waiting_for_data"
    
    main_analyzer.update_price(40000, 2000, datetime.now())
    res = client.get("/status").json()
    assert res["btc_price"] == 40000

def test_api_auth():
    # Testing the JWT login flow
    res = client.post("/token", data={"username": "admin", "password": "password"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    
    # Try accessing protected data with the token
    res = client.get("/protected-data", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    
    # Unauthorized check
    assert client.get("/protected-data").status_code == 401
    # Wrong pass check
    assert client.post("/token", data={"username": "a", "password": "b"}).status_code == 400

# --- Testing other components ---

@pytest.mark.asyncio
async def test_streamer_logic():
    # Manual test for the processing logic in streamer
    cb = AsyncMock()
    s = BinanceStreamer(on_price_update=cb)
    # Fake BTC update
    await s._process_message({"s": "BTCUSDT", "p": "40000", "E": 1000})
    # Fake ETH update - should trigger callback now
    await s._process_message({"s": "ETHUSDT", "p": "2000", "E": 1001})
    assert cb.called
    
    # Invalid symbol check
    await s._process_message({"s": "INVALID", "p": "100"})
    s.stop()
    assert s.running == False

@pytest.mark.asyncio
async def test_alerts_logic():
    # Testing if alerts get sent to DB mock
    asys = AlertSystem()
    data = {"timestamp": datetime.now(), "change_pct": 1.0, "beta": 1.0, "message": "test"}
    
    with patch("src.alerts.SessionLocal") as mock_db_factory:
        mock_db = MagicMock()
        mock_db_factory.return_value = mock_db
        await asys.send_alert(data)
        assert mock_db.add.called

@pytest.mark.asyncio
async def test_main_callback():
    # Testing the full loop from callback to save_state
    ts = datetime(2026, 3, 6, 0, 0, 0) # exactly on the minute for save_state
    from src.main import analyzer as main_analyzer
    with patch("src.main.alert_system.send_alert", new_callable=AsyncMock) as m:
        with patch("src.main.save_state") as ms:
            main_analyzer.alert_threshold = 0.00001 # force alert
            main_analyzer.update_price(40000, 2000, ts - timedelta(seconds=1))
            await price_update_callback(40000, 2010, ts)
            assert m.called
            assert ms.called

def test_save_state_error():
    # Checking error handling in save_state
    with patch("src.main.cipher_suite.encrypt", side_effect=Exception("oops")):
        save_state() # should just log the error and not crash

@pytest.mark.asyncio
async def test_auth_token_error():
    # Testing various auth failure cases
    with pytest.raises(HTTPException):
        await get_current_user("this-is-not-a-token")
    
    token = create_access_token({}) # token with no 'sub'
    with pytest.raises(HTTPException):
        await get_current_user(token)

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List

from cryptography.fernet import Fernet
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .config import settings
from .database import init_db, get_db
from .models import Alert
from .analyzer import PriceAnalyzer
from .streamer import BinanceStreamer
from .alerts import AlertSystem
from .auth import create_access_token, get_current_user

# standard logging so we can see what's happening
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# file for saving the state of the monitor
STATE_FILE = "data/monitoring_state.json"

# Initialization of encryption suite
if settings.ENCRYPTION_KEY:
    cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode())
else:
    # Fallback to ephemeral key if none provided (for development)
    logger.warning("No ENCRYPTION_KEY found in environment. Using ephemeral key.")
    cipher_suite = Fernet(Fernet.generate_key())

# initializing our main components
analyzer = PriceAnalyzer(
    alert_threshold=settings.ALERT_THRESHOLD_PERCENT,
    alert_window_minutes=settings.ALERT_WINDOW_MINUTES,
    beta_window_hours=settings.BETA_WINDOW_HOURS
)
alert_system = AlertSystem()

async def price_update_callback(btc_price: float, eth_price: float, timestamp: datetime):
    """
    Handles real-time price updates from the data streamer.
    Calculates own movement and triggers alerts if thresholds are exceeded.
    """
    alert_data = analyzer.update_price(btc_price, eth_price, timestamp)
    if alert_data:
        await alert_system.send_alert(alert_data)
    
    # save the state every minute just in case
    if int(timestamp.timestamp()) % 60 == 0:
        save_state()

def save_state():
    """
    Persists the current analysis state to an encrypted local file.
    This allows the application to resume status after a restart.
    """
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        state = {
            "last_update": datetime.now().isoformat(),
            "btc_price": analyzer.history.iloc[-1]["btc_price"] if not analyzer.history.empty else 0,
            "eth_price": analyzer.history.iloc[-1]["eth_price"] if not analyzer.history.empty else 0,
            "beta": analyzer.beta,
            "alert_threshold": settings.ALERT_THRESHOLD_PERCENT
        }
        json_data = json.dumps(state).encode()
        encrypted_data = cipher_suite.encrypt(json_data)
        
        with open(STATE_FILE, "wb") as f:
            f.write(encrypted_data)
        logger.info(f"Saved encrypted state to {STATE_FILE}")
    except Exception as e:
        logger.error(f"Couldn't save state: {e}")

streamer = BinanceStreamer(on_price_update=price_update_callback)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # start up: get the db ready and fire up the streamer
    logger.info("Setting up DB...")
    init_db()
    
    logger.info("Starting the Binance streamer...")
    asyncio.create_task(streamer.start())
    
    yield
    
    # shut down: stop the streamer so it doesn't hang
    logger.info("Shutting down streamer...")
    streamer.stop()

# the main fastapi app instance
app = FastAPI(
    title="ETH Price Monitor",
    description="Student project for monitoring ETH vs BTC movements",
    version="1.0.0",
    lifespan=lifespan
)

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticates users based on environment-configured credentials.
    Returns a JWT access token upon success.
    """
    if form_data.username == settings.ADMIN_USERNAME and form_data.password == settings.ADMIN_PASSWORD:
        access_token = create_access_token(data={"sub": form_data.username})
        return {"access_token": access_token, "token_type": "bearer"}
    raise HTTPException(status_code=400, detail="Wrong user or pass")

@app.get("/")
async def root():
    # just serve the dashboard html file at the root
    return FileResponse("src/static/index.html")

@app.get("/status")
async def get_status():
    # gives the frontend some data to show
    if analyzer.history.empty:
        return {"status": "waiting_for_data"}
        
    return {
        "btc_price": analyzer.history.iloc[-1]["btc_price"],
        "eth_price": analyzer.history.iloc[-1]["eth_price"],
        "beta": analyzer.beta,
        "history_count": len(analyzer.history),
        "last_update": analyzer.history.iloc[-1]["timestamp"].isoformat()
    }

@app.get("/alerts", response_model=List[dict])
async def get_alerts(db: Session = Depends(get_db)):
    # fetches recent alerts from the database
    alerts = db.query(Alert).order_by(Alert.timestamp.desc()).limit(100).all()
    return [a.to_dict() for a in alerts]

@app.get("/protected-data")
async def protected_data(username: str = Depends(get_current_user)):
    # example of a route that needs a login token
    return {"message": f"Hey {username}, here is some secret info."}

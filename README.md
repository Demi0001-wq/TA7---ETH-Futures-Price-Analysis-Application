# ETH Price Monitor (Filtering BTC movements)

This is a personal project to track how ETH moves compared to BTC in real-time. The goal is to see 'pure' ETH price changes by filtering out the general market noise (which is usually driven by BTC).

## How the analysis works
I'm using linear regression to find the 'Beta' (correlation) between ETH and BTC using data from the last 24 hours.

The 'own' movement of ETH is basically what's left over:
$$R_{ETH, own} = R_{ETH, total} - \beta \cdot R_{BTC, total}$$

If this own movement jumps or drops by 1% in an hour, the program sends an alert. It helps me find events that are only affecting Ethereum.

## Tech stack I used
- Python 3.11 (trying to follow OOP)
- FastAPI (for the backend and simple dashboard)
- SQLAlchemy (to keep a log of alerts in a local SQLite file)
- WebSockets (to get live prices from Binance)
- Pandas/NumPy (for the math parts)
- Docker (to make it easy to run anywhere)

## Getting it running

### Quick start with Docker
The easiest way is to use docker-compose:
```bash
cp .env.example .env
docker-compose up --build
```

### Running it manually
1. Install what's in requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the server using uvicorn:
   ```bash
   uvicorn src.main:app --host 0.0.0.0 --port 8000
   ```

## Where to find things
- `GET /` -> My dashboard
- `GET /status` -> Current prices and stats
- `GET /alerts` -> History of recent alerts
- `POST /token` -> Login for the dashboard (admin / password)

- `src/` -> Most of the code lives here
- `tests/` -> Some unit tests i wrote
- `thesis/` -> Documents for my thesis
- `data/` -> Where the database gets saved

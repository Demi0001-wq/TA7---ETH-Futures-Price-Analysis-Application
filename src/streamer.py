import asyncio
import json
import logging
import re
import websockets
from datetime import datetime
from typing import Callable, Coroutine, Optional
from .config import settings

# logger for tracking if binance actually talks to us
logger = logging.getLogger(__name__)

class BinanceStreamer:
    # This class handles all the websocket stuff with Binance.
    # It just listens for price updates and tells the analyzer.

    def __init__(self, on_price_update: Callable[[float, float, datetime], Coroutine]):
        self.on_price_update = on_price_update
        self.running = False
        self.btc_price: Optional[float] = None
        self.eth_price: Optional[float] = None
        
        # combining the streams into one url to save connections
        # combining the streams into one url to save connections
        base = settings.BASE_SYMBOL.lower()
        target = settings.TARGET_SYMBOL.lower()
        self.endpoint = f"{settings.BINANCE_WS_URL}/{base}@markPrice/{target}@markPrice"

    async def start(self):
        # starts the loop to receive prices
        self.running = True
        while self.running:
            try:
                # connecting to binance's websocket
                async with websockets.connect(self.endpoint) as websocket:
                    logger.info(f"Connected to Binance! Streaming: {settings.BASE_SYMBOL} vs {settings.TARGET_SYMBOL}")
                    while self.running:
                        message = await websocket.recv()
                        data = json.loads(message)
                        await self._process_message(data)
            except Exception as e:
                logger.error(f"WS error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    async def _process_message(self, data: dict):
        """Extracts prices and timestamps from Binance JSON packets."""
        symbol = data.get("s", "")
        
        if not re.match(r"^[A-Z]{3,}USDT$", symbol):
            return

        price = float(data.get("p", 0))
        timestamp = datetime.fromtimestamp(data.get("E", 0) / 1000.0)

        if symbol == settings.BASE_SYMBOL:
            self.btc_price = price
        elif symbol == settings.TARGET_SYMBOL:
            self.eth_price = price

        # wait until we have a price for both before doing the math
        if self.btc_price and self.eth_price:
            await self.on_price_update(self.btc_price, self.eth_price, timestamp)
            # we keep them and update every time either one changes

    def stop(self):
        # turns off the streamer
        self.running = False

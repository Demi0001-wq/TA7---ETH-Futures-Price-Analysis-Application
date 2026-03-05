import logging
import httpx
from typing import Optional
from .config import settings
from .database import SessionLocal
from .models import Alert

# logger for tracking alert activity
logger = logging.getLogger(__name__)

class AlertSystem:
    # This class manages how we tell the user something happened.
    # It can print to console, save to DB, and send helpful Telegram messages.

    def __init__(self):
        # pulling credentials from our config/env
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID

    async def send_alert(self, alert_data: dict):
        # the main entry to trigger an alert across all channels
        message = alert_data["message"]
        
        # 1. basic console output so we can see it in terminal
        print(message)
        logger.info(f"Alert triggered: {message}")
        
        # 2. log to our SQL database
        self._log_to_db(alert_data)
        
        # 3. send to telegram if the keys are set up
        if self.bot_token and self.chat_id:
            await self._send_telegram(message)

    def _log_to_db(self, alert_data: dict):
        # helper to save the alert record into the db
        db = SessionLocal()
        try:
            direction = "INCREASE" if alert_data["change_pct"] > 0 else "DECREASE"
            new_alert = Alert(
                timestamp=alert_data["timestamp"],
                direction=direction,
                change_pct=alert_data["change_pct"],
                beta=alert_data["beta"],
                message=alert_data["message"]
            )
            db.add(new_alert)
            db.commit()
            logger.info("Alert successfully saved to DB.")
        except Exception as e:
            logger.error(f"DB log failed: {e}")
        finally:
            db.close()

    async def _send_telegram(self, message: str):
        # uses httpx to talk to the telegram bot api
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                if response.status_code != 200:
                    logger.error(f"Telegram API being difficult: {response.text}")
        except Exception as e:
            logger.error(f"Couldn't send telegram message: {e}")

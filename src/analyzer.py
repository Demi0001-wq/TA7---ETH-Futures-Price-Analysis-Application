import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

# basic logging setup
logger = logging.getLogger(__name__)

class PriceAnalyzer:
    # This class does the heavy lifting - calculating how much ETH moves on its own
    # by subtracting the BTC 'market' part using beta.

    def __init__(self, alert_threshold: float = 1.0, alert_window_minutes: int = 60, beta_window_hours: int = 24):
        # converting % from settings to actual decimal for math
        self.alert_threshold = alert_threshold / 100.0  
        self.alert_window_minutes = alert_window_minutes
        self.beta_window_hours = beta_window_hours
        
        # history storage - using pandas since it handles time windows easily
        self.history = pd.DataFrame(columns=["timestamp", "btc_price", "eth_price"])
        self.history["btc_price"] = self.history["btc_price"].astype(float)
        self.history["eth_price"] = self.history["eth_price"].astype(float)
        self.beta: float = 1.0  # start with 1.0 until we have enough data
        self.last_alert_time: Optional[datetime] = None
        
        # tracking residues for the rolling alert window
        self.residue_history: List[Dict] = []

    def update_price(self, btc_price: float, eth_price: float, timestamp: datetime):
        # main loop function - called every time a new price comes in
        if btc_price <= 0 or eth_price <= 0:
            logger.warning(f"Got some weird prices: BTC={btc_price}, ETH={eth_price}")
            return None
            
        # add the new data point to our collection
        new_row = {"timestamp": timestamp, "btc_price": float(btc_price), "eth_price": float(eth_price)}
        self.history = pd.concat([self.history, pd.DataFrame([new_row])], ignore_index=True)
        
        # fix types just in case pandas gets confused
        self.history["btc_price"] = self.history["btc_price"].astype(float)
        self.history["eth_price"] = self.history["eth_price"].astype(float)
        
        # clean up old data so memory doesn't explode
        cutoff = timestamp - timedelta(hours=self.beta_window_hours + 1)
        self.history = self.history[self.history["timestamp"] > cutoff].reset_index(drop=True)
        
        if len(self.history) < 2:
            return None

        # recalculate the correlation (beta)
        self._calculate_beta()
        
        # calculate the current 'return' (percent change)
        prev_btc = self.history.iloc[-2]["btc_price"]
        prev_eth = self.history.iloc[-2]["eth_price"]
        
        # logs are better than simple % for financial math
        btc_return = np.log(btc_price / prev_btc)
        eth_return = np.log(eth_price / prev_eth)
        
        # this is the key: subtract the btc part to find the 'own' movement
        residue = eth_return - self.beta * btc_return
        
        self.residue_history.append({"timestamp": timestamp, "residue": residue})
        
        # only keep residue data within the alert window (e.g. 60 min)
        residue_cutoff = timestamp - timedelta(minutes=self.alert_window_minutes)
        self.residue_history = [r for r in self.residue_history if r["timestamp"] > residue_cutoff]
        
        # sum up the residues to see if there's a trend
        cumulative_residue = sum(r["residue"] for r in self.residue_history)
        
        # if it's bigger than our threshold, trigger an alert
        if abs(cumulative_residue) >= self.alert_threshold:
            return self._format_alert(cumulative_residue, timestamp)
            
        return None

    def _calculate_beta(self):
        # calculates how much ETH typically follows BTC
        if len(self.history) < 10:
            return # not enough data yet

        temp_df = self.history.copy()
        temp_df["btc_ret"] = np.log(temp_df["btc_price"] / temp_df["btc_price"].shift(1))
        temp_df["eth_ret"] = np.log(temp_df["eth_price"] / temp_df["eth_price"].shift(1))
        temp_df = temp_df.dropna()

        if len(temp_df) < 5:
            return

        try:
            # regression: beta = cov(x,y) / var(x)
            covariance = np.cov(temp_df["btc_ret"], temp_df["eth_ret"])[0, 1]
            variance = np.var(temp_df["btc_ret"])
            
            if variance > 0:
                self.beta = float(covariance / variance)
        except Exception as e:
            logger.error(f"Beta calc failed: {e}")
            
    def _format_alert(self, cumulative_residue: float, timestamp: datetime):
        # just helper to make the alert info readable
        change_pct = cumulative_residue * 100
        direction = "INCREASE" if change_pct > 0 else "DECREASE"
        message = (
            f"[{timestamp.strftime('%H:%M:%S')}] ALERT: ETH '{direction}' "
            f"of {abs(change_pct):.2f}% (filtered BTC, Beta: {self.beta:.2f})"
        )
        return {
            "timestamp": timestamp,
            "change_pct": float(change_pct),
            "beta": float(self.beta),
            "message": message
        }

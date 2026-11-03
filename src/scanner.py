"""
Opportunity scanner (new pairs / signals).
In production you would poll Birdeye, DexScreener, Helius, or your own indexer.
This is a clean stub that returns example opportunities.
"""

from __future__ import annotations
from typing import List, Dict, Any
import time
from .logger import TradeLogger


class Scanner:
    def __init__(self, logger: TradeLogger):
        self.logger = logger

    async def scan(self) -> List[Dict[str, Any]]:
        """
        Return a list of candidate opportunities.
        Replace this with real data sources.
        """
        self.logger.log_decision("scan", "Scanning for opportunities")

        # Example fake opportunity (replace with real API calls)
        opportunities = [
            {
                "mint": "So11111111111111111111111111111111111111112",  # example
                "symbol": "SOL",
                "liquidity_usd": 1_250_000,
                "score": 0.72,
                "price": 180.5,
                "timestamp": time.time(),
            }
        ]
        return opportunities
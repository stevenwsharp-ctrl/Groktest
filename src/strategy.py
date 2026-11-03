"""
Simple strategy module with hooks for self-refinement.
Replace the logic here with your real edge.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from .logger import TradeLogger


class Strategy:
    def __init__(self, config: Dict[str, Any], logger: TradeLogger):
        self.config = config.get("strategy", {})
        self.logger = logger
        self.params = {
            "min_liquidity_usd": self.config.get("min_liquidity_usd", 50_000),
            "max_position_size_sol": self.config.get("max_position_size_sol", 0.1),
            "take_profit_pct": self.config.get("take_profit_pct", 8.0),
            "stop_loss_pct": self.config.get("stop_loss_pct", 4.0),
        }

    def should_enter(self, opportunity: Dict[str, Any]) -> tuple[bool, str]:
        """
        Returns (enter: bool, reason: str)
        """
        liquidity = opportunity.get("liquidity_usd", 0)
        if liquidity < self.params["min_liquidity_usd"]:
            return False, f"Liquidity too low ({liquidity} < {self.params['min_liquidity_usd']})"

        # Add your real signals here (momentum, volume spike, social, etc.)
        # For now a simple placeholder
        score = opportunity.get("score", 0)
        if score < 0.6:
            return False, f"Score too low ({score})"

        return True, "Passed filters"

    def should_exit(self, position: Dict[str, Any], current_price: float) -> tuple[bool, str]:
        entry = position.get("entry_price", 0)
        if entry <= 0:
            return False, "No entry price"

        pnl_pct = ((current_price - entry) / entry) * 100

        if pnl_pct >= self.params["take_profit_pct"]:
            return True, f"Take profit hit (+{pnl_pct:.2f}%)"
        if pnl_pct <= -self.params["stop_loss_pct"]:
            return True, f"Stop loss hit ({pnl_pct:.2f}%)"

        return False, "Hold"

    def refine(self, recent_trades) -> Dict[str, Any]:
        """
        Very simple refinement example.
        In a real system you would run VectorBT optimization here
        and update self.params.
        """
        self.logger.log_decision("refine", "Running refinement pass", {"n_trades": len(recent_trades)})
        # Placeholder: just return current params
        return self.params
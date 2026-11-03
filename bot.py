#!/usr/bin/env python3
"""
Grok Solana Trading Bot - Single File Version
Paper-trading by default. Inspired by the Greshamtrade post.

Safety features included:
- Rejects stale quotes
- Max slippage check
- Clear reject reasons in terminal
- Logs every decision
"""

import asyncio
import time
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# ---------- Optional pretty printing ----------
try:
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    def log(msg, style=""):
        console.print(msg, style=style)
except ImportError:
    def log(msg, style=""):
        print(msg)

# ---------- Config ----------
MODE = "paper"                    # "paper" or "live"
MAX_SLIPPAGE_BPS = 50             # 0.5%
MAX_QUOTE_AGE_SECONDS = 15
PAPER_BALANCE_SOL = 1.0


class SimpleLogger:
    def __init__(self):
        self.trades = []
        self.decisions = []

    def log_trade(self, **kwargs):
        entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            **kwargs
        }
        self.trades.append(entry)
        log(f"[TRADE] {entry}", "cyan")

    def log_decision(self, stage: str, message: str, data: Optional[Dict] = None):
        entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "message": message,
            "data": data or {}
        }
        self.decisions.append(entry)
        log(f"[{stage.upper()}] {message}", "dim")


class Strategy:
    def __init__(self):
        self.min_liquidity = 50_000
        self.min_score = 0.60

    def should_enter(self, opp: Dict) -> tuple[bool, str]:
        if opp.get("liquidity_usd", 0) < self.min_liquidity:
            return False, f"Liquidity too low ({opp.get('liquidity_usd')})"
        if opp.get("score", 0) < self.min_score:
            return False, f"Score too low ({opp.get('score')})"
        return True, "Passed filters"


class Executor:
    def __init__(self, logger: SimpleLogger):
        self.logger = logger
        self.mode = MODE

    async def execute(self, opportunity: Dict, amount_in: float = 0.05) -> Dict:
        quote = {
            "price": opportunity.get("price", 1.0),
            "slippage_bps": 25,
            "timestamp": opportunity.get("timestamp", time.time()),
        }

        # Safety checks (exactly as the original post recommended)
        reason = None
        if time.time() - quote["timestamp"] > MAX_QUOTE_AGE_SECONDS:
            reason = f"Quote too old (>{MAX_QUOTE_AGE_SECONDS}s)"
        elif quote["slippage_bps"] > MAX_SLIPPAGE_BPS:
            reason = f"Slippage too high ({quote['slippage_bps']} bps)"

        if reason:
            log(f"REJECTED → {reason}", "bold red")
            self.logger.log_trade(action="reject", reason=reason, mint=opportunity.get("mint"))
            self.logger.log_decision("execute", f"Rejected: {reason}")
            return {"status": "rejected", "reason": reason}

        # Paper fill
        amount_out = amount_in * quote["price"] * 0.997
        result = {
            "status": "filled",
            "mode": "paper",
            "amount_in": amount_in,
            "amount_out": amount_out,
            "mint": opportunity.get("mint"),
            "symbol": opportunity.get("symbol"),
            "tx": f"paper_{int(time.time())}"
        }

        log(f"PAPER BUY  {amount_in} SOL → {amount_out:.6f} {opportunity.get('symbol')}", "bold green")
        self.logger.log_trade(**result)
        self.logger.log_decision("execute", "Trade filled (paper)", result)
        return result


async def scan() -> list:
    """Fake scanner – replace this later with real data (Birdeye, DexScreener, etc.)"""
    return [
        {
            "mint": "So11111111111111111111111111111111111111112",
            "symbol": "SOL",
            "liquidity_usd": 1_250_000,
            "score": 0.74,
            "price": 182.40,
            "timestamp": time.time(),
        }
    ]


async def main():
    log(Panel.fit(f"[bold cyan]Grok Solana Bot[/bold cyan]\nMode: [yellow]{MODE.upper()}[/yellow]", title="Starting"))
    log("Paper trading only. No real funds at risk.\n")

    logger = SimpleLogger()
    strategy = Strategy()
    executor = Executor(logger)

    try:
        while True:
            opportunities = await scan()
            for opp in opportunities:
                should, reason = strategy.should_enter(opp)
                if not should:
                    log(f"Skip {opp.get('symbol')}: {reason}", "dim")
                    logger.log_decision("filter", reason, opp)
                    continue

                await executor.execute(opp)

            await asyncio.sleep(12)

    except KeyboardInterrupt:
        log("\nStopped by user.", "yellow")
        log(f"Total paper trades logged: {len(logger.trades)}")


if __name__ == "__main__":
    asyncio.run(main())

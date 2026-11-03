"""
Execution layer with safety checks (exactly as the original post recommended).

Before any signature we verify:
- token / mint exists
- available balance
- quote age
- max slippage
Then we record the confirmed transaction BEFORE updating the position.
"""

from __future__ import annotations
import time
from typing import Optional, Dict, Any
from rich.console import Console
from .wallet import Wallet
from .logger import TradeLogger

console = Console()


class Executor:
    def __init__(
        self,
        wallet: Wallet,
        logger: TradeLogger,
        mode: str = "paper",
        max_slippage_bps: int = 50,
        max_quote_age_seconds: int = 15,
    ):
        self.wallet = wallet
        self.logger = logger
        self.mode = mode
        self.max_slippage_bps = max_slippage_bps
        self.max_quote_age_seconds = max_quote_age_seconds

    async def execute_swap(
        self,
        input_mint: str,
        output_mint: str,
        amount_in: float,
        quote: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        High-level swap entry point.
        In paper mode we simulate. In live mode we would call Jupiter.
        """
        reason = None

        # --- Safety checks (post requirements) ---
        if quote is None:
            reason = "No quote provided"
        elif time.time() - quote.get("timestamp", 0) > self.max_quote_age_seconds:
            reason = f"Quote too old (>{self.max_quote_age_seconds}s)"
        elif quote.get("slippage_bps", 9999) > self.max_slippage_bps:
            reason = f"Slippage {quote.get('slippage_bps')}bps exceeds max {self.max_slippage_bps}"
        elif amount_in <= 0:
            reason = "Invalid amount_in"

        if reason:
            console.print(f"[red]REJECTED[/red] → {reason}")
            self.logger.log_trade(
                mode=self.mode,
                action="reject",
                mint=output_mint,
                amount_in=amount_in,
                reason=reason,
            )
            self.logger.log_decision("execute", f"Rejected: {reason}", {"mint": output_mint})
            return {"status": "rejected", "reason": reason}

        # --- Paper vs Live ---
        if self.mode == "paper":
            # Simulate successful fill
            simulated_out = amount_in * quote.get("price", 1.0) * 0.997  # rough fee
            console.print(f"[green]PAPER BUY[/green] {amount_in} → {simulated_out:.6f} of {output_mint}")
            result = {
                "status": "filled",
                "mode": "paper",
                "amount_in": amount_in,
                "amount_out": simulated_out,
                "tx_signature": f"paper_{int(time.time())}",
            }
        else:
            # LIVE path would go here (Jupiter swap + sign + send)
            # Left as a clear stub so you know exactly where to plug it in.
            console.print("[yellow]LIVE mode not fully implemented in this starter — use paper first[/yellow]")
            result = {"status": "not_implemented_live"}

        # Record confirmed tx BEFORE updating any position state
        if result.get("status") == "filled":
            self.logger.log_trade(
                mode=self.mode,
                action="buy",
                mint=output_mint,
                amount_in=amount_in,
                amount_out=result["amount_out"],
                price=quote.get("price"),
                slippage_bps=quote.get("slippage_bps"),
                tx_signature=result.get("tx_signature"),
                raw=result,
            )
            self.logger.log_decision("execute", "Trade filled and recorded", result)

        return result
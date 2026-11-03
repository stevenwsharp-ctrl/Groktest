"""
Main entry point for the Grok Solana Trading Bot.
"""

from __future__ import annotations
import asyncio
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from .wallet import Wallet
from .logger import TradeLogger
from .scanner import Scanner
from .strategy import Strategy
from .executor import Executor

console = Console()
load_dotenv()


async def run_bot(mode: str = "paper"):
    console.print(Panel.fit(
        f"[bold cyan]Grok Solana Bot[/bold cyan]\nMode: [yellow]{mode.upper()}[/yellow]",
        title="Starting"
    ))

    # Load config
    config_path = Path("config.yaml")
    config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}

    # Components
    logger = TradeLogger()
    wallet = Wallet(
        private_key=os.getenv("PRIVATE_KEY") if mode == "live" else None,
        rpc_url=os.getenv("SOLANA_RPC_URL"),
    )
    scanner = Scanner(logger)
    strategy = Strategy(config, logger)
    executor = Executor(
        wallet=wallet,
        logger=logger,
        mode=mode,
        max_slippage_bps=config.get("risk", {}).get("max_slippage_bps", 50),
    )

    console.print(f"Wallet (public): {wallet.public_key}")
    console.print("Safety checks active: token • balance • quote age • max slippage")
    console.print("All decisions logged to DuckDB → data/trades.duckdb\n")

    try:
        while True:
            opportunities = await scanner.scan()

            for opp in opportunities:
                should, reason = strategy.should_enter(opp)
                if not should:
                    console.print(f"[dim]Skip {opp.get('symbol')}: {reason}[/dim]")
                    logger.log_decision("filter", reason, opp)
                    continue

                # Fake a quote for demo
                quote = {
                    "price": opp.get("price", 1.0),
                    "slippage_bps": 25,
                    "timestamp": opp.get("timestamp", 0),
                }

                result = await executor.execute_swap(
                    input_mint="So11111111111111111111111111111111111111112",  # SOL
                    output_mint=opp["mint"],
                    amount_in=0.05,  # small size
                    quote=quote,
                )

            # Simple refinement every N cycles (demo)
            recent = logger.get_recent_trades(30)
            if len(recent) > 0 and len(recent) % 10 == 0:
                strategy.refine(recent)

            await asyncio.sleep(15)  # scan interval

    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down gracefully...[/yellow]")
    finally:
        await wallet.close()
        logger.close()
        console.print("[green]Done. Check data/trades.duckdb for full history.[/green]")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Grok Solana Trading Bot")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    args = parser.parse_args()
    asyncio.run(run_bot(mode=args.mode))


if __name__ == "__main__":
    main()
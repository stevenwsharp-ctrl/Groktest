"""
QuantStats performance reports from the DuckDB trade log.
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd

try:
    import quantstats as qs
except ImportError:
    qs = None


def generate_report(db_path: str = "data/trades.duckdb", output: str = "data/report.html"):
    if qs is None:
        print("quantstats not installed")
        return

    import duckdb
    conn = duckdb.connect(db_path)
    df = conn.execute("""
        SELECT timestamp, amount_out / NULLIF(amount_in, 0) - 1 AS ret
        FROM trades
        WHERE action = 'buy' AND amount_in > 0
        ORDER BY timestamp
    """).fetchdf()
    conn.close()

    if df.empty:
        print("No trades yet — nothing to report")
        return

    returns = df.set_index("timestamp")["ret"]
    returns = returns.fillna(0)

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    qs.reports.html(returns, output=output, title="Grok Solana Bot Performance")
    print(f"Report written to {output}")
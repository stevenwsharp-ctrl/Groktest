"""
VectorBT backtesting helper.
Feed it historical OHLCV + your signals and get performance stats.
"""

from __future__ import annotations
from typing import Optional
import pandas as pd

try:
    import vectorbt as vbt
except ImportError:
    vbt = None


def run_simple_backtest(
    price: pd.Series,
    entries: pd.Series,
    exits: pd.Series,
    fees: float = 0.003,
    init_cash: float = 10_000,
) -> Optional[object]:
    if vbt is None:
        print("vectorbt not installed — skipping backtest")
        return None

    pf = vbt.Portfolio.from_signals(
        close=price,
        entries=entries,
        exits=exits,
        fees=fees,
        init_cash=init_cash,
        freq="1min",
    )
    print(pf.stats())
    return pf
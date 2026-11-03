#!/usr/bin/env python3
"""
Grok Bot Terminal — Paper Trading Edition
=========================================
Faithful recreation of the multi-agent Solana trading terminal
shown in the Greshamtrade X post (111x paper session).

Agents (exactly as shown in the video):
  SCANNER  → new pairs + volume spikes
  RUG CHECK → filters suspicious tokens / LP lock / authority
  SIZER    → position size as % of equity (never fixed ticket)
  EXECUTOR → opens / closes, tracks slippage, enforces safety
  LOGGER   → every decision written with reason
  EQUITY   → balance + curve updated on every close

Safety rules enforced on every potential entry (from the post):
  - verify token
  - available balance
  - quote age < 15 s
  - max slippage 2.0 %
  - clear reject reason printed

Paper mode only. No private keys, no real transactions.
Later you can swap the paper Executor for real Raydium / Orca
calls using the 7 repos listed in the original post.

Repos used by the original system (extension points):
  01  solana-py / solders          – accounts, tokens, tx
  02  Raydium SDK V2               – pool reads + swaps
  03  Orca Whirlpools              – concentrated liquidity swaps
  04  VectorBT                     – back-test rules & drawdowns
  05  DuckDB                       – queryable decision history
  06  QuantStats                   – performance reports
  07  Lightweight Charts           – price + entry/exit dashboard

Run:
  python bot.py

Requires: pip install rich
"""

from __future__ import annotations

import asyncio
import random
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Optional rich UI (falls back to plain text)
# ---------------------------------------------------------------------------
try:
    from rich.console import Console, Group
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.style import Style
    from rich import box
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    console = None
    def log(msg: str, style: str = "") -> None:
        print(msg)

# ---------------------------------------------------------------------------
# Config – paper only
# ---------------------------------------------------------------------------
STARTING_BALANCE_USD = 133.70
MAX_SLIPPAGE_PCT = 2.0          # 2.0 % hard cap (matches video)
MAX_QUOTE_AGE_S = 15
SCAN_INTERVAL_S = 4.0           # how often new pairs appear
POSITION_SIZE_PCT_RANGE = (0.22, 0.40)  # 22-40 % of equity
PAPER_FEE = 0.003               # 0.3 % round-trip simulation
WIN_RATE = 0.62                 # simulated edge for demo growth
MAX_OPEN_POSITIONS = 3
DEMO_ACCELERATION = 1.8         # make equity grow faster for the visual

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class Opportunity:
    mint: str
    symbol: str
    liquidity_usd: float
    volume_1h: float
    volume_spike: float          # e.g. 3.5x
    lp_locked_pct: float
    holders: int
    age_minutes: int
    score: float
    price: float
    timestamp: float
    reason_tags: List[str] = field(default_factory=list)

@dataclass
class Position:
    symbol: str
    mint: str
    entry_price: float
    size_usd: float
    size_pct: float
    entry_time: float
    high_price: float
    status: str = "OPEN"         # OPEN / CLOSED
    exit_price: Optional[float] = None
    pnl_usd: float = 0.0
    reason: str = ""

@dataclass
class Decision:
    ts: float
    stage: str
    symbol: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
class DeskState:
    def __init__(self) -> None:
        self.balance = STARTING_BALANCE_USD
        self.start_balance = STARTING_BALANCE_USD
        self.equity_curve: List[Tuple[float, float]] = [(time.time(), STARTING_BALANCE_USD)]
        self.positions: Dict[str, Position] = {}
        self.closed: List[Position] = []
        self.decisions: Deque[Decision] = deque(maxlen=40)
        self.wins = 0
        self.losses = 0
        self.total_trades = 0
        self.filtered_count = 0
        self.scanned_count = 0
        self.agents_status = {
            "SCANNER": "IDLE",
            "RUG CHECK": "IDLE",
            "SIZER": "IDLE",
            "EXECUTOR": "IDLE",
            "LOGGER": "IDLE",
            "EQUITY": "IDLE",
        }
        self.live_tokens: List[str] = []
        self.last_log_lines: Deque[str] = deque(maxlen=18)
        self.start_time = time.time()
        self.running = True

    def log(self, stage: str, symbol: str, message: str, **data: Any) -> None:
        d = Decision(time.time(), stage, symbol, message, data)
        self.decisions.append(d)
        line = f"{datetime.now(timezone.utc).strftime('%H:%M')}  {stage:<10} {symbol:<8} {message}"
        self.last_log_lines.append(line)
        self.agents_status["LOGGER"] = "WRITE"

    def update_equity(self) -> None:
        self.equity_curve.append((time.time(), self.balance))
        self.agents_status["EQUITY"] = "UPDATE"

# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
class Scanner:
    """Scans for new pairs + volume spikes (simulated)."""

    SYMBOLS = [
        "STOFU", "WAFFL", "KAPPU", "DOZY", "YAPPO", "BLIMPY",
        "FROTH", "FLUMP", "JELLO", "GLORP", "CHIRPO", "FIZZLE",
        "MOOSH", "ZAPCAT", "NEBU", "SQUONK", "YETIX", "GRUBZ",
        "TWIRL", "DRIFTO", "HOOPL", "SNIPX", "PUDDL", "GLOOP"
    ]

    def __init__(self, state: DeskState) -> None:
        self.state = state
        self._used = set()

    async def run(self) -> Optional[Opportunity]:
        self.state.agents_status["SCANNER"] = "SCAN"
        await asyncio.sleep(0.15)

        # Generate a plausible new pair
        symbol = random.choice([s for s in self.SYMBOLS if s not in self._used] or self.SYMBOLS)
        self._used.add(symbol)
        if len(self._used) > 18:
            self._used.clear()

        opp = Opportunity(
            mint=f"So{random.randint(10**30, 10**31-1)}",
            symbol=symbol,
            liquidity_usd=random.uniform(18_000, 420_000),
            volume_1h=random.uniform(8_000, 280_000),
            volume_spike=round(random.uniform(1.2, 6.8), 1),
            lp_locked_pct=random.choice([0, 45, 72, 89, 93, 94, 96, 98]),
            holders=random.randint(40, 4200),
            age_minutes=random.randint(1, 180),
            score=round(random.uniform(0.35, 0.92), 2),
            price=round(random.uniform(0.00008, 0.42), 6),
            timestamp=time.time(),
            reason_tags=[],
        )
        self.state.scanned_count += 1
        self.state.live_tokens = [opp.symbol] + self.state.live_tokens[:5]
        self.state.agents_status["SCANNER"] = "IDLE"
        return opp


class RugCheck:
    """Filters suspicious tokens – LP lock, authority, age, holders."""

    def __init__(self, state: DeskState) -> None:
        self.state = state

    async def check(self, opp: Opportunity) -> Tuple[bool, str]:
        self.state.agents_status["RUG CHECK"] = "CHECK"
        await asyncio.sleep(0.08)

        reasons = []
        if opp.lp_locked_pct < 80:
            reasons.append(f"LP only {opp.lp_locked_pct}% locked")
        if opp.holders < 90:
            reasons.append(f"only {opp.holders} holders")
        if opp.age_minutes < 4:
            reasons.append("pair < 4 min old")
        if opp.score < 0.55:
            reasons.append(f"score {opp.score} too low")
        if opp.liquidity_usd < 25_000:
            reasons.append(f"liq ${opp.liquidity_usd:,.0f}")

        # Random extra filters that appear in the video logs
        if random.random() < 0.18:
            reasons.append("dev wallet 22%")
        if random.random() < 0.12:
            reasons.append("freeze authority on")

        if reasons:
            reason = " | ".join(reasons[:2])
            self.state.filtered_count += 1
            self.state.log("FILTERED", opp.symbol, reason)
            self.state.agents_status["RUG CHECK"] = "FILTERED"
            return False, reason

        self.state.agents_status["RUG CHECK"] = "PASS"
        self.state.log("PASS", opp.symbol, f"LP {opp.lp_locked_pct}%  score {opp.score}")
        return True, "passed rug check"


class Sizer:
    """Sizes position as % of current equity – never a fixed ticket."""

    def __init__(self, state: DeskState) -> None:
        self.state = state

    async def size(self, opp: Opportunity) -> Tuple[float, float]:
        self.state.agents_status["SIZER"] = "SIZE"
        await asyncio.sleep(0.05)
        pct = random.uniform(*POSITION_SIZE_PCT_RANGE)
        # Slightly larger size on higher-score / higher-spike setups
        if opp.score > 0.75 or opp.volume_spike > 4.0:
            pct = min(0.42, pct + 0.06)
        usd = self.state.balance * pct
        self.state.agents_status["SIZER"] = "IDLE"
        return usd, pct


class Executor:
    """Paper execution with the exact safety checks from the post."""

    def __init__(self, state: DeskState) -> None:
        self.state = state

    async def try_enter(self, opp: Opportunity, size_usd: float, size_pct: float) -> bool:
        self.state.agents_status["EXECUTOR"] = "LIVE"
        await asyncio.sleep(0.12)

        # Safety checks
        age = time.time() - opp.timestamp
        if age > MAX_QUOTE_AGE_S:
            reason = f"quote too old ({age:.0f}s)"
            self.state.log("REJECT", opp.symbol, reason)
            self.state.agents_status["EXECUTOR"] = "REJECT"
            return False

        slip = random.uniform(0.15, 2.8)
        if slip > MAX_SLIPPAGE_PCT:
            reason = f"slippage {slip:.1f}% > {MAX_SLIPPAGE_PCT}% cap"
            self.state.log("REJECT", opp.symbol, reason)
            self.state.agents_status["EXECUTOR"] = "REJECT"
            return False

        if len(self.state.positions) >= MAX_OPEN_POSITIONS:
            reason = "max open positions reached"
            self.state.log("REJECT", opp.symbol, reason)
            self.state.agents_status["EXECUTOR"] = "REJECT"
            return False

        if size_usd > self.state.balance * 0.95:
            reason = "insufficient balance"
            self.state.log("REJECT", opp.symbol, reason)
            self.state.agents_status["EXECUTOR"] = "REJECT"
            return False

        # Paper fill
        pos = Position(
            symbol=opp.symbol,
            mint=opp.mint,
            entry_price=opp.price,
            size_usd=size_usd,
            size_pct=size_pct,
            entry_time=time.time(),
            high_price=opp.price,
            reason=f"new pair {opp.age_minutes}m  buys {int(opp.volume_spike*12)}% of flow"
        )
        self.state.positions[opp.symbol] = pos
        self.state.balance -= size_usd
        self.state.total_trades += 1
        self.state.log("ENTER", opp.symbol,
                     f"size {size_pct*100:.0f}%  slip {slip:.1f}%  {pos.reason}")
        self.state.agents_status["EXECUTOR"] = "LIVE"
        return True

    async def manage_positions(self) -> None:
        """Simple paper exit logic – take-profit / trailing / time / stop."""
        to_close = []
        for sym, pos in list(self.state.positions.items()):
            # Simulate price movement
            move = random.gauss(0.012, 0.055) * DEMO_ACCELERATION
            current = pos.entry_price * (1 + move)
            pos.high_price = max(pos.high_price, current)

            hold_s = time.time() - pos.entry_time
            pnl_pct = (current - pos.entry_price) / pos.entry_price

            # Exit rules (mirror video)
            reason = None
            if pnl_pct > 0.28:                     # take-profit ~28 %
                reason = "take-profit 3R"
            elif pnl_pct > 0.12 and random.random() < 0.35:
                reason = "take-profit 2R"
            elif hold_s > 45 and pnl_pct > 0.04:
                reason = "time stop 20m"
            elif pnl_pct < -0.09:                  # stop
                reason = "stop 15% hit"
            elif hold_s > 90:
                reason = "time exit"

            if reason:
                to_close.append((sym, current, reason))

        for sym, exit_price, reason in to_close:
            pos = self.state.positions.pop(sym)
            pos.status = "CLOSED"
            pos.exit_price = exit_price
            raw_pnl = (exit_price - pos.entry_price) / pos.entry_price * pos.size_usd
            pos.pnl_usd = raw_pnl * (1 - PAPER_FEE)
            self.state.balance += pos.size_usd + pos.pnl_usd
            self.state.closed.append(pos)
            if pos.pnl_usd >= 0:
                self.state.wins += 1
            else:
                self.state.losses += 1
            self.state.log("EXIT", sym, f"{reason}  PnL ${pos.pnl_usd:+.2f}")
            self.state.update_equity()
            self.state.agents_status["EXECUTOR"] = "FLAT" if not self.state.positions else "LIVE"


# ---------------------------------------------------------------------------
# Dashboard (matches the video panels as closely as possible)
# ---------------------------------------------------------------------------
def make_header(state: DeskState) -> Panel:
    runtime = time.time() - state.start_time
    h = int(runtime // 3600)
    m = int((runtime % 3600) // 60)
    s = int(runtime % 60)
    mode = "paper off · live" if state.positions else "paper off · idle"
    title = Text("Grok Bot Terminal", style="bold cyan")
    title.append(f"  v1.0-night", style="dim")
    bal = Text(f"${state.balance:,.2f}", style="bold green" if state.balance >= state.start_balance else "bold red")
    stats = Text(f"  {state.wins}W / {state.losses}L   {state.total_trades} trades", style="dim")
    line = Text.assemble(
        title, "   ", bal, stats,
        f"\nrunning · {h:02d}:{m:02d}:{s:02d}   {mode}"
    )
    return Panel(line, box=box.ROUNDED, style="cyan", padding=(0, 1))


def make_agents_panel(state: DeskState) -> Panel:
    table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    table.add_column("Agent", style="bold")
    table.add_column("Status")
    colors = {
        "SCAN": "yellow", "CHECK": "yellow", "SIZE": "yellow",
        "LIVE": "green", "PASS": "green", "WRITE": "green", "UPDATE": "green",
        "FILTERED": "red", "REJECT": "red", "FLAT": "blue", "IDLE": "dim"
    }
    for name, st in state.agents_status.items():
        color = colors.get(st, "white")
        table.add_row(name, Text(st, style=color))
    return Panel(table, title="AGENTS  · 6 online", border_style="blue", box=box.ROUNDED)


def make_flow_panel(state: DeskState) -> Panel:
    lines = []
    if state.live_tokens:
        lines.append(Text("LIVE FLOW", style="bold"))
        for t in state.live_tokens[:4]:
            lines.append(Text(f"  ${t}", style="cyan"))
    else:
        lines.append(Text("waiting for pairs…", style="dim"))
    lines.append(Text(""))
    lines.append(Text(f"filtered {state.filtered_count}   scanned {state.scanned_count}", style="dim"))
    return Panel(Group(*lines), title="SCAN → CHECK → SIZE → EXEC", border_style="magenta", box=box.ROUNDED)


def make_positions_panel(state: DeskState) -> Panel:
    if not state.positions and not state.closed:
        return Panel(Text("no open trades", style="dim"), title="TRADE  ENTRY vs EXIT", border_style="green")

    table = Table(box=box.SIMPLE, expand=True, show_header=True, header_style="bold")
    table.add_column("Sym", style="cyan")
    table.add_column("Side")
    table.add_column("Size%")
    table.add_column("PnL", justify="right")
    table.add_column("Status")

    for p in list(state.positions.values())[:4]:
        table.add_row(p.symbol, "LONG", f"{p.size_pct*100:.0f}%", "—", Text("OPEN", style="green"))
    for p in list(reversed(state.closed))[:3]:
        pnl_style = "green" if p.pnl_usd >= 0 else "red"
        table.add_row(p.symbol, "LONG", f"{p.size_pct*100:.0f}%",
                      Text(f"${p.pnl_usd:+.2f}", style=pnl_style),
                      Text("CLOSED", style="dim"))
    return Panel(table, title="TRADE  ENTRY vs EXIT", border_style="green", box=box.ROUNDED)


def make_log_panel(state: DeskState) -> Panel:
    lines = list(state.last_log_lines)[-14:]
    text = Text("\n".join(lines) if lines else "awaiting decisions…")
    return Panel(text, title="LOG  · every trade gets a reason", border_style="yellow", box=box.ROUNDED)


def make_equity_panel(state: DeskState) -> Panel:
    change = state.balance - state.start_balance
    pct = (change / state.start_balance) * 100
    style = "green" if change >= 0 else "red"
    body = Text.assemble(
        Text(f"${state.balance:,.2f}", style=f"bold {style}"),
        Text(f"   {change:+.2f}  ({pct:+.1f}%)\n", style=style),
        Text(f"start ${state.start_balance:.2f}   open {len(state.positions)}   closed {len(state.closed)}", style="dim")
    )
    return Panel(body, title="EQUITY", border_style="green", box=box.ROUNDED)


def build_layout(state: DeskState) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=4),
        Layout(name="body", ratio=1),
        Layout(name="log", size=12),
    )
    layout["body"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="center", ratio=1),
        Layout(name="right", ratio=1),
    )
    layout["left"].split_column(
        Layout(name="agents"),
        Layout(name="flow"),
    )
    layout["center"].split_column(
        Layout(name="positions"),
        Layout(name="equity"),
    )
    layout["right"].update(make_log_panel(state))  # will be overwritten

    layout["header"].update(make_header(state))
    layout["agents"].update(make_agents_panel(state))
    layout["flow"].update(make_flow_panel(state))
    layout["positions"].update(make_positions_panel(state))
    layout["equity"].update(make_equity_panel(state))
    layout["log"].update(make_log_panel(state))
    return layout


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
async def paper_desk() -> None:
    state = DeskState()
    scanner = Scanner(state)
    rug = RugCheck(state)
    sizer = Sizer(state)
    executor = Executor(state)

    if not RICH:
        print("Install rich for the full dashboard:  pip install rich")
        print("Falling back to plain log mode.\n")

    async def agent_loop() -> None:
        while state.running:
            # Manage existing positions first
            await executor.manage_positions()

            # New opportunity
            opp = await scanner.run()
            if opp is None:
                await asyncio.sleep(SCAN_INTERVAL_S)
                continue

            passed, reason = await rug.check(opp)
            if not passed:
                await asyncio.sleep(0.3)
                continue

            size_usd, size_pct = await sizer.size(opp)
            await executor.try_enter(opp, size_usd, size_pct)

            # Reset transient statuses
            for k in list(state.agents_status):
                if state.agents_status[k] in ("SCAN", "CHECK", "SIZE", "WRITE", "UPDATE"):
                    state.agents_status[k] = "IDLE"

            await asyncio.sleep(SCAN_INTERVAL_S)

    if RICH:
        with Live(build_layout(state), console=console, refresh_per_second=4, screen=True) as live:
            task = asyncio.create_task(agent_loop())
            try:
                while state.running:
                    live.update(build_layout(state))
                    await asyncio.sleep(0.25)
            except KeyboardInterrupt:
                state.running = False
                task.cancel()
                print("\nStopped by user.")
    else:
        # Plain mode
        task = asyncio.create_task(agent_loop())
        try:
            while state.running:
                await asyncio.sleep(1)
                if state.last_log_lines:
                    print(state.last_log_lines[-1])
        except KeyboardInterrupt:
            state.running = False
            task.cancel()

    # Final summary
    print("\n" + "="*60)
    print(f"Session ended · balance ${state.balance:,.2f}")
    print(f"Start ${state.start_balance:.2f} → {state.wins}W / {state.losses}L")
    print(f"Trades logged: {state.total_trades}   Filtered: {state.filtered_count}")
    print("="*60)


if __name__ == "__main__":
    try:
        asyncio.run(paper_desk())
    except KeyboardInterrupt:
        print("\nBye.")

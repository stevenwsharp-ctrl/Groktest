# Grok Solana Trading Bot (Self-Refining)

A modular, paper-trading-first Solana trading bot inspired by the Greshamtrade "Grok Bot" post.  
It scans opportunities, applies rules, executes (or simulates) swaps, logs everything to DuckDB, backtests with VectorBT, reports with QuantStats, and has a simple refinement loop.

**⚠️ High Risk Warning**  
Crypto trading bots can (and often do) lose money very quickly.  
This project defaults to **paper trading**.  
Past performance (including the original post’s claims) is not indicative of future results.  
You are solely responsible for any capital you risk.

## Stack (matching the post)

| Component              | Tool / Library                          | Purpose                              |
|------------------------|-----------------------------------------|--------------------------------------|
| Solana connection      | `solders` + `solana-py`                 | Wallet, RPC, transactions            |
| Swaps / routing        | Jupiter API (covers Raydium + Orca)     | Practical multi-DEX swaps            |
| Backtesting            | `vectorbt`                              | Strategy testing + optimization      |
| Storage / audit        | `duckdb`                                | Market snapshots + trade log         |
| Performance reports    | `quantstats`                            | Returns, drawdowns, risk metrics     |
| Dashboard              | Lightweight Charts (HTML) or Streamlit  | Visualize price + entries/exits      |

## Quick Start

```bash
# 1. Clone or copy this folder into your GitHub repo
git clone <your-repo-url>
cd grok-solana-bot

# 2. Create virtualenv
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env — put your RPC URL and (optional) private key for live mode

# 5. Run paper trading
python -m src.main --mode paper
```

## Project Layout

```
grok-solana-bot/
├── src/
│   ├── main.py           # Entry point + CLI
│   ├── wallet.py         # Keypair + RPC client
│   ├── scanner.py        # Opportunity / new-pair scanner
│   ├── strategy.py       # Entry/exit rules + self-refine hooks
│   ├── executor.py       # Jupiter swap + safety checks
│   ├── logger.py         # DuckDB trade & snapshot logger
│   ├── backtester.py     # VectorBT integration
│   ├── reporter.py       # QuantStats reports
│   └── dashboard.py      # Simple chart output
├── config.yaml           # Strategy parameters
├── data/                 # DuckDB files + reports
├── notebooks/            # Exploration notebooks
└── requirements.txt
```

## Safety Rules Built In (from the original post)

Before any live signature the executor always checks:
- Token validity / mint existence
- Available balance
- Quote age (stale quotes rejected)
- Maximum slippage
- Confirmed transaction is recorded **before** position is updated

Rejected entries print clear reasons in the terminal.

## Self-Refining Loop

1. Log every decision + outcome to DuckDB  
2. Periodically run VectorBT optimization on recent data  
3. Generate QuantStats report  
4. Adjust parameters (or flag for human review)  
5. Restart paper/live session with updated config

## Next Steps for You

1. Push this folder to your existing GitHub repo  
2. Start with paper trading on one pair (e.g. SOL/USDC)  
3. Add your own edge / signals in `strategy.py`  
4. Only move to live mode after extensive backtesting and small size

Happy (careful) building.  
Questions? Just ask.
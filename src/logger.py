"""
DuckDB logger for trades, decisions, and market snapshots.
Everything is queryable so you can reconstruct every decision.
"""

from __future__ import annotations
import duckdb
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import json


class TradeLogger:
    def __init__(self, db_path: str = "data/trades.duckdb"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP,
                mode VARCHAR,               -- paper / live
                action VARCHAR,             -- buy / sell / reject
                mint VARCHAR,
                amount_in DOUBLE,
                amount_out DOUBLE,
                price DOUBLE,
                slippage_bps INTEGER,
                reason VARCHAR,
                tx_signature VARCHAR,
                raw_json VARCHAR
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP,
                stage VARCHAR,              -- scan / filter / execute / refine
                message VARCHAR,
                data VARCHAR
            )
        """)
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS trades_id_seq START 1;
            CREATE SEQUENCE IF NOT EXISTS decisions_id_seq START 1;
        """)

    def log_trade(self, **kwargs):
        now = datetime.now(timezone.utc)
        self.conn.execute("""
            INSERT INTO trades
            (id, timestamp, mode, action, mint, amount_in, amount_out, price,
             slippage_bps, reason, tx_signature, raw_json)
            VALUES (nextval('trades_id_seq'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            now,
            kwargs.get("mode", "paper"),
            kwargs.get("action"),
            kwargs.get("mint"),
            kwargs.get("amount_in"),
            kwargs.get("amount_out"),
            kwargs.get("price"),
            kwargs.get("slippage_bps"),
            kwargs.get("reason"),
            kwargs.get("tx_signature"),
            json.dumps(kwargs.get("raw", {})),
        ])

    def log_decision(self, stage: str, message: str, data: Optional[Dict] = None):
        now = datetime.now(timezone.utc)
        self.conn.execute("""
            INSERT INTO decisions (id, timestamp, stage, message, data)
            VALUES (nextval('decisions_id_seq'), ?, ?, ?, ?)
        """, [now, stage, message, json.dumps(data or {})])

    def get_recent_trades(self, limit: int = 50):
        return self.conn.execute(
            "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", [limit]
        ).fetchdf()

    def close(self):
        self.conn.close()
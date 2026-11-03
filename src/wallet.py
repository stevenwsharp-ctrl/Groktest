"""
Wallet and Solana connection helpers.
Uses solders + solana-py as recommended for Python.
"""

from __future__ import annotations
import os
from typing import Optional
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
import base58


class Wallet:
    def __init__(self, private_key: Optional[str] = None, rpc_url: Optional[str] = None):
        self.rpc_url = rpc_url or os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
        self.client = AsyncClient(self.rpc_url, commitment=Confirmed)

        if private_key:
            try:
                secret = base58.b58decode(private_key)
                self.keypair = Keypair.from_bytes(secret)
            except Exception as e:
                raise ValueError(f"Invalid private key: {e}")
        else:
            # Paper trading or read-only mode
            self.keypair = Keypair()  # ephemeral, never used for signing in paper mode

    @property
    def public_key(self) -> Pubkey:
        return self.keypair.pubkey()

    async def get_sol_balance(self) -> float:
        """Return SOL balance in SOL units."""
        resp = await self.client.get_balance(self.public_key)
        lamports = resp.value
        return lamports / 1_000_000_000

    async def close(self):
        await self.client.close()
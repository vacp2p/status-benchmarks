# Python Imports
from typing import Any

# Project Imports
from src.rpc_client import AsyncRpcClient
from src.service import AsyncService


class WalletAsyncService(AsyncService):
    def __init__(self, async_rpc_client: AsyncRpcClient):
        super().__init__(async_rpc_client, "wallet")

    async def start_wallet(self) -> dict:
        json_response = await self.rpc_request("startWallet")
        return json_response

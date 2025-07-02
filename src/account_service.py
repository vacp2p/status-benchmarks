# Python Imports

# Project Imports
from src.rpc_client import AsyncRpcClient
from src.service import AsyncService


class AccountAsyncService(AsyncService):
    def __init__(self, rpc: AsyncRpcClient):
        super().__init__(rpc, "accounts")

    async def get_accounts(self) -> dict:
        response_dict = await self.rpc.rpc_valid_request("getAccounts")
        return response_dict

    async def get_account_keypairs(self) -> dict:
        response_dict = await self.rpc.rpc_valid_request("getKeypairs")
        return response_dict

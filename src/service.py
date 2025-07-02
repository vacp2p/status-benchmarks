# Python Imports
from typing import Optional, Any

# Project Imports
from src.rpc_client import AsyncRpcClient


class AsyncService:
    def __init__(self, async_rpc_client: AsyncRpcClient, name: str):
        self.rpc = async_rpc_client
        self.name = name

    async def rpc_request(self, method: str, params: Optional[list] = None, enable_logging: bool = True) -> Any:
        full_method_name = f"{self.name}_{method}"
        return await self.rpc.rpc_valid_request(full_method_name, params or [], enable_logging=enable_logging)

# Python Imports
from typing import List
from requests import Response

# Project Imports
from src.rpc_client import RpcClient


class Service:
    def __init__(self, client: RpcClient, name: str):
        assert name != ""
        self.rpc_client = client
        self.name = name

    def rpc_request(self, method: str, params: List = None, skip_validation: bool = False, enable_logging: bool = True) -> Response:
        full_method_name = f"{self.name}_{method}"
        return self.rpc_client.rpc_valid_request(full_method_name, params, skip_validation=skip_validation, enable_logging=enable_logging)

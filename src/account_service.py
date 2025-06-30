# Python Imports

# Project Imports
from src.rpc_client import RpcClient
from src.service import Service


class AccountService(Service):
    def __init__(self, client: RpcClient):
        super().__init__(client, "accounts")

    def get_accounts(self):
        response = self.rpc_request("getAccounts")
        return response.json()

    def get_account_keypairs(self):
        response = self.rpc_request("getKeypairs")
        return response.json()

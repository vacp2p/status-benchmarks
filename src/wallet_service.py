from src.rpc_client import RpcClient
from src.service import Service


class WalletService(Service):
    def __init__(self, client: RpcClient):
        super().__init__(client, "wallet")

    def start_wallet(self):
        return self.rpc_request("startWallet")

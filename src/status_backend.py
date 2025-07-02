import json
import logging
from typing import List, Dict
from aiohttp import ClientSession, ClientTimeout, ClientResponse

# Project Imports
from src.account_service import AccountAsyncService
from src.rpc_client import AsyncRpcClient
from src.signal_client import AsyncSignalClient
from src.wakuext_service import WakuextAsyncService
from src.wallet_service import WalletAsyncService

logger = logging.getLogger(__name__)


class StatusBackend:
    def __init__(self, url: str, await_signals: List[str] = None):
        self.base_url = url
        self.api_url = f"{url}/statusgo"
        self.ws_url = url.replace("http", "ws")
        self.rpc_url = f"{url}/statusgo/CallRPC"
        self.public_key = ""

        self.rpc = AsyncRpcClient(self.rpc_url)
        self.signal = AsyncSignalClient(self.ws_url, await_signals)
        self.session = ClientSession(timeout=ClientTimeout(total=10))

        self.wakuext_service = WakuextAsyncService(self.rpc)
        self.wallet_service = WalletAsyncService(self.rpc)
        self.accounts_service = AccountAsyncService(self.rpc)

    async def __aenter__(self):
        await self.rpc.__aenter__()
        await self.signal.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.signal.__aexit__(exc_type, exc_val, exc_tb)
        await self.rpc.__aexit__(exc_type, exc_val, exc_tb)
        await self.session.close()

    async def call_rpc(self, method: str, params: List = None):
        return await self.rpc.rpc_valid_request(method, params or [])

    async def api_request(self, method: str, data: Dict, url: str = None) -> ClientResponse:
        url = url or self.api_url
        url = f"{url}/{method}"
        logger.debug(f"Sending async POST request to {url} with data: {json.dumps(data, sort_keys=True)}")
        async with self.session.post(url, json=data) as response:
            logger.debug(f"Got response: {await response.text()}")
            return response

    async def verify_is_valid_api_response(self, response: ClientResponse):
        if response.status != 200:
            raise AssertionError(f"Bad HTTP status: {response.status}")
        try:
            json_data = await response.json()
            if "error" in json_data:
                raise AssertionError(f"API error: {json_data['error']}")
        except Exception as e:
            raise AssertionError(f"Invalid JSON response: {e}")

    async def api_valid_request(self, method: str, data: Dict, url: str = None) -> ClientResponse:
        response = await self.api_request(method, data, url)
        await self.verify_is_valid_api_response(response)
        return response

    async def start_status_backend(self) -> ClientResponse:
        try:
            await self.logout()
            logger.debug("Successfully logged out")
        except AssertionError:
            logger.debug("Failed to log out")

        method = "InitializeApplication"
        data = {
            "dataDir": "/usr/status-user",
            "logEnabled": True,
            "logLevel": "DEBUG",
            "apiLogging": True,
            "wakuFleetsConfigFilePath": "/static/configs/config.json"
            # TODO check wakuFleetsConfigFilePath?
        }
        return await self.api_valid_request(method, data)

    def _set_networks(self, data: Dict):
        anvil_network = {
            "ChainID": 31337,
            "ChainName": "Anvil",
            "Enabled": True,
            "IsTest": False,
            "Layer": 1,
            "NativeCurrencyDecimals": 18,
            "NativeCurrencyName": "Ether",
            "NativeCurrencySymbol": "ETH",
            "RpcProviders": [{
                "authType": "no-auth",
                "chainId": 31337,
                "enableRpsLimiter": False,
                "enabled": True,
                "name": "Anvil Direct",
                "type": "embedded-direct",
                "url": "http://127.0.0.1:8545"
            }],
            "ShortName": "eth"
        }
        data["testNetworksEnabled"] = False
        data["networkId"] = 31337
        data["networksOverride"] = [anvil_network]

    def _create_account_request(self, **kwargs) -> Dict:
        data = {
            "rootDataDir": "/usr/status-user",
            "kdfIterations": 256000,
            # Profile config
            "displayName": "",
            "password": "Strong12345", # TODO SAVE PASSWORDS FOR DIFFERENT USERS?
            "customizationColor": "red",
            # Logs config
            "logEnabled": True,
            "logLevel": "DEBUG",
            # Waku config
            "wakuV2LightClient": kwargs.get("wakuV2LightClient", False),
            "wakuV2Fleet": "dst.dev",
        }
        self._set_networks(data)
        return data

    async def create_account_and_login(self, **kwargs) -> ClientResponse:
        return await self.api_valid_request("CreateAccountAndLogin", self._create_account_request(**kwargs))

    async def login(self, key_uid: str) -> ClientResponse:
        return await self.api_valid_request("LoginAccount", {
            "password": "Strong12345",
            "keyUid": key_uid,
            "kdfIterations": 256000,
        })

    async def logout(self) -> ClientResponse:
        return await self.api_valid_request("Logout", {})

    def set_public_key(self):
        # Only make sense to call this method if the lodes are logged in, otherwise public_key will be set to None.
        self.public_key = self.signal.node_login_event.get("event", {}).get("settings", {}).get("public-key")

    def find_key_uid(self) -> str:
        return self.signal.node_login_event.get("event", {}).get("account", {}).get("key-uid")

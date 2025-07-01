# Python Imports
import json
import logging
import threading
import requests
from typing import List, Dict
from requests import Response

# Project Imports
from src.account_service import AccountService
from src.rpc_client import RpcClient
from src.signal_client import SignalClient
from src.wakuext_service import WakuextService
from src.wallet_service import WalletService

logger = logging.getLogger(__name__)

class StatusBackend(RpcClient, SignalClient):

    def __init__(self, url: str, await_signals: List[str] = None):
        self.base_url = url
        self.api_url = f"{url}/statusgo"
        self.ws_url = f"{url}".replace("http", "ws")
        self.rpc_url = f"{url}/statusgo/CallRPC"
        self.public_key = ""

        RpcClient.__init__(self, self.rpc_url)
        SignalClient.__init__(self, self.ws_url, await_signals)

        websocket_thread = threading.Thread(target=self._connect)
        websocket_thread.daemon = True
        websocket_thread.start()

        self.wakuext_service = WakuextService(self)
        self.wallet_service = WalletService(self)
        self.accounts_service = AccountService(self)

    def api_request(self, method: str, data: Dict, url: str = None) -> Response:
        url = url if url else self.api_url
        url = f"{url}/{method}"

        logger.debug(f"Sending POST request to url {url} with data: {json.dumps(data, sort_keys=True)}")
        response = requests.post(url, json=data)

        logger.debug(f"Got response: {response.content}")
        return response

    def verify_is_valid_api_response(self, response: Response):
        assert response.status_code == 200, f"Got response {response.content}, status code {response.status_code}"
        assert response.content
        logger.debug(f"Got response: {response.content}")
        try:
            error = response.json()["error"]
            assert not error, f"Error: {error}"
        except json.JSONDecodeError:
            raise AssertionError(f"Invalid JSON in response: {response.content}")
        except KeyError:
            pass

    def api_valid_request(self, method: str, data: Dict, url: str = None) -> Response:
        response = self.api_request(method, data, url)
        self.verify_is_valid_api_response(response)
        return response

    def start_status_backend(self) -> Response:
        logger.debug("Automatically logging out before InitializeApplication")
        try:
            self.logout()
            logger.debug("successfully logged out")
        except AssertionError:
            logger.debug("failed to log out")
            pass

        method = "InitializeApplication"
        data = {
            "dataDir": "/usr/status-user",
            "logEnabled": True,
            "logLevel": "DEBUG",
            "apiLogging": True,
            "wakuFleetsConfigFilePath": "/static/configs/config.json"
            # TODO check wakuFleetsConfigFilePath?
        }

        return self.api_valid_request(method, data)

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
                "RpcProviders": [
                    {
                        "authType": "no-auth",
                        "chainId": 31337,
                        "enableRpsLimiter": False,
                        "enabled": True,
                        "name": "Anvil Direct",
                        "type": "embedded-direct",
                        "url": "http://127.0.0.1:8545"
                    }
                ],
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

    def create_account_and_login(self, **kwargs) -> Response:
        method = "CreateAccountAndLogin"
        data = self._create_account_request(**kwargs)
        return self.api_valid_request(method, data)

    def login(self, key_uid: str) -> Response:
        method = "LoginAccount"
        data = {
            "password": "Strong12345",
            "keyUid": key_uid,
            "kdfIterations": 256000,
        }
        return self.api_valid_request(method, data)

    def logout(self) -> Response:
        method = "Logout"
        return self.api_valid_request(method, {})

    def set_public_key(self):
        self.public_key = self.node_login_event.get("event", {}).get("settings", {}).get("public-key")

    def find_key_uid(self) -> str:
        return self.node_login_event.get("event", {}).get("account", {}).get("key-uid")
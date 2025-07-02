# Python Imports
import asyncio
import json
import logging
from typing import List, Optional, Any
from aiohttp import ClientSession, ClientTimeout, ClientError
from tenacity import retry, stop_after_delay, wait_fixed, retry_if_exception_type

# Project Imports

logger = logging.getLogger(__name__)


class AsyncRpcClient:
    def __init__(self, rpc_url: str, session: Optional[ClientSession] = None):
        self.rpc_url = rpc_url
        self._owns_session = session is None
        self.session = session or ClientSession(timeout=ClientTimeout(total=10))
        self.request_counter = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any):
        await self.close()

    async def close(self):
        if self._owns_session:
            await self.session.close()

    def _check_key_in_json(self, data: dict, key: str) -> str:
        if key not in data:
            raise AssertionError(f"Key '{key}' missing in response: {data}")
        return data[key]

    def verify_is_valid_json_rpc_response(self, data: dict, request_id: Optional[str] = None):
        self._check_key_in_json(data, "result")
        if request_id is not None and str(data.get("id")) != str(request_id):
            raise AssertionError(f"Expected ID {request_id}, got {data.get('id')}")

    def verify_is_json_rpc_error(self, data: dict):
        self._check_key_in_json(data, "error")

    @retry(stop=stop_after_delay(10), wait=wait_fixed(0.5), reraise=True, retry=retry_if_exception_type((
            ClientError, json.JSONDecodeError, AssertionError, asyncio.TimeoutError
        )))
    async def rpc_request(self, method: str, params: Optional[List] = None, request_id: Optional[str] = None,
        url: Optional[str] = None, enable_logging: bool = True) -> dict:
        if request_id is None:
            request_id = self.request_counter
            self.request_counter += 1

        url = url or self.rpc_url
        payload = {"jsonrpc": "2.0", "method": method, "id": request_id, "params": params or []}

        if enable_logging:
            logger.debug(f"Sending async POST to {url} with data: {json.dumps(payload, sort_keys=True)}")

        async with self.session.post(url, json=payload) as response:
            resp_text = await response.text()

            if response.status != 200:
                raise AssertionError(f"Bad HTTP status: {response.status}, body: {resp_text}")

            try:
                resp_json = await response.json()
            except json.JSONDecodeError:
                raise AssertionError(f"Invalid JSON in response: {resp_text}")

            if enable_logging:
                logger.debug(f"Received response: {json.dumps(resp_json, sort_keys=True)}")

            if "error" in resp_json:
                raise AssertionError(f"JSON-RPC Error: {resp_json['error']}")

            return resp_json

    async def rpc_valid_request(self, method: str, params: Optional[List] = None, request_id: Optional[str] = None,
        url: Optional[str] = None, enable_logging: bool = True) -> dict:
        resp_json = await self.rpc_request(method, params, request_id, url, enable_logging=enable_logging)
        self.verify_is_valid_json_rpc_response(resp_json, request_id)
        return resp_json

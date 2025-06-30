# Python Imports
import json
import logging
import requests
from tenacity import retry, stop_after_delay, wait_fixed
from json import JSONDecodeError

# Project Imports


class RpcClient:

    def __init__(self, rpc_url, client=requests.Session()):
        self.client = client
        self.rpc_url = rpc_url
        self.request_counter = 0

    def _check_decode_and_key_errors_in_response(self, response, key):
        try:
            return response.json()[key]
        except json.JSONDecodeError:
            raise AssertionError(f"Invalid JSON in response: {response.content}")
        except KeyError:
            raise AssertionError(f"Key '{key}' not found in the JSON response: {response.content}")

    def verify_is_valid_json_rpc_response(self, response, _id=None, skip_validation=False):
        if skip_validation:
            return response

        assert response.status_code == 200, f"Got response {response.content}, status code {response.status_code}"
        assert response.content
        self._check_decode_and_key_errors_in_response(response, "result")

        if _id:
            try:
                if _id != response.json()["id"]:
                    raise AssertionError(f"got id: {response.json()['id']} instead of expected id: {_id}")
            except KeyError:
                raise AssertionError(f"no id in response {response.json()}")
        return response

    def verify_is_json_rpc_error(self, response):
        assert response.status_code == 200
        assert response.content
        self._check_decode_and_key_errors_in_response(response, "error")

    @retry(stop=stop_after_delay(10), wait=wait_fixed(0.5), reraise=True)
    def rpc_request(self, method, params=None, request_id=None, url=None, enable_logging=True):
        if not request_id:
            request_id = self.request_counter
            self.request_counter += 1
        if params is None:
            params = []
        url = url if url else self.rpc_url
        data = {"jsonrpc": "2.0", "method": method, "id": request_id}
        if params:
            data["params"] = params
        if enable_logging:
            logging.debug(f"Sending POST request to url {url} with data: {json.dumps(data, sort_keys=True)}")
        response = self.client.post(url, json=data)
        try:
            resp_json = response.json()
            if enable_logging:
                logging.debug(f"Got response: {json.dumps(resp_json, sort_keys=True)}")
            if resp_json.get("error"):
                assert "JSON-RPC client is unavailable" != resp_json["error"]
        except JSONDecodeError:
            if enable_logging:
                logging.debug(f"Got response: {response.content}")
        return response

    def rpc_valid_request(self, method, params=None, _id=None, url=None, skip_validation=False, enable_logging=True):
        response = self.rpc_request(method, params, _id, url, enable_logging=enable_logging)
        self.verify_is_valid_json_rpc_response(response, _id, skip_validation=skip_validation)
        return response

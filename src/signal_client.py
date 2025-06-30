# Python Imports
import json
import logging
import time
import websocket
import os
from typing import List, Any, Dict, Optional
from pathlib import Path
from datetime import datetime
from websocket import WebSocketApp

from src.enums import SignalType

LOG_SIGNALS_TO_FILE = False
SIGNALS_DIR = os.path.dirname(os.path.abspath(__file__))


class SignalType(Enum):
    MESSAGES_NEW = "messages.new"
    MESSAGE_DELIVERED = "message.delivered"
    NODE_READY = "node.ready"
    NODE_STARTED = "node.started"
    NODE_LOGIN = "node.login"
    NODE_LOGOUT = "node.stopped"



class SignalClient:
    def __init__(self, ws_url: str, await_signals: List[str]):
        self.url = f"{ws_url}/signals"

        self.await_signals = await_signals
        # TODO: Improve delta_count explanation
        self.received_signals = {
            # For each signal type, store:
            # - list of received signals
            # - expected received event delta count (resets to 1 after each wait_for_event call)
            # - expected received event count
            # - a function that takes the received signal as an argument and returns True if the signal is accepted (counted) or discarded
            signal: {
                "received": [],
                "delta_count": 1,
                "expected_count": 1,
                "accept_fn": None,
            }
            for signal in self.await_signals
        }
        if LOG_SIGNALS_TO_FILE:
            self.signal_file_path = os.path.join(
                SIGNALS_DIR,
                f"signal_{ws_url.split(':')[-1]}_{datetime.now().strftime('%H%M%S')}.log",
            )
            Path(SIGNALS_DIR).mkdir(parents=True, exist_ok=True)

    def on_message(self, ws: WebSocketApp, signal: str):
        signal_data = json.loads(signal)
        if LOG_SIGNALS_TO_FILE:
            self.write_signal_to_file(signal_data)

        signal_type = signal_data.get("type")
        if signal_type in self.await_signals:
            accept_fn = self.received_signals[signal_type]["accept_fn"]
            if not accept_fn or accept_fn(signal_data):
                self.received_signals[signal_type]["received"].append(signal_data)

    def check_signal_type(self, signal_type: str):
        if signal_type not in self.await_signals:
            raise ValueError(f"Signal type {signal_type} is not in the list of awaited signals")

    # Used to set up how many instances of a signal to wait for, before triggering the actions
    # that cause them to be emitted.
    def prepare_wait_for_signal(self, signal_type: str, delta_count: int, accept_fn=None):
        self.check_signal_type(signal_type)

        if delta_count < 1:
            raise ValueError("delta_count must be greater than 0")
        self.received_signals[signal_type]["delta_count"] = delta_count
        self.received_signals[signal_type]["expected_count"] = len(self.received_signals[signal_type]["received"]) + delta_count
        self.received_signals[signal_type]["accept_fn"] = accept_fn

    def wait_for_signal(self, signal_type: str, timeout: int = 20) -> Dict | List[Dict]:
        self.check_signal_type(signal_type)

        start_time = time.time()
        received_signals = self.received_signals.get(signal_type)
        while (not received_signals) or len(received_signals["received"]) < received_signals["expected_count"]:
            if time.time() - start_time >= timeout:
                raise TimeoutError(f"Signal {signal_type} is not received in {timeout} seconds")
            time.sleep(0.2)
        logging.debug(f"Signal {signal_type} is received in {round(time.time() - start_time)} seconds")
        # TODO: Improve delta_count explanation
        delta_count = received_signals["delta_count"]
        self.prepare_wait_for_signal(signal_type, 1)
        if delta_count == 1:
            return self.received_signals[signal_type]["received"][-1]
        return self.received_signals[signal_type]["received"][-delta_count:]

    def wait_for_login(self) -> Dict:
        signal = self.wait_for_signal(SignalType.NODE_LOGIN.value)
        if "error" in signal["event"]:
            error_details = signal["event"]["error"]
            assert not error_details, f"Unexpected error during login: {error_details}"
        self.node_login_event = signal
        return signal

    def wait_for_logout(self) -> Dict:
        signal = self.wait_for_signal(SignalType.NODE_LOGOUT.value)
        return signal

    def find_signal_containing_string(self, signal_type: str, event_string: str, timeout=20) -> Optional[Dict]:
        start_time = time.time()
        while True:
            if time.time() - start_time >= timeout:
                raise TimeoutError(f"Signal {signal_type} containing {event_string} is not received in {timeout} seconds")
            if not self.received_signals.get(signal_type):
                time.sleep(0.2)
                continue
            for event in self.received_signals[signal_type]["received"]:
                if event_string in json.dumps(event):
                    logging.info(f"Signal {signal_type} containing {event_string} is received in {round(time.time() - start_time)} seconds")
                    return event
            time.sleep(0.2)

    def _on_error(self, ws: WebSocketApp, error: Any):
        logging.error(f"Error: {error}")

    def _on_close(self, ws: WebSocketApp, close_status_code: Any, close_msg: Any):
        logging.info(f"Connection closed: {close_status_code}, {close_msg}")

    def _on_open(self, ws: WebSocketApp):
        logging.info("Connection opened")

    def _connect(self):
        ws = websocket.WebSocketApp(
            self.url,
            on_message=self.on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        ws.on_open = self._on_open
        ws.run_forever()

    def write_signal_to_file(self, signal_data: Dict):
        with open(self.signal_file_path, "a+") as file:
            json.dump(signal_data, file)
            file.write("\n")

# Python Imports
import asyncio
import json
import logging
import os
from typing import Optional, Callable
from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType
from pathlib import Path
from datetime import datetime
from src.enums import SignalType

# Project Imports

logger = logging.getLogger(__name__)

LOG_SIGNALS_TO_FILE = False
SIGNALS_DIR = os.path.dirname(os.path.abspath(__file__))


class AsyncSignalClient:
    def __init__(self, ws_url: str, await_signals: list[str]):
        self.url = f"{ws_url}/signals"

        self.await_signals = await_signals
        self.ws: Optional[ClientWebSocketResponse] = None
        self.session: Optional[ClientSession] = None
        self.signal_file_path = None
        self.signal_lock = asyncio.Lock()
        # TODO: Improve delta explanation
        self.received_signals: dict[str, dict] = {
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

        if LOG_SIGNALS_TO_FILE: # Not being used currently
            Path(SIGNALS_DIR).mkdir(parents=True, exist_ok=True)
            self.signal_file_path = os.path.join(
                SIGNALS_DIR,
                f"signal_{ws_url.split(':')[-1]}_{datetime.now().strftime('%H%M%S')}.log",
            )

    async def __aenter__(self):
        self.session = ClientSession()
        self.ws = await self.session.ws_connect(self.url)
        asyncio.create_task(self._listen())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()

    async def _listen(self):
        async for msg in self.ws:
            if msg.type == WSMsgType.TEXT:
                await self.on_message(msg.data)
            elif msg.type == WSMsgType.ERROR:
                logger.error(f"WebSocket error: {self.ws.exception()}")

    async def on_message(self, signal: str):
        signal_data = json.loads(signal)
        if LOG_SIGNALS_TO_FILE:
            pass # TODO

        signal_type = signal_data.get("type")
        if signal_type in self.await_signals:
            async with self.signal_lock:
                accept_fn = self.received_signals[signal_type]["accept_fn"]
                if not accept_fn or accept_fn(signal_data):
                    self.received_signals[signal_type]["received"].append(signal_data)

    # Used to set up how many instances of a signal to wait for, before triggering the actions
    # that cause them to be emitted.
    async def prepare_wait_for_signal(self, signal_type: str, delta_count: int, accept_fn: Optional[Callable] = None):
        if signal_type not in self.await_signals:
            raise ValueError(f"Signal type {signal_type} is not in the list of awaited signals")
        async with self.signal_lock:
            self.received_signals[signal_type]["delta_count"] = delta_count
            self.received_signals[signal_type]["expected_count"] = (
                len(self.received_signals[signal_type]["received"]) + delta_count
            )
            self.received_signals[signal_type]["accept_fn"] = accept_fn

    async def wait_for_signal(self, signal_type: str, timeout: int = 20) -> dict | list[dict]:
        if signal_type not in self.await_signals:
            raise ValueError(f"Signal type {signal_type} is not in the list of awaited signals")

        start_time = asyncio.get_event_loop().time()
        while True:
            async with self.signal_lock:
                received = self.received_signals[signal_type]["received"]
                expected = self.received_signals[signal_type]["expected_count"]
                delta_count = self.received_signals[signal_type]["delta_count"]

                if len(received) >= expected:
                    await self.prepare_wait_for_signal(signal_type, 1)
                    return received[-1] if delta_count == 1 else received[-delta_count:]

            if asyncio.get_event_loop().time() - start_time >= timeout:
                raise TimeoutError(f"Signal {signal_type} not received in {timeout} seconds")
            await asyncio.sleep(0.2)

    async def wait_for_login(self) -> dict:
        signal = await self.wait_for_signal(SignalType.NODE_LOGIN.value)
        if "error" in signal["event"]:
            error_details = signal["event"]["error"]
            assert not error_details, f"Unexpected error during login: {error_details}"
        self.node_login_event = signal
        return signal

    async def wait_for_logout(self) -> dict:
        return await self.wait_for_signal(SignalType.NODE_LOGOUT.value)

    async def find_signal_containing_string(self, signal_type: str, event_string: str, timeout=20) -> Optional[dict]:
        start_time = asyncio.get_event_loop().time()
        while True:
            async with self.signal_lock:
                for event in self.received_signals.get(signal_type, {}).get("received", []):
                    if event_string in json.dumps(event):
                        logger.info(f"Found {signal_type} containing '{event_string}'")
                        return event

            if asyncio.get_event_loop().time() - start_time >= timeout:
                raise TimeoutError(f"Signal {signal_type} containing '{event_string}' not received in {timeout} seconds")
            await asyncio.sleep(0.2)

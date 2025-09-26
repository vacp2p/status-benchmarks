# Python Imports
import asyncio
import contextlib
import json
import logging
import os
from typing import Optional, AsyncGenerator
from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType
from pathlib import Path
from datetime import datetime
from collections import deque

# Project Imports
from src.enums import SignalType

logger = logging.getLogger(__name__)

LOG_SIGNALS_TO_FILE = False
SIGNALS_DIR = os.path.dirname(os.path.abspath(__file__))


class BufferedQueue:
    def __init__(self, max_size: int = 100):
        self.queue = asyncio.Queue()
        self.buffer = deque(maxlen=max_size)

    async def put(self, item):
        self.buffer.append(item)
        await self.queue.put(item)

    async def get(self):
        return await self.queue.get()

    def recent(self) -> list:
        return list(self.buffer)


class AsyncSignalClient:
    def __init__(self, ws_url: str, await_signals: list[str], buffer_size: int = 100):
        self.url = f"{ws_url}/signals"
        self.await_signals = await_signals
        self.ws: Optional[ClientWebSocketResponse] = None
        self.session: Optional[ClientSession] = None
        self.signal_file_path = None
        self.listener_task = None

        self.signal_queues: dict[str, BufferedQueue] = {
            signal: BufferedQueue(max_size=buffer_size) for signal in self.await_signals
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
        self.listener_task = asyncio.create_task(self._listen())
        await asyncio.sleep(0)  # Yield control to ensure _listen starts
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
        if self.listener_task:
            self.listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.listener_task

    async def _listen(self):
        logger.debug("WebSocket listener started")
        async for msg in self.ws:
            if msg.type == WSMsgType.TEXT:
                await self.on_message(msg.data)
            elif msg.type == WSMsgType.ERROR:
                logger.error(f"WebSocket error: {self.ws.exception()}")

    async def on_message(self, signal: str):
        signal_data = json.loads(signal)
        logger.debug(f"Received WebSocket message: {signal_data}")

        if LOG_SIGNALS_TO_FILE:
            pass  # TODO: write to file if needed

        signal_type = signal_data.get("type")
        if signal_type in self.signal_queues:
            await self.signal_queues[signal_type].put(signal_data)
            logger.debug(f"Queued signal: {signal_type}")
        else:
            logger.debug(f"Ignored signal not in await list: {signal_type}")

    async def wait_for_signal(self, signal_type: str, timeout: int = 20) -> dict:
        if signal_type not in self.signal_queues:
            raise ValueError(f"Signal type {signal_type} is not in the list of awaited signals")
        try:
            signal = await asyncio.wait_for(self.signal_queues[signal_type].get(), timeout)
            logger.debug(f"Received {signal_type} signal: {signal}")
            return signal
        except asyncio.TimeoutError:
            raise TimeoutError(f"Signal {signal_type} not received in {timeout} seconds")

    async def signal_stream(self, signal_type: str) -> AsyncGenerator[dict, None]:
        if signal_type not in self.signal_queues:
            raise ValueError(f"Signal type {signal_type} is not in the list of awaited signals")
        while True:
            yield await self.signal_queues[signal_type].get()

    def get_recent_signals(self, signal_type: str) -> list:
        if signal_type not in self.signal_queues:
            raise ValueError(f"Signal type {signal_type} is not in the list of awaited signals")
        return self.signal_queues[signal_type].recent()

    async def wait_for_login(self) -> dict:
        logger.debug("Waiting for login signal...")
        signal = await self.wait_for_signal(SignalType.NODE_LOGIN.value)
        logger.debug(f"Login signal received: {signal}")
        if "error" in signal.get("event", {}):
            error_details = signal["event"]["error"]
            assert not error_details, f"Unexpected error during login: {error_details}"
        self.node_login_event = signal
        return signal

    async def wait_for_logout(self) -> dict:
        return await self.wait_for_signal(SignalType.NODE_LOGOUT.value)


    async def find_signal_containing_string(self, signal_type: str, event_string: str, timeout: int = 20) \
            -> Optional[dict]:
        if signal_type not in self.signal_queues:
            raise ValueError(f"Signal type {signal_type} is not in the list of awaited signals")

        queue = self.signal_queues[signal_type]
        end_time = asyncio.get_event_loop().time() + timeout

        while True:
            for signal in queue.recent():
                if event_string in json.dumps(signal):
                    # Remove the found signal from the buffer
                    queue.buffer.remove(signal)
                    logger.info(f"Found {signal_type} containing '{event_string}' in buffer")
                    return signal

            if asyncio.get_event_loop().time() > end_time:
                raise TimeoutError(f"{signal_type} containing '{event_string}' not found in {timeout} seconds")

            await asyncio.sleep(0.2)

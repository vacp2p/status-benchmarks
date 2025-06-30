import os
import time
import json
import logging
import signal
import sys
import websocket

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Retrieve WebSocket URL from environment variable
WEBSOCKET_URL = os.getenv("WEBSOCKET_URL", "ws://localhost:3333/signals")


ws = None
should_exit = False


def on_message(ws, message):
    try:
        data = json.loads(message)
        logger.info(f"Received valid message: {data}")
    except json.JSONDecodeError:
        logger.warning(f"Received invalid JSON message: {message}")


def on_error(ws, error):
    logger.error(f"WebSocket error: {error}")


def on_close(ws, close_status_code, close_msg):
    logger.info(f"WebSocket connection closed. Status code: {close_status_code}, Message: {close_msg}")


def on_open(ws):
    logger.info("Successfully connected to WebSocket server.")


def connect_to_websocket():
    global ws
    reconnect_delay = 1
    max_delay = 60  # Cap the reconnect delay to avoid indefinite growth

    while not should_exit:
        try:
            logger.info(f"Connecting to WebSocket endpoint: {WEBSOCKET_URL}")
            ws = websocket.WebSocketApp(
                WEBSOCKET_URL,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            ws.run_forever()
            logger.info("WebSocket connection closed. Retrying...")
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}")

        # Exponential backoff for reconnection
        reconnect_delay = min(reconnect_delay * 2, max_delay)
        if not should_exit:
            logger.info(f"Reconnecting in {reconnect_delay} seconds...")
            time.sleep(reconnect_delay)


def signal_handler(sig, frame):
    """Handle termination signals (SIGINT, SIGTERM) for graceful shutdown."""
    global should_exit
    logger.info("Received termination signal. Shutting down...")
    should_exit = True
    if ws:
        ws.close()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    connect_to_websocket()

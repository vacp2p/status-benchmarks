# Python Imports
import asyncio
import logging

# Project Imports
from src.status_backend import StatusBackend

logger = logging.getLogger(__name__)

async def inject_messages(pod: StatusBackend, msg_per_sec: int, chat_id: str, num_messages: int):
    delay = 1 / msg_per_sec
    for message_count in range(num_messages):
        try:
            logger.debug(f"Sending message {message_count}")
            await pod.wakuext_service.send_chat_message(chat_id, f"Message {message_count}")

            if message_count == 0:
                logger.info(f"Successfully began sending {num_messages} messages")
            elif message_count % 10 == 0:
                logger.debug(f"Sent {message_count} messages")

            await asyncio.sleep(delay)

        except AssertionError as e:
            logger.error(f"Error sending message: {e}")
            await asyncio.sleep(1)

    logger.info(f"Finished sending {num_messages} messages")

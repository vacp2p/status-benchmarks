# Python Imports
import asyncio
import logging

# Project Imports
from src.status_backend import StatusBackend

logger = logging.getLogger(__name__)

async def inject_messages(pod: StatusBackend, delay_between_message: float, chat_id: str, num_messages: int):
    for message_count in range(num_messages):
        try:
            logger.debug(f"Sending message {message_count}")
            await pod.wakuext_service.send_chat_message(chat_id, f"Message {message_count}")

            if message_count == 0:
                logger.info(f"Successfully began sending {num_messages} messages")
            elif message_count % 10 == 0:
                logger.debug(f"Sent {message_count} messages")

            await asyncio.sleep(delay_between_message)

        except AssertionError as e:
            logger.error(f"Error sending message: {e}")
            await asyncio.sleep(1)

    logger.info(f"Finished sending {num_messages} messages")

# TODO merge in same function
async def inject_messages_one_to_one(pod: StatusBackend, delay_between_message: float, contact_id: str, num_messages: int):
    for message_count in range(num_messages):
        try:
            logger.debug(f"Sending message {message_count}")
            await pod.wakuext_service.send_one_to_one_message(contact_id, f"Message {message_count}")

            if message_count == 0:
                logger.info(f"Successfully began sending {num_messages} messages")
            elif message_count % 10 == 0:
                logger.debug(f"Sent {message_count} messages")

            await asyncio.sleep(delay_between_message)

        except AssertionError as e:
            logger.error(f"Error sending message: {e}")
            await asyncio.sleep(1)

    logger.info(f"Finished sending {num_messages} messages")

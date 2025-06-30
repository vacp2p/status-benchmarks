# Python Imports
import logging
import time
import threading

# Project Imports
from src.status_backend import StatusBackend

logger = logging.getLogger(__name__)


# TODO times can get blocked by response time
def inject_messages(pod: StatusBackend, msg_per_sec: int, chat_id: str, num_messages: int):
    def message_sender():
        message_count = 0
        while message_count < num_messages:
            try:
                logger.info(f"Sending message {message_count}")
                response = pod.wakuext_service.send_chat_message(chat_id, f"Message {message_count}")

                if message_count == 0:
                    logger.info("Successfully began sending messages")
                elif message_count % 10 == 0:
                    logger.debug(f"Sent {message_count} messages")
                message_count += 1

                time.sleep(1 / msg_per_sec)

            except Exception as e:
                logger.error(f"Error sending message: {e}")
                time.sleep(1)

        logger.info(f"Finished sending {num_messages} messages")

    # Start the message sender in a background thread
    sender_thread = threading.Thread(target=message_sender, daemon=True)
    sender_thread.start()
    logger.info(f"Message injection started in background thread for {num_messages} messages")
    return sender_thread

# Python Imports
import asyncio
import logging
import time
from concurrent.futures import as_completed, ThreadPoolExecutor

# Project Imports
from src.status_backend import StatusBackend

logger = logging.getLogger(__name__)


async def initialize_nodes_application(pod_names: list[str], wakuV2LightClient=False) -> dict[str, StatusBackend]:
    # We don't need a lock here because we cannot have two pods with the same name, and no other operations are done.
    nodes_status: dict[str, StatusBackend] = {}

    async def _init_status(pod_name: str):
        try:
            status_backend = StatusBackend(
                url=f"http://{pod_name}:3333",
                await_signals=["messages.new", "message.delivered", "node.ready", "node.started", "node.login",
                               "node.stopped"]
            )
            await status_backend.start_status_backend()
            await status_backend.create_account_and_login(wakuV2LightClient=wakuV2LightClient)
            await status_backend.wallet_service.start_wallet()
            await status_backend.wakuext_service.start_messenger()
            nodes_status[pod_name.split(".")[0]] = status_backend
        except AssertionError as e:
            logger.error(f"Error initializing StatusBackend for pod {pod_name}: {e}")
            raise

    await asyncio.gather(*[_init_status(pod) for pod in pod_names])

    logger.info(f"All {len(pod_names)} nodes have been initialized successfully")
    return nodes_status


async def request_join_nodes_to_community(backend_nodes: dict, nodes_to_join: list[str], community_id: str):

    async def _request_to_join_to_community(node: StatusBackend, community_id: str) -> str:
        try:
            _ = await node.wakuext_service.fetch_community(community_id)
            response_to_join = await node.wakuext_service.request_to_join_community(community_id)
            join_id = response_to_join.get("result", {}).get("requestsToJoinCommunity", [{}])[0].get("id")

            return join_id

        except AssertionError as e:
            logger.error(f"Error requesting to join on StatusBackend {node.base_url}: {e}")
            raise

    join_ids = await asyncio.gather(*[_request_to_join_to_community(backend_nodes[node], community_id) for node in nodes_to_join])

    logger.info(f"All {len(nodes_to_join)} nodes have been joined successfully to {community_id}")

    return join_ids


def login_nodes(backend_nodes: dict, include: list[str]):
    with ThreadPoolExecutor(max_workers=len(include)) as executor:
        futures = []
        for node in include:
            futures.append(executor.submit(login_node, backend_nodes[node]))

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Login error for a node: {e}")
                return

    logger.info(f"All nodes have been login successfully")


def login_node(node: StatusBackend):
    try:
        key_uid = node.find_key_uid()
        node.login(key_uid)
        node.wait_for_login()
        node.wakuext_service.start_messenger()
        node.wallet_service.start_wallet()
    except Exception as e:
        logger.error(f"Error logging out node {node}: {e}")
        raise


# def logout_nodes(backend_nodes: dict, include: list[str]):
#     with ThreadPoolExecutor(max_workers=len(include)) as executor:  # Concurrency for multiple pods
#         futures = []
#
#         for node in include:
#             futures.append(executor.submit(_logout_node, backend_nodes[node]))
#
#         for future in as_completed(futures):
#             try:
#                 future.result()
#             except Exception as e:
#                 logger.error(f"Initialization error for a node: {e}")
#                 return
#
#     logger.info(f"All nodes have been logged out successfully")





def _join_community_on_node(node, community_id) -> str:
    response = node.wakuext_service.fetch_community(community_id)
    response_to_join = node.wakuext_service.request_to_join_community(community_id)
    join_id = response_to_join.get("result", {}).get("requestsToJoinCommunity", [{}])[0].get("id")

    return join_id


def accept_community_requests(node_owner, join_ids):
    chat_ids = []
    with ThreadPoolExecutor(max_workers=len(join_ids)) as executor:
        futures = []

        for join_id in join_ids:
            futures.append(
                executor.submit(_accept_community_request, node_owner, join_id))

        for future in as_completed(futures):
            try:
                chat_id = future.result()
                chat_ids.append(chat_id)
            except Exception as e:
                logger.error(f"Acceptance error for a node: {e}")
                return

    return chat_ids[0]


def reject_community_requests(node_owner, join_ids):
    with ThreadPoolExecutor(max_workers=len(join_ids)) as executor:
        futures = []

        for join_id in join_ids:
            futures.append(
                executor.submit(_reject_community_request, node_owner, join_id))

        for future in as_completed(futures):
            try:
                _ = future.result()
                # TODO CHECK _
            except Exception as e:
                logger.error(f"Rejection error for a node: {e}")
                return


def _accept_community_request(node, join_id):
    max_retries = 40
    retry_interval = 0.5
    for attempt in range(max_retries):
        try:
            response = node.wakuext_service.accept_request_to_join_community(join_id)
            if response.get("result"):
                break
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{max_retries}: Unexpected error: {e}")
            time.sleep(retry_interval)
    else:
        raise Exception(f"Failed to accept request to join community in {max_retries * retry_interval} seconds.")

    chats = response.get("result", {}).get("communities", [{}])[0].get("chats", {})
    chat_id = list(chats.keys())[0] if chats else None
    return chat_id


def _reject_community_request(node, join_id):
    max_retries = 40
    retry_interval = 0.5
    for attempt in range(max_retries):
        try:
            response = node.wakuext_service.reject_request_to_join_community(join_id)
            if response.get("result"):
                break
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{max_retries}: Unexpected error: {e}")
            time.sleep(retry_interval)
    else:
        raise Exception(f"Failed to reject request to join community in {max_retries * retry_interval} seconds.")


def send_friend_requests(nodes, senders, receivers):
    # This method doesn't work great with multiple senders to multiple receivers.
    # Better use it onl with multiple senders and a few receivers
    with ThreadPoolExecutor(max_workers=len(senders)) as executor:
        futures = []

        for sender in senders:
            futures.append(
                executor.submit(_send_friend_request, nodes[sender], receivers))

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Sending friend request error for a node: {e}")
                return

    logger.info("Send request sent and accepted")


def _send_friend_request(sender: StatusBackend, receivers: list[StatusBackend]):
    for receiver in receivers:
        response = sender.wakuext_service.send_contact_request(receiver.public_key, "contact request")
        expected_message = get_message_by_content_type(response, content_type=MessageContentType.CONTACT_REQUEST.value)[
            0]
        message_id = expected_message.get("id")
        receiver.find_signal_containing_string(SignalType.MESSAGES_NEW.value, event_string=message_id)
        response = receiver.wakuext_service.accept_contact_request(message_id)
        logger.info("Request sent and accepted")


def get_message_by_content_type(response, content_type, message_pattern=""):
    matched_messages = []
    messages = response.get("result", {}).get("messages", [])
    for message in messages:
        if message.get("contentType") != content_type:
            continue
        if not message_pattern or message_pattern in str(message):
            matched_messages.append(message)
    if matched_messages:
        return matched_messages
    else:
        raise ValueError(f"Failed to find a message with contentType '{content_type}' in response")

# Python Imports
import logging
import time
from concurrent.futures import as_completed, ThreadPoolExecutor
from typing import List, Dict

# Project Imports
from src.status_backend import StatusBackend

logger = logging.getLogger(__name__)


def initialize_nodes_application(pod_names: list[str], wakuV2LightClient=False):
    nodes_status = {}

    # Initialize thread pool for concurrent execution
    with ThreadPoolExecutor(max_workers=len(pod_names)) as executor:  # Concurrency for multiple pods
        futures = []

        # Step 1: Initialize StatusBackend and SignalClient for each pod
        for pod_name in pod_names:
            futures.append(
                executor.submit(_init_status, nodes_status, pod_name, wakuV2LightClient))  # One signal per backend

        # Wait for all initialization tasks to complete
        for future in as_completed(futures):  # Use concurrent.futures.as_completed here
            try:
                future.result()
            except Exception as e:
                logger.error(f"Initialization error for a node: {e}")
                return

    logger.info(f"All {len(pod_names)} nodes have been initialized successfully")

    return nodes_status



def join_nodes_to_community(backend_nodes: Dict, owner: StatusBackend, nodes_to_join, community_id):
    join_ids = []

    with ThreadPoolExecutor(max_workers=len(nodes_to_join)) as executor:  # Concurrency for multiple pods
        futures = []

        for node in nodes_to_join:
            selected_node = backend_nodes[node]
            futures.append(
                executor.submit(_join_community_on_node, selected_node, community_id))  # One signal per backend

        # Wait for all initialization tasks to complete
        for future in as_completed(futures):  # Use concurrent.futures.as_completed here
            try:
                join_id = future.result()
                join_ids.append(join_id)
            except Exception as e:
                logger.error(f"Initialization error for a node: {e}")
                return

    logger.info(f"All {len(nodes_to_join)} nodes have sent join community request")

    chat_ids = _accept_community_requests(owner, join_ids)

    logger.info(f"All {len(chat_ids)} nodes have accepted community request")
    logger.info(f"Chat IDs: {chat_ids}")

    return chat_ids


def login_nodes(backend_nodes: Dict, include: List[str]):
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


def logout_nodes(backend_nodes: Dict, include: List[str]):
    with ThreadPoolExecutor(max_workers=len(include)) as executor:  # Concurrency for multiple pods
        futures = []

        for node in include:
            futures.append(executor.submit(_logout_node, backend_nodes[node]))

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Initialization error for a node: {e}")
                return

    logger.info(f"All nodes have been logged out successfully")


def _logout_node(node: StatusBackend):
    try:
        node.logout()
        node.wait_for_logout()
    except Exception as e:
        logger.error(f"Error logging out node {node}: {e}")
        raise


def _init_status(nodes_status, pod_name, wakuV2LightClient):
    """
    Helper function to initialize a StatusBackend instance and its dedicated SignalClient.
    """
    try:
        status_backend = StatusBackend(url=f"http://{pod_name}:3333",
                                       await_signals=["messages.new", "message.delivered", "node.ready", "node.started",
                                                      "node.login", "node.stopped"])
        status_backend.init_status_backend()
        nodes_status[pod_name.split(".")[0]] = status_backend
        status_backend.create_account_and_login(wakuV2LightClient=wakuV2LightClient)
        status_backend.wait_for_login()
        status_backend.find_public_key()
        status_backend.wakuext_service.start_messenger()
        status_backend.wallet_service.start_wallet()
    except Exception as e:
        logger.error(f"Error initializing StatusBackend for pod {pod_name}: {e}")
        raise


def _join_community_on_node(node, community_id) -> str:
    response = node.wakuext_service.fetch_community(community_id)
    response_to_join = node.wakuext_service.request_to_join_community(community_id)
    join_id = response_to_join.get("result", {}).get("requestsToJoinCommunity", [{}])[0].get("id")

    return join_id


def _accept_community_requests(node_owner, join_ids):
    chat_ids = []
    with ThreadPoolExecutor(max_workers=len(join_ids)) as executor:  # Concurrency for multiple pods
        futures = []

        for join_id in join_ids:
            futures.append(
                executor.submit(_accept_community_request, node_owner, join_id))  # One signal per backend

        # Wait for all initialization tasks to complete
        for future in as_completed(futures):  # Use concurrent.futures.as_completed here
            try:
                chat_id = future.result()
                chat_ids.append(chat_id)
            except Exception as e:
                logger.error(f"Initialization error for a node: {e}")
                return

    return chat_ids


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

def _send_friend_request(sender: StatusBackend, receivers: List[StatusBackend]):
    for receiver in receivers:
        response = sender.wakuext_service.send_contact_request(receiver.public_key, "contact request")
        expected_message = get_message_by_content_type(response, content_type=MessageContentType.CONTACT_REQUEST.value)[0]
        message_id = expected_message.get("id")
        receiver.find_signal_containing_pattern(SignalType.MESSAGES_NEW.value, event_pattern=message_id)
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

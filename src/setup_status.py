# Python Imports
import asyncio
import logging
import random
import string
import time

# Project Imports
from src.enums import MessageContentType, SignalType
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


async def request_join_nodes_to_community(backend_nodes: dict[str, StatusBackend], nodes_to_join: list[str], community_id: str):
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

    logger.info(f"All {len(nodes_to_join)} nodes have requested joined a community successfully to {community_id}")

    return join_ids


async def login_nodes(backend_nodes: dict[str, StatusBackend], include: list[str]):
    async def _login_node(node: StatusBackend):
        try:
            await node.login(node.find_key_uid())
            await node.wakuext_service.start_messenger()
            await node.wallet_service.start_wallet()
        except AssertionError as e:
            logger.error(f"Error logging out node {node}: {e}")
            raise

    await asyncio.gather(*[_login_node(backend_nodes[node]) for node in include])


# TODO add an accept rate
async def accept_community_requests(node_owner: StatusBackend, join_ids: list[str]):
    async def _accept_community_request(node: StatusBackend, join_id: str) -> str:
        max_retries = 40
        retry_interval = 0.5

        for attempt in range(max_retries):
            try:
                response = await node.wakuext_service.accept_request_to_join_community(join_id)
                # We need to find the correspondant community of the join_id. We retrieve first chat because should be
                # the only one. We do this because there can be several communities if we reuse the node.
                # TODO why it returns the information of all communities? Getting the chat this way seems weird
                msgs = await get_messages_by_message_type(response, "requestsToJoinCommunity", join_id)
                for community in response.get("result").get("communities"):
                    # We always have one msg
                    if community.get("id") == msgs[0].get("communityId"):
                        # We always have one chat
                        return list(community.get("chats").keys())[0]
            except Exception as e:
                logging.error(f"Attempt {attempt + 1}/{max_retries}: Unexpected error: {e}")
                time.sleep(retry_interval)

        raise Exception(
            f"Failed to accept request to join community in {max_retries * retry_interval} seconds."
        )

    chat_ids = await asyncio.gather(*[_accept_community_request(node_owner, join_id) for join_id in join_ids])
    logger.info(f"All {len(join_ids)} nodes have been accepted successfully")

    # Same chat ID for everyone
    return chat_ids[0]

async def reject_community_requests(owner: StatusBackend, join_ids: list[str]):
    async def _reject_community_request(node: StatusBackend, join_id: str):
        max_retries = 40
        retry_interval = 0.5

        for attempt in range(max_retries):
            try:
                response = await node.wakuext_service.decline_request_to_join_community(join_id)
                return response # TODO do we want this
            except AssertionError as e:
                logging.error(f"Attempt {attempt + 1}/{max_retries}: Unexpected error: {e}")
                time.sleep(retry_interval)

        raise Exception(
            f"Failed to reject community request in {max_retries * retry_interval} seconds."
        )

    _ = await asyncio.gather(*[_reject_community_request(owner, join_id) for join_id in join_ids])

    logger.info(f"All {len(join_ids)} nodes have been rejected successfully")

async def send_friend_requests(nodes: dict[str, StatusBackend], senders: list[str], receivers: list[str]):
    async def _send_friend_request(nodes: dict[str, StatusBackend], sender: str, receivers: list[str]):
        # Send contact requests from sender -> receivers
        responses = await asyncio.gather(*[nodes[sender].wakuext_service.send_contact_request(nodes[node].public_key, "asd") for node in receivers])
        # Get responses and filter by contact requests
        request_responses = await asyncio.gather(*[get_messages_by_content_type(response, MessageContentType.CONTACT_REQUEST.value) for response in responses])
        # Create a dict {receiver: request}, using the first response (there is always only one friend request)
        request_ids = {receiver: request_responses[i][0].get("id") for i, receiver in enumerate(receivers)}

        return sender, request_ids

    requests_made = await asyncio.gather(*[_send_friend_request(nodes, sender, receivers) for sender in senders])
    # Returns a list of tuples like: [(sender name, {receiver: request_id, ...})]
    logger.info(f"All {len(receivers)} friend requests sent.")
    return requests_made


async def accept_friend_requests(nodes: dict[str, StatusBackend], requests: list[(str, dict[str, str])]):
    # Flatten all tasks into a single list and execute them concurrently
    async def _accept_friend_request(nodes: dict[str, StatusBackend], sender: str, receiver: str, request_id: str):
        max_retries = 40
        retry_interval = 0.5

        for attempt in range(max_retries):
            try:
                _ = await nodes[receiver].wakuext_service.accept_contact_request(request_id)
                accepted_signal = f"@{nodes[receiver].public_key} accepted your contact request"
                signal = await nodes[sender].signal.find_signal_containing_string(SignalType.MESSAGES_NEW.value, event_string=accepted_signal)
                return signal
            except Exception as e:
                logging.error(f"Attempt {attempt + 1}/{max_retries}: Unexpected error: {e}")
                time.sleep(retry_interval)

        raise Exception(
            f"Failed to accept friend request in {max_retries * retry_interval} seconds."
        )

    _ = await asyncio.gather(
        *[
            _accept_friend_request(nodes, sender, receiver, request_id)
            for sender, receivers in requests
            for receiver, request_id in receivers.items()
        ]
    )

    total_requests = sum(len(receivers) for _, receivers in requests)
    logger.info(f"All {total_requests} friend requests accepted.")


async def add_contacts(nodes: dict[str, StatusBackend], adders: list[str], contacts: list[str]):
    async def _add_contacts_to_node(nodes: dict[str, StatusBackend], adder: str, contacts: list[str]):
        _ = await asyncio.gather(*[nodes[adder].wakuext_service.add_contact(nodes[contact].public_key, contact) for contact in contacts])

        return _

    _ = await asyncio.gather(*[_add_contacts_to_node(nodes, adder, contacts) for adder in adders])

    logger.info(f"All {len(contacts)} contacts added to {len(adders)} nodes.")


async def decline_friend_requests(nodes: dict[str, StatusBackend], requests: list[(str, dict[str, str])]):
    # Flatten all tasks into a single list and execute them concurrently
    async def _decline_friend_request(nodes: dict[str, StatusBackend], sender: str, receiver: str, request_id: str):
        max_retries = 40
        retry_interval = 0.5

        for attempt in range(max_retries):
            try:
                _ = await nodes[receiver].wakuext_service.decline_contact_request(request_id)
                return _
            except Exception as e:
                logging.error(f"Attempt {attempt + 1}/{max_retries}: Unexpected error: {e}")
                time.sleep(retry_interval)

        raise Exception(
            f"Failed to reject friend request in {max_retries * retry_interval} seconds."
        )

    _ = await asyncio.gather(
        *[
            _decline_friend_request(nodes, sender, receiver, request_id)
            for sender, receivers in requests
            for receiver, request_id in receivers.items()
        ]
    )

    total_requests = sum(len(receivers) for _, receivers in requests)
    logger.info(f"All {total_requests} friend requests rejected.")


async def create_group_chat(admin: StatusBackend, receivers: list[str]):
    name = f"private_group_{''.join(random.choices(string.ascii_letters, k=10))}"
    logger.info(f"Creating private group {name}")
    response = await admin.wakuext_service.create_group_chat_with_members(receivers, name)
    group_id = response.get("result", {}).get("communities", [{}])[0].get("id")
    logger.info(f"Group {name} created with ID {group_id}")



async def get_messages_by_content_type(response: dict, content_type: str,  message_pattern: str="") -> list[dict]:
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


async def get_messages_by_message_type(response: dict, message_type: str = "messages",  message_pattern: str="") -> list[dict]:
    matched_messages = []
    messages = response.get("result", {}).get(message_type, [])
    for message in messages:
        if not message_pattern or message_pattern in str(message):
            matched_messages.append(message)
    if matched_messages:
        return matched_messages
    else:
        raise ValueError(f"Failed to find a message with message type '{message_type}' in response")

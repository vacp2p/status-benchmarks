# Python Imports
import asyncio
import logging
import random
import string
import time
from functools import partial
from typing import List

# Project Imports
from src.async_utils import launch_workers, collect_results_from_tasks, TaskResult, CollectedItem, \
    function_on_queue_item
from src.dataclasses import ResultEntry
from src.enums import MessageContentType, SignalType
from src.status_backend import StatusBackend

logger = logging.getLogger(__name__)

NodesInformation = dict[str, StatusBackend]


async def initialize_nodes_application(pod_names: list[str], wakuV2LightClient=False) -> NodesInformation:
    # We don't need a lock here because we cannot have two pods with the same name, and no other operations are done.
    nodes_status: NodesInformation = {}

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


async def send_friend_requests(nodes: NodesInformation,
                               results_queue: asyncio.Queue[CollectedItem | None],
                               senders: list[str], receivers: list[str],
                               finished_evt: asyncio.Event,
                               intermediate_delay: float = 1, max_in_flight: int = 0):

    async def _send_friend_request(nodes: NodesInformation, sender: str, receiver: str):
        response = await nodes[sender].wakuext_service.send_contact_request(nodes[receiver].public_key, "Friend Request")
        # Get responses and filter by contact requests to obtain request ids
        request_response = await get_messages_by_content_type(response, MessageContentType.CONTACT_REQUEST.value)
        # Create a ResultEntry using the first response (there is always only one friend request)
        request_result = ResultEntry(sender=sender, receiver=receiver, timestamp=int(request_response[0].get("timestamp")),
                                 result=request_response[0].get("id"))

        return request_id

    done_queue: asyncio.Queue[TaskResult | None] = asyncio.Queue()

    workers_to_launch = [
        partial(_send_friend_request, nodes, sender, receiver)
        for sender in senders
        for receiver in receivers
    ]

    collector_task = asyncio.create_task(collect_results_from_tasks(done_queue, results_queue, len(workers_to_launch), finished_evt))
    launcher_task = asyncio.create_task(launch_workers(workers_to_launch, done_queue, intermediate_delay, max_in_flight))

    await asyncio.gather(launcher_task, collector_task)


async def accept_friend_requests(nodes: dict[str, StatusBackend], results_queue: asyncio.Queue[CollectedItem | None],
                                 consumers: int, finished_evt: asyncio.Event) -> List[float]:
    # TODO: This should be activated when the signal is received instead of getting looped
    async def _accept_friend_request(queue_result: CollectedItem):
        max_retries = 40
        retry_interval = 2

        for attempt in range(max_retries):
            function_name, result_entry = queue_result
            try:
                _ = await nodes[result_entry.receiver].wakuext_service.accept_contact_request(result_entry.result)
                accepted_signal = f"@{nodes[result_entry.receiver].public_key} accepted your contact request"
                message = await nodes[result_entry.sender].signal.find_signal_containing_string(SignalType.MESSAGES_NEW.value,
                                                                                                event_string=accepted_signal,
                                                                                                timeout=10)
                return message[0] - int(result_entry.timestamp) // 1000  # Convert unix milliseconds to seconds
            except Exception as e:
                logging.error(f"Attempt {attempt + 1}/{max_retries} from {result_entry.sender} to {result_entry.receiver}: "
                              f"Unexpected error accepting friend request: {e}")
                time.sleep(2)

        raise Exception(
            f"Failed to accept friend request in {max_retries * retry_interval} seconds."
        )

    delays_queue: asyncio.Queue[float] = asyncio.Queue()

    workers = [asyncio.create_task(
        function_on_queue_item(results_queue, _accept_friend_request, delays_queue))
        for _ in range(consumers)]

    await finished_evt.wait()
    logger.info("All friend requests have been sent. Waiting for all to be accepted.")
    await results_queue.join()
    logger.info("All friend requests have been accepted.")

    for _ in range(consumers):
        results_queue.put_nowait(None)
    await asyncio.gather(*workers)

    delays: list[float] = []
    while not delays_queue.empty():
        delays.append(delays_queue.get_nowait())

    return delays


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

    return group_id


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

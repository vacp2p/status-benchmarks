# Python Imports
import asyncio
import random
import logging
import string
from dataclasses import dataclass
from typing import List, Callable, Optional, Awaitable

# Project Imports
import src.logger
from src.async_utils import CollectedItem, cleanup_queue_on_event
from src.setup_status import request_join_nodes_to_community, NodesInformation, \
    send_friend_requests

logger = logging.getLogger(__name__)


Action = Callable[[NodesInformation, asyncio.Queue[CollectedItem|None], int], Awaitable[asyncio.Queue[float]]]


@dataclass(frozen=True)
class CommunitySetupResult:
    community_id: str
    chat_id: str
    join_delays: list[float]


async def create_community_util(status_nodes: NodesInformation, owner: str, to_include: List[str],
                                action: Action, intermediate_delay: int = 1,
                                consumers: int = 4) -> Optional[CommunitySetupResult]:
    name = f"test_community_{''.join(random.choices(string.ascii_letters, k=10))}"
    logger.info(f"Creating community {name}")
    node_owner = status_nodes[owner]
    response = await node_owner.wakuext_service.create_community(name)
    community_id = response.get("result", {}).get("communities", [{}])[0].get("id")
    chat_id = response.get("result", {}).get("chats", [{}])[0].get("id")
    logger.info(f"Community {name} created with ID {community_id}")

    results_accept_queue: asyncio.Queue[CollectedItem | None] = asyncio.Queue()
    finished_accept_evt = asyncio.Event()

    send_to_accept_task = asyncio.create_task(
        request_join_nodes_to_community(status_nodes, results_accept_queue, to_include,
                                        community_id, finished_accept_evt,
                                        intermediate_delay))

    if action is None:
        return None

    accept_task = asyncio.create_task(action(node_owner, results_accept_queue, consumers))
    cleanup_task = asyncio.create_task(cleanup_queue_on_event(finished_accept_evt, results_accept_queue, consumers))

    _, delays_queue, _ = await asyncio.gather(send_to_accept_task, accept_task, cleanup_task)

    join_delays: list[float] = []
    while not delays_queue.empty():
        join_delays.append(delays_queue.get_nowait())

    logger.info(f"All nodes successfully joined community {community_id}. Delays are: {join_delays}")
    logger.info(f"Waiting 10 seconds")
    await asyncio.sleep(10)

    return CommunitySetupResult(community_id=community_id, chat_id=chat_id, join_delays=join_delays)


async def send_friend_requests_util(relay_nodes: NodesInformation, from_nodes, to_nodes, action: Action,
                                    cap_num_receivers: Optional[int] = None, consumers: int = 4) -> List[float]:
    results_queue: asyncio.Queue[CollectedItem | None] = asyncio.Queue()
    finished_evt = asyncio.Event()

    send_task = asyncio.create_task(
        send_friend_requests(relay_nodes, results_queue, from_nodes, to_nodes, finished_evt, cap_num_receivers))

    if action is None:
        return []

    accept_task = asyncio.create_task(action(relay_nodes, results_queue, consumers))
    cleanup_task = asyncio.create_task(cleanup_queue_on_event(finished_evt, results_queue, consumers))
    _, delays_queue, _ = await asyncio.gather(send_task, accept_task, cleanup_task)

    delays: list[float] = []
    while not delays_queue.empty():
        delays.append(delays_queue.get_nowait())

    return delays

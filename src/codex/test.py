# Python imports
import asyncio
import random
import string
import logging
from typing import cast

# Project imports
from src.enums import SignalType
from src.inject_messages import inject_messages
from src.logger import TraceLogger
from src.setup_status import request_join_nodes_to_community, accept_community_requests
from src import kube_utils, setup_status

logger = cast(TraceLogger, logging.getLogger(__name__))


async def codex_test():
    kube_utils.setup_kubernetes_client()
    backend_relay_pods = kube_utils.get_pods("status-backend-relay-codex", "status-go-test")
    relay_nodes = await setup_status.initialize_nodes_application(backend_relay_pods, codex_config_enabled=True, message_archive_interval=60, import_initial_delay=5)

    # Create community
    name = f"test_community_{''.join(random.choices(string.ascii_letters, k=10))}"
    logger.info(f"Creating community {name}")
    owner_node = relay_nodes["status-backend-relay-codex-0"]
    response = await owner_node.wakuext_service.create_community(name, history_archive_support_enabled=True)
    community_id = response.get("result", {}).get("communities", [{}])[0].get("id")
    community_chat_id = response.get("result", {}).get("chats", [{}])[0].get("id")
    logger.info(f"Community {name} created with ID {community_id}")

    # Add members but one
    nodes = [key for key in relay_nodes.keys() if key != "status-backend-relay-codex-0"]
    future_member = nodes[-1]
    members = nodes[:-1]
    join_ids = await request_join_nodes_to_community(relay_nodes, members, community_id)
    await accept_community_requests(owner_node, join_ids)

    # TODO: Looks like we also need to connect them manually, change it to discovery when it is available.
    info = await owner_node.wakuext_service.debug()
    for node in nodes:
        await relay_nodes[node].wakuext_service.connect(info.get("result", {})["id"], info.get("result", {})["addrs"])
        logger.trace(f"Connected {node} to owner.")

    logger.info("Waiting 5 seconds")
    await asyncio.sleep(5)

    # Do some publishing
    await inject_messages(owner_node, 5, community_chat_id, 2)

    # Archival should be created after 70 seconds
    logger.info("Waiting 70 seconds")
    await asyncio.sleep(70)

    # Add another member
    join_ids = await request_join_nodes_to_community(relay_nodes, [future_member], community_id)
    _ = await accept_community_requests(owner_node, join_ids)

    logger.info("Waiting 10 seconds")
    await asyncio.sleep(10)

    # All members should have the community archive, including the future member
    for node in nodes:
        await relay_nodes[node].signal.wait_for_signal(SignalType.COMMUNITY_IMPORTING_HISTORY_ARCHIVE_MESSAGES_FINISHED.value, timeout=20)
        logger.info(f"Node {node} has imported the community archive.")

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()])
    logger.info("Finished message_sending")

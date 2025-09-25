# Python Imports
import asyncio
import random
import string
import logging

# Project Imports
import src.logger
from src import kube_utils
from src import setup_status
from src.inject_messages import inject_messages
from src.setup_status import request_join_nodes_to_community, login_nodes, accept_community_requests

logger = logging.getLogger(__name__)


async def subscription_performance():
    # 10 relay nodes including 1 publisher node
    # 5 service nodes
    # 500 light nodes
    # One community setup
    # All relay and light nodes have joined the community
    # -> Relay and service nodes are running
    # -> 1 relay node is injecting messages
    # -> Start light nodes
    # -> Measure time from start to time messages are being received on filter
    kube_utils.setup_kubernetes_client()
    backend_relay_pods = kube_utils.get_pods("status-backend-relay", "status-go-test")
    backend_light_pods = kube_utils.get_pods("status-backend-light", "status-go-test")

    relay_nodes, light_nodes = await asyncio.gather(
        setup_status.initialize_nodes_application(backend_relay_pods),
        setup_status.initialize_nodes_application(backend_light_pods, wakuV2LightClient=True)
    )

    name = f"test_community_{''.join(random.choices(string.ascii_letters, k=10))}"
    logger.info(f"Creating community {name}")
    response = await relay_nodes["status-backend-relay-0"].wakuext_service.create_community(name)
    community_id = response.get("result", {}).get("communities", [{}])[0].get("id")
    logger.info(f"Community {name} created with ID {community_id}")

    owner = relay_nodes["status-backend-relay-0"]
    nodes = [key for key in relay_nodes.keys() if key != "status-backend-relay-0"]

    joins_ids_relay, join_ids_light = await asyncio.gather(
        request_join_nodes_to_community(relay_nodes, nodes, community_id),
        request_join_nodes_to_community(light_nodes, light_nodes.keys(), community_id)
    )

    logger.info(f"Join IDs: {joins_ids_relay}, \n {join_ids_light}")

    chat_id_relays, chat_id_lights = await asyncio.gather(
        accept_community_requests(owner, joins_ids_relay),
        accept_community_requests(owner, join_ids_light),
    )

    message_task = asyncio.create_task(inject_messages(owner, 1, community_id + chat_id_relays, 30))
    await asyncio.sleep(10)
    logger.info("Logging out light nodes")
    await asyncio.gather(*[node.logout() for node in light_nodes.values()])
    logger.info("Logging in light nodes")
    await login_nodes(light_nodes, light_nodes.keys())

    await message_task

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()])
    await asyncio.gather(*[node.shutdown() for node in light_nodes.values()])
    logger.info("Finished subscription_performance")

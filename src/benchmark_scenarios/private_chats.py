# Python Imports
import asyncio
import logging
import random

# Project Imports
import src.logger
from src import kube_utils
from src.setup_status import initialize_nodes_application, send_friend_requests, accept_friend_requests

logger = logging.getLogger(__name__)

async def idle_relay():
    # 1 relay node alice
    # 100 relay nodes - friends
    # friends have accepted contact request with alice, who accepted it

    kube_utils.setup_kubernetes_client()
    backend_relay_pods = kube_utils.get_pods("status-backend-relay", "status-go-test")
    relay_nodes = await initialize_nodes_application(backend_relay_pods)

    alice = "status-backend-relay-0"
    friends = [key for key in relay_nodes.keys() if key != alice]
    requests_made = await send_friend_requests(relay_nodes, [alice], friends)
    _ = await accept_friend_requests(relay_nodes, requests_made)

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()])
    logger.info("Finished idle_relay")


async def idle_light():
    # 1 light node alice
    # 100 light nodes - friends
    # friends have accepted contact request with alice

    kube_utils.setup_kubernetes_client()
    backend_light_pods = kube_utils.get_pods("status-backend-light", "status-go-test")
    light_nodes = await initialize_nodes_application(backend_light_pods)

    alice = "status-backend-light-0"
    friends = [key for key in light_nodes.keys() if key != alice]
    requests_made = await send_friend_requests(light_nodes, [alice], friends)
    _ = await accept_friend_requests(light_nodes, requests_made)

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in light_nodes.values()])
    logger.info("Finished idle_light")

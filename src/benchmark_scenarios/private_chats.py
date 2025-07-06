# Python Imports
import asyncio
import logging
import random

# Project Imports
import src.logger
from src import kube_utils, setup_status
from src.setup_status import initialize_nodes_application, send_friend_requests, accept_friend_requests, \
    decline_friend_requests

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


async def contact_request():
    # relay: 25 requesters, 60 requested (20 accept, 20 reject, 20 ignore), 25 idle
    # light: 25 requesters, 60 requested (20 accept, 20 reject, 20 ignore), 25 idle
    # -> Each requester send a contact request to 3 nodes in the requested set (random selection)
    # -> accepting nodes in the set accept the request
    # -> rejecting nodes rejects the request
    # -> ignoring nodes ignore the request
    # measure: Success rate of contact requests received
    # measure: Success rate of contact request accepted
    kube_utils.setup_kubernetes_client()
    backend_relay_pods = kube_utils.get_pods("status-backend-relay", "status-go-test")
    backend_light_pods = kube_utils.get_pods("status-backend-light", "status-go-test")

    relay_nodes, light_nodes = await asyncio.gather(
        setup_status.initialize_nodes_application(backend_relay_pods),
        setup_status.initialize_nodes_application(backend_light_pods, wakuV2LightClient=True)
    )

    backend_relay_pods = [pod_name.split(".")[0] for pod_name in backend_relay_pods]
    backend_light_pods = [pod_name.split(".")[0] for pod_name in backend_light_pods]

    relay_requesters = backend_relay_pods[:25]
    light_requesters = backend_light_pods[:25]
    relay_requested = backend_relay_pods[25:85]
    light_requested = backend_light_pods[25:85]

    # Returns a list of tuples like: [(sender name, {receiver: request_id, ...})]
    relay_friend_requests, light_friend_requests = await asyncio.gather(
        *[send_friend_requests(relay_nodes, [requester], random.sample(relay_requested, 3)) for requester in
          relay_requesters],
        *[send_friend_requests(light_nodes, [requester], random.sample(light_requested, 3)) for requester in
          light_requesters]
    )

    to_accept_requests_relay = random.sample(relay_friend_requests, 20)
    remaining_relay = list(set(relay_friend_requests) - set(to_accept_requests_relay))
    to_reject_requests_relay = random.sample(remaining_relay, 20)

    to_accept_requests_light = random.sample(light_friend_requests, 20)
    remaining_light = list(set(light_friend_requests) - set(to_accept_requests_light))
    to_reject_requests_light = random.sample(remaining_light, 20)


    _ = await asyncio.gather(
        *[accept_friend_requests(relay_nodes, to_accept_requests_relay)],
        *[accept_friend_requests(light_nodes, to_accept_requests_light)],
        *[decline_friend_requests(relay_nodes, to_reject_requests_relay)],
        *[decline_friend_requests(light_nodes, to_reject_requests_light)],
    )

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()],
                         *[node.shutdown() for node in light_nodes.values()])
    logger.info("Finished contact_request")

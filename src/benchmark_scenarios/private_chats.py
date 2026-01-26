# Python Imports
import asyncio
import logging
import random

# Project Imports
import src.logger
from src import kube_utils, setup_status
from src.benchmark_scenarios.scenario_utils import send_friend_requests_util
from src.inject_messages import inject_messages_one_to_one, inject_messages_group_chat
from src.setup_status import initialize_nodes_application, accept_friend_requests, \
    decline_friend_requests, create_group_chat, add_contacts

logger = logging.getLogger(__name__)


async def idle_relay(consumers: int = 4):
    # 1 relay node alice
    # 100 relay nodes - friends
    # friends have accepted contact request with alice, who accepted it

    kube_utils.setup_kubernetes_client()
    backend_relay_pods = kube_utils.get_pods("status-backend-relay", "status-go-test")
    relay_nodes = await initialize_nodes_application(backend_relay_pods)

    for node_id, node in relay_nodes.items():
        peers = await node.wakuext_service.peers()
        logger.info(f"Peers from {node_id}: {peers}")

    alice = "status-backend-relay-0"
    friends = [key for key in relay_nodes.keys() if key != alice]

    delays = await send_friend_requests_util(relay_nodes, [alice], friends, accept_friend_requests, consumers)
    logger.info(f"Delays are: {delays}")

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()])
    logger.info("Finished idle_relay")


async def idle_light(consumers: int = 4):
    # 1 light node alice
    # 100 light nodes - friends
    # friends have accepted contact request with alice, who accepted it

    kube_utils.setup_kubernetes_client()
    backend_light_pods = kube_utils.get_pods("status-backend-light", "status-go-test")
    light_nodes = await initialize_nodes_application(backend_light_pods, wakuV2LightClient=True)

    await asyncio.sleep(10)

    alice = "status-backend-light-0"
    friends = [key for key in light_nodes.keys() if key != alice]

    delays = await send_friend_requests_util(light_nodes, [alice], friends, accept_friend_requests, consumers)

    logger.info(f"Delays are: {delays}")

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in light_nodes.values()])
    logger.info("Finished idle_light")


async def contact_request(consumers: int = 4):
    # relay: 25 requesters, 60 requested (20 accept, 20 reject, 20 ignore), 25 idle ## 5 12 5 (4,4,4)
    # light: 25 requesters, 60 requested (20 accept, 20 reject, 20 ignore), 25 idle ## 5 12 5 (4,4,4)
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

    await asyncio.sleep(20)

    backend_relay_pods = [pod_name.split(".")[0] for pod_name in backend_relay_pods]
    backend_light_pods = [pod_name.split(".")[0] for pod_name in backend_light_pods]

    requesters = backend_relay_pods[:25] + backend_light_pods[:25]
    receiver_accept = backend_relay_pods[25:45] + backend_light_pods[25:45]
    receiver_reject = backend_relay_pods[45:65] + backend_light_pods[45:65]
    receiver_ignore = backend_relay_pods[65:85] + backend_light_pods[65:85]

    random.shuffle(requesters)
    random.shuffle(receiver_accept)
    random.shuffle(receiver_reject)

    logger.info("Sending friend requests")
    delays_accept = await send_friend_requests_util(light_nodes, requesters, receiver_accept, accept_friend_requests, 3, consumers)
    delays_reject = await send_friend_requests_util(light_nodes, requesters, receiver_reject, decline_friend_requests, 3, consumers)
    _ = await send_friend_requests_util(light_nodes, requesters, receiver_reject, None)

    logger.info(f"Accept delays ({len(delays_accept)}) are: {delays_accept}")
    logger.info(f"Reject delays ({len(delays_reject)})  are: {delays_reject}")

    await asyncio.sleep(10)

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()],
                         *[node.shutdown() for node in light_nodes.values()])
    logger.info("Finished contact_request")


async def send_one_to_one_message():
    # 50 sending nodes
    # 50 receiving nodes
    # 50 idle nodes
    # Each sending node has sent a contact request to a receiving node, that accepted it
    # -> Sending nodes send one text message per 10 sec
    kube_utils.setup_kubernetes_client()
    backend_relay_pods = kube_utils.get_pods("status-backend-relay", "status-go-test")
    relay_nodes = await initialize_nodes_application(backend_relay_pods)

    backend_relay_pods = [pod_name.split(".")[0] for pod_name in backend_relay_pods]

    senders = backend_relay_pods[:50]
    receiving = backend_relay_pods[50:100]

    friend_requests = await send_friend_requests(relay_nodes, senders, receiving)
    _ = await accept_friend_requests(relay_nodes, friend_requests)

    await asyncio.gather(*[inject_messages_one_to_one(relay_nodes[senders[i]], 10, relay_nodes[receiving[i]].public_key, 60) for i in range(50)])

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()])
    logger.info("Finished send_one_to_one_message")


async def create_private_group():
    # 10 admin nodes
    # 100 single-group members
    # Each admin node create a group and invite 10 single-group members in it, who accept the invite
    # single-group members accept the invite
    kube_utils.setup_kubernetes_client()
    backend_relay_pods = kube_utils.get_pods("status-backend-relay", "status-go-test")
    relay_nodes = await initialize_nodes_application(backend_relay_pods)

    backend_relay_pods = [pod_name.split(".")[0] for pod_name in backend_relay_pods]

    admin_nodes = backend_relay_pods[:10]
    members = backend_relay_pods[10:110]
    members_pub_keys = [relay_nodes[node].public_key for node in members]

    # In order to create a group, first they need to be friends
    friend_requests = await send_friend_requests(relay_nodes, admin_nodes, members)
    logger.info("Accepting friend requests")
    _ = await accept_friend_requests(relay_nodes, friend_requests)
    _ = await add_contacts(relay_nodes, admin_nodes, members)

    # 1 admin to 10 users, no overlap
    await asyncio.gather(*[create_group_chat(relay_nodes[admin], members_pub_keys[10*i: (10*i)+10]) for i, admin in enumerate(admin_nodes)])

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()])
    logger.info("Finished create_private_group")


async def send_group_message():
    # 10 admin nodes
    # 100 single-group members
    # Each admin node create a group and invite 10 single-group members in it, who accept the invite
    # -> Every member send a message in their group every 10 seconds
    kube_utils.setup_kubernetes_client()
    backend_relay_pods = kube_utils.get_pods("status-backend-relay", "status-go-test")
    relay_nodes = await initialize_nodes_application(backend_relay_pods)

    backend_relay_pods = [pod_name.split(".")[0] for pod_name in backend_relay_pods]

    admin_nodes = backend_relay_pods[:10]
    members = backend_relay_pods[10:110]
    members_pub_keys = [relay_nodes[node].public_key for node in members]

    # In order to create a group, first they need to be friends
    friend_requests = await send_friend_requests(relay_nodes, admin_nodes, members)
    logger.info("Accepting friend requests")
    _ = await accept_friend_requests(relay_nodes, friend_requests)
    _ = await add_contacts(relay_nodes, admin_nodes, members)

    # 1 admin to 10 users, no overlap
    group_ids = await asyncio.gather(*[create_group_chat(relay_nodes[admin], members_pub_keys[10*i: (10*i)+10]) for i, admin in enumerate(admin_nodes)])
    await asyncio.sleep(10)

    await asyncio.gather(*[
        inject_messages_group_chat(relay_nodes[member],
                                   delay_between_message=10,
                                   group_id=group_ids[i//10], # 10 first nodes to group 0, 10 to group 1, ...
                                   num_messages=10) for i, member in members
    ])


    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()])
    logger.info("Finished send_one_to_one_message")

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
from src.setup_status import request_join_nodes_to_community, login_nodes, accept_community_requests, \
    reject_community_requests

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


async def store_performance():
    # 1 publisher node
    # 1-2 service nodes
    # 200 light nodes
    # 200 relay nodes
    # One community setup
    # All relay and light nodes have joined the community
    # -> Only publisher and service nodes are up
    # -> publisher node publishes messages (they get stored in store), then stops
    # -> light and relay nodes go online
    # -> They automatically perform store queries
    # -> Measure time from start to time they get first query
    # -> Measure on wire store query performance
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

    chat_id_relays, chat_id_lights = await asyncio.gather(
        accept_community_requests(owner, joins_ids_relay),
        accept_community_requests(owner, join_ids_light),
    )

    await asyncio.gather(*[relay_nodes[node].logout() for node in nodes])
    await asyncio.gather(*[node.logout() for node in light_nodes.values()])

    await inject_messages(owner, 1, community_id + chat_id_relays, 30)

    await asyncio.gather(*[relay_nodes[node].login(relay_nodes[node].find_key_uid()) for node in nodes])
    await asyncio.gather(*[node.login(node.find_key_uid()) for node in light_nodes.values()])

    await asyncio.sleep(10) # Some time to receive signals

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()])
    await asyncio.gather(*[node.shutdown() for node in light_nodes.values()])
    logger.info("Finished store_performance")

async def message_sending():
    # 1 community owner
    # 500 users
    # all joined
    # -> 100 nodes send 1 message every 5s
    kube_utils.setup_kubernetes_client()
    backend_relay_pods = kube_utils.get_pods("status-backend-relay", "status-go-test")
    relay_nodes = await setup_status.initialize_nodes_application(backend_relay_pods)

    name = f"test_community_{''.join(random.choices(string.ascii_letters, k=10))}"
    logger.info(f"Creating community {name}")
    response = await relay_nodes["status-backend-relay-0"].wakuext_service.create_community(name)
    community_id = response.get("result", {}).get("communities", [{}])[0].get("id")
    logger.info(f"Community {name} created with ID {community_id}")

    owner = relay_nodes["status-backend-relay-0"]
    nodes = [key for key in relay_nodes.keys() if key != "status-backend-relay-0"]
    join_ids = await request_join_nodes_to_community(relay_nodes, nodes, community_id)
    chat_id = await accept_community_requests(owner, join_ids)

    await asyncio.gather(*[inject_messages(relay_nodes[node], 5, community_id+chat_id, 100) for node in nodes[:100]])

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()])
    logger.info("Finished store_performance")


async def request_to_join_community_mix():
    # 1 community owner
    # 500 user nodes
        # 200 joined
        # 300 didn't
    # -> 200/300 send request to owner
    # -> request each second or all at same time
    # -> accepts 100 and reject 100 from those 200
    kube_utils.setup_kubernetes_client()
    backend_relay_pods = kube_utils.get_pods("status-backend-relay", "status-go-test")
    relay_nodes = await setup_status.initialize_nodes_application(backend_relay_pods)

    name = f"test_community_{''.join(random.choices(string.ascii_letters, k=10))}"
    logger.info(f"Creating community {name}")
    response = relay_nodes["status-backend-relay-0"].wakuext_service.create_community(name)
    community_id = response.get("result", {}).get("communities", [{}])[0].get("id")
    logger.info(f"Community {name} created with ID {community_id}")

    owner = relay_nodes["status-backend-relay-0"]
    nodes = [key for key in relay_nodes.keys() if key != "status-backend-relay-0"]
    nodes_200 = nodes[:200]
    nodes_300 = nodes[200:]
    join_ids = await request_join_nodes_to_community(relay_nodes, nodes_200, community_id)
    _ = await accept_community_requests(owner, join_ids)

    join_ids = await request_join_nodes_to_community(relay_nodes, nodes_300[:200], community_id)
    _ = accept_community_requests(owner, join_ids[:100])
    await reject_community_requests(owner, join_ids[:100]) # TODO fails because can't find community?

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()])
    logger.info("Finished store_performance")


async def isolated_traffic_chat_messages_1():
    # 1 community owner
    # 500 user nodes
    # 250 in community
    # 1 -> community members send 1 message every 10s, measure volume
    # 2 -> stop members doesn't impact non-members traffic.
    # Measure non-joined nodes have minimal traffic not correlated to community traffic in 1 and 2
    kube_utils.setup_kubernetes_client()
    backend_relay_pods = kube_utils.get_pods("status-backend-relay", "status-go-test")
    relay_nodes = await setup_status.initialize_nodes_application(backend_relay_pods)

    name = f"test_community_{''.join(random.choices(string.ascii_letters, k=10))}"
    logger.info(f"Creating community {name}")
    response = await relay_nodes["status-backend-relay-0"].wakuext_service.create_community(name)
    community_id = response.get("result", {}).get("communities", [{}])[0].get("id")
    logger.info(f"Community {name} created with ID {community_id}")

    owner = relay_nodes["status-backend-relay-0"]
    nodes = [key for key in relay_nodes.keys() if key != "status-backend-relay-0"]
    nodes_250 = nodes[:250]
    join_ids = await request_join_nodes_to_community(relay_nodes, nodes_250, community_id)
    chat_id = await accept_community_requests(owner, join_ids)

    await inject_messages(owner, 10, community_id+chat_id, 30)
    await asyncio.sleep(10)
    await asyncio.gather(*[relay_nodes[node].logout() for node in nodes_250])

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()])
    logger.info("Finished store_performance")

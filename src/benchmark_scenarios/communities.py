# Python Imports
import asyncio
import logging

# Project Imports
import src.logger
from src import kube_utils
from src import setup_status
from src.benchmark_scenarios.scenario_utils import create_community_util
from src.enums import SignalType
from src.inject_messages import inject_messages
from src.setup_status import login_nodes, accept_community_requests, reject_community_requests

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

    await asyncio.sleep(10)
    status_nodes = {**relay_nodes, **light_nodes}
    community_owner = "status-backend-relay-0"
    nodes_to_join = [key for key in status_nodes.keys() if key != community_owner]

    community_setup_result = await create_community_util(status_nodes, community_owner, nodes_to_join, accept_community_requests)

    logger.info("Logging out light nodes")
    await asyncio.gather(*[node.logout(True) for node in light_nodes.values()])
    await asyncio.sleep(5)

    logger.info(f"Started injecting {30} messages")
    message_task = asyncio.create_task(
        inject_messages(status_nodes[community_owner], 1, community_setup_result.chat_id, 30))
    await asyncio.sleep(15)

    logger.info("Logging in light nodes")
    await login_nodes(light_nodes, list(light_nodes.keys()))

    await message_task
    await asyncio.sleep(30)

    messages = []
    for node in status_nodes.values():
        messages.append(len(node.signal.signal_queues[SignalType.MESSAGES_NEW.value].messages))
    logger.info(f"Messages received: {messages}")
    logger.info(len(set(messages)) == 1)

    times = []
    for light_node in light_nodes.values():
        times.append(
            light_node.signal.signal_queues[SignalType.MESSAGES_NEW.value].messages[0][0] - light_node.last_login)
    logger.info(f"Average time is {sum(times) / len(times)} seconds")
    logger.info(f"Times: {times}")

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in status_nodes.values()])
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

    await asyncio.sleep(10)
    status_nodes = {**relay_nodes, **light_nodes}
    community_owner = "status-backend-relay-0"
    nodes_to_join = [key for key in status_nodes.keys() if key != community_owner]

    community_setup_result = await create_community_util(status_nodes, community_owner, nodes_to_join, accept_community_requests)

    await asyncio.gather(*[status_nodes[node].logout() for node in nodes_to_join])

    await inject_messages(status_nodes[community_owner], 1, community_setup_result.chat_id, 30)

    await asyncio.sleep(20)

    await login_nodes(status_nodes, nodes_to_join)

    await asyncio.sleep(40)  # Some time to receive signals

    light_times = []
    relay_times = []

    for relay_node in relay_nodes.values():
        relay_times.append(
            relay_node.signal.signal_queues[SignalType.MESSAGES_NEW.value].messages[0][0] - relay_node.last_login)
    logger.info(f"Average relay time is {sum(relay_times) / len(relay_times)} seconds")
    logger.info(f"Relay Times: {relay_times}")
    for light_node in light_nodes.values():
        light_times.append(
            light_node.signal.signal_queues[SignalType.MESSAGES_NEW.value].messages[0][0] - light_node.last_login)
    logger.info(f"Average light time is {sum(light_times) / len(light_times)} seconds")
    logger.info(f"Light Times: {light_times}")

    relay_messages = []
    for relay_node in relay_nodes.values():
        relay_messages.append(len(relay_node.signal.signal_queues[SignalType.MESSAGES_NEW.value].messages))
    logger.info(f"Relay messages received: {relay_messages} for {len(relay_messages)} relay nodes")

    light_messages = []
    for light_node in light_nodes.values():
        light_messages.append(len(light_node.signal.signal_queues[SignalType.MESSAGES_NEW.value].messages))
    logger.info(f"Light messages received: {light_messages} for {len(light_messages)} light nodes")

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in status_nodes.values()])
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
    # Community members send 1 message every 10s, measure volume
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

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()])
    logger.info("Finished store_performance")


async def isolated_traffic_chat_messages_2():
    # 1 community owner
    # 500 user nodes
    # 250 in community
    # Stopping members shouldn't impact non-members traffic.
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

    await asyncio.sleep(10)
    await asyncio.gather(*[relay_nodes[node].logout() for node in nodes_250])
    await asyncio.sleep(10)

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()])
    logger.info("Finished store_performance")

async def isolated_traffic_request_to_join():
    # 1 community owner
    # 500 user nodes
    # 250 in community
    # Measure non-joined nodes have minimal traffic not correlated to community request traffic
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

    logger.info("Shutting down node connections")
    await asyncio.gather(*[node.shutdown() for node in relay_nodes.values()])
    logger.info("Finished store_performance")

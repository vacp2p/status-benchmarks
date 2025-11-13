# Python Imports
import asyncio
import os
import logging

import src.logger
from src.benchmark_scenarios.communities import store_performance, message_sending, request_to_join_community_mix, \
    isolated_traffic_chat_messages_1, subscription_performance, isolated_traffic_request_to_join, \
    isolated_traffic_chat_messages_2
from src.benchmark_scenarios.meeting import test_function
from src.benchmark_scenarios.private_chats import idle_relay, idle_light, create_private_group, contact_request, \
    send_one_to_one_message, send_group_message
from src.codex.test import codex_test

# os.environ['KUBERNETES_SERVICE_HOST'] = '10.43.0.1'
os.environ['KUBERNETES_SERVICE_HOST'] = '10.96.0.1' # local k8s
os.environ['KUBERNETES_SERVICE_PORT'] = '443'
os.environ['KUBERNETES_SERVICE_ACCOUNT_TOKEN_PATH'] = '/var/run/secrets/kubernetes.io/serviceaccount/token'
os.environ['KUBERNETES_SERVICE_ACCOUNT_CA_CERT_PATH'] = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'


logger = logging.getLogger(__name__)


if __name__ == "__main__":
    asyncio.run(codex_test())

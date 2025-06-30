# Python Imports
import kubernetes
import logging
from kubernetes.client import ApiException
from typing import List

# Project Imports

logger = logging.getLogger(__name__)


def setup_kubernetes_client():
    logger.info("Setting up Kubernetes client")

    try:
        kubernetes.config.load_incluster_config()
        logger.debug("Loaded in-cluster Kubernetes configuration")
    except kubernetes.config.config_exception.ConfigException:
        try:
            kubernetes.config.load_kube_config()
            logger.info("Loaded kubeconfig configuration")
        except kubernetes.config.config_exception.ConfigException:
            logger.error("Could not configure Kubernetes client")
            raise RuntimeError("Failed to configure Kubernetes client. Are you running inside Kubernetes or have a valid kubeconfig?")


def get_pods(name: str, namespace: str) -> List[str]:
    pods = []

    try:
        statefulset = kubernetes.client.AppsV1Api().read_namespaced_stateful_set(
            name=name,
            namespace=namespace
        )
        replicas = statefulset.status.replicas
        for replica in range(replicas):
            pods.append(f"{name}-{replica}.{name}.{namespace}")
        logger.info(f"Found {replicas} pods with name {name} in namespace {namespace}")
    except ApiException as e:
        logger.error(f"Failed to get pods: {e}")
        raise

    return pods

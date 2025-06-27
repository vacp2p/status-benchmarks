#!/bin/bash
#
# Deployer tool for status-go-test
# Deploys the Anvil/geth service and SNT contracts and prepares the environment for running status-backend
KUBECONFIG="$HOME/.kube/sapphire.yaml"
cd "$(dirname "$0")"

# Deploy the Anvil service
kubectl --kubeconfig $KUBECONFIG apply -f anvil-service.yaml

# Deploy the Anvil statefulset
kubectl --kubeconfig $KUBECONFIG apply -f anvil-statefulset.yaml

# Deploy secret + configmap
kubectl --kubeconfig $KUBECONFIG apply -f snt-configmap-and-secret.yaml

# Check for liveness of Anvil statefulset before deploying contracts
kubectl --kubeconfig $KUBECONFIG wait --for=condition=ready pod -l app=anvil --timeout=60s --namespace=status-go-test

# Deploy SNT contracts
kubectl --kubeconfig $KUBECONFIG apply -f snt-contract-deployment.yaml

# Deploy Communities contracts
kubectl --kubeconfig $KUBECONFIG apply -f snt-communities-deployment.yaml

# Wait and delete pods that finished their task
sleep 10

kubectl --kubeconfig $KUBECONFIG wait --for=condition=ready pod -l app=deploy-sntv2 --timeout=60s --namespace=status-go-test
kubectl --kubeconfig $KUBECONFIG wait --for=condition=ready pod -l app=deploy-communities-contracts --timeout=60s --namespace=status-go-test

kubectl --kubeconfig $KUBECONFIG delete -f snt-contract-deployment.yaml
kubectl --kubeconfig $KUBECONFIG delete -f snt-communities-deployment.yaml

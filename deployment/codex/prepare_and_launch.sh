#!/usr/bin/env bash
set -e

namespace="status-go-test"
if ! kubectl get namespace "$namespace" >/dev/null 2>&1; then
  echo "Namespace '$namespace' does not exist. Creating it..."
  kubectl create namespace "$namespace"
else
  echo "Namespace '$namespace' already exists."
fi


./deploy_codex_local.sh

# Get the controlbox pod name dynamically
controlbox_name=$(kubectl get pods -n "$namespace" | grep controlbox | awk '{print $1}' | head -n 1)

echo "Using control box: $controlbox_name"

# Create the target directory inside the pod
kubectl exec -n "$namespace" "$controlbox_name" -- mkdir -p /home/code/

# Copy your local 'src' directory into the pod
kubectl cp ../../src/ "$namespace/$controlbox_name:/home/code/"
kubectl cp ../../main.py "$namespace/$controlbox_name:/home/code/"
kubectl cp ../../requirements.txt "$namespace/$controlbox_name:/home/code/"

# Create a Python venv (installs python3-venv if missing)
kubectl exec -n "$namespace" "$controlbox_name" -- bash -c "
    apt-get update -qq && apt-get install -y -qq python3-venv &&
    python3 -m venv /home/venv &&
    source /home/venv/bin/activate &&
    pip install --upgrade pip &&
    pip install -r /home/code/requirements.txt
"

# Run the script
kubectl exec -n "$namespace" "$controlbox_name" -- bash -c "
    source /home/venv/bin/activate &&
    cd /home/code &&
    python main.py
"


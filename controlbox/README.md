# Controlbox

In order to easy access the status-desktop nodes with requests like:
```
base_url = f"http://{pod}:3333/statusgo/CallRPC"

response = requests.post(base_url, json={
        "jsonrpc": "2.0",
        "method": "wakuext_fetchCommunity",
        "params": [{
            "communityKey": community_id,
            "waitForResponse": True,
            "tryDatabase": True
        }],
        "id": 1
    })
```

We will create a pod inside the namespace. Scripts will be run from inside the cluster,
having easier access to all nodes addresses. Also, this can be port-forwarded so you can
still work from your IDE, setting up breakpoints and exploring variables.

This was the most comfortable/fastest approach to being able to concurrently interact
with a big number of nodes.

## Building
```
docker build -t controlbox .
```

Make sure you put your GitHub handle in the following line inside the Dockerfile:
```
RUN wget https://github.com/<your_github_handle>.keys -O /root/.ssh/authorized_keys \
    && chmod 600 /root/.ssh/authorized_keys
```

## Running
Apply the controlbox.yaml file to your Kubernetes cluster.

## Connecting to the Controlbox
Create a port forward to the controlbox pod on port 2222 -> 22, then:
```
ssh -p 2222 root@<controlbox-ip>
```

Alternatively (useful for scripts that need Kubernetes env vars) use k9s to shell into the pod.

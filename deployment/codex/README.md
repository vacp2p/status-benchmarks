## Install docker-desktop

Make sure docker-desktop is installed on your machine with the Kubernetes extension.

## Build controlbox

Controlbox is a pod (single container) that will run inside the K8s cluster to run the python scripts that will
control the scenario. The docker image needs to be build with the ssh keys of the person that will
connect to the controlbox pod.

In order to do this, go to `controlbox` folder:
- Substitute `<your_github_handle>` with the handle of the user.
    - These keys will be later used to ssh in the pod.
- Build the image.
- Make sure to use that image in `deployment/codex/controlbox_codex.yaml`

There is a bit more of information in the `controlbox/README.md` file.

## Deploy everything

You just need to run `./prepare_and_launch.sh`
This will create the K8s namespace, then `deploy_codex_local.sh` will deploy:
- Anvil, SNT contracts, services and everything that can be needed for more complex scenarios
- Controlbox pod
- K8s services
- Nwaku bootstrap node
- Nwaku store node
- Status-codex nodes (without being initialized)
  - You can modify how many nodes you want to deploy in the replicas field in `status-backend-relay-codex.yaml`

After this, the code will be copied to the controlbox pod and the python scripts will be executed.

Editing and rerunning process is much faster and easier if you create an ssh venv from your IDE. Pycharm licensed supports this. I guess
this can also be done with vscode. The only thing you need to do is enable the port forward, and the IDE should let you
transfer the files to the controlbox, and create the venv. I am explaining here the slow-safe approach just in case.

There are other tools that also makes this process faster and easier (K9s to check logs, do portforwarding, etc.)
But again, didn't want to introduce too many new dependencies.

## Extra information

Status nodes are connecting automatically to the waku bootstrap node and waku store node.
This process behaves like:
- We deploy bootstrap and store nodes
  - We wait for them to be ready
- We deploy status nodes
  - In the status deployment yaml, there is an init container that will fetch the ENRs from the bootstrap node and store node.
  - This information will be used in another init container, that is in charge of creating the fleet config file for status
    - This script can be found in `docker-utils/status-init/init_container.py`
  - In this way, every status node will be connected to the bootstrap and store nodes, and the discovery process between
status nodes will be automatic.
- Nodes are ready to be used. and the initialization, message publishing and the rest of the cheks are done in a python script.

Logging can be adjusted in `src/logger_config.yaml` if needed.
Waku store configuration is in `deployment/codex/status-service-node-codex.yaml`
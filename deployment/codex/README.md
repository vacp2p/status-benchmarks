## Install docker-desktop

Make sure docker-desktop is installed on your machine with the Kubernetes extension.

## Build controlbox

Controlbox is a pod (single container) that will run inside the cluster to run the python scripts that will
control the scenario. The docker image needs to be build with the ssh keys of the person that will
connect to the controlbox pod.

In order to do this, go to `controlbox` folder:
- Substitute `<your_github_handle>` with the handle of the used.
    - These keys will be later used to ssh in the pod.
- Build the image.
- Make sure to use that image in `deployment/codex/controlbox_codex.yaml`

There is a bit more of information in the `controlbox/README.md` file.

## Deploy everything

`deploy_codex_local.sh` will deploy:
- Anvil, SNT contracts, services and everything that can be needed for more complex scenarios
- Controlbox pod
- K8s services
- Nwaku bootstrap node
- Nwaku store node
- Status-codex nodes (without being initialized)
  - You can modify how many nodes you want to deploy in the replicas field in `status-backend-relay-codex.yaml`

Note that if you want to repeat the deployment, you just need to run `cleanup_local.sh` and `deploy_codex_local.sh` again.
If the cluster still has anvil and controlbox, there are things you need to comment in `deploy_codex_local.sh`.
Those deployments are only needed on a fresh cluster.

## Upload code to controlbox and execute

Run `./prepare_and_launch.sh`

Editing and rerunning process is much faster and easier if you create an ssh venv from your IDE. Pycharm licensed supports this. I guess
this can also be done with vscode. The only thing you need to do is enable the port forward, and the IDE should let you
transfer the files to the controlbox, and create the venv. I am explaining here the slow-safe approach just in case.

There are other tools that also makes this process faster and easier (K9s to check logs, do portforwarding, etc.)
But again, didn't want to introduce too many new dependencies.
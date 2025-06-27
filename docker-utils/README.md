# Docker-utils

Containers that will be needed for the experiments.

## status-init

This container is in charge of preparing `/static/configs/config.json` file for `status-backend`.
It will grab the ENR of the store nodes that will also act as bootstrap, and put it in the json file.

## status-subscriber

Simple container that will connect to `status-backend` signal to log information.


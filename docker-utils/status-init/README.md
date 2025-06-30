# status-init

This container is in charge of preparing `/static/configs/config.json` file for `status-backend`.
It will grab the env variables of BOOT_ENRS and STORE_ENRS (bootstrap and store nodes) and put them it in the configuration.

## Changelog

- v1.0.0
  - Working with status-backend `b22c58bd3bdd4a387dc09dccba1d866d5ae09adf`

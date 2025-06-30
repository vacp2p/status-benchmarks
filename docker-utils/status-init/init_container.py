import json
import os
import sys
import logging
from pathlib import Path


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def update_config():
    bootstrap_enrs = [
        os.getenv(env)
        for env in os.environ
        if env.startswith("BOOT_ENRS") and os.getenv(env).startswith("enr:")
    ]

    store_enrs = [
        os.getenv(env)
        for env in os.environ
        if env.startswith("STORE_ENRS") and os.getenv(env).startswith("enr:")
    ]

    config_path = os.getenv("CONFIG_PATH", "/static/configs/config.json")

    try:
        config_dir = Path(config_path).parent
        config_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured config folder exists at: {config_dir}")

        config = {
            "dst.dev": {
                "wakuNodes": bootstrap_enrs,
                "discV5BootstrapNodes": [],
                "clusterId": int(os.getenv("CLUSTER_ID", 16)),
                "storeNodes": []
            }
        }

        for counter, enr in enumerate(store_enrs):
            config["dst.dev"]["storeNodes"].append({
                "id": f"store-node-{counter}",
                "enr": enr,
                "addr": "",
                "fleet": "dst.dev"
            })

        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        logger.info(f"Configuration successfully written to {config_path}")

    except Exception as e:
        logger.error(f"Failed to update config: {e}", exc_info=True)
        sys.exit(1)


def main():
    update_config()


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import os
import threading
import webbrowser
from pathlib import Path
from typing import Sequence

import uvicorn

from .app import create_app
from .config import default_config_path, load_config
from .obs_gateway import ObsWebSocketGateway, SimulatedObsGateway


def _arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the T&V HDMI Floor Box Controller")
    parser.add_argument("--config", type=Path, help="Path to room configuration JSON")
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run without OBS for UI review and operator training",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the controller in the default browser after startup",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> None:
    options = _arguments(arguments)
    config_path = options.config.resolve() if options.config else default_config_path()
    config = load_config(config_path)
    simulate = options.simulate or os.getenv("TV_CONTROLLER_SIMULATE") == "1"
    gateway = SimulatedObsGateway() if simulate else ObsWebSocketGateway(config.obs)

    if options.open_browser:
        url = f"http://{config.server.host}:{config.server.port}"
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(
        create_app(config, gateway, config_path),
        host=config.server.host,
        port=config.server.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()

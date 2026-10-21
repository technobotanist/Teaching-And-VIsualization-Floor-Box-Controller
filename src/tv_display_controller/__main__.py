from __future__ import annotations

import argparse
import errno
import json
import os
import threading
import webbrowser
from pathlib import Path
from typing import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener

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


def _reuse_running_controller(url: str, config_path: Path, simulate: bool) -> bool:
    try:
        # Local controller traffic must not go through a machine's HTTP proxy.
        with build_opener(ProxyHandler({})).open(
            f"{url}/api/v1/instance", timeout=3
        ) as response:
            instance = json.load(response)
    except HTTPError as error:
        raise RuntimeError(
            f"Another server is using {url}. Stop it before starting this controller."
        ) from error
    except URLError as error:
        if isinstance(error.reason, OSError) and (
            error.reason.errno == errno.ECONNREFUSED
            or getattr(error.reason, "winerror", None) == 10061
        ):
            return False
        raise RuntimeError(f"Could not check the controller at {url}: {error}") from error
    except (ValueError, TimeoutError) as error:
        raise RuntimeError(f"The server at {url} did not return a valid controller response.") from error

    if not isinstance(instance, dict) or instance.get("application") != "tv-display-controller":
        raise RuntimeError(f"Another server is using {url}. Stop it before starting this controller.")
    existing_path = instance.get("config_path")
    if (
        not isinstance(existing_path, str)
        or Path(existing_path).resolve() != config_path.resolve()
        or instance.get("simulation") is not simulate
    ):
        raise RuntimeError(
            f"A controller with a different configuration or simulation setting is running at {url}. "
            "Stop it with Ctrl+C in its server window, then launch again."
        )
    return True


def main(arguments: Sequence[str] | None = None) -> None:
    options = _arguments(arguments)
    config_path = options.config.resolve() if options.config else default_config_path()
    config = load_config(config_path)
    simulate = options.simulate or os.getenv("TV_CONTROLLER_SIMULATE") == "1"
    url = f"http://{config.server.host}:{config.server.port}"
    if _reuse_running_controller(url, config_path, simulate):
        print(f"Controller already running at {url}")
        if options.open_browser:
            webbrowser.open(url)
        return

    gateway = SimulatedObsGateway() if simulate else ObsWebSocketGateway(config.obs)

    if options.open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(
        create_app(config, gateway, config_path),
        host=config.server.host,
        port=config.server.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import platform
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict
from functools import lru_cache
from typing import Any

from .config import (
    CUSTOM_SLOT_SCENE_NAMES,
    FLOOR_BOX_SOURCE_NAMES,
    ControllerConfig,
    ProjectorConfig,
)
from .config_store import ConfigStore
from .display_identifier import show_display_identifier
from .obs_gateway import ObsCommissioningData, ObsGateway, ObsGatewayError


EXPECTED_PROFILE = "T&V Display System"
EXPECTED_SCENE_COLLECTION = "T&V Production"
EXPECTED_INPUTS = [*FLOOR_BOX_SOURCE_NAMES, "SERVER_DESKTOP"]


def _check(
    check_id: str,
    label: str,
    passed: bool,
    detail: str,
    severity: str = "required",
) -> dict[str, object]:
    return {
        "id": check_id,
        "label": label,
        "status": "pass" if passed else ("warn" if severity == "advisory" else "fail"),
        "detail": detail,
    }


def _powershell_json(command: str) -> Any:
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
        timeout=12,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = completed.stdout.strip()
    return json.loads(output) if output else []


@lru_cache(maxsize=1)
def collect_system_summary() -> dict[str, object]:
    summary: dict[str, object] = {
        "computer_name": platform.node(),
        "windows": platform.platform(),
        "python": sys.version.split()[0],
        "gpus": [],
        "monitor_devices": [],
        "media_devices": [],
        "inventory_error": None,
    }
    if sys.platform != "win32":
        summary["inventory_error"] = "Detailed hardware inventory is available on Windows only"
        return summary

    command = """
$inventory = [ordered]@{
  gpus = @(Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, Status)
  monitors = @(Get-CimInstance Win32_PnPEntity | Where-Object PNPClass -eq 'Monitor' | Select-Object Name, Manufacturer, Status)
  media = @(Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPClass -in @('Camera','MEDIA') -or $_.Name -match 'capture|video input' } | Select-Object PNPClass, Name, Manufacturer, Status)
}
$inventory | ConvertTo-Json -Depth 4 -Compress
"""
    try:
        inventory = _powershell_json(command)
        summary["gpus"] = inventory.get("gpus", [])
        summary["monitor_devices"] = inventory.get("monitors", [])
        summary["media_devices"] = inventory.get("media", [])
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        summary["inventory_error"] = f"Hardware inventory failed: {type(error).__name__}"
    return summary


class CommissioningService:
    def __init__(
        self,
        store: ConfigStore,
        gateway: ObsGateway,
        display_identifier: Callable[[str, int, dict[str, object]], None] | None = None,
    ) -> None:
        self._store = store
        self._gateway = gateway
        self._display_identifier = display_identifier or show_display_identifier

    def snapshot(self) -> dict[str, object]:
        config = self._store.current()
        try:
            obs_data = self._gateway.commissioning_data()
            obs_payload: dict[str, object] = asdict(obs_data)
            checks = self._checks(config, obs_data)
            obs_error = None
        except ObsGatewayError as error:
            obs_payload = {}
            checks = [
                _check("obs-connection", "OBS WebSocket", False, str(error))
            ]
            obs_error = str(error)

        projectors = [
            {
                **projector.model_dump(),
                "ready": projector.monitor_index is not None,
            }
            for projector in config.outputs.projectors
        ]
        passed_required = all(check["status"] == "pass" for check in checks)
        return {
            "system": collect_system_summary(),
            "obs": obs_payload,
            "obs_error": obs_error,
            "checks": checks,
            "obs_contract_ready": passed_required and not obs_payload.get("simulation", False),
            "projectors": projectors,
            "commissioned_count": sum(projector.enabled for projector in config.outputs.projectors),
            "auto_open": config.outputs.auto_open,
        }

    def refresh_inventory(self) -> dict[str, object]:
        collect_system_summary.cache_clear()
        return self.snapshot()

    def assign_projector(
        self,
        projector_id: str,
        monitor_index: int | None,
        enabled: bool,
    ) -> ControllerConfig:
        return self._store.assign_projector(projector_id, monitor_index, enabled)

    def test_projector(self, projector_id: str) -> None:
        config = self._store.current()
        projector = next(
            (candidate for candidate in config.outputs.projectors if candidate.id == projector_id),
            None,
        )
        if projector is None:
            raise ValueError(f"Unknown projector '{projector_id}'")
        if projector.monitor_index is None:
            raise ValueError(f"{projector.label} requires a monitor assignment before testing")
        test_projector = projector.model_copy(update={"enabled": True})
        self._gateway.open_projectors([test_projector])

    def identify_projector(self, projector_id: str) -> None:
        config = self._store.current()
        projector = next(
            (candidate for candidate in config.outputs.projectors if candidate.id == projector_id),
            None,
        )
        if projector is None:
            raise ValueError(f"Unknown projector '{projector_id}'")
        if projector.monitor_index is None:
            raise ValueError(f"{projector.label} requires a monitor assignment before identification")
        obs_data = self._gateway.commissioning_data()
        monitor = next(
            (
                candidate
                for candidate in obs_data.monitors
                if candidate.get("index") == projector.monitor_index
            ),
            None,
        )
        if monitor is None:
            raise ValueError(
                f"OBS monitor index {projector.monitor_index} is no longer available"
            )
        self._display_identifier(
            projector.id.upper(),
            projector.monitor_index,
            monitor,
        )

    @staticmethod
    def _checks(
        config: ControllerConfig,
        obs_data: ObsCommissioningData,
    ) -> list[dict[str, object]]:
        required_scenes = {
            *(mode.scene for mode in config.modes if mode.enabled),
            config.outputs.router_scene,
            *(projector.source_name for projector in config.outputs.projectors),
            *CUSTOM_SLOT_SCENE_NAMES,
        }
        required_scenes.discard(None)
        missing_scenes = sorted(required_scenes - set(obs_data.scenes))
        missing_inputs = sorted(set(EXPECTED_INPUTS) - set(obs_data.inputs))
        expected_fps = config.room.fps
        return [
            _check(
                "live-obs",
                "Production OBS connection",
                not obs_data.simulation,
                "Live OBS WebSocket session"
                if not obs_data.simulation
                else "Simulation data only; restart without --simulate",
            ),
            _check(
                "profile",
                "OBS profile",
                obs_data.profile_name == EXPECTED_PROFILE,
                f"Current: {obs_data.profile_name}",
            ),
            _check(
                "scene-collection",
                "Scene collection",
                obs_data.scene_collection_name == EXPECTED_SCENE_COLLECTION,
                f"Current: {obs_data.scene_collection_name}",
            ),
            _check(
                "canvas",
                "Panoramic canvas",
                obs_data.base_width == config.room.canvas_width
                and obs_data.base_height == config.room.canvas_height,
                f"Current: {obs_data.base_width} x {obs_data.base_height}",
            ),
            _check(
                "fps",
                "Frame rate",
                abs(obs_data.fps - expected_fps) < 0.02,
                f"Current: {obs_data.fps:.2f} FPS",
            ),
            _check(
                "scenes",
                "Required scenes",
                not missing_scenes,
                "Complete" if not missing_scenes else f"Missing: {', '.join(missing_scenes)}",
            ),
            _check(
                "inputs",
                "Floor-box sources",
                not missing_inputs,
                "FB_01 through FB_08 and SERVER_DESKTOP found"
                if not missing_inputs
                else f"Missing: {', '.join(missing_inputs)}",
            ),
            _check(
                "monitors",
                (
                    "Blended display discovery"
                    if config.outputs.topology == "single-program"
                    else "OBS monitor discovery"
                ),
                len(obs_data.monitors) >= len(config.outputs.projectors),
                f"{len(obs_data.monitors)} display(s) visible to OBS",
            ),
        ]

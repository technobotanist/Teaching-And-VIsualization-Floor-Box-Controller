from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Callable

from .config import ControllerConfig, ModeConfig
from .obs_gateway import ObsGateway, ObsGatewayError, ObsStatus


class ModeNotFoundError(LookupError):
    pass


class ModeDisabledError(RuntimeError):
    pass


@dataclass(frozen=True)
class ControllerStatus:
    obs: ObsStatus
    active_mode_id: str | None
    outputs_opened: bool
    commissioned_output_count: int


class DisplayController:
    def __init__(
        self,
        config: ControllerConfig,
        gateway: ObsGateway,
        open_editor: Callable[[], bool | None] | None = None,
    ) -> None:
        self.config = config
        self._gateway = gateway
        self._open_editor = open_editor or (lambda: False)
        self._lock = RLock()
        self._outputs_opened = False

    def replace_config(
        self,
        config: ControllerConfig,
        reset_outputs: bool = True,
    ) -> None:
        with self._lock:
            self.config = config
            if reset_outputs:
                self._outputs_opened = False

    def _mode(self, mode_id: str) -> ModeConfig:
        mode = next((candidate for candidate in self.config.modes if candidate.id == mode_id), None)
        if mode is None:
            raise ModeNotFoundError(f"Unknown room mode '{mode_id}'")
        if not mode.enabled:
            raise ModeDisabledError(f"Room mode '{mode_id}' is disabled")
        return mode

    def _mode_for_scene(self, scene_name: str | None) -> ModeConfig | None:
        return next(
            (mode for mode in self.config.modes if mode.scene == scene_name),
            None,
        )

    def status(self) -> ControllerStatus:
        with self._lock:
            obs_status = self._gateway.status()
            active_mode = self._mode_for_scene(obs_status.current_scene)
            commissioned_count = sum(
                projector.enabled for projector in self.config.outputs.projectors
            )
            return ControllerStatus(
                obs=obs_status,
                active_mode_id=active_mode.id if active_mode else None,
                outputs_opened=self._outputs_opened,
                commissioned_output_count=commissioned_count,
            )

    def activate(self, mode_id: str) -> ControllerStatus:
        with self._lock:
            mode = self._mode(mode_id)
            if mode.kind == "custom":
                self._gateway.configure_custom_routing(
                    self.config.custom_routing.assignments
                )
            commissioned = [
                projector
                for projector in self.config.outputs.projectors
                if projector.enabled
            ]
            router_scene_names = (
                [self.config.outputs.router_scene]
                if commissioned and self.config.outputs.router_scene
                else []
            )
            route_source_names = [
                candidate.routing_source
                for candidate in self.config.modes
                if candidate.enabled
            ]
            self._gateway.activate_mode(
                mode.scene,
                mode.routing_source,
                router_scene_names,
                route_source_names,
            )

            if self.config.outputs.auto_open and not self._outputs_opened:
                self.open_outputs()

            return self.status()

    def open_outputs(self, force: bool = False) -> ControllerStatus:
        with self._lock:
            if force or not self._outputs_opened:
                commissioned = [
                    projector
                    for projector in self.config.outputs.projectors
                    if projector.enabled
                ]
                if commissioned:
                    self._gateway.open_projectors(commissioned)
                    self._outputs_opened = True
            return self.status()

    def focus_editor(self) -> bool:
        with self._lock:
            return bool(self._open_editor())

    def monitor_names(self) -> list[str]:
        with self._lock:
            return self._gateway.monitor_names()

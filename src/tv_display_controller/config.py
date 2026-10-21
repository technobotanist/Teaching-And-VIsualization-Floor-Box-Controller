from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PROJECTOR_IDS = tuple(f"p{number}" for number in range(1, 9))
FLOOR_BOX_SOURCE_NAMES = tuple(f"FB_{number:02d}" for number in range(1, 9))
CUSTOM_SLOT_SCENE_NAMES = tuple(
    f"CUSTOM_SLOT_P{number}" for number in range(1, 9)
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoomInfo(StrictModel):
    name: str
    site: str
    canvas_width: int = Field(gt=0)
    canvas_height: int = Field(gt=0)
    fps: int = Field(gt=0, le=120)


class ServerSettings(StrictModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)


class ObsSettings(StrictModel):
    host: str = "127.0.0.1"
    port: int = Field(default=4455, ge=1, le=65535)
    password_environment_variable: str = "OBS_WEBSOCKET_PASSWORD"
    timeout_seconds: float = Field(default=3.0, gt=0, le=30)


class ModeConfig(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    label: str
    key: str
    scene: str
    route_source: str | None = None
    detail: str
    kind: Literal["layout", "blank", "custom"] = "layout"
    enabled: bool = True

    @property
    def routing_source(self) -> str:
        return self.route_source or self.scene


class ProjectorConfig(StrictModel):
    id: str = Field(pattern=r"^p[1-8]$")
    label: str
    kind: Literal["source", "program"] = "source"
    source_name: str | None = None
    monitor_index: int | None = Field(default=None, ge=0)
    enabled: bool = False

    @model_validator(mode="after")
    def source_projector_has_source(self) -> ProjectorConfig:
        if self.kind == "source" and not self.source_name:
            raise ValueError("source_name is required for a source projector")
        return self


class OutputSettings(StrictModel):
    topology: Literal["single-program", "eight-source-projectors"]
    router_scene: str | None = None
    auto_open: bool = False
    projectors: list[ProjectorConfig]

    @model_validator(mode="after")
    def enabled_projectors_are_commissioned(self) -> OutputSettings:
        has_enabled_source = any(
            projector.enabled and projector.kind == "source"
            for projector in self.projectors
        )
        if has_enabled_source and not self.router_scene:
            raise ValueError("router_scene is required for enabled source projectors")
        for projector in self.projectors:
            if projector.enabled and projector.monitor_index is None:
                raise ValueError(
                    f"{projector.id} requires a verified monitor_index before it can be enabled"
                )
        assigned_indexes = [
            projector.monitor_index
            for projector in self.projectors
            if projector.monitor_index is not None
        ]
        if len(assigned_indexes) != len(set(assigned_indexes)):
            raise ValueError("projector monitor indexes must be unique")
        return self


class CustomRoutingConfig(StrictModel):
    assignments: dict[str, str | None]

    @model_validator(mode="after")
    def assignments_cover_projector_slots(self) -> CustomRoutingConfig:
        assignment_ids = set(self.assignments)
        expected_ids = set(PROJECTOR_IDS)
        if assignment_ids != expected_ids:
            raise ValueError("custom routing must assign p1 through p8")

        invalid_sources = sorted(
            source_name
            for source_name in self.assignments.values()
            if source_name is not None and source_name not in FLOOR_BOX_SOURCE_NAMES
        )
        if invalid_sources:
            raise ValueError(
                f"unknown custom routing source '{invalid_sources[0]}'"
            )
        return self


class ControllerConfig(StrictModel):
    room: RoomInfo
    server: ServerSettings
    obs: ObsSettings
    outputs: OutputSettings
    custom_routing: CustomRoutingConfig
    modes: list[ModeConfig]

    @model_validator(mode="after")
    def identifiers_are_unique(self) -> ControllerConfig:
        mode_ids = [mode.id for mode in self.modes]
        if len(mode_ids) != len(set(mode_ids)):
            raise ValueError("mode ids must be unique")

        scenes = [mode.scene for mode in self.modes]
        if len(scenes) != len(set(scenes)):
            raise ValueError("mode scenes must be unique")

        projector_ids = [projector.id for projector in self.outputs.projectors]
        if len(projector_ids) != len(set(projector_ids)):
            raise ValueError("projector ids must be unique")
        return self


def default_config_path() -> Path:
    configured_path = os.getenv("TV_CONTROLLER_CONFIG")
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "config" / "room.json"


def load_config(path: Path | None = None) -> ControllerConfig:
    config_path = path or default_config_path()
    return ControllerConfig.model_validate_json(config_path.read_text(encoding="utf-8"))

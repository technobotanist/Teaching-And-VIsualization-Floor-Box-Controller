from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import obsws_python as obs

from .config import (
    CUSTOM_SLOT_SCENE_NAMES,
    FLOOR_BOX_SOURCE_NAMES,
    PROJECTOR_IDS,
    ObsSettings,
    ProjectorConfig,
)


class ObsGatewayError(RuntimeError):
    pass


@dataclass(frozen=True)
class ObsStatus:
    connected: bool
    current_scene: str | None
    obs_version: str | None
    message: str


@dataclass(frozen=True)
class ObsCommissioningData:
    simulation: bool
    profile_name: str
    scene_collection_name: str
    base_width: int
    base_height: int
    output_width: int
    output_height: int
    fps: float
    scenes: list[str]
    inputs: list[str]
    monitors: list[dict[str, object]]
    stats: dict[str, float | int]


class ObsGateway(Protocol):
    def status(self) -> ObsStatus: ...

    def activate_mode(
        self,
        scene_name: str,
        route_source_name: str,
        router_scene_names: list[str],
        all_route_source_names: list[str],
    ) -> None: ...

    def configure_custom_routing(
        self,
        assignments: dict[str, str | None],
    ) -> None: ...

    def open_projectors(self, projectors: list[ProjectorConfig]) -> None: ...

    def monitor_names(self) -> list[str]: ...

    def commissioning_data(self) -> ObsCommissioningData: ...


class ObsWebSocketGateway:
    def __init__(self, settings: ObsSettings) -> None:
        self._settings = settings
        self._client: obs.ReqClient | None = None
        self._route_item_ids: dict[tuple[str, str], int] = {}
        self._active_route_source: str | None = None
        self._custom_assignments: dict[str, str | None] = {}

    def _connect(self) -> obs.ReqClient:
        if self._client is not None:
            return self._client

        password = os.getenv(self._settings.password_environment_variable, "")
        try:
            self._client = obs.ReqClient(
                host=self._settings.host,
                port=self._settings.port,
                password=password,
                timeout=self._settings.timeout_seconds,
            )
        except Exception as error:
            raise ObsGatewayError("OBS WebSocket is unavailable") from error
        return self._client

    def _reset(self) -> None:
        self._client = None
        self._route_item_ids.clear()
        self._active_route_source = None
        self._custom_assignments.clear()

    def status(self) -> ObsStatus:
        try:
            client = self._connect()
            version = client.get_version()
            scene = client.get_current_program_scene()
            return ObsStatus(
                connected=True,
                current_scene=scene.current_program_scene_name,
                obs_version=version.obs_version,
                message="OBS connected",
            )
        except Exception:
            self._reset()
            return ObsStatus(
                connected=False,
                current_scene=None,
                obs_version=None,
                message="OBS is not connected",
            )

    def _route_item_id(
        self,
        client: obs.ReqClient,
        router_scene_name: str,
        route_source_name: str,
    ) -> int:
        cache_key = (router_scene_name, route_source_name)
        if cache_key not in self._route_item_ids:
            response = client.get_scene_item_id(router_scene_name, route_source_name)
            self._route_item_ids[cache_key] = response.scene_item_id
        return self._route_item_ids[cache_key]

    def activate_mode(
        self,
        scene_name: str,
        route_source_name: str,
        router_scene_names: list[str],
        all_route_source_names: list[str],
    ) -> None:
        try:
            client = self._connect()
            previous_route = self._active_route_source

            for router_scene_name in router_scene_names:
                target_item_id = self._route_item_id(
                    client,
                    router_scene_name,
                    route_source_name,
                )
                client.set_scene_item_enabled(router_scene_name, target_item_id, True)

                routes_to_disable = (
                    [previous_route]
                    if previous_route and previous_route != route_source_name
                    else [
                        source_name
                        for source_name in all_route_source_names
                        if source_name != route_source_name
                    ]
                )
                for source_name in routes_to_disable:
                    item_id = self._route_item_id(client, router_scene_name, source_name)
                    client.set_scene_item_enabled(router_scene_name, item_id, False)

            client.set_current_program_scene(scene_name)
            if router_scene_names:
                self._active_route_source = route_source_name
        except Exception as error:
            self._reset()
            raise ObsGatewayError(f"Could not route OBS mode '{scene_name}'") from error

    def configure_custom_routing(
        self,
        assignments: dict[str, str | None],
    ) -> None:
        try:
            client = self._connect()
            for projector_id, slot_scene_name in zip(
                PROJECTOR_IDS,
                CUSTOM_SLOT_SCENE_NAMES,
                strict=True,
            ):
                target_source = assignments[projector_id]
                if self._custom_assignments.get(projector_id) == target_source:
                    continue

                if target_source is not None:
                    target_item_id = self._route_item_id(
                        client,
                        slot_scene_name,
                        target_source,
                    )
                    client.set_scene_item_enabled(
                        slot_scene_name,
                        target_item_id,
                        True,
                    )

                if projector_id in self._custom_assignments:
                    sources_to_disable = [self._custom_assignments[projector_id]]
                else:
                    sources_to_disable = [
                        source_name
                        for source_name in FLOOR_BOX_SOURCE_NAMES
                        if source_name != target_source
                    ]

                for source_name in sources_to_disable:
                    if source_name is None or source_name == target_source:
                        continue
                    item_id = self._route_item_id(
                        client,
                        slot_scene_name,
                        source_name,
                    )
                    client.set_scene_item_enabled(slot_scene_name, item_id, False)

            self._custom_assignments = dict(assignments)
        except Exception as error:
            self._reset()
            raise ObsGatewayError("Could not configure custom projector routing") from error

    def open_projectors(self, projectors: list[ProjectorConfig]) -> None:
        client = self._connect()
        try:
            for projector in projectors:
                if not projector.enabled or projector.monitor_index is None:
                    continue
                if projector.kind == "program":
                    client.open_video_mix_projector(
                        "OBS_WEBSOCKET_VIDEO_MIX_TYPE_PROGRAM",
                        monitor_index=projector.monitor_index,
                    )
                else:
                    client.open_source_projector(
                        projector.source_name or "",
                        monitor_index=projector.monitor_index,
                    )
        except Exception as error:
            self._reset()
            raise ObsGatewayError("Could not open the commissioned projector outputs") from error

    def monitor_names(self) -> list[str]:
        try:
            response = self._connect().get_monitor_list()
            return [monitor["monitorName"] for monitor in response.monitors]
        except Exception as error:
            self._reset()
            raise ObsGatewayError("Could not read the OBS monitor list") from error

    def commissioning_data(self) -> ObsCommissioningData:
        try:
            client = self._connect()
            profile = client.get_profile_list()
            collection = client.get_scene_collection_list()
            video = client.get_video_settings()
            scene_list = client.get_scene_list()
            input_list = client.get_input_list()
            monitor_list = client.get_monitor_list()
            stats = client.get_stats()

            fps_denominator = max(video.fps_denominator, 1)
            monitors = [
                {
                    "index": monitor.get("monitorIndex", index),
                    "name": monitor.get("monitorName", f"Display {index}"),
                    "width": monitor.get("monitorWidth"),
                    "height": monitor.get("monitorHeight"),
                    "x": monitor.get("monitorPositionX"),
                    "y": monitor.get("monitorPositionY"),
                }
                for index, monitor in enumerate(monitor_list.monitors)
            ]
            return ObsCommissioningData(
                simulation=False,
                profile_name=profile.current_profile_name,
                scene_collection_name=collection.current_scene_collection_name,
                base_width=video.base_width,
                base_height=video.base_height,
                output_width=video.output_width,
                output_height=video.output_height,
                fps=video.fps_numerator / fps_denominator,
                scenes=sorted(scene["sceneName"] for scene in scene_list.scenes),
                inputs=sorted(item["inputName"] for item in input_list.inputs),
                monitors=monitors,
                stats={
                    "cpu_usage": stats.cpu_usage,
                    "memory_usage": stats.memory_usage,
                    "active_fps": stats.active_fps,
                    "average_frame_render_time": stats.average_frame_render_time,
                    "render_skipped_frames": stats.render_skipped_frames,
                    "render_total_frames": stats.render_total_frames,
                    "output_skipped_frames": stats.output_skipped_frames,
                    "output_total_frames": stats.output_total_frames,
                },
            )
        except Exception as error:
            self._reset()
            raise ObsGatewayError("Could not inspect the OBS commissioning state") from error


class SimulatedObsGateway:
    def __init__(self, initial_scene: str = "00_BLACK") -> None:
        self.current_scene = initial_scene
        self.opened_projectors: list[str] = []
        self.scene_changes: list[str] = []
        self.routing_requests: list[tuple[str, tuple[str, ...]]] = []
        self.custom_routing_requests: list[dict[str, str | None]] = []

    def status(self) -> ObsStatus:
        return ObsStatus(
            connected=True,
            current_scene=self.current_scene,
            obs_version="simulation",
            message="Simulation mode",
        )

    def activate_mode(
        self,
        scene_name: str,
        route_source_name: str,
        router_scene_names: list[str],
        all_route_source_names: list[str],
    ) -> None:
        self.current_scene = scene_name
        self.scene_changes.append(scene_name)
        if router_scene_names:
            self.routing_requests.append((route_source_name, tuple(router_scene_names)))

    def configure_custom_routing(
        self,
        assignments: dict[str, str | None],
    ) -> None:
        self.custom_routing_requests.append(dict(assignments))

    def open_projectors(self, projectors: list[ProjectorConfig]) -> None:
        self.opened_projectors.extend(
            projector.id for projector in projectors if projector.enabled
        )

    def monitor_names(self) -> list[str]:
        return [f"Simulated display {number}" for number in range(1, 9)]

    def commissioning_data(self) -> ObsCommissioningData:
        scenes = [
            "00_BLACK",
            "01_EIGHT_SOURCE",
            "04_WRAPAROUND",
            "05_CUSTOM",
            "06_LECTURE_SINGLE",
            "07_LECTURE_DOUBLE",
            "08_LECTURE_SINGLE_BACKGROUND",
            "09_LECTURE_DOUBLE_BACKGROUND",
            "ROUTE_ACTIVE",
            *CUSTOM_SLOT_SCENE_NAMES,
            *(f"OUT_P{number}" for number in range(1, 9)),
        ]
        return ObsCommissioningData(
            simulation=True,
            profile_name="T&V Display System",
            scene_collection_name="T&V Production",
            base_width=11860,
            base_height=1080,
            output_width=11860,
            output_height=1080,
            fps=60.0,
            scenes=scenes,
            inputs=[*FLOOR_BOX_SOURCE_NAMES, "SERVER_DESKTOP"],
            monitors=[
                {
                    "index": index,
                    "name": f"Simulated display {index + 1}",
                    "width": 1920,
                    "height": 1080,
                    "x": index * 1480,
                    "y": 0,
                }
                for index in range(8)
            ],
            stats={
                "cpu_usage": 18.4,
                "memory_usage": 1260.0,
                "active_fps": 60.0,
                "average_frame_render_time": 3.2,
                "render_skipped_frames": 0,
                "render_total_frames": 216000,
                "output_skipped_frames": 0,
                "output_total_frames": 216000,
            },
        )

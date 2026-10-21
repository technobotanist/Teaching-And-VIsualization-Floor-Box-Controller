from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .commissioning import CommissioningService
from .config import (
    FLOOR_BOX_SOURCE_NAMES,
    ControllerConfig,
    default_config_path,
    load_config,
)
from .config_store import ConfigStore, ConfigUpdateError
from .field_session import (
    FIELD_CHECK_IDS,
    FieldSessionNotFoundError,
    FieldSessionStore,
    InputMapping,
    ProjectorTestResult,
    SessionSnapshot,
    SoakState,
)
from .field_report import build_field_report, render_field_report
from .display_identifier import DisplayIdentifierError
from .mode_exercise import ModeExerciseError, ModeExerciseRunner
from .obs_gateway import ObsGateway, ObsGatewayError, ObsWebSocketGateway
from .obs_setup import ObsSetupError, ObsSetupService
from .service import (
    ControllerStatus,
    DisplayController,
    ModeDisabledError,
    ModeNotFoundError,
)
from .windows import focus_obs_editor


class CommissioningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectorAssignmentRequest(CommissioningRequest):
    monitor_index: int | None = Field(default=None, ge=0)
    enabled: bool = False
    confirmation: str


class ProjectorTestRequest(CommissioningRequest):
    confirmation: str


class CustomRoutingRequest(CommissioningRequest):
    assignments: dict[str, str | None]


class ObsWebSocketSetupRequest(CommissioningRequest):
    port: int = Field(default=4455, ge=1, le=65535)
    confirmation: str


class ObsPasswordSetupRequest(CommissioningRequest):
    password: SecretStr
    confirmation: str


class FieldSessionUpdateRequest(CommissioningRequest):
    current_phase: Literal["hardware", "obs-contract", "projectors", "acceptance"]
    notes: str = Field(default="", max_length=10000)


class FieldCheckRequest(CommissioningRequest):
    checked: bool


class InputMappingRequest(CommissioningRequest):
    floor_label: str = Field(default="", max_length=120)
    capture_device: str = Field(default="", max_length=240)
    capture_channel: str = Field(default="", max_length=120)
    signal_status: Literal["untested", "pass", "fail"] = "untested"
    notes: str = Field(default="", max_length=1000)


class ProjectorTestResultRequest(CommissioningRequest):
    status: Literal["untested", "pass", "wrong_display", "no_signal"]
    observed_display: str = Field(default="", max_length=240)
    notes: str = Field(default="", max_length=1000)


class SoakActionRequest(CommissioningRequest):
    action: Literal["start", "reset", "complete"]


class ModeExerciseStartRequest(CommissioningRequest):
    mode_ids: list[str] = Field(default_factory=list, max_length=20)
    interval_seconds: float = Field(default=5.0, ge=1.0, le=60.0)
    target_cycles: int = Field(default=25, ge=1, le=100)


def _status_payload(status: ControllerStatus) -> dict[str, object]:
    return {
        "obs": {
            "connected": status.obs.connected,
            "current_scene": status.obs.current_scene,
            "version": status.obs.obs_version,
            "message": status.obs.message,
        },
        "active_mode_id": status.active_mode_id,
        "outputs_opened": status.outputs_opened,
        "commissioned_output_count": status.commissioned_output_count,
    }


def _custom_routing_payload(config: ControllerConfig) -> dict[str, object]:
    return {
        "projectors": [
            {"id": projector.id, "label": projector.label}
            for projector in config.outputs.projectors
        ],
        "sources": list(FLOOR_BOX_SOURCE_NAMES),
        "assignments": config.custom_routing.assignments,
    }


def _session_payload(session: object) -> dict[str, object]:
    return session.model_dump(mode="json")


def create_app(
    config: ControllerConfig | None = None,
    gateway: ObsGateway | None = None,
    config_path: Path | None = None,
    editor_focus: Callable[[], bool | None] | None = None,
    obs_setup_service: ObsSetupService | None = None,
    field_session_directory: Path | None = None,
) -> FastAPI:
    resolved_config_path = config_path or (default_config_path() if config is None else None)
    room_config = config or load_config(resolved_config_path)
    obs_gateway = gateway or ObsWebSocketGateway(room_config.obs)
    config_store = ConfigStore(room_config, resolved_config_path)
    controller = DisplayController(room_config, obs_gateway, editor_focus or focus_obs_editor)
    commissioning = CommissioningService(config_store, obs_gateway)
    if field_session_directory is None and resolved_config_path is not None:
        config_directory = resolved_config_path.resolve().parent
        project_root = (
            config_directory.parent
            if config_directory.name.lower() == "config"
            else config_directory
        )
        field_session_directory = project_root / "state" / "field-sessions"
    field_sessions = FieldSessionStore(field_session_directory)
    mode_exercise = ModeExerciseRunner(controller, field_sessions)
    obs_setup = obs_setup_service or ObsSetupService(
        room_config.obs,
        focus_editor=editor_focus or focus_obs_editor,
    )

    app = FastAPI(
        title="T&V HDMI Floor Box Controller",
        version="0.3.0",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.state.controller = controller
    app.state.commissioning = commissioning
    app.state.field_sessions = field_sessions
    app.state.mode_exercise = mode_exercise
    app.state.obs_setup = obs_setup

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/config")
    def public_config() -> dict[str, object]:
        current_config = controller.config
        return {
            "room": current_config.room.model_dump(),
            "modes": [mode.model_dump() for mode in current_config.modes],
            "outputs": {
                "topology": current_config.outputs.topology,
                "auto_open": current_config.outputs.auto_open,
                "projector_count": len(current_config.outputs.projectors),
            },
        }

    @app.get("/api/v1/status")
    def status() -> dict[str, object]:
        return _status_payload(controller.status())

    @app.post("/api/v1/modes/{mode_id}/activate")
    def activate_mode(mode_id: str) -> dict[str, object]:
        try:
            return _status_payload(controller.activate(mode_id))
        except ModeNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ModeDisabledError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ObsGatewayError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.get("/api/v1/custom-routing")
    def custom_routing() -> dict[str, object]:
        return _custom_routing_payload(controller.config)

    @app.put("/api/v1/custom-routing")
    def update_custom_routing(
        request: CustomRoutingRequest,
    ) -> dict[str, object]:
        try:
            updated = config_store.set_custom_routes(request.assignments)
            controller.replace_config(updated, reset_outputs=False)
            status = controller.activate("custom")
            return {
                **_custom_routing_payload(updated),
                "status": _status_payload(status),
            }
        except ConfigUpdateError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ObsGatewayError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.post("/api/v1/outputs/open")
    def open_outputs() -> dict[str, object]:
        try:
            return _status_payload(controller.open_outputs(force=True))
        except ObsGatewayError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.post("/api/v1/editor/focus")
    def focus_editor() -> dict[str, bool]:
        return {"focused": controller.focus_editor()}

    @app.get("/api/v1/obs/setup")
    def obs_setup_status() -> dict[str, object]:
        try:
            return obs_setup.status().payload()
        except ObsSetupError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/v1/obs/setup/launch")
    def launch_obs() -> dict[str, object]:
        try:
            return obs_setup.launch_or_focus().payload()
        except ObsSetupError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.put("/api/v1/obs/setup/websocket")
    def configure_obs_websocket(
        request: ObsWebSocketSetupRequest,
    ) -> dict[str, object]:
        expected_confirmation = "CONFIGURE OBS"
        if request.confirmation.strip().upper() != expected_confirmation:
            raise HTTPException(
                status_code=409,
                detail=f"Type '{expected_confirmation}' to confirm OBS configuration",
            )
        try:
            return obs_setup.configure_websocket(request.port).payload()
        except ObsSetupError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.put("/api/v1/obs/setup/password")
    def configure_obs_password(
        request: ObsPasswordSetupRequest,
    ) -> dict[str, object]:
        expected_confirmation = "SAVE OBS PASSWORD"
        if request.confirmation.strip().upper() != expected_confirmation:
            raise HTTPException(
                status_code=409,
                detail=f"Type '{expected_confirmation}' to confirm credential storage",
            )
        try:
            return obs_setup.set_controller_password(
                request.password.get_secret_value()
            ).payload()
        except ObsSetupError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/v1/monitors")
    def monitors() -> dict[str, list[str]]:
        try:
            return {"monitors": controller.monitor_names()}
        except ObsGatewayError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.get("/api/v1/commissioning")
    def commissioning_snapshot() -> dict[str, object]:
        return commissioning.snapshot()

    @app.post("/api/v1/commissioning/inventory/refresh")
    def refresh_commissioning_inventory() -> dict[str, object]:
        return commissioning.refresh_inventory()

    @app.put("/api/v1/commissioning/projectors/{projector_id}")
    def assign_projector(
        projector_id: str,
        request: ProjectorAssignmentRequest,
    ) -> dict[str, object]:
        expected_confirmation = f"MAP {projector_id.upper()}"
        if request.confirmation.strip().upper() != expected_confirmation:
            raise HTTPException(
                status_code=409,
                detail=f"Type '{expected_confirmation}' to confirm this monitor assignment",
            )
        try:
            updated = commissioning.assign_projector(
                projector_id,
                request.monitor_index,
                request.enabled,
            )
            controller.replace_config(updated)
            return commissioning.snapshot()
        except ConfigUpdateError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/v1/commissioning/projectors/{projector_id}/test")
    def test_projector(
        projector_id: str,
        request: ProjectorTestRequest,
    ) -> dict[str, str]:
        expected_confirmation = f"TEST {projector_id.upper()}"
        if request.confirmation.strip().upper() != expected_confirmation:
            raise HTTPException(
                status_code=409,
                detail=f"Type '{expected_confirmation}' to open this projector test",
            )
        try:
            commissioning.test_projector(projector_id)
            return {"status": "opened", "projector_id": projector_id}
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ObsGatewayError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.post("/api/v1/commissioning/projectors/{projector_id}/identify")
    def identify_projector(
        projector_id: str,
        request: ProjectorTestRequest,
    ) -> dict[str, str]:
        expected_confirmation = f"IDENTIFY {projector_id.upper()}"
        if request.confirmation.strip().upper() != expected_confirmation:
            raise HTTPException(
                status_code=409,
                detail=f"Type '{expected_confirmation}' to show this display identifier",
            )
        try:
            commissioning.identify_projector(projector_id)
            return {"status": "opened", "projector_id": projector_id}
        except (ValueError, DisplayIdentifierError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ObsGatewayError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    def get_field_session(session_id: str):
        try:
            return field_sessions.get(session_id)
        except FieldSessionNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/v1/field-session")
    def active_field_session() -> dict[str, object | None]:
        session = field_sessions.active()
        if session is None:
            sessions = field_sessions.list()
            session = sessions[0] if sessions else None
        return {"session": _session_payload(session) if session else None}

    @app.post("/api/v1/field-session")
    def start_field_session() -> dict[str, object]:
        active = field_sessions.active()
        if active is not None:
            return _session_payload(active)
        session = field_sessions.create(
            room_config.room.name,
            commissioning.snapshot(),
        )
        return _session_payload(session)

    @app.get("/api/v1/field-session/{session_id}")
    def field_session(session_id: str) -> dict[str, object]:
        return _session_payload(get_field_session(session_id))

    @app.put("/api/v1/field-session/{session_id}")
    def update_field_session(
        session_id: str,
        request: FieldSessionUpdateRequest,
    ) -> dict[str, object]:
        get_field_session(session_id)
        session = field_sessions.update(
            session_id,
            lambda current: current.model_copy(
                update={
                    "current_phase": request.current_phase,
                    "notes": request.notes,
                }
            ),
        )
        return _session_payload(session)

    @app.put("/api/v1/field-session/{session_id}/checks/{check_id}")
    def update_field_check(
        session_id: str,
        check_id: str,
        request: FieldCheckRequest,
    ) -> dict[str, object]:
        get_field_session(session_id)
        if check_id not in FIELD_CHECK_IDS:
            raise HTTPException(status_code=404, detail=f"Unknown field check '{check_id}'")
        session = field_sessions.update(
            session_id,
            lambda current: current.model_copy(
                update={"checks": {**current.checks, check_id: request.checked}}
            ),
        )
        return _session_payload(session)

    @app.put("/api/v1/field-session/{session_id}/inputs/{source_name}")
    def update_input_mapping(
        session_id: str,
        source_name: str,
        request: InputMappingRequest,
    ) -> dict[str, object]:
        get_field_session(session_id)
        normalized_source = source_name.upper()
        if normalized_source not in FLOOR_BOX_SOURCE_NAMES:
            raise HTTPException(status_code=404, detail=f"Unknown input '{source_name}'")
        mapping = InputMapping(source_name=normalized_source, **request.model_dump())
        session = field_sessions.update(
            session_id,
            lambda current: current.model_copy(
                update={
                    "input_mappings": {
                        **current.input_mappings,
                        normalized_source: mapping,
                    }
                }
            ),
        )
        return _session_payload(session)

    @app.put("/api/v1/field-session/{session_id}/projectors/{projector_id}")
    def update_projector_test_result(
        session_id: str,
        projector_id: str,
        request: ProjectorTestResultRequest,
    ) -> dict[str, object]:
        get_field_session(session_id)
        normalized_id = projector_id.lower()
        if normalized_id not in {projector.id for projector in room_config.outputs.projectors}:
            raise HTTPException(status_code=404, detail=f"Unknown projector '{projector_id}'")
        result = ProjectorTestResult(
            projector_id=normalized_id,
            tested_at=datetime.now(UTC),
            **request.model_dump(),
        )
        session = field_sessions.update(
            session_id,
            lambda current: current.model_copy(
                update={
                    "projector_tests": {
                        **current.projector_tests,
                        normalized_id: result,
                    }
                }
            ),
        )
        return _session_payload(session)

    @app.put("/api/v1/field-session/{session_id}/soak")
    def update_soak(
        session_id: str,
        request: SoakActionRequest,
    ) -> dict[str, object]:
        get_field_session(session_id)
        now = datetime.now(UTC)

        def update(current):
            if request.action == "start":
                soak = SoakState(started_at=now, duration_seconds=current.soak.duration_seconds)
            elif request.action == "complete":
                soak = current.soak.model_copy(update={"completed_at": now})
            else:
                soak = SoakState(duration_seconds=current.soak.duration_seconds)
            return current.model_copy(update={"soak": soak})

        return _session_payload(field_sessions.update(session_id, update))

    @app.post("/api/v1/field-session/{session_id}/mode-exercise/start")
    def start_mode_exercise(
        session_id: str,
        request: ModeExerciseStartRequest,
    ) -> dict[str, object]:
        get_field_session(session_id)
        try:
            session = mode_exercise.start(
                session_id,
                request.mode_ids,
                request.interval_seconds,
                request.target_cycles,
            )
            return _session_payload(session)
        except ModeExerciseError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/v1/field-session/{session_id}/mode-exercise/stop")
    def stop_mode_exercise(session_id: str) -> dict[str, object]:
        get_field_session(session_id)
        return _session_payload(mode_exercise.stop(session_id))

    @app.post("/api/v1/field-session/{session_id}/snapshots/{kind}")
    def capture_field_snapshot(
        session_id: str,
        kind: Literal["pre_reboot", "post_reboot", "final"],
    ) -> dict[str, object]:
        get_field_session(session_id)
        snapshot = SessionSnapshot(kind=kind, data=commissioning.snapshot())
        session = field_sessions.update(
            session_id,
            lambda current: current.model_copy(
                update={"snapshots": [*current.snapshots, snapshot]}
            ),
        )
        return _session_payload(session)

    @app.post("/api/v1/field-session/{session_id}/complete")
    def complete_field_session(session_id: str) -> dict[str, object]:
        current = get_field_session(session_id)
        if current.mode_exercise.status == "running":
            raise HTTPException(
                status_code=409,
                detail="Stop the mode exercise before completing this visit",
            )
        now = datetime.now(UTC)
        final_snapshot = SessionSnapshot(kind="final", data=commissioning.snapshot())
        session = field_sessions.update(
            session_id,
            lambda current: current.model_copy(
                update={
                    "status": "completed",
                    "completed_at": now,
                    "updated_at": now,
                    "current_phase": "acceptance",
                    "snapshots": [*current.snapshots, final_snapshot],
                }
            ),
        )
        return _session_payload(session)

    @app.get("/api/v1/field-session/{session_id}/report.json")
    def field_session_json_report(session_id: str) -> JSONResponse:
        session = get_field_session(session_id)
        report = build_field_report(session, controller.config)
        return JSONResponse(
            report,
            headers={
                "Content-Disposition": f'attachment; filename="field-test-{session_id}.json"'
            },
        )

    @app.get("/api/v1/field-session/{session_id}/report.html")
    def field_session_html_report(session_id: str) -> HTMLResponse:
        session = get_field_session(session_id)
        report = build_field_report(session, controller.config)
        return HTMLResponse(render_field_report(report))

    web_directory = Path(__file__).parent / "web"
    index_path = web_directory / "index.html"
    commissioning_path = web_directory / "commissioning.html"

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(index_path)

    @app.get("/commissioning")
    def commissioning_page() -> FileResponse:
        return FileResponse(commissioning_path)

    app.mount("/assets", StaticFiles(directory=web_directory), name="assets")
    return app

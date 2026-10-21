from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Callable, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .config import FLOOR_BOX_SOURCE_NAMES, PROJECTOR_IDS


SessionStatus = Literal["in_progress", "completed"]
SignalStatus = Literal["untested", "pass", "fail"]
ProjectorTestStatus = Literal["untested", "pass", "wrong_display", "no_signal"]
ExerciseStatus = Literal["idle", "running", "stopped", "completed", "failed"]
FIELD_CHECK_IDS = (
    "inputs-verified",
    "outputs-identified",
    "hardware-soak",
    "input-order",
    "opaque-scenes",
    "route-switching",
    "geometry-locked",
    "seams-verified",
    "no-editor-output",
    "switch-cycles",
    "power-cycle",
    "input-recovery",
    "shortcuts-installed",
    "backup-restored",
    "staff-trained",
)


def _now() -> datetime:
    return datetime.now(UTC)


class SessionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InputMapping(SessionModel):
    source_name: str
    floor_label: str = ""
    capture_device: str = ""
    capture_channel: str = ""
    signal_status: SignalStatus = "untested"
    notes: str = ""


class ProjectorTestResult(SessionModel):
    projector_id: str
    status: ProjectorTestStatus = "untested"
    observed_display: str = ""
    notes: str = ""
    tested_at: datetime | None = None


class SoakState(SessionModel):
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: int = Field(default=3600, ge=1)


class ModeExerciseState(SessionModel):
    status: ExerciseStatus = "idle"
    mode_ids: list[str] = Field(default_factory=list)
    interval_seconds: float = Field(default=5.0, ge=1.0, le=60.0)
    target_cycles: int = Field(default=25, ge=1, le=100)
    current_mode_id: str | None = None
    switch_count: int = Field(default=0, ge=0)
    completed_cycles: int = Field(default=0, ge=0)
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    errors: list[str] = Field(default_factory=list)


class SessionSnapshot(SessionModel):
    kind: Literal["baseline", "pre_reboot", "post_reboot", "final"]
    captured_at: datetime = Field(default_factory=_now)
    data: dict[str, object] = Field(default_factory=dict)


class FieldTestSession(SessionModel):
    schema_version: int = 1
    id: str
    room_name: str
    status: SessionStatus = "in_progress"
    current_phase: str = "hardware"
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    completed_at: datetime | None = None
    notes: str = ""
    checks: dict[str, bool] = Field(
        default_factory=lambda: {check_id: False for check_id in FIELD_CHECK_IDS}
    )
    input_mappings: dict[str, InputMapping] = Field(default_factory=dict)
    projector_tests: dict[str, ProjectorTestResult] = Field(default_factory=dict)
    soak: SoakState = Field(default_factory=SoakState)
    mode_exercise: ModeExerciseState = Field(default_factory=ModeExerciseState)
    snapshots: list[SessionSnapshot] = Field(default_factory=list)


class FieldSessionNotFoundError(LookupError):
    pass


class FieldSessionStore:
    def __init__(self, directory: Path | None) -> None:
        self._directory = directory.resolve() if directory else None
        self._sessions: dict[str, FieldTestSession] = {}
        self._lock = RLock()

    def create(
        self,
        room_name: str,
        baseline: dict[str, object] | None = None,
    ) -> FieldTestSession:
        with self._lock:
            session = FieldTestSession(
                id=str(uuid4()),
                room_name=room_name,
                input_mappings={
                    source_name: InputMapping(source_name=source_name)
                    for source_name in FLOOR_BOX_SOURCE_NAMES
                },
                projector_tests={
                    projector_id: ProjectorTestResult(projector_id=projector_id)
                    for projector_id in PROJECTOR_IDS
                },
                snapshots=[SessionSnapshot(kind="baseline", data=baseline or {})],
            )
            self._persist(session)
            self._sessions[session.id] = session
            return session

    def get(self, session_id: str) -> FieldTestSession:
        with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]
            path = self._session_path(session_id)
            if path is None or not path.exists():
                raise FieldSessionNotFoundError(
                    f"Unknown field-test session '{session_id}'"
                )
            session = FieldTestSession.model_validate_json(
                path.read_text(encoding="utf-8")
            )
            self._sessions[session.id] = session
            return session

    def save(self, session: FieldTestSession) -> FieldTestSession:
        with self._lock:
            updated = session.model_copy(update={"updated_at": _now()})
            self._persist(updated)
            self._sessions[updated.id] = updated
            return updated

    def update(
        self,
        session_id: str,
        updater: Callable[[FieldTestSession], FieldTestSession],
    ) -> FieldTestSession:
        with self._lock:
            current = self.get(session_id)
            updated = updater(current)
            if updated.id != current.id:
                raise ValueError("A field-test session update cannot change its id")
            return self.save(updated)

    def list(self) -> list[FieldTestSession]:
        with self._lock:
            sessions = dict(self._sessions)
            if self._directory and self._directory.exists():
                for path in self._directory.glob("*.json"):
                    try:
                        session = FieldTestSession.model_validate_json(
                            path.read_text(encoding="utf-8")
                        )
                    except (OSError, ValueError):
                        continue
                    sessions[session.id] = session
            ordered = sorted(
                sessions.values(),
                key=lambda session: session.updated_at,
                reverse=True,
            )
            self._sessions = {session.id: session for session in ordered}
            return ordered

    def active(self) -> FieldTestSession | None:
        return next(
            (session for session in self.list() if session.status == "in_progress"),
            None,
        )

    def _session_path(self, session_id: str) -> Path | None:
        try:
            normalized_id = str(UUID(session_id))
        except ValueError as error:
            raise FieldSessionNotFoundError(
                f"Unknown field-test session '{session_id}'"
            ) from error
        if self._directory is None:
            return None
        return self._directory / f"{normalized_id}.json"

    def _persist(self, session: FieldTestSession) -> None:
        path = self._session_path(session.id)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(".json.tmp")
        try:
            temporary_path.write_text(
                f"{session.model_dump_json(indent=2)}\n",
                encoding="utf-8",
            )
            os.replace(temporary_path, path)
        except OSError:
            temporary_path.unlink(missing_ok=True)
            raise
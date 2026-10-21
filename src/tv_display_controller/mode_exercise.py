from __future__ import annotations

from datetime import UTC, datetime
from threading import Event, RLock, Thread

from .field_session import FieldSessionStore, ModeExerciseState
from .service import DisplayController


class ModeExerciseError(RuntimeError):
    pass


class ModeExerciseRunner:
    def __init__(
        self,
        controller: DisplayController,
        sessions: FieldSessionStore,
    ) -> None:
        self._controller = controller
        self._sessions = sessions
        self._lock = RLock()
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._blank_mode_id = next(
            (mode.id for mode in controller.config.modes if mode.kind == "blank" and mode.enabled),
            None,
        )
        active = sessions.active()
        if active and active.mode_exercise.status == "running":
            sessions.update(active.id, self._mark_interrupted)

    @staticmethod
    def _mark_interrupted(session):
        exercise = session.mode_exercise.model_copy(
            update={
                "status": "stopped",
                "stopped_at": datetime.now(UTC),
                "errors": [
                    *session.mode_exercise.errors,
                    "Controller restarted before the mode exercise completed",
                ],
            }
        )
        return session.model_copy(update={"mode_exercise": exercise})

    def start(
        self,
        session_id: str,
        mode_ids: list[str],
        interval_seconds: float,
        target_cycles: int,
    ):
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise ModeExerciseError("A mode exercise is already running")
            if self._blank_mode_id is None:
                raise ModeExerciseError("No enabled Blank mode is configured")

            session = self._sessions.get(session_id)
            if session.status != "in_progress":
                raise ModeExerciseError("Completed field sessions cannot run mode exercises")

            available = {
                mode.id for mode in self._controller.config.modes if mode.enabled
            }
            requested = mode_ids or [
                mode.id for mode in self._controller.config.modes if mode.enabled
            ]
            normalized = list(dict.fromkeys(requested))
            invalid = [mode_id for mode_id in normalized if mode_id not in available]
            if invalid:
                raise ModeExerciseError(f"Unknown or disabled room mode '{invalid[0]}'")
            if not normalized:
                raise ModeExerciseError("Select at least one room mode")

            exercise = ModeExerciseState(
                status="running",
                mode_ids=normalized,
                interval_seconds=interval_seconds,
                target_cycles=target_cycles,
                started_at=datetime.now(UTC),
            )
            updated = self._sessions.update(
                session_id,
                lambda current: current.model_copy(update={"mode_exercise": exercise}),
            )
            self._stop_event = Event()
            self._thread = Thread(
                target=self._run,
                args=(session_id,),
                name="room-mode-exercise",
                daemon=True,
            )
            self._thread.start()
            return updated

    def stop(self, session_id: str):
        with self._lock:
            self._sessions.get(session_id)
            self._stop_event.set()
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=10)

        blank_error = self._activate_blank()

        def update(current):
            errors = list(current.mode_exercise.errors)
            if thread and thread.is_alive():
                errors.append("Mode exercise did not stop within ten seconds")
            if blank_error:
                errors.append(blank_error)
            exercise = current.mode_exercise.model_copy(
                update={
                    "status": "stopped",
                    "current_mode_id": self._blank_mode_id,
                    "stopped_at": datetime.now(UTC),
                    "errors": errors,
                }
            )
            return current.model_copy(update={"mode_exercise": exercise})

        return self._sessions.update(session_id, update)

    def wait(self, timeout: float | None = None) -> bool:
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

    def _run(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        modes = session.mode_exercise.mode_ids
        try:
            while not self._stop_event.is_set():
                for mode_id in modes:
                    if self._stop_event.is_set():
                        return
                    self._controller.activate(mode_id)

                    def record_switch(current):
                        current_exercise = current.mode_exercise
                        switch_count = current_exercise.switch_count + 1
                        completed_cycles = switch_count // len(modes)
                        exercise = current_exercise.model_copy(
                            update={
                                "current_mode_id": mode_id,
                                "switch_count": switch_count,
                                "completed_cycles": completed_cycles,
                            }
                        )
                        return current.model_copy(update={"mode_exercise": exercise})

                    updated = self._sessions.update(session_id, record_switch)
                    if (
                        updated.mode_exercise.completed_cycles
                        >= updated.mode_exercise.target_cycles
                    ):
                        self._finish(session_id, "completed")
                        return
                    if self._stop_event.wait(updated.mode_exercise.interval_seconds):
                        return
        except Exception as error:
            self._finish(
                session_id,
                "failed",
                f"{type(error).__name__}: {error}",
            )

    def _finish(
        self,
        session_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        blank_error = self._activate_blank()

        def update(current):
            errors = list(current.mode_exercise.errors)
            if error:
                errors.append(error)
            if blank_error:
                errors.append(blank_error)
            final_status = "failed" if errors else status
            exercise = current.mode_exercise.model_copy(
                update={
                    "status": final_status,
                    "current_mode_id": self._blank_mode_id,
                    "stopped_at": datetime.now(UTC),
                    "errors": errors,
                }
            )
            checks = dict(current.checks)
            if final_status == "completed" and exercise.target_cycles >= 25:
                checks["switch-cycles"] = True
            return current.model_copy(
                update={"mode_exercise": exercise, "checks": checks}
            )

        self._sessions.update(session_id, update)

    def _activate_blank(self) -> str | None:
        if self._blank_mode_id is None:
            return "No enabled Blank mode is configured"
        try:
            self._controller.activate(self._blank_mode_id)
        except Exception as error:
            return f"Could not activate Blank: {error}"
        return None
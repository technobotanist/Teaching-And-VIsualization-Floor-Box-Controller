from __future__ import annotations

import os
from pathlib import Path
from threading import RLock

from pydantic import ValidationError

from .config import ControllerConfig


class ConfigUpdateError(RuntimeError):
    pass


class ConfigStore:
    def __init__(self, config: ControllerConfig, path: Path | None = None) -> None:
        self._config = config
        self._path = path.resolve() if path else None
        self._lock = RLock()

    def current(self) -> ControllerConfig:
        with self._lock:
            return self._config

    def assign_projector(
        self,
        projector_id: str,
        monitor_index: int | None,
        enabled: bool,
    ) -> ControllerConfig:
        with self._lock:
            config_data = self._config.model_dump()
            projectors = config_data["outputs"]["projectors"]
            projector = next(
                (candidate for candidate in projectors if candidate["id"] == projector_id),
                None,
            )
            if projector is None:
                raise ConfigUpdateError(f"Unknown projector '{projector_id}'")

            projector["monitor_index"] = monitor_index
            projector["enabled"] = enabled
            try:
                updated = ControllerConfig.model_validate(config_data)
            except ValidationError as error:
                message = error.errors()[0].get("msg", "Invalid projector assignment")
                raise ConfigUpdateError(message.removeprefix("Value error, ")) from error

            self._persist(updated)
            self._config = updated
            return updated

    def set_custom_routes(
        self,
        assignments: dict[str, str | None],
    ) -> ControllerConfig:
        with self._lock:
            config_data = self._config.model_dump()
            config_data["custom_routing"]["assignments"] = assignments
            try:
                updated = ControllerConfig.model_validate(config_data)
            except ValidationError as error:
                message = error.errors()[0].get("msg", "Invalid custom routing")
                raise ConfigUpdateError(message.removeprefix("Value error, ")) from error

            self._persist(updated)
            self._config = updated
            return updated

    def _persist(self, config: ControllerConfig) -> None:
        if self._path is None:
            return

        temporary_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
        try:
            temporary_path.write_text(
                f"{config.model_dump_json(indent=2)}\n",
                encoding="utf-8",
            )
            os.replace(temporary_path, self._path)
        except OSError as error:
            temporary_path.unlink(missing_ok=True)
            raise ConfigUpdateError("Could not persist the room configuration") from error

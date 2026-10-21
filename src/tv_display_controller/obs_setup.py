from __future__ import annotations

import ctypes
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import ObsSettings
from .windows import focus_obs_editor


class ObsSetupError(RuntimeError):
    pass


@dataclass(frozen=True)
class ObsSetupStatus:
    installed: bool
    executable_path: str | None
    running: bool
    websocket_config_exists: bool
    websocket_enabled: bool
    websocket_port: int
    authentication_required: bool
    password_configured: bool
    controller_password_configured: bool
    websocket_listening: bool
    automatic_configuration_available: bool

    def payload(self) -> dict[str, object]:
        return asdict(self)


def _default_executable_path() -> Path | None:
    configured = os.getenv("OBS_EXECUTABLE")
    candidates = [
        Path(configured) if configured else None,
        Path(os.getenv("ProgramFiles", r"C:\Program Files"))
        / "obs-studio"
        / "bin"
        / "64bit"
        / "obs64.exe",
        Path(os.getenv("LOCALAPPDATA", ""))
        / "Programs"
        / "obs-studio"
        / "bin"
        / "64bit"
        / "obs64.exe",
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate.resolve()
    discovered = shutil.which("obs64.exe")
    return Path(discovered).resolve() if discovered else None


def _default_websocket_config_path() -> Path:
    app_data = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
    return app_data / "obs-studio" / "plugin_config" / "obs-websocket" / "config.json"


def _obs_is_running() -> bool:
    if sys.platform != "win32":
        return False
    try:
        completed = subprocess.run(
            [
                "tasklist.exe",
                "/FI",
                "IMAGENAME eq obs64.exe",
                "/FO",
                "CSV",
                "/NH",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return '"obs64.exe"' in completed.stdout.casefold()


def _port_is_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.15):
            return True
    except OSError:
        return False


def _launch_obs(executable_path: Path) -> None:
    creation_flags = (
        getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )
    try:
        subprocess.Popen(
            [str(executable_path)],
            cwd=executable_path.parent,
            close_fds=True,
            creationflags=creation_flags,
        )
    except OSError as error:
        raise ObsSetupError("Could not launch OBS Studio") from error


def _persist_user_environment(name: str, value: str) -> None:
    if sys.platform != "win32":
        return
    import winreg

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        result = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF,
            0x001A,
            0,
            "Environment",
            0x0002,
            5000,
            ctypes.byref(result),
        )
    except OSError as error:
        raise ObsSetupError("Could not persist the controller password environment") from error


class ObsSetupService:
    def __init__(
        self,
        settings: ObsSettings,
        executable_path: Path | None = None,
        websocket_config_path: Path | None = None,
        is_running: Callable[[], bool] | None = None,
        port_is_listening: Callable[[int], bool] | None = None,
        launch_process: Callable[[Path], None] | None = None,
        focus_editor: Callable[[], bool] | None = None,
        persist_environment: Callable[[str, str], None] | None = None,
    ) -> None:
        self._settings = settings
        self._executable_path = executable_path or _default_executable_path()
        self._websocket_config_path = (
            websocket_config_path or _default_websocket_config_path()
        )
        self._is_running = is_running or _obs_is_running
        self._port_is_listening = port_is_listening or _port_is_listening
        self._launch_process = launch_process or _launch_obs
        self._focus_editor = focus_editor or focus_obs_editor
        self._persist_environment = (
            persist_environment or _persist_user_environment
        )

    def _websocket_config(self) -> dict[str, object]:
        if not self._websocket_config_path.is_file():
            return {}
        try:
            payload = json.loads(
                self._websocket_config_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise ObsSetupError("Could not read the OBS WebSocket configuration") from error
        if not isinstance(payload, dict):
            raise ObsSetupError("OBS WebSocket configuration is not a JSON object")
        return payload

    def status(self) -> ObsSetupStatus:
        config = self._websocket_config()
        running = self._is_running()
        port = int(config.get("server_port", self._settings.port))
        enabled = bool(config.get("server_enabled", False))
        authentication_required = bool(config.get("auth_required", True))
        password_configured = bool(config.get("server_password"))
        controller_password_configured = bool(
            os.getenv(self._settings.password_environment_variable)
        )
        installed = bool(
            self._executable_path and self._executable_path.is_file()
        )
        return ObsSetupStatus(
            installed=installed,
            executable_path=(
                str(self._executable_path) if self._executable_path else None
            ),
            running=running,
            websocket_config_exists=self._websocket_config_path.is_file(),
            websocket_enabled=enabled,
            websocket_port=port,
            authentication_required=authentication_required,
            password_configured=password_configured,
            controller_password_configured=controller_password_configured,
            websocket_listening=enabled and self._port_is_listening(port),
            automatic_configuration_available=installed and not running,
        )

    def launch_or_focus(self) -> ObsSetupStatus:
        if self._is_running():
            self._focus_editor()
            return self.status()
        if not self._executable_path or not self._executable_path.is_file():
            raise ObsSetupError("OBS Studio is not installed in a known location")
        self._launch_process(self._executable_path)
        return self.status()

    def configure_websocket(self, port: int) -> ObsSetupStatus:
        if not 1 <= port <= 65535:
            raise ObsSetupError("OBS WebSocket port must be between 1 and 65535")
        if self._is_running():
            raise ObsSetupError(
                "Close OBS Studio before applying automatic WebSocket settings"
            )

        config = self._websocket_config()
        password = secrets.token_urlsafe(32)
        config.update(
            {
                "server_enabled": True,
                "server_port": port,
                "auth_required": True,
                "server_password": password,
            }
        )

        try:
            self._websocket_config_path.parent.mkdir(parents=True, exist_ok=True)
            if self._websocket_config_path.is_file():
                backup_path = self._websocket_config_path.with_name(
                    "config.controller-backup.json"
                )
                shutil.copy2(self._websocket_config_path, backup_path)
            temporary_path = self._websocket_config_path.with_suffix(".json.tmp")
            temporary_path.write_text(
                f"{json.dumps(config, indent=4)}\n",
                encoding="utf-8",
            )
            os.replace(temporary_path, self._websocket_config_path)
        except OSError as error:
            raise ObsSetupError("Could not update OBS WebSocket settings") from error

        variable_name = self._settings.password_environment_variable
        os.environ[variable_name] = password
        self._persist_environment(variable_name, password)
        return self.status()

    def set_controller_password(self, password: str) -> ObsSetupStatus:
        if len(password) < 12:
            raise ObsSetupError("OBS WebSocket password must be at least 12 characters")
        variable_name = self._settings.password_environment_variable
        os.environ[variable_name] = password
        self._persist_environment(variable_name, password)
        return self.status()
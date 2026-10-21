import json
import os
from pathlib import Path

import pytest

from tv_display_controller.config import ObsSettings
from tv_display_controller.obs_setup import ObsSetupError, ObsSetupService


def create_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    running: bool = False,
) -> tuple[ObsSetupService, Path, Path, list[tuple[str, str]], list[Path]]:
    executable = tmp_path / "obs64.exe"
    executable.write_bytes(b"")
    config_path = tmp_path / "plugin_config" / "config.json"
    persisted_environment: list[tuple[str, str]] = []
    launched: list[Path] = []
    monkeypatch.delenv("OBS_WEBSOCKET_PASSWORD", raising=False)
    service = ObsSetupService(
        ObsSettings(),
        executable_path=executable,
        websocket_config_path=config_path,
        is_running=lambda: running,
        port_is_listening=lambda port: port == 4455 and running,
        launch_process=launched.append,
        focus_editor=lambda: True,
        persist_environment=lambda name, value: persisted_environment.append(
            (name, value)
        ),
    )
    return service, executable, config_path, persisted_environment, launched


def test_status_reports_setup_without_exposing_password(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _, config_path, _, _ = create_service(tmp_path, monkeypatch)
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "server_enabled": False,
                "server_port": 4455,
                "auth_required": True,
                "server_password": "existing-secret",
            }
        ),
        encoding="utf-8",
    )

    payload = service.status().payload()

    assert payload["installed"] is True
    assert payload["websocket_enabled"] is False
    assert payload["password_configured"] is True
    assert "password" not in payload


def test_configure_websocket_preserves_settings_and_manages_password(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _, config_path, persisted_environment, _ = create_service(
        tmp_path,
        monkeypatch,
    )
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "alerts_enabled": False,
                "server_enabled": False,
                "server_port": 4455,
                "auth_required": True,
                "server_password": "old-secret",
            }
        ),
        encoding="utf-8",
    )

    status = service.configure_websocket(4455)

    updated = json.loads(config_path.read_text(encoding="utf-8"))
    assert updated["alerts_enabled"] is False
    assert updated["server_enabled"] is True
    assert updated["auth_required"] is True
    assert updated["server_password"] != "old-secret"
    assert config_path.with_name("config.controller-backup.json").is_file()
    assert persisted_environment == [
        ("OBS_WEBSOCKET_PASSWORD", updated["server_password"])
    ]
    assert os.environ["OBS_WEBSOCKET_PASSWORD"] == updated["server_password"]
    assert status.controller_password_configured is True


def test_configure_websocket_refuses_to_edit_while_obs_is_running(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _, _, _, _ = create_service(tmp_path, monkeypatch, running=True)

    with pytest.raises(ObsSetupError, match="Close OBS Studio"):
        service.configure_websocket(4455)


def test_launch_uses_discovered_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, executable, _, _, launched = create_service(tmp_path, monkeypatch)

    service.launch_or_focus()

    assert launched == [executable]


def test_manual_password_handoff_persists_without_changing_obs_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _, config_path, persisted_environment, _ = create_service(
        tmp_path,
        monkeypatch,
        running=True,
    )

    status = service.set_controller_password("manual-password-value")

    assert config_path.exists() is False
    assert persisted_environment == [
        ("OBS_WEBSOCKET_PASSWORD", "manual-password-value")
    ]
    assert status.controller_password_configured is True


def test_manual_password_handoff_requires_minimum_length(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _, _, _, _ = create_service(tmp_path, monkeypatch)

    with pytest.raises(ObsSetupError, match="at least 12 characters"):
        service.set_controller_password("too-short")
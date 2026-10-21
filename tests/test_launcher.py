import errno
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from unittest.mock import Mock

import pytest
import uvicorn

from tv_display_controller import __main__ as launcher
from tv_display_controller.app import create_app
from tv_display_controller.config import load_config
from tv_display_controller.obs_gateway import SimulatedObsGateway


ROOT = Path(__file__).parents[1]
CONFIG_PATH = ROOT / "config" / "room.json"


def mock_instance(monkeypatch, payload):
    opener = Mock()
    opener.open.return_value = io.BytesIO(json.dumps(payload).encode())
    monkeypatch.setattr(launcher, "build_opener", Mock(return_value=opener))
    return opener


def test_existing_controller_opens_browser_without_starting_server(monkeypatch):
    opener = mock_instance(monkeypatch, {
        "application": "tv-display-controller",
        "config_path": str(CONFIG_PATH.resolve()),
        "simulation": True,
    })
    browser = Mock()
    server = Mock()
    monkeypatch.setattr(launcher.webbrowser, "open", browser)
    monkeypatch.setattr(launcher.uvicorn, "run", server)

    launcher.main(["--config", str(CONFIG_PATH), "--simulate", "--open-browser"])

    browser.assert_called_once_with("http://127.0.0.1:8765")
    server.assert_not_called()
    opener.open.assert_called_once_with(
        "http://127.0.0.1:8765/api/v1/instance", timeout=3
    )


def test_existing_controller_respects_no_browser(monkeypatch):
    mock_instance(monkeypatch, {
        "application": "tv-display-controller",
        "config_path": str(CONFIG_PATH.resolve()),
        "simulation": True,
    })
    browser = Mock()
    monkeypatch.setattr(launcher.webbrowser, "open", browser)

    launcher.main(["--config", str(CONFIG_PATH), "--simulate"])

    browser.assert_not_called()


def test_connection_refused_starts_server(monkeypatch):
    opener = mock_instance(monkeypatch, {})
    opener.open.side_effect = URLError(ConnectionRefusedError(errno.ECONNREFUSED, "refused"))
    server = Mock()
    monkeypatch.setattr(launcher.uvicorn, "run", server)

    launcher.main(["--config", str(CONFIG_PATH), "--simulate"])

    server.assert_called_once()
    assert server.call_args.kwargs["port"] == 8765
    assert server.call_args.args[0].state.controller is not None


@pytest.mark.parametrize("payload", [
    [],
    {"application": "another-server"},
    {"application": "tv-display-controller", "config_path": None, "simulation": True},
    {"application": "tv-display-controller", "config_path": str(CONFIG_PATH), "simulation": False},
    {"application": "tv-display-controller", "config_path": str(ROOT / "other.json"), "simulation": True},
])
def test_incompatible_server_is_not_silently_reused(monkeypatch, payload):
    mock_instance(monkeypatch, payload)

    with pytest.raises(RuntimeError, match="Another server|different configuration"):
        launcher._reuse_running_controller("http://127.0.0.1:8765", CONFIG_PATH, True)


@pytest.mark.parametrize("error", [
    HTTPError("http://127.0.0.1:8765", 404, "Not Found", {}, None),
    URLError(TimeoutError("timeout")),
    URLError(OSError(errno.EACCES, "denied")),
    TimeoutError("timeout"),
    ValueError("invalid JSON"),
])
def test_probe_failures_are_reported(monkeypatch, error):
    opener = mock_instance(monkeypatch, {})
    opener.open.side_effect = error

    with pytest.raises(RuntimeError):
        launcher._reuse_running_controller("http://127.0.0.1:8765", CONFIG_PATH, True)


def test_live_server_is_reused_and_serves_ui(tmp_path, monkeypatch, capsys):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        config_data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        config_data["server"]["port"] = port
        config_path = tmp_path / "room.json"
        config_path.write_text(json.dumps(config_data), encoding="utf-8")
        app = create_app(load_config(config_path), SimulatedObsGateway(), config_path)
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert server.started, "Test controller did not become ready"
            url = f"http://127.0.0.1:{port}"
            with launcher.build_opener(launcher.ProxyHandler({})).open(url, timeout=3) as response:
                assert response.status == 200
                assert b"Projector assignment matrix" in response.read()
            browser = Mock()
            monkeypatch.setattr(launcher.webbrowser, "open", browser)

            launcher.main(["--config", str(config_path), "--simulate", "--open-browser"])

            assert f"Controller already running at {url}" in capsys.readouterr().out
            browser.assert_called_once_with(url)
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive(), "Test controller did not stop"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop shortcuts")
def test_desktop_shortcuts_launch_with_spaces_and_ampersands(tmp_path):
    project = tmp_path / "T&V controller folder"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    shutil.copyfile(
        ROOT / "scripts" / "Install-DesktopShortcuts.ps1",
        scripts / "Install-DesktopShortcuts.ps1",
    )
    for filename in ("Start-Controller.cmd", "Start-Simulation.cmd"):
        shutil.copyfile(ROOT / filename, project / filename)
    (scripts / "Start-Controller.ps1").write_text(
        "param([switch]$AutoInstall, [switch]$Simulate)\n"
        'if (-not $AutoInstall) { throw "Automatic installation was not enabled." }\n'
        '$Mode = if ($Simulate) { "simulation" } else { "real" }\n'
        'Set-Content -Path (Join-Path $PSScriptRoot "..\\arguments.txt") -Value $Mode\n',
        encoding="ascii",
    )
    powershell = str(
        Path(os.environ["SystemRoot"])
        / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    )
    subprocess.run([
        powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(scripts / "Install-DesktopShortcuts.ps1"),
        "-Destination", str(desktop),
    ], check=True, capture_output=True, text=True)
    assert len(list(desktop.glob("*.lnk"))) == 10

    for name, expected in [
        ("T&V HDMI Floor Box Controller", "real"),
        ("T&V Controller - Simulation", "simulation"),
    ]:
        shortcut_path = str(desktop / f"{name}.lnk").replace("'", "''")
        result = subprocess.run([
            powershell, "-NoProfile", "-Command",
            "$s = (New-Object -ComObject WScript.Shell).CreateShortcut("
            f"'{shortcut_path}'); "
            "$s | Select-Object TargetPath,Arguments,WorkingDirectory,WindowStyle "
            "| ConvertTo-Json -Compress",
        ], check=True, capture_output=True, text=True)
        shortcut = json.loads(result.stdout)
        assert shortcut["WorkingDirectory"] == str(project)
        assert shortcut["WindowStyle"] == 7
        subprocess.run(
            f'"{shortcut["TargetPath"]}" {shortcut["Arguments"]}',
            cwd=project, check=True, capture_output=True, text=True,
        )
        assert (project / "arguments.txt").read_text().strip() == expected

    subprocess.run(
        f'"{os.environ["ComSpec"]}" /d /c ""{project / "Start-Simulation.cmd"}""',
        cwd=project, check=True, capture_output=True, text=True,
    )
    assert (project / "arguments.txt").read_text().strip() == "simulation"

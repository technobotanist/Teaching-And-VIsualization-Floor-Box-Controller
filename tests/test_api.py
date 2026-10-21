from pathlib import Path

from fastapi.testclient import TestClient

from tv_display_controller.app import create_app
from tv_display_controller.config import load_config
from tv_display_controller.obs_gateway import SimulatedObsGateway
from tv_display_controller.obs_setup import ObsSetupService


CONFIG_PATH = Path(__file__).parents[1] / "config" / "room.json"


def test_instance_identifies_config_and_simulation(tmp_path: Path) -> None:
    config_path = tmp_path / "room.json"
    config_path.write_text(CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    client = TestClient(create_app(
        load_config(config_path), SimulatedObsGateway(), config_path
    ))

    response = client.get("/api/v1/instance")

    assert response.status_code == 200
    assert response.json() == {
        "application": "tv-display-controller",
        "config_path": str(config_path.resolve()),
        "simulation": True,
    }


def test_config_endpoint_exposes_operator_data_only() -> None:
    config = load_config(CONFIG_PATH)
    client = TestClient(create_app(config, SimulatedObsGateway()))

    response = client.get("/api/v1/config")

    assert response.status_code == 200
    assert response.json()["room"]["canvas_width"] == 11860
    assert "obs" not in response.json()


def test_mode_activation_updates_status() -> None:
    config = load_config(CONFIG_PATH)
    client = TestClient(create_app(config, SimulatedObsGateway()))

    response = client.post("/api/v1/modes/wraparound/activate")

    assert response.status_code == 200
    assert response.json()["active_mode_id"] == "wraparound"
    assert response.json()["obs"]["current_scene"] == "04_WRAPAROUND"


def test_custom_routing_endpoint_persists_applies_and_activates(tmp_path: Path) -> None:
    config_path = tmp_path / "room.json"
    config_path.write_text(CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    gateway = SimulatedObsGateway()
    client = TestClient(create_app(load_config(config_path), gateway, config_path))
    assignments = {
        "p1": "FB_04",
        "p2": "FB_05",
        "p3": None,
        "p4": "FB_04",
        "p5": "FB_05",
        "p6": None,
        "p7": "FB_08",
        "p8": "FB_08",
    }

    response = client.put(
        "/api/v1/custom-routing",
        json={"assignments": assignments},
    )

    assert response.status_code == 200
    assert response.json()["assignments"] == assignments
    assert response.json()["status"]["active_mode_id"] == "custom"
    assert gateway.custom_routing_requests == [assignments]
    assert load_config(config_path).custom_routing.assignments == assignments


def test_custom_routing_endpoint_rejects_unknown_floor_box() -> None:
    config = load_config(CONFIG_PATH)
    client = TestClient(create_app(config, SimulatedObsGateway()))
    assignments = dict(config.custom_routing.assignments)
    assignments["p1"] = "FB_09"

    response = client.put(
        "/api/v1/custom-routing",
        json={"assignments": assignments},
    )

    assert response.status_code == 409
    assert "unknown custom routing source" in response.json()["detail"]


def test_unknown_mode_returns_not_found() -> None:
    config = load_config(CONFIG_PATH)
    client = TestClient(create_app(config, SimulatedObsGateway()))

    response = client.post("/api/v1/modes/unknown/activate")

    assert response.status_code == 404


def test_uncommissioned_outputs_are_not_opened() -> None:
    config = load_config(CONFIG_PATH)
    gateway = SimulatedObsGateway()
    client = TestClient(create_app(config, gateway))

    response = client.post("/api/v1/outputs/open")

    assert response.status_code == 200
    assert response.json()["outputs_opened"] is False
    assert gateway.opened_projectors == []


def test_editor_focus_reports_whether_obs_was_found() -> None:
    config = load_config(CONFIG_PATH)
    client = TestClient(
        create_app(config, SimulatedObsGateway(), editor_focus=lambda: True)
    )

    response = client.post("/api/v1/editor/focus")

    assert response.status_code == 200
    assert response.json() == {"focused": True}


def test_obs_setup_api_configures_websocket_without_returning_secret(
    tmp_path: Path,
    monkeypatch,
) -> None:
    executable = tmp_path / "obs64.exe"
    executable.write_bytes(b"")
    websocket_config = tmp_path / "obs-websocket" / "config.json"
    websocket_config.parent.mkdir()
    websocket_config.write_text(
        '{"server_enabled": false, "auth_required": true}',
        encoding="utf-8",
    )
    monkeypatch.delenv("OBS_WEBSOCKET_PASSWORD", raising=False)
    setup = ObsSetupService(
        load_config(CONFIG_PATH).obs,
        executable_path=executable,
        websocket_config_path=websocket_config,
        is_running=lambda: False,
        port_is_listening=lambda port: False,
        launch_process=lambda path: None,
        persist_environment=lambda name, value: None,
    )
    client = TestClient(
        create_app(
            load_config(CONFIG_PATH),
            SimulatedObsGateway(),
            obs_setup_service=setup,
        )
    )

    response = client.put(
        "/api/v1/obs/setup/websocket",
        json={"port": 4455, "confirmation": "CONFIGURE OBS"},
    )

    assert response.status_code == 200
    assert response.json()["websocket_enabled"] is True
    assert response.json()["controller_password_configured"] is True
    assert "server_password" not in response.json()


def test_operator_interface_and_assets_are_served() -> None:
    config = load_config(CONFIG_PATH)
    client = TestClient(create_app(config, SimulatedObsGateway()))

    page = client.get("/")
    script = client.get("/assets/app.js")
    stylesheet = client.get("/assets/styles.css")

    assert page.status_code == 200
    assert "Teaching &amp; Visualization Lab" in page.text
    assert "Projector assignment matrix" in page.text
    assert "1 BLENDED DISPLAY" in page.text
    assert "Apply routing" in page.text
    assert "Show active layout full screen" in page.text
    assert script.status_code == 200
    assert "applyCustomRouting" in script.text
    assert "Show ${activeLayout} full screen" in script.text
    assert stylesheet.status_code == 200
    assert "--red: #cc0000" in stylesheet.text


def test_commissioning_interface_and_assets_are_served() -> None:
    config = load_config(CONFIG_PATH)
    client = TestClient(create_app(config, SimulatedObsGateway()))

    page = client.get("/commissioning")
    script = client.get("/assets/commissioning.js")
    stylesheet = client.get("/assets/commissioning.css")

    assert page.status_code == 200
    assert "Commissioning Console" in page.text
    assert "Renderer connection" in page.text
    assert "Blended display output" in page.text
    assert "Room layout scene mapping" in page.text
    assert script.status_code == 200
    assert "confirmAction" in script.text
    assert "loadObsSetup" in script.text
    assert "/api/v1/commissioning/mode-scenes" in script.text
    assert stylesheet.status_code == 200
    assert ".projector-table" in stylesheet.text
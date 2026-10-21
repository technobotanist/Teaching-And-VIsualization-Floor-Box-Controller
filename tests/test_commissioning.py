from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tv_display_controller.app import create_app
from tv_display_controller.commissioning import CommissioningService
from tv_display_controller.config import load_config
from tv_display_controller.config_store import ConfigStore
from tv_display_controller.obs_gateway import SimulatedObsGateway


CONFIG_PATH = Path(__file__).parents[1] / "config" / "room.json"


def test_simulation_cannot_satisfy_production_obs_gate(monkeypatch) -> None:
    monkeypatch.setattr(
        "tv_display_controller.commissioning.collect_system_summary",
        lambda: {"computer_name": "test-room"},
    )
    config = load_config(CONFIG_PATH)
    service = CommissioningService(ConfigStore(config), SimulatedObsGateway())

    snapshot = service.snapshot()

    assert snapshot["obs_contract_ready"] is False
    assert snapshot["checks"][0]["id"] == "live-obs"
    assert snapshot["checks"][0]["status"] == "fail"
    assert all(check["status"] == "pass" for check in snapshot["checks"][1:])
    assert len(snapshot["obs"]["monitors"]) == 8
    assert snapshot["checks"][-1]["label"] == "Blended display discovery"


def test_projector_mapping_requires_confirmation(tmp_path: Path) -> None:
    config_path = tmp_path / "room.json"
    config_path.write_text(CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    config = load_config(config_path)
    client = TestClient(create_app(config, SimulatedObsGateway(), config_path))

    response = client.put(
        "/api/v1/commissioning/projectors/p1",
        json={"monitor_index": 0, "enabled": True, "confirmation": "yes"},
    )

    assert response.status_code == 409
    assert load_config(config_path).outputs.projectors[0].monitor_index is None


def test_projector_mapping_persists_and_updates_controller(tmp_path: Path) -> None:
    config_path = tmp_path / "room.json"
    config_path.write_text(CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    config = load_config(config_path)
    client = TestClient(create_app(config, SimulatedObsGateway(), config_path))

    response = client.put(
        "/api/v1/commissioning/projectors/p1",
        json={"monitor_index": 0, "enabled": True, "confirmation": "MAP P1"},
    )

    assert response.status_code == 200
    assert response.json()["commissioned_count"] == 1
    persisted = load_config(config_path)
    assert persisted.outputs.projectors[0].monitor_index == 0
    assert persisted.outputs.projectors[0].enabled is True
    assert client.get("/api/v1/status").json()["commissioned_output_count"] == 1


def test_blended_display_test_opens_program_output(tmp_path: Path) -> None:
    config_path = tmp_path / "room.json"
    config_path.write_text(CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    gateway = SimulatedObsGateway()
    client = TestClient(create_app(load_config(config_path), gateway, config_path))
    client.put(
        "/api/v1/commissioning/projectors/p1",
        json={"monitor_index": 2, "enabled": False, "confirmation": "MAP P1"},
    )

    response = client.post(
        "/api/v1/commissioning/projectors/p1/test",
        json={"confirmation": "TEST P1"},
    )

    assert response.status_code == 200
    assert gateway.opened_projectors == ["p1"]


def test_projector_identifier_targets_assigned_monitor(tmp_path: Path) -> None:
    config = load_config(CONFIG_PATH)
    store = ConfigStore(config)
    store.assign_projector("p1", 2, False)
    identified: list[tuple[str, int, dict[str, object]]] = []
    service = CommissioningService(
        store,
        SimulatedObsGateway(),
        lambda label, monitor_index, monitor: identified.append(
            (label, monitor_index, monitor)
        ),
    )

    service.identify_projector("p1")

    assert identified[0][0] == "P1"
    assert identified[0][1] == 2
    assert identified[0][2]["name"] == "Simulated display 3"
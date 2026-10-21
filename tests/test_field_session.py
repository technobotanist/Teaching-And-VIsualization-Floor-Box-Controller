from pathlib import Path

from fastapi.testclient import TestClient

from tv_display_controller.app import create_app
from tv_display_controller.config import load_config
from tv_display_controller.field_session import FieldSessionStore
from tv_display_controller.mode_exercise import ModeExerciseRunner
from tv_display_controller.obs_gateway import SimulatedObsGateway
from tv_display_controller.service import DisplayController


CONFIG_PATH = Path(__file__).parents[1] / "config" / "room.json"


def test_field_session_survives_store_restart(tmp_path: Path) -> None:
    session_directory = tmp_path / "field-sessions"
    store = FieldSessionStore(session_directory)
    session = store.create("Teaching and Visualization Lab", {"computer": "ROOM-PC"})
    mapping = session.input_mappings["FB_01"].model_copy(
        update={
            "floor_label": "Floor box 1",
            "capture_device": "DeckLink Quad 2",
            "capture_channel": "Input 1",
            "signal_status": "pass",
        }
    )
    session = session.model_copy(
        update={"input_mappings": {**session.input_mappings, "FB_01": mapping}}
    )
    store.save(session)

    restored = FieldSessionStore(session_directory).active()

    assert restored is not None
    assert restored.id == session.id
    assert restored.snapshots[0].data == {"computer": "ROOM-PC"}
    assert restored.input_mappings["FB_01"].capture_channel == "Input 1"
    assert restored.input_mappings["FB_01"].signal_status == "pass"


def test_field_session_api_survives_app_restart(tmp_path: Path) -> None:
    session_directory = tmp_path / "field-sessions"
    config = load_config(CONFIG_PATH)
    client = TestClient(
        create_app(
            config,
            SimulatedObsGateway(),
            field_session_directory=session_directory,
        )
    )
    session = client.post("/api/v1/field-session").json()
    assert list(session["projector_tests"]) == ["p1"]

    input_response = client.put(
        f"/api/v1/field-session/{session['id']}/inputs/FB_01",
        json={
            "floor_label": "Lectern east",
            "capture_device": "DeckLink Quad 2",
            "capture_channel": "Input 1",
            "signal_status": "pass",
            "notes": "Stable at 1080p60",
        },
    )
    check_response = client.put(
        f"/api/v1/field-session/{session['id']}/checks/inputs-verified",
        json={"checked": True},
    )

    assert input_response.status_code == 200
    assert check_response.status_code == 200
    restarted_client = TestClient(
        create_app(
            config,
            SimulatedObsGateway(),
            field_session_directory=session_directory,
        )
    )
    restored = restarted_client.get("/api/v1/field-session").json()["session"]
    assert restored["id"] == session["id"]
    assert restored["checks"]["inputs-verified"] is True
    assert restored["input_mappings"]["FB_01"]["capture_channel"] == "Input 1"


def test_mode_exercise_cycles_modes_and_finishes_on_blank(tmp_path: Path) -> None:
    config = load_config(CONFIG_PATH)
    gateway = SimulatedObsGateway()
    store = FieldSessionStore(tmp_path / "field-sessions")
    session = store.create(config.room.name)
    runner = ModeExerciseRunner(DisplayController(config, gateway), store)
    tested_modes = [mode.id for mode in config.modes if mode.kind != "blank"][:2]
    blank_scene = next(mode.scene for mode in config.modes if mode.kind == "blank")

    runner.start(session.id, tested_modes, interval_seconds=1, target_cycles=1)

    assert runner.wait(timeout=3)
    completed = store.get(session.id)
    assert completed.mode_exercise.status == "completed"
    assert completed.mode_exercise.switch_count == 2
    assert completed.mode_exercise.completed_cycles == 1
    assert gateway.scene_changes[-1] == blank_scene


def test_mode_exercise_stop_activates_blank(tmp_path: Path) -> None:
    config = load_config(CONFIG_PATH)
    gateway = SimulatedObsGateway()
    store = FieldSessionStore(tmp_path / "field-sessions")
    session = store.create(config.room.name)
    runner = ModeExerciseRunner(DisplayController(config, gateway), store)
    tested_modes = [mode.id for mode in config.modes if mode.kind != "blank"][:2]
    blank_mode = next(mode for mode in config.modes if mode.kind == "blank")

    runner.start(session.id, tested_modes, interval_seconds=1, target_cycles=100)
    stopped = runner.stop(session.id)

    assert stopped.mode_exercise.status == "stopped"
    assert stopped.mode_exercise.current_mode_id == blank_mode.id
    assert gateway.scene_changes[-1] == blank_mode.scene


def test_field_session_reports_are_downloadable_and_escape_notes(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            load_config(CONFIG_PATH),
            SimulatedObsGateway(),
            field_session_directory=tmp_path / "field-sessions",
        )
    )
    session = client.post("/api/v1/field-session").json()
    client.put(
        f"/api/v1/field-session/{session['id']}",
        json={"current_phase": "hardware", "notes": "<script>alert(1)</script>"},
    )

    json_response = client.get(
        f"/api/v1/field-session/{session['id']}/report.json"
    )
    html_response = client.get(
        f"/api/v1/field-session/{session['id']}/report.html"
    )

    assert json_response.status_code == 200
    assert "attachment" in json_response.headers["content-disposition"]
    assert len(json_response.json()["config_sha256"]) == 64
    assert html_response.status_code == 200
    assert "Print / Save PDF" in html_response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_response.text
    assert "<script>alert(1)</script>" not in html_response.text


def test_latest_completed_session_remains_available_after_restart(tmp_path: Path) -> None:
    session_directory = tmp_path / "field-sessions"
    config = load_config(CONFIG_PATH)
    client = TestClient(
        create_app(
            config,
            SimulatedObsGateway(),
            field_session_directory=session_directory,
        )
    )
    completed = client.post("/api/v1/field-session").json()
    response = client.post(f"/api/v1/field-session/{completed['id']}/complete")

    assert response.status_code == 200
    restarted = TestClient(
        create_app(
            config,
            SimulatedObsGateway(),
            field_session_directory=session_directory,
        )
    )
    latest = restarted.get("/api/v1/field-session").json()["session"]
    fresh = restarted.post("/api/v1/field-session").json()
    assert latest["id"] == completed["id"]
    assert latest["status"] == "completed"
    assert fresh["id"] != completed["id"]
    assert fresh["status"] == "in_progress"
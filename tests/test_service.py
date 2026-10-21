import json
from pathlib import Path

import pytest

from tv_display_controller.config import ControllerConfig, load_config
from tv_display_controller.obs_gateway import SimulatedObsGateway
from tv_display_controller.service import DisplayController, ModeNotFoundError


CONFIG_PATH = Path(__file__).parents[1] / "config" / "room.json"


def test_activate_switches_only_the_logical_scene() -> None:
    config = load_config(CONFIG_PATH)
    gateway = SimulatedObsGateway()
    controller = DisplayController(config, gateway)

    status = controller.activate("lecture-single")

    assert gateway.scene_changes == ["06_LECTURE_SINGLE"]
    assert gateway.opened_projectors == []
    assert status.active_mode_id == "lecture-single"


def test_custom_mode_applies_saved_projector_routes() -> None:
    config = load_config(CONFIG_PATH)
    gateway = SimulatedObsGateway()
    controller = DisplayController(config, gateway)

    controller.activate("custom")

    assert gateway.current_scene == "05_CUSTOM"
    assert gateway.custom_routing_requests == [config.custom_routing.assignments]


def test_editor_can_be_focused_again() -> None:
    config = load_config(CONFIG_PATH)
    gateway = SimulatedObsGateway()
    controller = DisplayController(config, gateway, lambda: True)

    assert controller.focus_editor() is True


def test_unknown_mode_does_not_change_obs() -> None:
    config = load_config(CONFIG_PATH)
    gateway = SimulatedObsGateway()
    controller = DisplayController(config, gateway)

    with pytest.raises(ModeNotFoundError):
        controller.activate("not-a-mode")

    assert gateway.scene_changes == []


def test_commissioned_outputs_route_without_changing_projector_geometry() -> None:
    raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for monitor_index, projector in enumerate(raw_config["outputs"]["projectors"], start=1):
        projector["monitor_index"] = monitor_index
        projector["enabled"] = True
    config = ControllerConfig.model_validate(raw_config)
    gateway = SimulatedObsGateway()
    controller = DisplayController(config, gateway)

    controller.activate("multi-source")

    assert gateway.routing_requests == [
        (
            "01_EIGHT_SOURCE",
            ("ROUTE_ACTIVE",),
        )
    ]
    assert gateway.opened_projectors == []
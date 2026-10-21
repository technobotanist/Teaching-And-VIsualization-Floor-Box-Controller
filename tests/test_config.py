import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tv_display_controller.config import ControllerConfig, load_config


CONFIG_PATH = Path(__file__).parents[1] / "config" / "room.json"


def test_production_config_is_valid() -> None:
    config = load_config(CONFIG_PATH)

    assert config.room.canvas_width == 11860
    assert [mode.id for mode in config.modes] == [
        "wraparound",
        "lecture-single",
        "lecture-double",
        "lecture-single-background",
        "lecture-double-background",
        "multi-source",
        "custom",
        "blank",
    ]
    assert config.custom_routing.assignments == {
        f"p{number}": f"FB_{number:02d}" for number in range(1, 9)
    }
    assert config.outputs.topology == "single-program"
    assert len(config.outputs.projectors) == 1
    assert config.outputs.projectors[0].kind == "program"
    assert not any(projector.enabled for projector in config.outputs.projectors)


def test_duplicate_mode_ids_are_rejected() -> None:
    raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw_config["modes"][1]["id"] = raw_config["modes"][0]["id"]

    with pytest.raises(ValidationError, match="mode ids must be unique"):
        ControllerConfig.model_validate(raw_config)


def test_enabled_projector_requires_verified_monitor_index() -> None:
    raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw_config["outputs"]["projectors"][0]["enabled"] = True

    with pytest.raises(ValidationError, match="requires a verified monitor_index"):
        ControllerConfig.model_validate(raw_config)


def test_enabled_source_projectors_require_shared_router_scene() -> None:
    raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    projector = raw_config["outputs"]["projectors"][0]
    projector["kind"] = "source"
    projector["source_name"] = "OUT_P1"
    projector["enabled"] = True
    projector["monitor_index"] = 1
    raw_config["outputs"]["router_scene"] = None

    with pytest.raises(ValidationError, match="router_scene is required"):
        ControllerConfig.model_validate(raw_config)


def test_program_output_does_not_require_router_scene() -> None:
    raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    projector = raw_config["outputs"]["projectors"][0]
    projector["enabled"] = True
    projector["monitor_index"] = 1

    config = ControllerConfig.model_validate(raw_config)

    assert config.outputs.router_scene is None
    assert config.outputs.projectors[0].kind == "program"


def test_custom_routing_requires_all_projector_slots() -> None:
    raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    del raw_config["custom_routing"]["assignments"]["p8"]

    with pytest.raises(ValidationError, match="must assign p1 through p8"):
        ControllerConfig.model_validate(raw_config)


def test_custom_routing_rejects_unknown_floor_box() -> None:
    raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw_config["custom_routing"]["assignments"]["p1"] = "FB_09"

    with pytest.raises(ValidationError, match="unknown custom routing source"):
        ControllerConfig.model_validate(raw_config)

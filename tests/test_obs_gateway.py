from types import SimpleNamespace

from tv_display_controller.config import ObsSettings
from tv_display_controller.obs_gateway import ObsWebSocketGateway


class FakeObsClient:
    def __init__(self) -> None:
        self.lookup_calls: list[tuple[str, str]] = []
        self.enabled_calls: list[tuple[str, int, bool]] = []
        self.program_scenes: list[str] = []

    def get_scene_item_id(self, scene_name: str, source_name: str) -> SimpleNamespace:
        self.lookup_calls.append((scene_name, source_name))
        return SimpleNamespace(scene_item_id=len(self.lookup_calls))

    def set_scene_item_enabled(self, scene_name: str, item_id: int, enabled: bool) -> None:
        self.enabled_calls.append((scene_name, item_id, enabled))

    def set_current_program_scene(self, scene_name: str) -> None:
        self.program_scenes.append(scene_name)


class FakeCommissioningClient:
    def get_profile_list(self) -> SimpleNamespace:
        return SimpleNamespace(current_profile_name="T&V Display System")

    def get_scene_collection_list(self) -> SimpleNamespace:
        return SimpleNamespace(current_scene_collection_name="T&V Production")

    def get_video_settings(self) -> SimpleNamespace:
        return SimpleNamespace(
            base_width=11860,
            base_height=1080,
            output_width=11860,
            output_height=1080,
            fps_numerator=60000,
            fps_denominator=1000,
        )

    def get_scene_list(self) -> SimpleNamespace:
        return SimpleNamespace(scenes=[{"sceneName": "00_BLACK"}])

    def get_input_list(self) -> SimpleNamespace:
        return SimpleNamespace(inputs=[{"inputName": "FB_01"}])

    def get_monitor_list(self) -> SimpleNamespace:
        return SimpleNamespace(
            monitors=[
                {
                    "monitorIndex": 7,
                    "monitorName": "Projector test",
                    "monitorWidth": 1920,
                    "monitorHeight": 1080,
                    "monitorPositionX": 3840,
                    "monitorPositionY": 0,
                }
            ]
        )

    def get_stats(self) -> SimpleNamespace:
        return SimpleNamespace(
            cpu_usage=12.5,
            memory_usage=900.0,
            active_fps=60.0,
            average_frame_render_time=2.5,
            render_skipped_frames=0,
            render_total_frames=1000,
            output_skipped_frames=0,
            output_total_frames=1000,
        )


def test_router_normalizes_once_then_switches_only_previous_and_next() -> None:
    gateway = ObsWebSocketGateway(ObsSettings())
    client = FakeObsClient()
    gateway._client = client  # type: ignore[assignment]
    routers = ["ROUTE_ACTIVE"]
    sources = ["01_EIGHT_SOURCE", "02_FOUR_SOURCE", "00_BLACK"]

    gateway.activate_mode("01_EIGHT_SOURCE", "01_EIGHT_SOURCE", routers, sources)

    assert len(client.lookup_calls) == 3
    assert client.program_scenes == ["01_EIGHT_SOURCE"]
    assert sum(enabled for _, _, enabled in client.enabled_calls) == 1
    assert len(client.enabled_calls) == 3

    client.enabled_calls.clear()
    gateway.activate_mode("02_FOUR_SOURCE", "02_FOUR_SOURCE", routers, sources)

    assert len(client.lookup_calls) == 3
    assert client.program_scenes[-1] == "02_FOUR_SOURCE"
    assert [enabled for _, _, enabled in client.enabled_calls] == [True, False]


def test_custom_routing_normalizes_slots_then_changes_only_updated_assignment() -> None:
    gateway = ObsWebSocketGateway(ObsSettings())
    client = FakeObsClient()
    gateway._client = client  # type: ignore[assignment]
    assignments = {f"p{number}": f"FB_{number:02d}" for number in range(1, 9)}

    gateway.configure_custom_routing(assignments)

    assert len(client.lookup_calls) == 64
    assert len(client.enabled_calls) == 64
    assert sum(enabled for _, _, enabled in client.enabled_calls) == 8

    client.enabled_calls.clear()
    gateway.configure_custom_routing({**assignments, "p1": "FB_02"})

    assert [enabled for _, _, enabled in client.enabled_calls] == [True, False]


def test_commissioning_data_normalizes_obs_responses() -> None:
    gateway = ObsWebSocketGateway(ObsSettings())
    gateway._client = FakeCommissioningClient()  # type: ignore[assignment]

    data = gateway.commissioning_data()

    assert data.simulation is False
    assert data.profile_name == "T&V Display System"
    assert data.fps == 60.0
    assert data.scenes == ["00_BLACK"]
    assert data.inputs == ["FB_01"]
    assert data.monitors == [
        {
            "index": 7,
            "name": "Projector test",
            "width": 1920,
            "height": 1080,
            "x": 3840,
            "y": 0,
        }
    ]
    assert data.stats["render_skipped_frames"] == 0
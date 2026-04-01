import pytest

from ocw_workbench.gui.interaction.view_place_controller import ViewPlaceController, map_view_point_to_controller_xy
from ocw_workbench.gui.interaction.view_place_preview import (
    PREVIEW_METADATA_KEY,
    clear_preview_state,
    load_preview_state,
    store_preview_state,
)
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.recompute_count = 0
        self.transactions = []

    def recompute(self) -> None:
        self.recompute_count += 1

    def openTransaction(self, label: str) -> None:
        self.transactions.append(("open", label))

    def commitTransaction(self) -> None:
        self.transactions.append(("commit", None))

    def abortTransaction(self) -> None:
        self.transactions.append(("abort", None))


class FakeView:
    def __init__(self) -> None:
        self.callbacks = []
        self.cursor = None
        self.cursor_history = []

    def addEventCallback(self, event_type, callback):
        handle = (event_type, callback, len(self.callbacks))
        self.callbacks.append(handle)
        return handle

    def removeEventCallback(self, event_type, handle):
        self.callbacks = [item for item in self.callbacks if item != handle]

    def getPoint(self, x, y):
        return (float(x), float(y), 0.0)

    def setCursor(self, cursor):
        self.cursor = cursor
        self.cursor_history.append(cursor)

    def unsetCursor(self):
        self.cursor = None
        self.cursor_history.append(None)


def test_map_view_point_to_controller_xy_clamps_and_snaps():
    mapped = map_view_point_to_controller_xy(
        (12.2, 103.4, 0.0),
        controller_width=100.0,
        controller_depth=80.0,
        snap_enabled=True,
        grid_mm=5.0,
    )

    assert mapped == (10.0, 80.0)


def test_preview_metadata_roundtrip():
    doc = FakeDocument()

    store_preview_state(doc, "omron_b3f_1000", x=12.5, y=18.0, rotation=0.0)
    loaded = load_preview_state(doc)
    clear_preview_state(doc)

    assert loaded == {
        "version": 1,
        "template_id": "omron_b3f_1000",
        "x": 12.5,
        "y": 18.0,
        "rotation": 0.0,
        "mode": "place",
        "snap_enabled": None,
        "grid_mm": None,
        "validation": None,
        "snap": None,
        "axis_lock": None,
        "components": None,
        "addition_id": None,
        "label": None,
        "target_zone_id": None,
        "placement_feedback": None,
    }
    assert getattr(doc, PREVIEW_METADATA_KEY, None) is None


def test_view_place_controller_preview_updates_metadata_only():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    before_state = controller_service.get_state(doc)

    controller = ViewPlaceController(
        controller_service=controller_service,
        interaction_service=interaction_service,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.active_template_id = "omron_b3f_1000"
    controller.preview_active = True

    payload = controller.update_preview_from_screen(12.2, 18.7)
    after_state = controller_service.get_state(doc)

    assert payload == {
        "version": 1,
        "template_id": "omron_b3f_1000",
        "x": 12.0,
        "y": 19.0,
        "rotation": 0.0,
        "mode": "place",
        "snap_enabled": True,
        "grid_mm": 1.0,
        "validation": {
            "valid": True,
            "severity": None,
            "status": "Valid placement",
            "status_code": "valid",
            "commit_allowed": True,
            "findings": [],
            "summary": {"error_count": 0, "warning_count": 0, "total_count": 0},
        },
        "snap": None,
        "axis_lock": None,
        "components": None,
        "addition_id": None,
        "label": None,
        "target_zone_id": None,
        "placement_feedback": None,
    }
    assert load_preview_state(doc) == payload
    assert after_state == before_state
    assert doc.transactions == []


def test_view_place_controller_commit_creates_single_transaction_after_multiple_previews():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})

    controller = ViewPlaceController(
        controller_service=controller_service,
        interaction_service=interaction_service,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.active_template_id = "omron_b3f_1000"
    controller.preview_active = True

    controller.update_preview_from_screen(12.2, 18.7)
    controller.update_preview_from_screen(25.1, 40.4)
    controller.commit()

    assert doc.transactions == [("open", "OCW Place Component"), ("commit", None)]
    assert controller.doc is doc
    assert controller.active_template_id == "omron_b3f_1000"
    assert load_preview_state(doc) is None


def test_view_place_controller_continues_after_commit_for_multiple_clicks():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller = ViewPlaceController(
        controller_service=controller_service,
        interaction_service=interaction_service,
    )
    view = FakeView()
    controller._active_view = lambda _doc: view

    assert controller.start(doc, "omron_b3f_1000") is True
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (12, 19)})
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "UP", "Button": "BUTTON1", "Position": (12, 19)})
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (30, 41)})
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "UP", "Button": "BUTTON1", "Position": (30, 41)})

    state = controller_service.get_state(doc)
    settings = interaction_service.get_settings(doc)

    assert len(state["components"]) == 2
    assert doc.transactions == [
        ("open", "OCW Place Component"),
        ("commit", None),
        ("open", "OCW Place Component"),
        ("commit", None),
    ]
    assert controller.doc is doc
    assert controller.active_template_id == "omron_b3f_1000"
    assert settings["active_interaction"] == "place"
    assert load_preview_state(doc) is None


def test_view_place_controller_drag_updates_preview_and_commits_on_release():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller = ViewPlaceController(
        controller_service=controller_service,
        interaction_service=interaction_service,
    )
    view = FakeView()
    controller._active_view = lambda _doc: view

    assert controller.start(doc, "omron_b3f_1000") is True
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (12, 19)})
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (25, 32)})

    preview = load_preview_state(doc)

    assert preview is not None
    assert controller.is_dragging is True
    assert controller.drag_start_position == (12.0, 19.0)
    assert controller.current_preview_position == (25.0, 32.0)

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "UP", "Button": "BUTTON1", "Position": (25, 32)})

    state = controller_service.get_state(doc)
    assert len(state["components"]) == 1
    assert state["components"][0]["x"] == 25.0
    assert state["components"][0]["y"] == 32.0
    assert controller.is_dragging is False
    assert controller.drag_start_position is None


def test_view_place_controller_blocks_commit_for_invalid_preview():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 40.0, "depth": 40.0, "height": 30.0})

    controller = ViewPlaceController(
        controller_service=controller_service,
        interaction_service=interaction_service,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.active_template_id = "omron_b3f_1000"
    controller.preview_active = True

    preview = controller.update_preview_from_screen(2.0, 2.0)

    assert preview is not None
    assert preview["validation"]["commit_allowed"] is False
    assert controller._preview_allows_commit(preview) is False
    with pytest.raises(ValueError, match="invalid"):
        controller.commit()
    assert controller_service.get_state(doc)["components"] == []


def test_view_place_controller_escape_cancels_and_clears_interaction_state():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller = ViewPlaceController(
        controller_service=controller_service,
        interaction_service=interaction_service,
    )
    view = FakeView()
    controller._active_view = lambda _doc: view

    assert controller.start(doc, "omron_b3f_1000") is True
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (12, 18)})
    assert load_preview_state(doc) is not None

    controller.handle_view_event({"Type": "SoKeyboardEvent", "State": "DOWN", "Key": "ESCAPE"})

    settings = interaction_service.get_settings(doc)
    assert load_preview_state(doc) is None
    assert settings["active_interaction"] is None
    assert controller.doc is None
    assert view.cursor is None


def test_view_place_controller_sets_cursor_for_active_place_mode():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller = ViewPlaceController(
        controller_service=controller_service,
        interaction_service=interaction_service,
    )
    view = FakeView()
    controller._active_view = lambda _doc: view

    assert controller.start(doc, "omron_b3f_1000") is True
    assert view.cursor is not None


def test_overlay_service_includes_drag_preview_ghost():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    store_preview_state(doc, "generic_45mm_linear_fader", x=40.0, y=30.0)

    from ocw_workbench.services.overlay_service import OverlayService

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    item_ids = {item["id"] for item in overlay["items"]}

    assert "preview_component:generic_45mm_linear_fader" in item_ids
    assert "preview_keepout:generic_45mm_linear_fader" in item_ids
    assert "preview_cutout:generic_45mm_linear_fader" in item_ids
    assert "preview_label:generic_45mm_linear_fader" in item_ids


def test_overlay_service_styles_invalid_preview_as_error():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 40.0, "depth": 40.0, "height": 30.0, "top_thickness": 3.0})
    interaction_service.add_component_preview(doc, "omron_b3f_1000", target_x=2.0, target_y=2.0)

    from ocw_workbench.services.overlay_service import OverlayService

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    preview_item = next(item for item in overlay["items"] if item["id"] == "preview_component:omron_b3f_1000")
    preview_label = next(item for item in overlay["items"] if item["id"] == "preview_label:omron_b3f_1000")

    assert preview_item["severity"] == "error"
    assert preview_item["style"]["kind"] == "component_preview_error"
    assert preview_label["style"]["kind"] == "preview_label_error"
    assert "@ 2.0, 2.0 mm" in preview_label["label"]
    assert "Out of bounds" in preview_label["label"]


def test_overlay_service_valid_preview_label_includes_coordinates_and_action_hint():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    interaction_service.add_component_preview(doc, "omron_b3f_1000", target_x=12.0, target_y=19.0)

    from ocw_workbench.services.overlay_service import OverlayService

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    preview_label = next(item for item in overlay["items"] if item["id"] == "preview_label:omron_b3f_1000")

    assert "@ 12.0, 19.0 mm" in preview_label["label"]
    assert "Snap 1.0 mm" in preview_label["label"]
    assert preview_label["label"].endswith("Click to place")


def test_overlay_service_includes_snap_marker_and_axis_lock_guide():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    store_preview_state(
        doc,
        "omron_b3f_1000",
        x=30.0,
        y=20.0,
        snap={"type": "point", "x": 30.0, "y": 20.0, "target_reference": "component:btn1", "distance": 0.0},
        axis_lock={"active": True, "axis": "x", "anchor_x": 10.0, "anchor_y": 20.0},
    )

    from ocw_workbench.services.overlay_service import OverlayService

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    item_ids = {item["id"] for item in overlay["items"]}
    preview_label = next(item for item in overlay["items"] if item["id"] == "preview_label:omron_b3f_1000")

    assert "preview_snap_marker:omron_b3f_1000" in item_ids
    assert "preview_axis_lock:omron_b3f_1000" in item_ids
    assert "Point snap" in preview_label["label"]
    assert "Axis X lock" in preview_label["label"]


def test_view_place_controller_shift_locks_primary_axis():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller = ViewPlaceController(
        controller_service=controller_service,
        interaction_service=interaction_service,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.active_template_id = "omron_b3f_1000"
    controller.preview_active = True

    first = controller.update_preview_from_screen(10.0, 10.0, shift_pressed=True)
    second = controller.update_preview_from_screen(25.0, 14.0, shift_pressed=True)

    assert first is not None
    assert second is not None
    assert second["y"] == 10.0
    assert second["axis_lock"] == {"active": True, "axis": "x", "anchor_x": 10.0, "anchor_y": 10.0}


def test_view_place_controller_on_committed_fires_after_each_click():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    committed_states: list[dict] = []
    controller = ViewPlaceController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        on_committed=committed_states.append,
    )
    view = FakeView()
    controller._active_view = lambda _doc: view

    assert controller.start(doc, "omron_b3f_1000") is True
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (12, 19)})
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "UP", "Button": "BUTTON1", "Position": (12, 19)})
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (30, 41)})
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "UP", "Button": "BUTTON1", "Position": (30, 41)})

    assert len(committed_states) == 2
    assert controller.doc is doc
    assert controller.active_template_id == "omron_b3f_1000"


def test_view_place_controller_on_committed_not_fired_on_cancel():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    committed_states: list[dict] = []
    controller = ViewPlaceController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        on_committed=committed_states.append,
    )
    view = FakeView()
    controller._active_view = lambda _doc: view

    assert controller.start(doc, "omron_b3f_1000") is True
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (12, 18)})
    controller.handle_view_event({"Type": "SoKeyboardEvent", "State": "DOWN", "Key": "ESCAPE"})

    assert committed_states == []
    assert controller.doc is None

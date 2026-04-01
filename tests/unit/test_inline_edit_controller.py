from __future__ import annotations

from ocw_workbench.gui.interaction.inline_edit_controller import InlineEditController
from ocw_workbench.gui.interaction.inline_edit_state import load_inline_edit_state
from ocw_workbench.gui.interaction.tool_manager import reset_tool_manager
from ocw_workbench.gui.overlay.renderer import OverlayRenderer
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService
from ocw_workbench.services.overlay_service import OverlayService


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

    def unsetCursor(self):
        self.cursor = None


def _build_controller() -> tuple[FakeDocument, ControllerService, OverlayRenderer, InlineEditController, FakeView]:
    reset_tool_manager()
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0)
    controller_service.select_component(doc, "btn1")
    InteractionService(controller_service).update_settings(doc, {"snap_enabled": False})
    overlay_renderer = OverlayRenderer(OverlayService(controller_service=controller_service))
    view = FakeView()
    controller = InlineEditController(
        controller_service=controller_service,
        overlay_renderer=overlay_renderer,
    )
    controller._active_view = lambda _doc: view
    assert controller.start(doc) is True
    return doc, controller_service, overlay_renderer, controller, view


def _overlay_item(doc: FakeDocument, item_id: str) -> dict:
    return next(item for item in doc.OCWOverlayState["items"] if item["id"] == item_id)


def test_overlay_service_shows_inline_handles_for_single_selected_component() -> None:
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0)
    controller_service.select_component(doc, "btn1")

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    item_ids = {item["id"] for item in overlay["items"]}

    assert "inline_handle:move:btn1" in item_ids
    assert "inline_handle:rotate:btn1" in item_ids
    assert "inline_handle:cap_width:btn1" in item_ids
    assert "inline_action:duplicate:btn1" in item_ids
    assert "inline_action:rotate_cw_90:btn1" in item_ids
    assert "inline_action:mirror_horizontal:btn1" in item_ids


def test_inline_edit_move_handle_updates_component_and_clears_tool_on_commit() -> None:
    doc, controller_service, _overlay_renderer, controller, _view = _build_controller()
    tools = reset_tool_manager()

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (25, 25)})
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (38, 32)})

    during = controller_service.get_component(doc, "btn1")
    assert during["x"] == 38.0
    assert during["y"] == 32.0
    assert tools.current_tool == "inline_edit:inline_handle:move:btn1"

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "UP", "Button": "BUTTON1", "Position": (38, 32)})

    moved = controller_service.get_component(doc, "btn1")
    assert moved["x"] == 38.0
    assert moved["y"] == 32.0
    assert tools.current_tool is None
    assert load_inline_edit_state(doc)["active_handle_id"] is None


def test_inline_edit_cancel_restores_original_component_state() -> None:
    doc, controller_service, _overlay_renderer, controller, _view = _build_controller()
    original = controller_service.get_component(doc, "btn1")

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (25, 25)})
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (38, 32)})
    controller.handle_view_event({"Type": "SoKeyboardEvent", "State": "DOWN", "Key": "ESCAPE"})

    restored = controller_service.get_component(doc, "btn1")
    assert restored["x"] == original["x"]
    assert restored["y"] == original["y"]
    assert restored.get("rotation", 0.0) == original.get("rotation", 0.0)


def test_inline_edit_rotate_handle_updates_rotation() -> None:
    doc, controller_service, _overlay_renderer, controller, _view = _build_controller()
    rotate_handle = _overlay_item(doc, "inline_handle:rotate:btn1")
    geometry = rotate_handle["geometry"]

    controller.handle_view_event(
        {
            "Type": "SoMouseButtonEvent",
            "State": "DOWN",
            "Button": "BUTTON1",
            "Position": (geometry["x"], geometry["y"]),
        }
    )
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (40, 25)})
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "UP", "Button": "BUTTON1", "Position": (40, 25)})

    rotated = controller_service.get_component(doc, "btn1")
    assert rotated["rotation"] == -90.0


def test_inline_edit_parameter_handle_updates_button_cap_width() -> None:
    doc, controller_service, _overlay_renderer, controller, _view = _build_controller()
    parameter_handle = _overlay_item(doc, "inline_handle:cap_width:btn1")
    geometry = parameter_handle["geometry"]

    controller.handle_view_event(
        {
            "Type": "SoMouseButtonEvent",
            "State": "DOWN",
            "Button": "BUTTON1",
            "Position": (geometry["x"], geometry["y"]),
        }
    )
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (geometry["x"] + 4.0, geometry["y"])})
    controller.handle_view_event(
        {
            "Type": "SoMouseButtonEvent",
            "State": "UP",
            "Button": "BUTTON1",
            "Position": (geometry["x"] + 4.0, geometry["y"]),
        }
    )

    updated = controller_service.get_component(doc, "btn1")
    assert float(updated.get("properties", {}).get("cap_width", 0.0)) > 8.0


def test_inline_edit_hover_marks_handle_in_transient_state() -> None:
    doc, _controller_service, _overlay_renderer, controller, _view = _build_controller()
    handle = _overlay_item(doc, "inline_handle:rotate:btn1")
    geometry = handle["geometry"]

    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (geometry["x"], geometry["y"])})

    state = load_inline_edit_state(doc)
    assert state["hovered_handle_id"] == "inline_handle:rotate:btn1"


def test_inline_edit_hover_marks_inline_action_in_transient_state() -> None:
    doc, _controller_service, _overlay_renderer, controller, _view = _build_controller()
    action = _overlay_item(doc, "inline_action:duplicate:btn1")
    geometry = action["geometry"]

    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (geometry["x"], geometry["y"])})

    state = load_inline_edit_state(doc)
    assert state["hovered_handle_id"] == "inline_action:duplicate:btn1"


def test_inline_edit_action_click_invokes_callback_without_starting_session() -> None:
    reset_tool_manager()
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0)
    controller_service.select_component(doc, "btn1")
    InteractionService(controller_service).update_settings(doc, {"snap_enabled": False})
    overlay_renderer = OverlayRenderer(OverlayService(controller_service=controller_service))
    view = FakeView()
    calls: list[tuple[str, str, str]] = []
    controller = InlineEditController(
        controller_service=controller_service,
        overlay_renderer=overlay_renderer,
        on_action=lambda action_id, component_id, command_id: calls.append((action_id, component_id, command_id)),
    )
    controller._active_view = lambda _doc: view
    assert controller.start(doc) is True

    action = _overlay_item(doc, "inline_action:duplicate:btn1")
    geometry = action["geometry"]
    controller.handle_view_event(
        {
            "Type": "SoMouseButtonEvent",
            "State": "DOWN",
            "Button": "BUTTON1",
            "Position": (geometry["x"], geometry["y"]),
        }
    )

    assert calls == [("duplicate", "btn1", "OCW_DuplicateOnce")]
    assert controller.session is None
    assert load_inline_edit_state(doc)["active_handle_id"] is None

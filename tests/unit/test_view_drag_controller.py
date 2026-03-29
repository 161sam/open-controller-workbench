from ocw_workbench.gui.interaction.view_drag_controller import ViewDragController
from ocw_workbench.gui.interaction.view_place_preview import load_preview_state
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


class RecordingOverlayRenderer:
    def __init__(self, items=None) -> None:
        self.calls = []
        self.items = items or []

    def refresh(self, doc):
        self.calls.append(doc)
        payload = {"items": list(self.items), "summary": {"visual_only": True}}
        doc.OCWOverlayState = payload
        return payload


def test_view_drag_controller_preview_is_visual_only_until_commit():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    overlay = RecordingOverlayRenderer(
        items=[
            {
                "id": "component:btn1",
                "type": "rect",
                "geometry": {"x": 20.0, "y": 20.0, "width": 14.0, "height": 14.0, "rotation": 0.0},
                "source_component_id": "btn1",
            }
        ]
    )
    controller = ViewDragController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        overlay_renderer=overlay,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.armed = True
    before_transactions = list(doc.transactions)

    before_state = controller_service.get_state(doc)
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (20, 20)})
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (31, 29)})
    preview = load_preview_state(doc)
    during_state = controller_service.get_state(doc)
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "UP", "Button": "BUTTON1", "Position": (31, 29)})
    moved = controller_service.get_component(doc, "btn1")

    assert preview == {
        "version": 1,
        "component_id": "btn1",
        "x": 31.0,
        "y": 29.0,
        "rotation": 0.0,
        "mode": "move",
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
    }
    assert during_state["components"] == before_state["components"]
    assert during_state["controller"] == before_state["controller"]
    assert during_state["meta"]["selection"] == before_state["meta"]["selection"]
    assert moved["x"] == 31.0
    assert moved["y"] == 29.0
    assert len(overlay.calls) >= 3
    assert doc.transactions[len(before_transactions):] == [("open", "OCW Drag Move Component"), ("commit", None)]


def test_view_drag_controller_escape_cancels_without_side_effects():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    overlay = RecordingOverlayRenderer(
        items=[
            {
                "id": "component:btn1",
                "type": "rect",
                "geometry": {"x": 20.0, "y": 20.0, "width": 14.0, "height": 14.0, "rotation": 0.0},
                "source_component_id": "btn1",
            }
        ]
    )
    controller = ViewDragController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        overlay_renderer=overlay,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.armed = True

    before = controller_service.get_component(doc, "btn1")
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (20, 20)})
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (40, 35)})
    controller.handle_view_event({"Type": "SoKeyboardEvent", "State": "DOWN", "Key": "ESCAPE"})
    after = controller_service.get_component(doc, "btn1")

    assert load_preview_state(doc) is None
    assert before["x"] == after["x"] == 20.0
    assert before["y"] == after["y"] == 20.0
    assert controller.session is None


def test_view_drag_controller_hover_highlights_hit_target_before_drag():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    overlay = RecordingOverlayRenderer(
        items=[
            {
                "id": "component:btn1",
                "type": "rect",
                "geometry": {"x": 20.0, "y": 20.0, "width": 14.0, "height": 14.0, "rotation": 0.0},
                "source_component_id": "btn1",
            }
        ]
    )
    statuses: list[str] = []
    controller = ViewDragController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        overlay_renderer=overlay,
        on_status=statuses.append,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.armed = True

    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (20, 20)})

    settings = interaction_service.get_settings(doc)
    assert settings["hovered_component_id"] == "btn1"
    assert statuses[-1] == "Ready to drag 'btn1'. Hold the left mouse button to move it."


def test_view_drag_controller_uses_selected_component_as_drag_source():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn2", x=50.0, y=20.0)
    controller_service.select_component(doc, "btn2")
    overlay = RecordingOverlayRenderer(
        items=[
            {
                "id": "component:btn1",
                "type": "rect",
                "geometry": {"x": 20.0, "y": 20.0, "width": 14.0, "height": 14.0, "rotation": 0.0},
                "source_component_id": "btn1",
            },
            {
                "id": "component:btn2",
                "type": "rect",
                "geometry": {"x": 50.0, "y": 20.0, "width": 14.0, "height": 14.0, "rotation": 0.0},
                "source_component_id": "btn2",
            },
        ]
    )
    statuses: list[str] = []
    controller = ViewDragController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        overlay_renderer=overlay,
        on_status=statuses.append,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.armed = True

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (20, 20)})

    assert controller.session is None
    assert controller_service.get_ui_context(doc)["selection"] == "btn2"
    assert statuses[-1] == "Drag is locked to selected 'btn2'. Click the selected component to move it."


def test_view_drag_controller_preserves_grab_offset_during_preview():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    overlay = RecordingOverlayRenderer(
        items=[
            {
                "id": "component:btn1",
                "type": "rect",
                "geometry": {"x": 20.0, "y": 20.0, "width": 14.0, "height": 14.0, "rotation": 0.0},
                "source_component_id": "btn1",
            }
        ]
    )
    controller = ViewDragController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        overlay_renderer=overlay,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.armed = True

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (23, 24)})
    preview = controller.update_preview_from_screen(33, 34)

    assert controller.session is not None
    assert controller.session.grab_offset_x == 3.0
    assert controller.session.grab_offset_y == 4.0
    assert preview["x"] == 30.0
    assert preview["y"] == 30.0


def test_view_drag_controller_clamps_and_snaps_to_bounds():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    interaction_service.update_settings(doc, {"grid_mm": 5.0, "snap_enabled": True})
    overlay = RecordingOverlayRenderer(
        items=[
            {
                "id": "component:btn1",
                "type": "rect",
                "geometry": {"x": 20.0, "y": 20.0, "width": 14.0, "height": 14.0, "rotation": 0.0},
                "source_component_id": "btn1",
            }
        ]
    )
    controller = ViewDragController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        overlay_renderer=overlay,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.armed = True
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (20, 20)})

    preview = controller.update_preview_from_screen(102.2, 81.1)

    assert preview == {
        "version": 1,
        "component_id": "btn1",
        "x": 100.0,
        "y": 80.0,
        "rotation": 0.0,
        "mode": "move",
        "snap_enabled": True,
        "grid_mm": 5.0,
        "validation": {
            "valid": False,
            "severity": "error",
            "status": "Out of bounds",
            "status_code": "out_of_bounds",
            "commit_allowed": False,
            "findings": preview["validation"]["findings"],
            "summary": preview["validation"]["summary"],
        },
    }


def test_view_drag_controller_commit_keeps_dragged_component_selected():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn2", x=50.0, y=20.0)
    controller_service.select_component(doc, "btn2")
    overlay = RecordingOverlayRenderer(
        items=[
            {
                "id": "component:btn2",
                "type": "rect",
                "geometry": {"x": 50.0, "y": 20.0, "width": 14.0, "height": 14.0, "rotation": 0.0},
                "source_component_id": "btn2",
            }
        ]
    )
    controller = ViewDragController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        overlay_renderer=overlay,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.armed = True

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (50, 20)})
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (65, 28)})
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "UP", "Button": "BUTTON1", "Position": (65, 28)})

    context = controller_service.get_ui_context(doc)
    settings = interaction_service.get_settings(doc)

    assert context["selection"] == "btn2"
    assert settings["active_interaction"] is None
    assert settings["move_component_id"] is None


def test_view_drag_controller_start_marks_selected_component_as_active():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    controller_service.select_component(doc, "btn1")
    controller = ViewDragController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        overlay_renderer=RecordingOverlayRenderer(),
    )
    controller._active_view = lambda _doc: FakeView()

    assert controller.start(doc) is True

    settings = interaction_service.get_settings(doc)
    assert settings["active_interaction"] == "drag"
    assert settings["move_component_id"] == "btn1"
    assert settings["hovered_component_id"] == "btn1"


def test_view_drag_controller_updates_cursor_during_hover_drag_and_cancel():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    overlay = RecordingOverlayRenderer(
        items=[
            {
                "id": "component:btn1",
                "type": "rect",
                "geometry": {"x": 20.0, "y": 20.0, "width": 14.0, "height": 14.0, "rotation": 0.0},
                "source_component_id": "btn1",
            }
        ]
    )
    controller = ViewDragController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        overlay_renderer=overlay,
    )
    view = FakeView()
    controller._active_view = lambda _doc: view

    assert controller.start(doc) is True
    ready_cursor = view.cursor
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (20, 20)})
    hover_cursor = view.cursor
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (20, 20)})
    drag_cursor = view.cursor
    controller.cancel()

    assert ready_cursor is not None
    assert hover_cursor is not None
    assert drag_cursor is not None
    assert view.cursor is None


def test_view_drag_controller_miss_publishes_hint_status():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    overlay = RecordingOverlayRenderer(
        items=[
            {
                "id": "component:btn1",
                "type": "rect",
                "geometry": {"x": 20.0, "y": 20.0, "width": 14.0, "height": 14.0, "rotation": 0.0},
                "source_component_id": "btn1",
            }
        ]
    )
    statuses: list[str] = []
    controller = ViewDragController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        overlay_renderer=overlay,
        on_status=statuses.append,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.armed = True
    controller_service.clear_selection(doc)

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (80, 70)})

    assert controller.session is None
    assert any("No component at that position" in s for s in statuses)


def test_view_drag_controller_second_click_during_active_drag_is_ignored():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    overlay = RecordingOverlayRenderer(
        items=[
            {
                "id": "component:btn1",
                "type": "rect",
                "geometry": {"x": 20.0, "y": 20.0, "width": 14.0, "height": 14.0, "rotation": 0.0},
                "source_component_id": "btn1",
            }
        ]
    )
    controller = ViewDragController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        overlay_renderer=overlay,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.armed = True

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (20, 20)})
    first_session = controller.session

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (25, 25)})

    assert controller.session is first_session


def test_view_drag_controller_can_reenter_after_cancel():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    overlay = RecordingOverlayRenderer(
        items=[
            {
                "id": "component:btn1",
                "type": "rect",
                "geometry": {"x": 20.0, "y": 20.0, "width": 14.0, "height": 14.0, "rotation": 0.0},
                "source_component_id": "btn1",
            }
        ]
    )
    controller = ViewDragController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        overlay_renderer=overlay,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.armed = True

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (20, 20)})
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (30, 30)})
    controller.handle_view_event({"Type": "SoKeyboardEvent", "State": "DOWN", "Key": "ESCAPE"})

    assert controller.session is None
    assert load_preview_state(doc) is None
    assert interaction_service.get_settings(doc)["move_component_id"] is None

    controller.doc = doc
    controller.view = FakeView()
    controller.armed = True
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (20, 20)})
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (34, 32)})
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "UP", "Button": "BUTTON1", "Position": (34, 32)})

    moved = controller_service.get_component(doc, "btn1")
    settings = interaction_service.get_settings(doc)
    assert moved["x"] == 34.0
    assert moved["y"] == 32.0
    assert settings["move_component_id"] is None
    assert settings["hovered_component_id"] is None


def test_view_drag_controller_remains_operable_after_full_sync():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    overlay = RecordingOverlayRenderer(
        items=[
            {
                "id": "component:btn1",
                "type": "rect",
                "geometry": {"x": 20.0, "y": 20.0, "width": 14.0, "height": 14.0, "rotation": 0.0},
                "source_component_id": "btn1",
            }
        ]
    )
    controller = ViewDragController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        overlay_renderer=overlay,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.armed = True

    controller_service.sync_document(doc)

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (20, 20)})
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (36, 27)})
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "UP", "Button": "BUTTON1", "Position": (36, 27)})

    moved = controller_service.get_component(doc, "btn1")
    assert moved["x"] == 36.0
    assert moved["y"] == 27.0


def test_view_drag_controller_uses_primary_selection_with_multi_select():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn2", x=50.0, y=20.0)
    controller_service.set_selected_component_ids(doc, ["btn1", "btn2"], primary_id="btn2")
    overlay = RecordingOverlayRenderer(
        items=[
            {
                "id": "component:btn2",
                "type": "rect",
                "geometry": {"x": 50.0, "y": 20.0, "width": 14.0, "height": 14.0, "rotation": 0.0},
                "source_component_id": "btn2",
            }
        ]
    )
    controller = ViewDragController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        overlay_renderer=overlay,
    )
    controller.doc = doc
    controller.view = FakeView()
    controller.armed = True

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (50, 20)})
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (62, 24)})
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "UP", "Button": "BUTTON1", "Position": (62, 24)})

    btn1 = controller_service.get_component(doc, "btn1")
    btn2 = controller_service.get_component(doc, "btn2")
    context = controller_service.get_ui_context(doc)
    assert btn1["x"] == 20.0
    assert btn1["y"] == 20.0
    assert btn2["x"] == 62.0
    assert btn2["y"] == 24.0
    assert context["selection"] == "btn2"

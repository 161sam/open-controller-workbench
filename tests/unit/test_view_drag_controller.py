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

    def addEventCallback(self, event_type, callback):
        handle = (event_type, callback, len(self.callbacks))
        self.callbacks.append(handle)
        return handle

    def removeEventCallback(self, event_type, handle):
        self.callbacks = [item for item in self.callbacks if item != handle]

    def getPoint(self, x, y):
        return (float(x), float(y), 0.0)


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
    assert statuses[-1] == "Ready to drag 'btn1'. Press and hold the left mouse button, then release to commit."


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
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (35, 28)})
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "UP", "Button": "BUTTON1", "Position": (35, 28)})

    context = controller_service.get_ui_context(doc)
    settings = interaction_service.get_settings(doc)

    assert context["selection"] == "btn1"
    assert settings["active_interaction"] is None


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

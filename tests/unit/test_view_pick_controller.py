from ocw_workbench.gui.interaction.view_pick_controller import ViewPickController
from ocw_workbench.services.controller_service import ControllerService


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
        self.items = items or []

    def refresh(self, doc):
        payload = {"items": list(self.items), "summary": {}}
        doc.OCWOverlayState = payload
        return payload


def test_view_pick_controller_selects_component_on_click():
    doc = FakeDocument()
    controller_service = ControllerService()
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
    selected: list[str] = []
    statuses: list[str] = []
    controller = ViewPickController(
        controller_service=controller_service,
        overlay_renderer=overlay,
        on_status=statuses.append,
        on_selected=selected.append,
    )
    view = FakeView()
    controller._active_view = lambda _doc: view
    controller.start(doc)

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (20, 20)})

    context = controller_service.get_ui_context(doc)
    assert context["selection"] == "btn1"
    assert selected == ["btn1"]
    assert any("Direct actions now target this component." in s for s in statuses)


def test_view_pick_controller_miss_does_not_change_selection():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn2", x=60.0, y=60.0)
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
    selected: list[str] = []
    controller = ViewPickController(
        controller_service=controller_service,
        overlay_renderer=overlay,
        on_selected=selected.append,
    )
    view = FakeView()
    controller._active_view = lambda _doc: view
    controller.start(doc)

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (80, 70)})

    assert selected == []
    context = controller_service.get_ui_context(doc)
    assert context["selection"] == "btn2"


def test_view_pick_controller_cancel_detaches_callbacks():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    overlay = RecordingOverlayRenderer()
    controller = ViewPickController(
        controller_service=controller_service,
        overlay_renderer=overlay,
    )
    view = FakeView()
    controller._active_view = lambda _doc: view
    controller.start(doc)
    assert len(view.callbacks) > 0

    controller.cancel()

    assert len(view.callbacks) == 0
    assert controller.doc is None


def test_view_pick_controller_mouse_move_does_not_select():
    doc = FakeDocument()
    controller_service = ControllerService()
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
    selected: list[str] = []
    controller = ViewPickController(
        controller_service=controller_service,
        overlay_renderer=overlay,
        on_selected=selected.append,
    )
    view = FakeView()
    controller._active_view = lambda _doc: view
    controller.start(doc)

    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (20, 20)})

    assert selected == []


def test_view_pick_controller_rebinds_when_view_is_recreated():
    doc = FakeDocument()
    controller_service = ControllerService()
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
    selected: list[str] = []
    controller = ViewPickController(
        controller_service=controller_service,
        overlay_renderer=overlay,
        on_selected=selected.append,
    )
    view_a = FakeView()
    view_b = FakeView()
    current_view = [view_a]
    controller._active_view = lambda _doc: current_view[0]

    assert controller.start(doc) is True
    current_view[0] = view_b

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (20, 20)})

    assert len(view_a.callbacks) == 0
    assert len(view_b.callbacks) == 3
    assert selected == ["btn1"]

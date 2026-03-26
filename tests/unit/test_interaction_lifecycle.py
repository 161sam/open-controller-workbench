from __future__ import annotations

import pytest

from ocw_workbench.gui.interaction.lifecycle import InteractionSessionManager, ViewEventCallbackRegistry
from ocw_workbench.gui.interaction.view_drag_controller import ViewDragController
from ocw_workbench.gui.interaction.view_place_controller import ViewPlaceController
from ocw_workbench.gui.interaction.view_place_preview import load_preview_state
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService
from ocw_workbench.workbench import ProductWorkbenchPanel


class FakeDocument:
    def __init__(self, name: str = "Controller") -> None:
        self.Name = name
        self.Objects = []
        self.recompute_count = 0

    def recompute(self) -> None:
        self.recompute_count += 1


class FakeView:
    def __init__(self) -> None:
        self.callbacks: list[tuple[str, object, int]] = []
        self.removed: list[tuple[str, object, int]] = []

    def addEventCallback(self, event_type, callback):
        handle = (event_type, callback, len(self.callbacks))
        self.callbacks.append(handle)
        return handle

    def removeEventCallback(self, event_type, handle):
        self.removed.append(handle)
        self.callbacks = [item for item in self.callbacks if item != handle]

    def getPoint(self, x, y):
        return (float(x), float(y), 0.0)


def _build_place_controller(doc: FakeDocument, view: FakeView, statuses: list[str]) -> ViewPlaceController:
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller = ViewPlaceController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        on_status=statuses.append,
    )
    controller._active_view = lambda current_doc: view if current_doc is doc else None
    return controller


def _build_drag_controller(doc: FakeDocument, view: FakeView, statuses: list[str]) -> ViewDragController:
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    controller = ViewDragController(
        controller_service=controller_service,
        interaction_service=interaction_service,
        on_status=statuses.append,
    )
    controller._active_view = lambda current_doc: view if current_doc is doc else None
    return controller


def test_view_event_callback_registry_is_idempotent_and_rebinds():
    registry = ViewEventCallbackRegistry()
    view_a = FakeView()
    view_b = FakeView()

    assert registry.attach(view_a, object()) is True
    assert len(view_a.callbacks) == 3

    assert registry.attach(view_a, registry._callback) is True
    assert len(view_a.callbacks) == 3

    assert registry.attach(view_b, registry._callback) is True
    assert len(view_a.callbacks) == 0
    assert len(view_b.callbacks) == 3

    registry.detach()
    registry.detach()
    assert len(view_b.callbacks) == 0


def test_interaction_session_manager_handles_switch_and_document_change():
    calls: list[tuple[str, str, bool]] = []
    doc_a = FakeDocument("A")
    doc_b = FakeDocument("B")

    def cancel_a(reason: str, publish_status: bool) -> None:
        calls.append(("a", reason, publish_status))

    def cancel_b(reason: str, publish_status: bool) -> None:
        calls.append(("b", reason, publish_status))

    manager = InteractionSessionManager()
    manager.activate("place", doc_a, cancel_a)
    manager.activate("drag", doc_b, cancel_b)
    manager.handle_document_changed(None)

    assert calls == [("a", "switch", False), ("b", "document_changed", False)]
    assert manager.active_name is None


def test_place_controller_cleanup_is_idempotent_and_clears_preview():
    doc = FakeDocument()
    view = FakeView()
    statuses: list[str] = []
    controller = _build_place_controller(doc, view, statuses)

    assert controller.start(doc, "omron_b3f_1000") is True
    controller.update_preview_from_screen(12.2, 18.7)
    assert load_preview_state(doc) is not None

    controller.cancel()
    controller.cancel()

    assert load_preview_state(doc) is None
    assert controller.doc is None
    assert len(view.callbacks) == 0
    assert statuses[-1] == "Cancelled"


def test_place_controller_rebinds_when_view_is_recreated():
    doc = FakeDocument()
    view_a = FakeView()
    view_b = FakeView()
    statuses: list[str] = []
    controller = _build_place_controller(doc, view_a, statuses)
    current_view = [view_a]
    controller._active_view = lambda current_doc: current_view[0] if current_doc is doc else None

    assert controller.start(doc, "omron_b3f_1000") is True
    current_view[0] = view_b
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (15, 10)})

    assert len(view_a.callbacks) == 0
    assert len(view_b.callbacks) == 3
    assert load_preview_state(doc)["x"] == 15.0


def test_place_controller_commit_error_cleans_up():
    doc = FakeDocument()
    view = FakeView()
    statuses: list[str] = []
    controller = _build_place_controller(doc, view, statuses)

    def fail_add_component(*args, **kwargs):
        raise RuntimeError("boom")

    controller.controller_service.add_component = fail_add_component  # type: ignore[method-assign]
    controller.start(doc, "omron_b3f_1000")
    controller.update_preview_from_screen(20.0, 20.0)

    with pytest.raises(RuntimeError):
        controller.commit()

    assert load_preview_state(doc) is None
    assert controller.doc is None
    assert len(view.callbacks) == 0
    assert statuses[-1] == "Interaction error"


def test_drag_controller_cancel_is_idempotent_and_restores_selection():
    doc = FakeDocument()
    view = FakeView()
    statuses: list[str] = []
    controller = _build_drag_controller(doc, view, statuses)

    assert controller.start(doc) is True
    controller.controller_service.select_component(doc, "btn1")
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (20, 20)})
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (35, 40)})
    assert load_preview_state(doc) is not None

    controller.cancel()
    controller.cancel()

    assert load_preview_state(doc) is None
    assert controller.session is None
    assert len(view.callbacks) == 0
    assert statuses[-1] == "Cancelled"


def test_workbench_second_tool_start_cleans_previous_session():
    doc = FakeDocument()
    service = ControllerService()
    workbench = ProductWorkbenchPanel(doc, controller_service=service)
    place_view = FakeView()
    drag_view = FakeView()
    workbench.place_controller._active_view = lambda current_doc: place_view if current_doc is doc else None
    workbench.drag_controller._active_view = lambda current_doc: drag_view if current_doc is doc else None
    service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0, "height": 30.0})
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)

    assert workbench.start_place_mode("omron_b3f_1000") is True
    workbench.place_controller.update_preview_from_screen(10.0, 10.0)
    assert load_preview_state(doc) is not None

    assert workbench.start_drag_mode() is True

    assert load_preview_state(doc) is None
    assert len(place_view.callbacks) == 0
    assert len(drag_view.callbacks) == 3
    assert workbench.interaction_manager.active_name == "drag"


def test_workbench_document_change_cleans_active_interaction():
    doc = FakeDocument("A")
    other_doc = FakeDocument("B")
    service = ControllerService()
    workbench = ProductWorkbenchPanel(doc, controller_service=service)
    view = FakeView()
    workbench.place_controller._active_view = lambda current_doc: view if current_doc is doc else None

    assert workbench.start_place_mode("omron_b3f_1000") is True
    workbench.place_controller.update_preview_from_screen(10.0, 10.0)
    workbench.handle_document_context_changed(other_doc)

    assert load_preview_state(doc) is None
    assert len(view.callbacks) == 0
    assert workbench.interaction_manager.active_name is None

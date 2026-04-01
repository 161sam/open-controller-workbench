from __future__ import annotations

from ocw_workbench.gui.interaction.suggested_addition_place_controller import SuggestedAdditionPlaceController
from ocw_workbench.gui.interaction.view_place_preview import load_preview_state
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.recompute_count = 0
        self.transactions: list[tuple[str, str | None]] = []

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


def test_suggested_addition_place_controller_cancel_clears_preview_and_state() -> None:
    doc = FakeDocument()
    service = ControllerService()
    interaction_service = InteractionService(service)
    statuses: list[str] = []

    service.create_from_template(doc, "pad_grid_4x4")
    controller = SuggestedAdditionPlaceController(
        controller_service=service,
        interaction_service=interaction_service,
        on_status=statuses.append,
    )
    view = FakeView()
    controller._active_view = lambda current_doc: view if current_doc is doc else None

    assert controller.start(doc, "display_header") is True
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (90, 12)})
    assert load_preview_state(doc) is not None

    controller.cancel()

    assert load_preview_state(doc) is None
    assert interaction_service.get_settings(doc)["active_interaction"] is None
    assert controller.session is None
    assert statuses[-1] == "Placement cancelled"


def test_suggested_addition_place_controller_commit_adds_components_and_finishes() -> None:
    doc = FakeDocument()
    service = ControllerService()
    interaction_service = InteractionService(service)

    service.create_from_template(doc, "pad_grid_4x4")
    controller = SuggestedAdditionPlaceController(
        controller_service=service,
        interaction_service=interaction_service,
    )
    controller.interaction_service.preview_validation_service.validate_components = lambda _doc, *, components: {
        "valid": True,
        "severity": None,
        "status": "Valid placement",
        "status_code": "valid",
        "commit_allowed": True,
        "findings": [],
        "summary": {"error_count": 0, "warning_count": 0, "total_count": 0},
    }
    view = FakeView()
    controller._active_view = lambda current_doc: view if current_doc is doc else None

    assert controller.start(doc, "display_header") is True
    assert load_preview_state(doc) is not None
    assert load_preview_state(doc)["validation"]["commit_allowed"] is True
    controller.commit()

    state = service.get_state(doc)
    displays = [component for component in state["components"] if component.get("properties", {}).get("suggested_addition_id") == "display_header"]

    assert len(displays) == 1
    assert displays[0]["zone_id"] == "display_header"
    assert controller.session is None
    assert interaction_service.get_settings(doc)["active_interaction"] is None


def test_suggested_addition_place_controller_sets_hover_active_and_invalid_target_states() -> None:
    doc = FakeDocument()
    service = ControllerService()
    interaction_service = InteractionService(service)
    service.create_from_template(doc, "encoder_module")
    controller = SuggestedAdditionPlaceController(
        controller_service=service,
        interaction_service=interaction_service,
    )
    controller.interaction_service.preview_validation_service.validate_components = lambda _doc, *, components: {
        "valid": True,
        "severity": None,
        "status": "Valid placement",
        "status_code": "valid",
        "commit_allowed": True,
        "findings": [],
        "summary": {"error_count": 0, "warning_count": 0, "total_count": 0},
    }
    view = FakeView()
    controller._active_view = lambda current_doc: view if current_doc is doc else None

    assert controller.start(doc, "display_header") is True
    bounds = controller.session.target_bounds
    assert isinstance(bounds, dict)

    initial_preview = controller.update_preview_from_screen(float(bounds["x"]), float(bounds["y"]))
    assert initial_preview is not None
    assert initial_preview["placement_feedback"]["active_zone_id"] == "display_header"
    assert initial_preview["placement_feedback"]["invalid_target"] is False

    moved_preview = controller.update_preview_from_screen(60.0, 40.0)

    assert moved_preview is not None
    assert moved_preview["placement_feedback"]["hover_zone_id"] is None
    assert moved_preview["placement_feedback"]["active_zone_id"] is None
    assert moved_preview["placement_feedback"]["invalid_target"] is True


def test_suggested_addition_place_controller_does_not_commit_outside_target_zone() -> None:
    doc = FakeDocument()
    service = ControllerService()
    interaction_service = InteractionService(service)
    service.create_from_template(doc, "encoder_module")
    controller = SuggestedAdditionPlaceController(
        controller_service=service,
        interaction_service=interaction_service,
    )
    view = FakeView()
    controller._active_view = lambda current_doc: view if current_doc is doc else None

    assert controller.start(doc, "display_header") is True
    before = list(service.get_state(doc)["components"])

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (60, 40)})
    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "UP", "Button": "BUTTON1", "Position": (60, 40)})

    assert service.get_state(doc)["components"] == before
    preview = load_preview_state(doc)
    assert preview is not None
    assert preview["placement_feedback"]["invalid_target"] is True


def test_suggested_addition_place_controller_drag_commits_on_release_in_active_zone() -> None:
    doc = FakeDocument()
    service = ControllerService()
    interaction_service = InteractionService(service)
    service.create_from_template(doc, "encoder_module")
    controller = SuggestedAdditionPlaceController(
        controller_service=service,
        interaction_service=interaction_service,
    )
    controller.interaction_service.preview_validation_service.validate_components = lambda _doc, *, components: {
        "valid": True,
        "severity": None,
        "status": "Valid placement",
        "status_code": "valid",
        "commit_allowed": True,
        "findings": [],
        "summary": {"error_count": 0, "warning_count": 0, "total_count": 0},
    }
    view = FakeView()
    controller._active_view = lambda current_doc: view if current_doc is doc else None

    assert controller.start(doc, "display_header") is True
    bounds = controller.session.target_bounds
    assert isinstance(bounds, dict)

    controller.handle_view_event({"Type": "SoMouseButtonEvent", "State": "DOWN", "Button": "BUTTON1", "Position": (90, 12)})
    controller.handle_view_event({"Type": "SoLocation2Event", "Position": (float(bounds["x"]), float(bounds["y"]))})

    assert controller.session is not None
    assert controller.session.is_dragging is True
    assert controller.session.current_preview_position == (float(bounds["x"]), float(bounds["y"]))

    controller.handle_view_event(
        {"Type": "SoMouseButtonEvent", "State": "UP", "Button": "BUTTON1", "Position": (float(bounds["x"]), float(bounds["y"]))}
    )

    state = service.get_state(doc)
    displays = [component for component in state["components"] if component.get("zone_id") == "display_header"]
    assert len(displays) == 1
    assert controller.session is None

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

    def addEventCallback(self, event_type, callback):
        handle = (event_type, callback, len(self.callbacks))
        self.callbacks.append(handle)
        return handle

    def removeEventCallback(self, event_type, handle):
        self.callbacks = [item for item in self.callbacks if item != handle]

    def getPoint(self, x, y):
        return (float(x), float(y), 0.0)


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
    assert "Out of bounds" in preview_label["label"]

from ocf_freecad.gui.interaction.selection import SelectionController
from ocf_freecad.services.controller_service import ControllerService
from ocf_freecad.services.interaction_service import InteractionService
from ocf_freecad.services.overlay_service import OverlayService


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.recompute_count = 0

    def recompute(self) -> None:
        self.recompute_count += 1


def test_overlay_service_builds_surface_zones_components_and_keepouts():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_from_template(doc, "encoder_module")
    controller_service.validate_layout(doc)

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    item_ids = {item["id"] for item in overlay["items"]}

    assert overlay["enabled"] is True
    assert "surface" in item_ids
    assert any(item_id.startswith("zone:") for item_id in item_ids)
    assert any(item_id.startswith("component:") for item_id in item_ids)
    assert any(item_id.startswith("keepout_top:") for item_id in item_ids)
    assert any(item_id.startswith("cutout:") for item_id in item_ids)


def test_overlay_service_includes_constraint_feedback_items():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(
        doc,
        {
            "id": "demo",
            "width": 100.0,
            "depth": 100.0,
            "height": 30.0,
            "top_thickness": 3.0,
            "mounting_holes": [{"id": "mh1", "x": 30.0, "y": 30.0, "diameter": 3.0}],
        },
    )
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=30.0, y=30.0)
    controller_service.validate_layout(doc)

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    error_items = [item for item in overlay["items"] if item.get("severity") == "error"]

    assert overlay["validation"]["summary"]["error_count"] >= 1
    assert any(item["id"] == "component:btn1" for item in error_items)
    assert any(item["type"] == "text_marker" for item in error_items)


def test_interaction_service_moves_with_snap_and_revalidates():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "alps_ec11e15204a3", component_id="enc1", x=12.2, y=18.7)
    controller_service.select_component(doc, "enc1")

    result = interaction_service.move_selected_component(doc, target_x=12.2, target_y=18.7, grid_mm=5.0, snap_enabled=True)
    component = controller_service.get_component(doc, "enc1")

    assert result["x"] == 10.0
    assert result["y"] == 20.0
    assert component["x"] == 10.0
    assert isinstance(result["validation"], dict)


def test_selection_controller_can_select_component_from_overlay_hit_test():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0)

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    selection = SelectionController(controller_service)
    component_id = selection.select_from_overlay(doc, overlay["items"], x=25.0, y=25.0)

    assert component_id == "btn1"
    assert controller_service.get_ui_context(doc)["selection"] == "btn1"

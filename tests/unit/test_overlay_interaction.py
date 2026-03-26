from ocw_workbench.gui.interaction.selection import SelectionController
from ocw_workbench.gui.overlay.renderer import OverlayRenderer
from ocw_workbench.gui.interaction.hit_test import hit_test_item
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService
from ocw_workbench.services.overlay_service import OverlayService


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


def test_overlay_renderer_refresh_stays_visual_only_without_recompute():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_from_template(doc, "encoder_module")
    renderer = OverlayRenderer(OverlayService(controller_service=controller_service))
    recomputes_before = doc.recompute_count

    payload = renderer.refresh(doc)

    assert payload["summary"]["visual_only"] is True
    assert doc.recompute_count == recomputes_before
    assert doc.OCWOverlayRender["build_duration_ms"] >= 0.0
    assert doc.OCWOverlayRender["render_duration_ms"] >= 0.0


def test_overlay_renderer_render_ignores_recompute_requests_for_visual_updates():
    doc = FakeDocument()
    renderer = OverlayRenderer()
    recomputes_before = doc.recompute_count

    payload = renderer.render(
        doc,
        {
            "enabled": True,
            "controller_height": 5.0,
            "items": [
                {"id": "surface", "type": "rect", "geometry": {"x": 10.0, "y": 10.0, "width": 20.0, "height": 10.0}, "style": {}},
            ],
            "summary": {"item_count": 1},
        },
        recompute=True,
    )

    assert payload["summary"]["visual_only"] is True
    assert doc.recompute_count == recomputes_before


def test_overlay_renderer_records_profile_metrics_when_enabled():
    doc = FakeDocument()
    doc.OCWDebugProfiling = {"enabled": True, "log": False}
    controller_service = ControllerService()
    controller_service.create_from_template(doc, "encoder_module")
    renderer = OverlayRenderer(OverlayService(controller_service=controller_service))

    renderer.refresh(doc)

    profile = doc.OCWPerformance["sections"]["overlay"]
    assert profile["build"]["duration_ms"] >= 0.0
    assert profile["render"]["duration_ms"] >= 0.0


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


def test_selection_controller_supports_additive_and_toggle_multi_select():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0)
    controller_service.add_component(doc, "alps_ec11e15204a3", component_id="enc1", x=50.0, y=25.0)
    selection = SelectionController(controller_service)

    selection.select_component(doc, "btn1")
    selection.select_component(doc, "enc1", additive=True)
    context = controller_service.get_ui_context(doc)
    selection.select_component(doc, "btn1", toggle=True)
    reduced = controller_service.get_ui_context(doc)

    assert context["selection"] == "btn1"
    assert context["selected_ids"] == ["btn1", "enc1"]
    assert reduced["selection"] == "enc1"
    assert reduced["selected_ids"] == ["enc1"]


def test_overlay_service_marks_primary_and_secondary_selected_components():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0)
    controller_service.add_component(doc, "alps_ec11e15204a3", component_id="enc1", x=50.0, y=25.0)
    controller_service.set_selected_component_ids(doc, ["btn1", "enc1"], primary_id="enc1")

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    primary_item = next(item for item in overlay["items"] if item["id"] == "component:enc1")
    secondary_item = next(item for item in overlay["items"] if item["id"] == "component:btn1")

    assert primary_item["style"]["kind"] == "component_selected"
    assert secondary_item["style"]["kind"] == "component_selected_secondary"
    assert overlay["summary"]["selected_count"] == 2


def test_overlay_service_and_hit_test_respect_rect_rotation():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0, rotation=90.0)

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    component_item = next(item for item in overlay["items"] if item["id"] == "component:btn1")
    keepout_item = next(item for item in overlay["items"] if item["id"] == "keepout_top:btn1")
    cutout_item = next(item for item in overlay["items"] if item["id"] == "cutout:btn1")

    assert component_item["geometry"]["rotation"] == 90.0
    assert keepout_item["geometry"]["rotation"] == 90.0
    assert cutout_item["geometry"]["rotation"] == 90.0

    selection = SelectionController(controller_service)
    component_id = selection.select_from_overlay(doc, overlay["items"], x=22.0, y=25.0)

    assert component_id == "btn1"


def test_overlay_service_builds_rotated_slot_cutout_for_fader():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "generic_45mm_linear_fader", component_id="fader1", x=60.0, y=40.0, rotation=90.0)

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    component_item = next(item for item in overlay["items"] if item["id"] == "component:fader1")
    cutout_item = next(item for item in overlay["items"] if item["id"] == "cutout:fader1")

    assert component_item["type"] == "rect"
    assert component_item["geometry"]["rotation"] == 90.0
    assert cutout_item["type"] == "slot"
    assert cutout_item["geometry"]["rotation"] == 90.0
    assert cutout_item["geometry"]["width"] == 53.0
    assert cutout_item["geometry"]["height"] == 2.2


def test_slot_hit_test_respects_rotation():
    item = {
        "id": "cutout:fader1",
        "type": "slot",
        "geometry": {"x": 60.0, "y": 40.0, "width": 53.0, "height": 2.2, "rotation": 90.0},
    }

    assert hit_test_item(item, x=60.0, y=50.0) is True
    assert hit_test_item(item, x=70.0, y=40.0) is False


def test_overlay_service_builds_large_overlay_for_pad_grid_variant_without_item_loss():
    doc = FakeDocument()
    controller_service = ControllerService()
    state = controller_service.create_from_variant(doc, "pad_grid_4x4_oled")

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    item_ids = {item["id"] for item in overlay["items"]}

    assert len(state["components"]) == 17
    assert overlay["summary"]["component_count"] == 17
    assert overlay["summary"]["item_count"] >= 17
    assert "component:oled_status" in item_ids
    assert "cutout:oled_status" in item_ids
    assert sum(1 for item_id in item_ids if item_id.startswith("component:")) == 17

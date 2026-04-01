from ocw_workbench.gui.interaction.selection import SelectionController
from ocw_workbench.gui.interaction.tool_manager import reset_tool_manager
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


def test_overlay_service_marks_hovered_component_before_drag():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0)
    controller_service.clear_selection(doc)
    interaction_service.set_hovered_component(doc, "btn1")

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    hovered_item = next(item for item in overlay["items"] if item["id"] == "component:btn1")

    assert hovered_item["style"]["kind"] == "component_hover"
    assert hovered_item["label"].endswith(">")
    assert overlay["summary"]["hovered_component_id"] == "btn1"
    assert overlay["summary"]["interaction_layer"] == "hover"


def test_overlay_service_prioritizes_manipulated_component_over_selection():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0)
    controller_service.select_component(doc, "btn1")
    interaction_service.update_settings(doc, {"move_component_id": "btn1", "hovered_component_id": "btn1"})

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    item = next(item for item in overlay["items"] if item["id"] == "component:btn1")

    assert item["style"]["kind"] == "component_manipulated"
    assert item["label"].endswith("#")
    assert overlay["summary"]["interaction_layer"] == "manipulation"


def test_overlay_service_marks_selected_context_component_when_selection_overlaps_context():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_from_template(doc, "encoder_module")
    controller_service.select_component(doc, "enc2")
    feedback = controller_service.resolve_suggested_addition_feedback(doc, "display_header")
    components = controller_service.build_suggested_addition(doc, "display_header")
    interaction_service.add_suggested_addition_preview(
        doc,
        addition_id="display_header",
        label="Add Display Header",
        components=components,
        target_zone_id="display_header",
        validation={
            "valid": True,
            "severity": None,
            "status": "Valid placement",
            "status_code": "valid",
            "commit_allowed": True,
            "findings": [],
            "summary": {"error_count": 0, "warning_count": 0, "total_count": 0},
        },
        placement_feedback={
            **feedback,
            "hover_zone_id": "display_header",
            "active_zone_id": "display_header",
            "invalid_target": False,
        },
    )

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    item = next(item for item in overlay["items"] if item["id"] == "component:enc2")

    assert item["style"]["kind"] == "component_selected_context"
    assert " *" in item["label"]


def test_overlay_service_marks_placement_target_context_and_group_frame() -> None:
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_from_template(doc, "encoder_module")
    feedback = controller_service.resolve_suggested_addition_feedback(doc, "display_header")
    components = controller_service.build_suggested_addition(doc, "display_header")
    interaction_service.add_suggested_addition_preview(
        doc,
        addition_id="display_header",
        label="Add Display Header",
        components=components,
        target_zone_id="display_header",
        validation={
            "valid": True,
            "severity": None,
            "status": "Valid placement",
            "status_code": "valid",
            "commit_allowed": True,
            "findings": [],
            "summary": {"error_count": 0, "warning_count": 0, "total_count": 0},
        },
        placement_feedback={
            **feedback,
            "hover_zone_id": "display_header",
            "active_zone_id": "display_header",
            "invalid_target": False,
        },
    )

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    placement_zone = next(item for item in overlay["items"] if item["id"] == "placement_zone:display_header")
    context_group = next(item for item in overlay["items"] if item["id"] == "placement_context_group")
    preview_group = next(item for item in overlay["items"] if item["id"].startswith("preview_group_frame:"))
    context_component = next(item for item in overlay["items"] if item["id"] == "component:enc2")

    assert placement_zone["style"]["kind"] == "placement_zone_active"
    assert context_group["style"]["kind"] == "placement_context_group"
    assert preview_group["style"]["kind"] == "preview_group_frame"
    assert context_component["style"]["kind"].startswith("component_context")
    assert overlay["summary"]["placement_active"] is True
    assert overlay["summary"]["placement_invalid"] is False


def test_overlay_service_marks_invalid_placement_target() -> None:
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_from_template(doc, "encoder_module")
    feedback = controller_service.resolve_suggested_addition_feedback(doc, "display_header")
    components = controller_service.build_suggested_addition(doc, "display_header")
    interaction_service.add_suggested_addition_preview(
        doc,
        addition_id="display_header",
        label="Add Display Header",
        components=components,
        target_zone_id="display_header",
        validation={
            "valid": False,
            "severity": "error",
            "status": "Out of bounds",
            "status_code": "out_of_bounds",
            "commit_allowed": False,
            "findings": [],
            "summary": {"error_count": 1, "warning_count": 0, "total_count": 1},
        },
        placement_feedback={
            **feedback,
            "hover_zone_id": "display_header",
            "active_zone_id": None,
            "invalid_target": True,
        },
    )

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)
    placement_zone = next(item for item in overlay["items"] if item["id"] == "placement_zone:display_header")

    assert placement_zone["style"]["kind"] == "placement_zone_invalid"
    assert overlay["summary"]["placement_invalid"] is True


def test_overlay_summary_reports_selection_layer_and_inline_handles():
    doc = FakeDocument()
    controller_service = ControllerService()
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0)
    controller_service.select_component(doc, "btn1")

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)

    assert overlay["summary"]["interaction_layer"] == "selection"
    assert overlay["summary"]["handles_visible"] is True


def test_overlay_hides_inline_handles_during_active_tool_priority():
    tools = reset_tool_manager()
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0)
    controller_service.select_component(doc, "btn1")

    assert tools.activate_tool("place:omron_b3f_1000", activator=lambda: True) is True
    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)

    assert overlay["summary"]["interaction_layer"] == "tool_active"
    assert overlay["summary"]["handles_visible"] is False
    assert not any(item["id"].startswith("inline_handle:") for item in overlay["items"])

    tools.clear_active_tool()


def test_overlay_hides_inline_handles_when_drag_interaction_is_active():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0, "top_thickness": 3.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0)
    controller_service.select_component(doc, "btn1")
    interaction_service.begin_interaction(doc, "drag")

    overlay = OverlayService(controller_service=controller_service).build_overlay(doc)

    assert overlay["summary"]["handles_visible"] is False
    assert not any(item["id"].startswith("inline_handle:") for item in overlay["items"])


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

from ocw_workbench.gui.panels.components_panel import ComponentsPanel
from ocw_workbench.gui.panels.constraints_panel import ConstraintsPanel
from ocw_workbench.gui.panels._common import current_text, widget_value
from ocw_workbench.gui.panels.create_panel import CreatePanel
from ocw_workbench.gui.panels.info_panel import InfoPanel
from ocw_workbench.gui.panels.layout_panel import LayoutPanel
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.workbench import ProductWorkbenchPanel


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.recompute_count = 0

    def recompute(self) -> None:
        self.recompute_count += 1


def _select_combo_by_suffix(combo, suffix: str) -> None:
    for index, item in enumerate(combo.items):
        if item.endswith(suffix):
            combo.setCurrentIndex(index)
            return
    raise AssertionError(f"Missing combo entry with suffix {suffix!r}")


def test_create_panel_supports_template_and_variant_flow():
    doc = FakeDocument()
    service = ControllerService()
    panel = CreatePanel(doc, controller_service=service)

    _select_combo_by_suffix(panel.form["template"], "(encoder_module)")
    panel.handle_template_changed()
    _select_combo_by_suffix(panel.form["variant"], "(encoder_module_compact)")

    preview = panel.refresh_preview()
    state = panel.create_controller()

    assert "Components: 4" in preview
    assert state["meta"]["template_id"] == "encoder_module"
    assert state["meta"]["variant_id"] == "encoder_module_compact"


def test_create_panel_renders_parameter_controls_and_uses_them_for_creation():
    doc = FakeDocument()
    service = ControllerService()
    panel = CreatePanel(doc, controller_service=service)

    _select_combo_by_suffix(panel.form["template"], "(fader_strip)")
    panel.handle_template_changed()
    panel.form["parameter_editor"].control_widget("fader_length").setCurrentIndex(0)
    panel.handle_parameter_widget_changed()
    state = panel.create_controller()

    assert "fader_length=45" in panel.form["preview"].text
    assert state["components"][0]["library_ref"] == "generic_45mm_linear_fader"


def test_create_panel_can_apply_template_parameter_preset():
    doc = FakeDocument()
    service = ControllerService()
    panel = CreatePanel(doc, controller_service=service)

    _select_combo_by_suffix(panel.form["template"], "(pad_grid_4x4)")
    panel.handle_template_changed()
    panel.form["parameter_editor"].parts["preset"].setCurrentIndex(2)
    panel.handle_apply_template_preset()

    preview = panel.refresh_preview()

    assert "pad_count_x=8" in preview
    assert "preset pad_grid_8x2" in preview


def test_create_panel_shows_active_project_state_after_creation():
    doc = FakeDocument()
    service = ControllerService()
    panel = CreatePanel(doc, controller_service=service)

    _select_combo_by_suffix(panel.form["template"], "(pad_grid_4x4)")
    panel.handle_template_changed()
    panel.create_controller()

    active_project = panel.form["active_project"].text

    assert "template pad_grid_4x4" in active_project
    assert "16 components" in active_project
    assert "layout grid" in active_project


def test_create_panel_reuses_saved_project_parameters_when_reopened():
    doc = FakeDocument()
    service = ControllerService()
    service.create_from_template(
        doc,
        "fader_strip",
        overrides={"parameters": {"fader_length": 45, "case_width": 220.0}},
    )

    panel = CreatePanel(doc, controller_service=service)

    assert current_text(panel.form["template"]).endswith("(fader_strip)")
    assert panel.form["parameter_editor"].control_widget("fader_length").currentText() == "45 mm"
    assert panel.form["parameter_status"].text == "Project parameters loaded from saved project metadata."
    assert "parameters ready" in panel.form["active_project"].text


def test_create_panel_uses_legacy_override_fallback_for_reparameterization():
    doc = FakeDocument()
    service = ControllerService()
    service.save_state(
        doc,
        {
            "controller": {"id": "demo", "width": 180.0, "depth": 100.0},
            "components": [],
            "meta": {
                "template_id": "pad_grid_4x4",
                "variant_id": None,
                "overrides": {
                    "parameters": {"pad_count_x": 8, "pad_count_y": 4},
                    "parameter_preset_id": "pad_grid_8x2",
                },
            },
        },
    )

    panel = CreatePanel(doc, controller_service=service)

    assert widget_value(panel.form["parameter_editor"].control_widget("pad_count_x")) == 8
    assert "legacy project overrides" in panel.form["parameter_status"].text
    assert "parameters legacy_fallback" in panel.form["active_project"].text


def test_create_panel_reparameterizes_existing_project_after_reopen():
    doc = FakeDocument()
    service = ControllerService()
    service.create_from_template(
        doc,
        "pad_grid_4x4",
        overrides={"parameters": {"pad_count_x": 4, "pad_count_y": 4}},
    )

    panel = CreatePanel(doc, controller_service=service)
    panel.form["parameter_editor"].control_widget("pad_count_x").setValue(8)
    panel.form["parameter_editor"].control_widget("pad_count_y").setValue(4)
    panel.handle_parameter_widget_changed()
    state = panel.apply_parameters()

    assert len(state["components"]) == 32
    assert state["meta"]["parameters"]["values"]["pad_count_x"] == 8
    assert state["meta"]["template_id"] == "pad_grid_4x4"


def test_create_panel_reports_missing_project_parameter_source():
    doc = FakeDocument()
    service = ControllerService()
    service.save_state(
        doc,
        {
            "controller": {"id": "demo", "width": 180.0, "depth": 100.0},
            "components": [{"id": "enc1", "type": "encoder", "library_ref": "alps_ec11e15204a3", "x": 10.0, "y": 10.0, "rotation": 0.0}],
            "meta": {"template_id": "missing_template", "variant_id": None},
        },
    )

    panel = CreatePanel(doc, controller_service=service)

    assert "missing_template" in panel.form["parameter_status"].text
    assert "parameters missing_source" in panel.form["active_project"].text
    assert panel.form["apply_parameters_button"].enabled is False


def test_layout_components_constraints_and_info_panels_share_document_state():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 200.0, "depth": 120.0})
    service.add_component(doc, "alps_ec11e15204a3")
    service.add_component(doc, "alps_ec11e15204a3")
    service.add_component(doc, "omron_b3f_1000")
    service.add_component(doc, "omron_b3f_1000")

    layout_panel = LayoutPanel(doc, controller_service=service)
    components_panel = ComponentsPanel(doc, controller_service=service)
    constraints_panel = ConstraintsPanel(doc, controller_service=service)
    info_panel = InfoPanel(doc, controller_service=service)

    layout_result = layout_panel.apply_auto_layout()
    report = constraints_panel.validate()
    component = components_panel.load_selected_component()
    components_panel.update_selected_component()
    info_text = info_panel.refresh()

    assert len(layout_result["placements"]) >= 1
    assert report["summary"]["error_count"] == 0
    assert component["id"] in info_text
    assert "Components: 4" in info_text


def test_info_panel_shows_multi_selection_count_and_ids():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 200.0, "depth": 120.0})
    service.add_component(doc, "alps_ec11e15204a3", component_id="enc1", x=20.0, y=20.0)
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=40.0, y=20.0)
    service.set_selected_component_ids(doc, ["enc1", "btn1"], primary_id="enc1")

    panel = InfoPanel(doc, controller_service=service)
    info_text = panel.refresh()

    assert panel.form["selection"].text == "enc1 (+1)"
    assert panel.form["selection_count"].text == "2"
    assert "Selected ids: enc1, btn1" in info_text


def test_layout_panel_reads_active_project_layout_defaults():
    doc = FakeDocument()
    service = ControllerService()
    service.create_from_template(doc, "pad_grid_4x4")

    layout_panel = LayoutPanel(doc, controller_service=service)

    assert current_text(layout_panel.form["preset"]) == "grid"
    assert widget_value(layout_panel.form["grid_mm"]) == 1.0
    assert widget_value(layout_panel.form["spacing_mm"]) == 36.0
    assert widget_value(layout_panel.form["padding_mm"]) == 10.0


def test_info_panel_updates_controller_geometry():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    info_panel = InfoPanel(doc, controller_service=service)

    info_panel.form["width"].setValue(190.0)
    info_panel.form["depth"].setValue(120.0)
    info_panel.form["surface_shape"].setCurrentIndex(1)
    info_panel.form["corner_radius"].setValue(8.0)
    info_panel.apply_controller_updates()

    state = service.get_state(doc)

    assert state["controller"]["width"] == 190.0
    assert state["controller"]["depth"] == 120.0
    assert state["controller"]["surface"]["shape"] == "rounded_rect"
    assert state["controller"]["surface"]["corner_radius"] == 8.0


def test_product_workbench_panel_orchestrates_iteration_flow():
    doc = FakeDocument()
    service = ControllerService()
    workbench = ProductWorkbenchPanel(doc, controller_service=service)

    _select_combo_by_suffix(workbench.create_panel.form["template"], "(encoder_module)")
    workbench.create_panel.handle_template_changed()
    workbench.create_panel.create_controller()
    workbench.layout_panel.apply_auto_layout()
    workbench.components_panel.add_component()

    context = service.get_ui_context(doc)
    constraints_text = workbench.constraints_panel.form["results"].text
    info_text = workbench.info_panel.form["info"].text

    assert context["template_id"] == "encoder_module"
    assert context["validation"] is not None
    assert context["component_count"] == 5
    assert "Errors:" in constraints_text
    assert "Components: 5" in info_text


def test_workbench_overlay_toggles_do_not_add_recomputes_for_visual_updates():
    doc = FakeDocument()
    service = ControllerService()
    workbench = ProductWorkbenchPanel(doc, controller_service=service)
    recomputes_before = doc.recompute_count

    workbench.toggle_overlay()
    workbench.toggle_measurements()
    workbench.toggle_constraint_overlay()

    assert doc.recompute_count == recomputes_before


def test_workbench_uses_clearer_status_text_for_create_and_overlay_actions():
    doc = FakeDocument()
    service = ControllerService()
    workbench = ProductWorkbenchPanel(doc, controller_service=service)

    _select_combo_by_suffix(workbench.create_panel.form["template"], "(encoder_module)")
    workbench.create_panel.handle_template_changed()
    workbench.create_panel.create_controller()
    created_status = workbench.form["status"].text

    workbench.toggle_overlay()
    overlay_status = workbench.form["status"].text

    assert "Controller created." in created_status
    assert "use Components or Auto Place" in created_status
    assert "Overlay" in overlay_status
    assert "without changing model geometry" in overlay_status


def test_components_panel_saves_position_without_move_step():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=10.0, y=10.0)
    panel = ComponentsPanel(doc, controller_service=service)

    panel.form["x"].setValue(42.0)
    panel.form["y"].setValue(26.0)
    panel.form["rotation"].setValue(15.0)
    panel.update_selected_component()

    component = service.get_component(doc, "btn1")

    assert component["x"] == 42.0
    assert component["y"] == 26.0
    assert component["rotation"] == 15.0


def test_components_panel_uses_clearer_action_labels_and_details():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=10.0, y=10.0)
    panel = ComponentsPanel(doc, controller_service=service)

    details = panel.form["details"].text

    assert panel.form["update_button"].text == "Apply Changes"
    assert panel.form["arm_move_button"].text == "Pick In 3D"
    assert "Groups: placement, generic metadata, and type-specific properties." in details


def test_components_panel_maps_selection_to_component_specific_editor():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    service.add_component(doc, "adafruit_oled_096_i2c_ssd1306", component_id="disp1", x=10.0, y=10.0)
    panel = ComponentsPanel(doc, controller_service=service)

    component = panel.load_selected_component()

    assert component["id"] == "disp1"
    assert panel.form["selected_id"].text == "ID: disp1"
    assert panel.form["selected_type"].text == "Type: display"
    assert panel.form["specific_editor"].control_widget("orientation").currentText() == "Portrait"


def test_components_panel_applies_component_metadata_and_reset():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    service.add_component(doc, "adafruit_oled_096_i2c_ssd1306", component_id="disp1", x=10.0, y=10.0)
    panel = ComponentsPanel(doc, controller_service=service)

    panel.form["label"].setText("Main Display")
    panel.form["tags"].setText("ui, primary")
    panel.form["visible"].setChecked(False)
    panel.form["specific_editor"].control_widget("orientation").setCurrentIndex(1)
    panel.form["specific_editor"].control_widget("bezel").setChecked(False)
    panel.update_selected_component()

    component = service.get_component(doc, "disp1")
    assert component["label"] == "Main Display"
    assert component["tags"] == ["ui", "primary"]
    assert component["visible"] is False
    assert component["properties"]["orientation"] == "landscape"
    assert component["properties"]["bezel"] is False

    panel.form["label"].setText("Temp Label")
    panel.form["specific_editor"].control_widget("bezel").setChecked(True)
    panel.handle_reset_clicked()

    assert panel.form["label"].text == "Main Display"
    assert panel.form["specific_editor"].control_widget("bezel").isChecked() is False


def test_components_panel_can_switch_fader_variant_from_property_panel():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    service.add_component(doc, "generic_45mm_linear_fader", component_id="f1", x=10.0, y=10.0)
    panel = ComponentsPanel(doc, controller_service=service)

    current_label = current_text(panel.form["library_ref"])
    for index, label in enumerate(panel.form["library_ref"].items):
        if label != current_label:
            panel.form["library_ref"].setCurrentIndex(index)
            break
    panel.update_selected_component()

    component = service.get_component(doc, "f1")

    assert component["library_ref"] != "generic_45mm_linear_fader"


def test_panels_expose_tooltips_for_key_workflows():
    doc = FakeDocument()
    service = ControllerService()
    layout_panel = LayoutPanel(doc, controller_service=service)
    components_panel = ComponentsPanel(doc, controller_service=service)
    info_panel = InfoPanel(doc, controller_service=service)
    constraints_panel = ConstraintsPanel(doc, controller_service=service)

    assert "placement strategy" in layout_panel.form["preset"].tooltip
    assert layout_panel.form["overlay_button"].text == "Overlay Visibility"
    assert "helper graphics" in layout_panel.form["overlay_button"].tooltip
    assert "Horizontal center position" in components_panel.form["x"].tooltip
    assert "3D view" in components_panel.form["arm_move_button"].tooltip
    assert "Overall controller width" in info_panel.form["width"].tooltip
    assert "spacing, overlap and edge-distance" in constraints_panel.form["validate_button"].tooltip

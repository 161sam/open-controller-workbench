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
        self.transactions: list[tuple[str, str | None]] = []

    def recompute(self) -> None:
        self.recompute_count += 1

    def openTransaction(self, label: str) -> None:
        self.transactions.append(("open", label))

    def commitTransaction(self) -> None:
        self.transactions.append(("commit", None))

    def abortTransaction(self) -> None:
        self.transactions.append(("abort", None))


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


def test_create_panel_uses_three_clear_sections_and_initial_state():
    doc = FakeDocument()
    service = ControllerService()
    panel = CreatePanel(doc, controller_service=service)

    assert panel.form["template_section"] is not None
    assert panel.form["geometry_section"] is not None
    assert panel.form["action_section"] is not None
    assert panel.form["document_actions_section"] is not None
    assert "No controller loaded yet" in panel.form["active_project"].text
    assert "Choose a template to load its default controller setup." == panel.form["template_summary"].text
    assert "Choose a template to unlock geometry controls." == panel.form["parameter_status"].text
    assert panel.form["create_button"].text == "Create Controller"
    assert panel.form["apply_parameters_button"].text == "Apply Geometry"


def test_create_panel_exposes_template_variant_and_geometry_controls():
    doc = FakeDocument()
    service = ControllerService()
    panel = CreatePanel(doc, controller_service=service)

    _select_combo_by_suffix(panel.form["template"], "(pad_grid_4x4)")
    panel.handle_template_changed()

    assert panel.form["template"] is not None
    assert panel.form["variant"] is not None
    assert panel.form["parameter_editor"].control_widget("case_width") is not None
    assert panel.form["parameter_editor"].control_widget("case_depth") is not None
    assert "Width" in panel.form["geometry_summary"].text
    assert "Height" in panel.form["geometry_summary"].text
    assert panel.form["create_button"].text == "Create Controller"


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


def test_workbench_uses_single_flow_context_summary_for_active_step():
    doc = FakeDocument()
    service = ControllerService()
    workbench = ProductWorkbenchPanel(doc, controller_service=service)

    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    workbench.refresh_all()
    workbench.focus_panel("constraints")
    validate_summary = workbench.form["context_summary"].text
    workbench.focus_panel("plugins")
    plugins_summary = workbench.form["context_summary"].text

    assert validate_summary.startswith("Validate |")
    assert "0 components" in validate_summary
    assert "validation clear" in validate_summary
    assert plugins_summary.startswith("Plugins |")


def test_workbench_exposes_single_navigation_and_all_main_sections_are_reachable():
    doc = FakeDocument()
    service = ControllerService()
    workbench = ProductWorkbenchPanel(doc, controller_service=service)

    assert workbench.form["primary_navigation"] == "stepper"
    assert workbench.form["navigation_count"] == 1
    assert workbench.form["navigation_items"] == ["Template", "Components", "Layout", "Validate", "Plugins"]
    assert workbench.form["content_host"] is workbench.form["stack"]
    assert "tab_widget" not in workbench.form

    for panel_name, expected_prefix in (
        ("create", "Template |"),
        ("components", "Components |"),
        ("layout", "Layout |"),
        ("constraints", "Validate |"),
        ("plugins", "Plugins |"),
    ):
        workbench.focus_panel(panel_name)
        assert workbench.form["active_step"] == panel_name
        assert workbench.form["context_summary"].text.startswith(expected_prefix)


def test_workbench_shell_builds_single_flow_regions_and_switches_visible_content():
    doc = FakeDocument()
    service = ControllerService()
    workbench = ProductWorkbenchPanel(doc, controller_service=service)

    assert workbench.form["header_bar"] is not None
    assert workbench.form["stepper_bar"] is not None
    assert workbench.form["content_host"] is not None
    assert workbench.form["footer_bar"] is not None
    assert workbench.form["content_host"].currentIndex() == 0

    workbench.focus_panel("layout")

    assert workbench.form["content_host"].currentIndex() == 2
    assert workbench.form["active_step"] == "layout"
    assert workbench.form["step_buttons"]["layout"].isChecked() is True



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

    assert panel.form["update_button"].text == "Apply"
    assert panel.form["arm_move_button"].text == "Pick In 3D"
    assert "Edit placement here. Re-run Validate after geometry changes." in details


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


def test_components_panel_enters_bulk_mode_for_multi_selection():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    service.add_component(doc, "generic_45mm_linear_fader", component_id="f1", x=10.0, y=10.0)
    service.add_component(doc, "generic_60mm_linear_fader", component_id="f2", x=20.0, y=10.0)
    service.set_selected_component_ids(doc, ["f1", "f2"], primary_id="f1")
    panel = ComponentsPanel(doc, controller_service=service)

    panel.refresh_components()

    assert panel.form["bulk_box"].visible is True
    assert panel.form["selector_box"].visible is False
    assert panel.form["bulk_count"].text == "Selected: 2"
    assert panel.form["bulk_types"].text == "Types: fader"
    assert "Bulk edit" in panel.form["bulk_summary"].text


def test_components_panel_uses_contextual_summary_and_quick_add_visibility():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    empty_panel = ComponentsPanel(doc, controller_service=service)

    assert "Start with Quick Add" in empty_panel.form["context_summary"].text
    assert empty_panel.form["empty_state_box"].visible is True
    assert "No components placed yet" in empty_panel.form["empty_state"].text
    assert empty_panel.form["empty_state_cta"].text == "Add first component"
    assert empty_panel.form["quick_add_box"].visible is True

    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=10.0, y=10.0)
    panel = ComponentsPanel(doc, controller_service=service)

    assert "Selected component ready" in panel.form["context_summary"].text
    assert panel.form["empty_state_box"].visible is False
    assert panel.form["quick_add_box"].visible is True


def test_components_panel_exposes_clear_work_sections_and_selected_state():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=10.0, y=10.0)
    panel = ComponentsPanel(doc, controller_service=service)

    assert panel.form["quick_add_section"] is not None
    assert panel.form["selected_component_box"] is not None
    assert panel.form["component_list_box"] is not None
    assert panel.form["bulk_section"] is not None
    assert panel.form["add_button"].text == "Add"
    assert panel.form["selected_empty_state"].visible is False
    assert panel.form["component_list_box"].visible is True
    assert panel.form["update_button"].text == "Apply"
    assert panel.form["arm_move_button"].text == "Pick In 3D"


def test_components_panel_applies_bulk_changes_to_selected_components():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    service.add_component(doc, "generic_45mm_linear_fader", component_id="f1", x=10.0, y=10.0)
    service.add_component(doc, "generic_60mm_linear_fader", component_id="f2", x=20.0, y=10.0)
    service.set_selected_component_ids(doc, ["f1", "f2"], primary_id="f1")
    panel = ComponentsPanel(doc, controller_service=service)

    panel.form["bulk_apply_rotation"].setChecked(True)
    panel.form["bulk_rotation"].setValue(30.0)
    panel.form["bulk_apply_cap_width"].setChecked(True)
    panel.form["bulk_cap_width"].setValue(14.0)
    panel.form["bulk_apply_label_prefix"].setChecked(True)
    panel.form["bulk_label_prefix"].setText("Deck")
    panel.bulk_update_selected_components()

    first = service.get_component(doc, "f1")
    second = service.get_component(doc, "f2")

    assert first["rotation"] == 30.0
    assert second["rotation"] == 30.0
    assert first["properties"]["cap_width"] == 14.0
    assert second["properties"]["cap_width"] == 14.0
    assert first["label"] == "Deck1"
    assert second["label"] == "Deck2"


def test_product_workbench_panel_aligns_multi_selection_with_single_operation():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=10.0, y=10.0)
    service.add_component(doc, "omron_b3f_1000", component_id="btn2", x=25.0, y=20.0)
    service.add_component(doc, "omron_b3f_1000", component_id="btn3", x=40.0, y=30.0)
    service.set_selected_component_ids(doc, ["btn1", "btn2", "btn3"], primary_id="btn2")
    workbench = ProductWorkbenchPanel(doc, controller_service=service)

    result = workbench.apply_selection_arrangement("align_center_x")

    assert result["selected_count"] == 3
    assert result["moved_count"] == 2
    state = service.get_state(doc)
    assert {component["x"] for component in state["components"]} == {25.0}
    assert doc.transactions[-2:] == [("open", "OCW Align Center X"), ("commit", None)]


def test_product_workbench_panel_distributes_multi_selection_horizontally():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=10.0, y=10.0)
    service.add_component(doc, "omron_b3f_1000", component_id="btn2", x=20.0, y=10.0)
    service.add_component(doc, "omron_b3f_1000", component_id="btn3", x=50.0, y=10.0)
    service.add_component(doc, "omron_b3f_1000", component_id="btn4", x=100.0, y=10.0)
    service.set_selected_component_ids(doc, ["btn1", "btn2", "btn3", "btn4"], primary_id="btn1")
    workbench = ProductWorkbenchPanel(doc, controller_service=service)

    result = workbench.apply_selection_arrangement("distribute_horizontal")

    assert result["selected_count"] == 4
    state = service.get_state(doc)
    by_id = {component["id"]: component for component in state["components"]}
    assert by_id["btn1"]["x"] == 10.0
    assert by_id["btn2"]["x"] == 40.0
    assert by_id["btn3"]["x"] == 70.0
    assert by_id["btn4"]["x"] == 100.0
    assert doc.transactions[-2:] == [("open", "OCW Distribute Horizontally"), ("commit", None)]


def test_product_workbench_panel_rotates_multi_selection_with_single_operation():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=10.0, y=10.0, rotation=0.0)
    service.add_component(doc, "omron_b3f_1000", component_id="btn2", x=30.0, y=10.0, rotation=90.0)
    service.set_selected_component_ids(doc, ["btn1", "btn2"], primary_id="btn1")
    workbench = ProductWorkbenchPanel(doc, controller_service=service)

    result = workbench.apply_selection_transform("rotate_cw_90")

    assert result["selected_count"] == 2
    assert result["moved_count"] == 2
    state = service.get_state(doc)
    by_id = {component["id"]: component for component in state["components"]}
    assert by_id["btn1"]["rotation"] == 90.0
    assert by_id["btn2"]["rotation"] == 180.0
    assert doc.transactions[-2:] == [("open", "OCW Rotate +90"), ("commit", None)]


def test_product_workbench_panel_mirrors_selection_vertically_via_rotation():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    service.add_component(doc, "adafruit_oled_096_i2c_ssd1306", component_id="disp1", x=20.0, y=20.0, rotation=90.0)
    service.set_selected_component_ids(doc, ["disp1"], primary_id="disp1")
    workbench = ProductWorkbenchPanel(doc, controller_service=service)

    result = workbench.apply_selection_transform("mirror_vertical")

    assert result["selected_count"] == 1
    assert result["moved_count"] == 1
    component = service.get_component(doc, "disp1")
    assert component["rotation"] == 270.0
    assert doc.transactions[-2:] == [("open", "OCW Mirror Vertically"), ("commit", None)]


def test_product_workbench_panel_duplicates_multi_selection_as_group():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=10.0, y=10.0)
    service.add_component(doc, "omron_b3f_1000", component_id="btn2", x=30.0, y=10.0)
    service.set_selected_component_ids(doc, ["btn1", "btn2"], primary_id="btn1")
    workbench = ProductWorkbenchPanel(doc, controller_service=service)

    result = workbench.duplicate_selection_once(offset_x=40.0, offset_y=5.0)

    assert result["created_count"] == 2
    state = service.get_state(doc)
    by_id = {component["id"]: component for component in state["components"]}
    assert by_id["btn3"]["x"] == 50.0
    assert by_id["btn3"]["y"] == 15.0
    assert by_id["btn4"]["x"] == 70.0
    assert by_id["btn4"]["y"] == 15.0
    assert state["meta"]["selected_ids"] == ["btn3", "btn4"]
    assert doc.transactions[-2:] == [("open", "OCW Duplicate Components"), ("commit", None)]


def test_product_workbench_panel_creates_grid_array_from_selection():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    service.add_component(doc, "generic_mpc_pad_30mm", component_id="pad1", x=10.0, y=10.0)
    service.set_selected_component_ids(doc, ["pad1"], primary_id="pad1")
    workbench = ProductWorkbenchPanel(doc, controller_service=service)

    result = workbench.array_selection_grid(rows=2, cols=2, spacing_x=20.0, spacing_y=20.0)

    assert result["created_count"] == 3
    state = service.get_state(doc)
    by_id = {component["id"]: component for component in state["components"]}
    assert by_id["pad2"]["x"] == 30.0
    assert by_id["pad2"]["y"] == 10.0
    assert by_id["pad3"]["x"] == 10.0
    assert by_id["pad3"]["y"] == 30.0
    assert by_id["pad4"]["x"] == 30.0
    assert by_id["pad4"]["y"] == 30.0
    assert doc.transactions[-2:] == [("open", "OCW Grid Array"), ("commit", None)]


def test_panels_expose_tooltips_for_key_workflows():
    doc = FakeDocument()
    service = ControllerService()
    layout_panel = LayoutPanel(doc, controller_service=service)
    components_panel = ComponentsPanel(doc, controller_service=service)
    info_panel = InfoPanel(doc, controller_service=service)
    constraints_panel = ConstraintsPanel(doc, controller_service=service)

    assert "placement strategy" in layout_panel.form["preset"].tooltip
    assert layout_panel.form["apply_button"].text == "Auto Place"
    assert layout_panel.form["rerun_button"].text == "Re-run Placement"
    assert layout_panel.form["overlay_button"].text == "Overlay Visibility"
    assert "helper graphics" in layout_panel.form["overlay_button"].tooltip
    assert "Horizontal center position" in components_panel.form["x"].tooltip
    assert "3D view" in components_panel.form["arm_move_button"].tooltip
    assert "Overall controller width" in info_panel.form["width"].tooltip
    assert "spacing, overlap and edge-distance" in constraints_panel.form["validate_button"].tooltip


def test_layout_panel_shows_compact_validation_and_overlay_state():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 160.0, "depth": 100.0, "height": 30.0})
    panel = LayoutPanel(doc, controller_service=service)

    assert panel.form["settings_box"] is not None
    assert panel.form["helper_box"] is not None
    assert panel.form["state_box"] is not None
    assert panel.form["validation_status"].text == "Validation has not been run yet."
    assert "Overlay on" in panel.form["overlay_status"].text


def test_constraints_panel_exposes_validate_step_state_and_release_hint():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 200.0, "depth": 120.0})
    service.add_component(doc, "alps_ec11e15204a3", component_id="enc1", x=20.0, y=20.0)
    panel = ConstraintsPanel(doc, controller_service=service)

    assert panel.form["review_value"].text == "Not run"
    assert "Run Validate" in panel.form["next_step"].text
    assert "Reviewing 1 component" in panel.form["validation_scope"].text
    assert panel.form["empty_state_box"].visible is True

    panel.validate()

    assert panel.form["review_value"].text == "Ready for Plugins"
    assert "Continue with Plugins" in panel.form["next_step"].text
    assert panel.form["success_box"].visible is True
    assert panel.form["success_title"].text == "Layout valid - ready for export"


def test_constraints_panel_shows_issue_list_and_clearer_focus_action_when_report_has_findings():
    doc = FakeDocument()
    service = ControllerService()
    service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0})
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=5.0, y=5.0)
    service.add_component(doc, "omron_b3f_1000", component_id="btn2", x=6.0, y=5.0)
    panel = ConstraintsPanel(doc, controller_service=service)

    report = panel.validate()

    assert report["summary"]["error_count"] > 0 or report["summary"]["warning_count"] > 0
    assert panel.form["list_box"].visible is True
    assert panel.form["detail_box"].visible is True
    assert panel.form["success_box"].visible is False
    assert panel.form["focus_button"].text == "Focus In Components"

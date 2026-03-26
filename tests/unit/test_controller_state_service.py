from __future__ import annotations

from ocw_workbench.services.controller_state_service import ControllerStateService


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.recompute_count = 0

    def recompute(self) -> None:
        self.recompute_count += 1


def test_state_service_updates_project_state_without_document_sync():
    service = ControllerStateService()
    doc = FakeDocument()

    service.create_controller(doc, {"id": "demo", "width": 180.0, "depth": 100.0})
    service.add_component(doc, "alps_ec11e15204a3", component_id="enc1", x=20.0, y=20.0)
    service.update_component(doc, "enc1", {"x": 55.0, "y": 35.0, "rotation": 15.0})

    state = service.get_state(doc)

    assert state["controller"]["id"] == "demo"
    assert state["components"][0]["x"] == 55.0
    assert state["components"][0]["y"] == 35.0
    assert state["components"][0]["rotation"] == 15.0
    assert doc.recompute_count == 0


def test_state_service_create_from_template_applies_layout_without_sync():
    service = ControllerStateService()
    doc = FakeDocument()

    state = service.create_from_template(doc, "pad_grid_4x4")

    assert len(state["components"]) == 16
    assert state["meta"]["layout"]["strategy"] == "grid"
    assert state["meta"]["layout"]["source"] == "template"
    assert len({(component["x"], component["y"]) for component in state["components"]}) == 16
    assert doc.recompute_count == 0


def test_state_service_persists_parameter_values_and_sources():
    service = ControllerStateService()
    doc = FakeDocument()

    state = service.create_from_template(
        doc,
        "display_nav_module",
        overrides={"parameters": {"display_size_inch": "1.3", "knob_diameter": 24}},
    )
    context = service.get_ui_context(doc)

    assert state["meta"]["parameters"]["values"]["display_size_inch"] == "1.3"
    assert state["meta"]["parameters"]["sources"]["display_size_inch"] == "user"
    assert context["parameters"]["values"]["knob_diameter"] == 24


def test_state_service_select_and_validate_touch_only_state():
    service = ControllerStateService()
    doc = FakeDocument()

    service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0})
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0)
    service.select_component(doc, "btn1")
    report = service.validate_layout(doc)
    context = service.get_ui_context(doc)

    assert report["summary"]["error_count"] == 0
    assert context["selection"] == "btn1"
    assert isinstance(context["validation"], dict)
    assert doc.recompute_count == 0


def test_state_service_supports_multi_selection_with_primary():
    service = ControllerStateService()
    doc = FakeDocument()

    service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0})
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0)
    service.add_component(doc, "alps_ec11e15204a3", component_id="enc1", x=45.0, y=25.0)
    state = service.set_selected_component_ids(doc, ["btn1", "enc1"], primary_id="enc1")

    assert state["meta"]["selection"] == "enc1"
    assert state["meta"]["selected_ids"] == ["enc1", "btn1"]
    assert service.get_selected_component_ids(doc) == ["enc1", "btn1"]


def test_state_service_toggle_and_clear_selection():
    service = ControllerStateService()
    doc = FakeDocument()

    service.create_controller(doc, {"id": "demo", "width": 120.0, "depth": 80.0, "height": 30.0})
    service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=25.0, y=25.0)
    service.add_component(doc, "alps_ec11e15204a3", component_id="enc1", x=45.0, y=25.0)
    service.select_component(doc, "btn1")
    toggled = service.toggle_selection(doc, "enc1", make_primary=False)
    reduced = service.toggle_selection(doc, "btn1")
    cleared = service.clear_selection(doc)

    assert toggled["meta"]["selected_ids"] == ["btn1", "enc1"]
    assert reduced["meta"]["selection"] == "enc1"
    assert reduced["meta"]["selected_ids"] == ["enc1"]
    assert cleared["meta"]["selection"] is None
    assert cleared["meta"]["selected_ids"] == []


def test_state_service_updates_component_metadata_and_properties():
    service = ControllerStateService()
    doc = FakeDocument()

    service.create_controller(doc, {"id": "demo", "width": 180.0, "depth": 100.0})
    service.add_component(doc, "adafruit_oled_096_i2c_ssd1306", component_id="disp1", x=30.0, y=20.0)
    service.update_component(
        doc,
        "disp1",
        {
            "label": "Main Display",
            "tags": ["ui", "primary"],
            "visible": False,
            "properties": {"orientation": "landscape", "bezel": False},
        },
    )

    component = service.get_component(doc, "disp1")

    assert component["label"] == "Main Display"
    assert component["tags"] == ["ui", "primary"]
    assert component["visible"] is False
    assert component["properties"] == {"orientation": "landscape", "bezel": False}
    assert doc.recompute_count == 0


def test_state_service_normalizes_nested_legacy_meta_defaults():
    service = ControllerStateService()
    doc = FakeDocument()

    service.save_state(
        doc,
        {
            "controller": {"id": "demo"},
            "components": [],
            "meta": {
                "template_id": "pad_grid_4x4",
                "parameters": {},
                "ui": {"snap_enabled": False},
            },
        },
    )

    context = service.get_ui_context(doc)

    assert context["template_id"] == "pad_grid_4x4"
    assert context["parameters"]["values"] == {}
    assert context["parameters"]["sources"] == {}
    assert context["parameters"]["preset_id"] is None
    assert context["ui"]["snap_enabled"] is False
    assert context["ui"]["overlay_enabled"] is True

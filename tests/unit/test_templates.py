from pathlib import Path

import pytest

from ocw_workbench.templates.generator import TemplateGenerator
from ocw_workbench.templates.loader import TemplateLoader
from ocw_workbench.templates.registry import TemplateRegistry
from ocw_workbench.templates.resolver import TemplateResolver
from ocw_workbench.utils.yaml_io import dump_yaml


def test_template_loader_loads_encoder_module():
    loader = TemplateLoader()
    template = loader.load("ocw_workbench/templates/library/encoder_module.yaml")

    assert template.id == "encoder_module"
    assert template.controller["surface"]["type"] == "rounded_rect"
    assert len(template.components) == 4


def test_template_registry_lists_default_templates():
    registry = TemplateRegistry()
    templates = registry.list_templates()
    ids = {template["template"]["id"] for template in templates}

    assert {
        "encoder_module",
        "transport_module",
        "fader_strip",
        "pad_grid_4x4",
        "display_nav_module",
    }.issubset(ids)
    assert "basic_templates_pack.mini_controller" in ids


def test_template_resolver_applies_overrides():
    registry = TemplateRegistry()
    resolver = TemplateResolver()
    template = registry.get_template("encoder_module")

    resolved = resolver.resolve(
        template,
        overrides={
            "controller": {"surface": {"width": 140}},
            "defaults": {"io_strategy": "matrix"},
            "components": {
                "update": {
                    "enc1": {"library_ref": "generic_ec11_encoder_with_push"},
                },
                "add": [
                    {"id": "enc5", "type": "encoder", "library_ref": "alps_ec11e15204a3", "zone": "main_controls"}
                ],
            },
        },
    )

    assert resolved["controller"]["surface"]["width"] == 140
    assert resolved["defaults"]["io_strategy"] == "matrix"
    assert any(component["id"] == "enc5" for component in resolved["components"])
    assert next(component for component in resolved["components"] if component["id"] == "enc1")["library_ref"] == "generic_ec11_encoder_with_push"


def test_template_generator_outputs_controller_project():
    generator = TemplateGenerator()

    project = generator.generate_from_template(
        "display_nav_module",
        overrides={"controller": {"height": 36}, "defaults": {"io_strategy": "direct_gpio"}},
    )

    assert project["controller"]["surface"]["shape"] == "rounded_rect"
    assert project["controller"]["height"] == 36
    assert len(project["components"]) == 5
    assert project["layout"]["strategy"] == "zone"
    assert project["components"][0]["io_strategy"] == "direct_gpio"
    assert project["components"][0]["zone_id"] is not None


def test_template_generator_applies_controller_shell_defaults():
    project = TemplateGenerator().generate_from_template("encoder_module")

    assert project["controller"]["wall_thickness"] == 3.0
    assert project["controller"]["bottom_thickness"] == 3.0
    assert project["controller"]["lid_inset"] == 1.5
    assert project["controller"]["inner_clearance"] == 0.35


def test_template_generator_preserves_pad_grid_layout_config():
    project = TemplateGenerator().generate_from_template("pad_grid_4x4")

    assert project["layout"]["strategy"] == "grid"
    assert project["layout"]["config"]["grid_mm"] == 1
    assert project["layout"]["config"]["padding_mm"] == 10
    assert project["layout"]["config"]["rows"] == 4
    assert project["layout"]["config"]["cols"] == 4
    assert project["layout"]["config"]["spacing_x_mm"] == 36
    assert project["layout"]["config"]["spacing_y_mm"] == 36


def test_parameterized_pad_grid_template_changes_component_count_and_case_size():
    project = TemplateGenerator().generate_from_template(
        "pad_grid_4x4",
        overrides={"parameters": {"pad_count_x": 8, "pad_count_y": 2, "case_width": 300.0, "case_depth": 110.0}},
    )

    assert len(project["components"]) == 16
    assert project["controller"]["width"] == 300.0
    assert project["controller"]["depth"] == 110.0
    assert project["layout"]["config"]["rows"] == 2
    assert project["layout"]["config"]["cols"] == 8
    assert project["components"][0]["group_id"] == "pad_matrix"
    assert project["components"][0]["group_role"] == "performance_pad_matrix"
    assert project["components"][0]["label"] == "Pad 1,1"
    assert project["components"][0]["tags"] == ["performance", "grid"]
    assert project["components"][-1]["label"] == "Pad 2,8"


def test_template_component_defaults_apply_by_zone_and_type():
    project = TemplateGenerator().generate_from_template("display_nav_module")

    display = next(component for component in project["components"] if component["id"] == "oled_status")
    button = next(component for component in project["components"] if component["id"] == "btn_back")

    assert display["tags"] == ["status", "template"]
    assert button["tags"] == ["navigation", "template"]


def test_parameterized_fader_template_switches_library_ref():
    project = TemplateGenerator().generate_from_template(
        "fader_strip",
        overrides={"parameters": {"fader_length": 45}},
    )

    assert project["components"][0]["library_ref"] == "generic_45mm_linear_fader"


def test_parameterized_display_template_switches_display_and_knob_profiles():
    project = TemplateGenerator().generate_from_template(
        "display_nav_module",
        overrides={"parameters": {"display_size_inch": "1.3", "knob_diameter": 24}},
    )

    display = next(component for component in project["components"] if component["id"] == "oled_status")
    left_encoder = next(component for component in project["components"] if component["id"] == "enc_left")

    assert display["library_ref"] == "adafruit_oled_130_i2c_ssd1306"
    assert left_encoder["library_ref"] == "generic_ec11_encoder_with_push_large_knob"


def test_unknown_template_id_raises_key_error():
    generator = TemplateGenerator()

    with pytest.raises(KeyError, match="Unknown template id: does_not_exist"):
        generator.generate_from_template("does_not_exist")


def test_missing_library_ref_in_template_raises_error(tmp_path: Path):
    template_path = tmp_path / "broken.yaml"
    dump_yaml(
        template_path,
        {
            "template": {"id": "broken", "name": "Broken", "description": "Broken template"},
            "controller": {"surface": {"type": "rectangle", "width": 80, "height": 40}},
            "components": [{"id": "x1", "type": "button"}],
        },
    )

    with pytest.raises(ValueError, match="missing a valid 'library_ref'"):
        TemplateLoader().load(template_path)


def test_template_loader_accepts_custom_fcstd_base_geometry(tmp_path: Path):
    template_path = tmp_path / "custom_fcstd.yaml"
    dump_yaml(
        template_path,
        {
            "template": {"id": "custom_fcstd_demo", "name": "Custom FCStd Demo", "description": "Demo"},
            "controller": {
                "width": 120.0,
                "depth": 80.0,
                "height": 30.0,
                "surface": {"type": "rectangle", "shape": "rectangle", "width": 120.0, "height": 80.0},
                "geometry": {
                    "base": {
                        "type": "custom_fcstd",
                        "filename": "/tmp/source.FCStd",
                        "target_ref": "Top::Face1",
                        "origin": {"type": "manual", "offset_x": 0.0, "offset_y": 0.0},
                    }
                },
            },
            "components": [],
            "metadata": {"source": {"type": "fcstd"}},
        },
    )

    loaded = TemplateLoader().load(template_path)

    assert loaded.controller["geometry"]["base"]["type"] == "custom_fcstd"


def test_template_loader_rejects_invalid_custom_fcstd_base_geometry(tmp_path: Path):
    template_path = tmp_path / "broken_custom_fcstd.yaml"
    dump_yaml(
        template_path,
        {
            "template": {"id": "broken_custom_fcstd", "name": "Broken", "description": "Broken"},
            "controller": {
                "width": 120.0,
                "depth": 80.0,
                "height": 30.0,
                "surface": {"type": "rectangle", "shape": "rectangle", "width": 120.0, "height": 80.0},
                "geometry": {"base": {"type": "custom_fcstd", "filename": "/tmp/source.FCStd"}},
            },
            "components": [],
        },
    )

    with pytest.raises(ValueError, match="target_ref"):
        TemplateLoader().load(template_path)


def test_template_generator_preserves_custom_fcstd_geometry():
    template = {
        "template": {"id": "custom_fcstd_demo", "name": "Custom FCStd Demo", "description": "Demo"},
        "controller": {
            "width": 120.0,
            "depth": 80.0,
            "height": 30.0,
            "surface": {"type": "rectangle", "shape": "rectangle", "width": 120.0, "height": 80.0},
            "geometry": {
                "base": {
                    "type": "custom_fcstd",
                    "filename": "/tmp/source.FCStd",
                    "target_ref": "Top::Face1",
                    "rotation_deg": 90.0,
                }
            },
        },
        "components": [],
        "zones": [],
        "layout": {},
        "constraints": {},
        "defaults": {},
    }

    project = TemplateGenerator().build_project_from_resolved_template(template)

    assert project["controller"]["geometry"]["base"]["type"] == "custom_fcstd"
    assert project["controller"]["geometry"]["base"]["filename"] == "/tmp/source.FCStd"
    assert project["controller"]["surface"]["shape"] == "rectangle"


def test_data_plugin_template_generates_controller_from_alias():
    generator = TemplateGenerator()

    project = generator.generate_from_template("mini_controller")

    assert project["template"]["id"] == "basic_templates_pack.mini_controller"
    assert len(project["components"]) == 3
    assert project["components"][0]["library_ref"].startswith("basic_components_pack.")

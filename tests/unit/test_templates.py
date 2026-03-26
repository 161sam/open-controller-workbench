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


def test_template_generator_preserves_pad_grid_layout_config():
    project = TemplateGenerator().generate_from_template("pad_grid_4x4")

    assert project["layout"]["strategy"] == "grid"
    assert project["layout"]["config"]["rows"] == 4
    assert project["layout"]["config"]["cols"] == 4
    assert project["layout"]["config"]["spacing_x_mm"] == 36
    assert project["layout"]["config"]["spacing_y_mm"] == 36


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


def test_data_plugin_template_generates_controller_from_alias():
    generator = TemplateGenerator()

    project = generator.generate_from_template("mini_controller")

    assert project["template"]["id"] == "basic_templates_pack.mini_controller"
    assert len(project["components"]) == 3
    assert project["components"][0]["library_ref"].startswith("basic_components_pack.")

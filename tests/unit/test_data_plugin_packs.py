from __future__ import annotations

from pathlib import Path

import pytest

from ocw_workbench.library.manager import ComponentLibraryManager
from ocw_workbench.services.plugin_service import reset_plugin_service
from ocw_workbench.templates.generator import TemplateGenerator
from ocw_workbench.utils.yaml_io import dump_yaml
from ocw_workbench.variants.generator import VariantGenerator


@pytest.fixture(autouse=True)
def _reset_plugin_service_after_test():
    yield
    reset_plugin_service()


def test_data_plugin_component_is_namespaced_and_available_by_alias():
    manager = ComponentLibraryManager()

    component = manager.get_component("rotary_encoder_12mm")

    assert component["id"] == "basic_components_pack.rotary_encoder_12mm"
    assert component["manufacturer"] == "ALPS"


def test_data_plugin_template_builds_project():
    project = TemplateGenerator().generate_from_template("mini_controller")

    assert project["template"]["id"] == "basic_templates_pack.mini_controller"
    assert [component["id"] for component in project["components"]] == ["enc1", "btn1", "oled1"]


def test_data_plugin_variant_applies_overrides_and_additions():
    project = VariantGenerator().generate_from_variant("simple_variant")

    enc1 = next(component for component in project["components"] if component["id"] == "enc1")
    assert enc1["x"] == 30.0
    assert any(component["id"] == "btn2" for component in project["components"])


def test_invalid_data_plugin_file_is_skipped_without_breaking_pack(tmp_path: Path):
    internal_root = tmp_path / "internal"
    plugin_dir = internal_root / "safe_pack"
    components_dir = plugin_dir / "components"
    components_dir.mkdir(parents=True)
    dump_yaml(
        plugin_dir / "plugin.yaml",
        {
            "plugin": {
                "id": "safe_pack",
                "name": "Safe Pack",
                "version": "0.1.0",
                "api_version": "1.0",
                "type": "component_pack",
            },
            "entrypoints": {"components": "components"},
            "capabilities": ["components"],
            "dependencies": [],
        },
    )
    dump_yaml(
        components_dir / "valid.yaml",
        {
            "id": "valid_knob",
            "type": "encoder",
            "manufacturer": "Test",
            "mechanical": {},
            "electrical": {},
            "ui": {"category": "controls"},
        },
    )
    dump_yaml(
        components_dir / "broken.yaml",
        {
            "type": "encoder",
        },
    )

    reset_plugin_service(internal_root=internal_root, external_root=tmp_path / "external", state_base_dir=tmp_path)
    ids = {component["id"] for component in ComponentLibraryManager().list_components()}

    assert "safe_pack.valid_knob" in ids
    assert "safe_pack.broken" not in ids

from __future__ import annotations

from pathlib import Path

import pytest

from ocw_workbench.library.manager import ComponentLibraryManager
from ocw_workbench.plugins.loader import PluginLoader
from ocw_workbench.plugins.manifest import load_plugin_manifest
from ocw_workbench.services.plugin_service import reset_plugin_service
from ocw_workbench.templates.registry import TemplateRegistry
from ocw_workbench.utils.yaml_io import dump_yaml
from ocw_workbench.variants.registry import VariantRegistry


@pytest.fixture(autouse=True)
def _reset_plugin_service_after_test():
    yield
    reset_plugin_service()


def test_plugin_manifest_loads_internal_template_pack() -> None:
    manifest = load_plugin_manifest("ocw_workbench/plugins/internal/default_templates/manifest.yaml")

    assert manifest.plugin_id == "default_templates"
    assert manifest.plugin_type == "template_pack"
    assert manifest.entrypoints.templates == "../../../templates/library"


def test_plugin_manifest_rejects_incompatible_api_version(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    dump_yaml(
        manifest_path,
        {
            "plugin": {
                "id": "broken_api",
                "name": "Broken",
                "version": "0.1.0",
                "api_version": "2.0",
                "type": "template_pack",
            },
            "entrypoints": {"templates": "templates"},
            "capabilities": ["templates"],
            "dependencies": [],
        },
    )

    with pytest.raises(ValueError, match="incompatible"):
        load_plugin_manifest(manifest_path)


def test_plugin_loader_loads_internal_plugins_and_registers_sources_and_exporters() -> None:
    loader = PluginLoader()

    registry = loader.load_all()

    plugin_ids = {descriptor.plugin_id for descriptor in registry.plugin_descriptors()}
    assert {
        "core_components",
        "default_templates",
        "default_variants",
        "default_exporters",
        "basic_components_pack",
        "basic_templates_pack",
        "basic_variants_pack",
    } <= plugin_ids
    assert any(path.name == "components" for path in registry.component_sources())
    assert any(path.name == "library" for path in registry.template_sources())
    assert any(path.name == "library" for path in registry.variant_sources())
    assert any(path.name == "templates" for path in registry.template_sources())
    assert any(path.name == "variants" for path in registry.variant_sources())
    assert "bom_yaml" in registry.exporters()
    assert "kicad_layout" in registry.exporters()


def test_plugin_loader_skips_invalid_plugins(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "invalid_plugin"
    plugin_dir.mkdir(parents=True)
    dump_yaml(
        plugin_dir / "manifest.yaml",
        {
            "plugin": {
                "id": "broken",
                "name": "Broken",
                "version": "0.1.0",
                "api_version": "1.0",
                "type": "not_a_plugin_type",
            },
            "entrypoints": {},
            "capabilities": [],
            "dependencies": [],
        },
    )

    loader = PluginLoader(internal_root=tmp_path, external_root=tmp_path / "empty")
    registry = loader.load_all()

    assert registry.plugin_descriptors() == []
    assert any("Failed to load plugin manifest" in warning for warning in loader.warnings)


def test_default_registries_load_data_via_plugin_service() -> None:
    reset_plugin_service()

    components = ComponentLibraryManager().list_components()
    templates = TemplateRegistry().list_templates()
    variants = VariantRegistry().list_variants()

    assert any(component["id"] == "alps_ec11e15204a3" for component in components)
    assert any(component["id"] == "basic_components_pack.rotary_encoder_12mm" for component in components)
    assert any(template["template"]["id"] == "encoder_module" for template in templates)
    assert any(template["template"]["id"] == "basic_templates_pack.mini_controller" for template in templates)
    assert any(variant["variant"]["id"] == "encoder_module_compact" for variant in variants)
    assert any(variant["variant"]["id"] == "basic_variants_pack.simple_variant" for variant in variants)


def test_plugin_loader_supports_plugin_yaml_files(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "yaml_plugin"
    plugin_dir.mkdir(parents=True)
    dump_yaml(
        plugin_dir / "plugin.yaml",
        {
            "plugin": {
                "id": "yaml_plugin",
                "name": "YAML Plugin",
                "version": "0.1.0",
                "api_version": "1.0",
                "type": "component_pack",
            },
            "entrypoints": {"components": "components"},
            "capabilities": ["components"],
            "dependencies": [],
        },
    )
    (plugin_dir / "components").mkdir()

    registry = PluginLoader(internal_root=tmp_path, external_root=tmp_path / "empty").load_all()

    assert {descriptor.plugin_id for descriptor in registry.plugin_descriptors()} == {"yaml_plugin"}


def test_plugin_dependency_is_required(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "dependent_plugin"
    plugin_dir.mkdir(parents=True)
    dump_yaml(
        plugin_dir / "manifest.yaml",
        {
            "plugin": {
                "id": "dependent",
                "name": "Dependent",
                "version": "0.1.0",
                "api_version": "1.0",
                "type": "template_pack",
            },
            "entrypoints": {"templates": "templates"},
            "capabilities": ["templates"],
            "dependencies": ["missing_plugin"],
        },
    )
    (plugin_dir / "templates").mkdir()

    loader = PluginLoader(internal_root=tmp_path, external_root=tmp_path / "empty")
    registry = loader.load_all()

    assert registry.plugin_descriptors() == []
    assert any("dependencies are missing" in warning for warning in loader.warnings)

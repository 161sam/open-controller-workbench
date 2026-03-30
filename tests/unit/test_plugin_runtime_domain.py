from __future__ import annotations

from pathlib import Path

import pytest

import ocw_workbench.components.adapter as component_adapter_module
import ocw_workbench.templates.adapter as template_adapter_module
import ocw_workbench.variants.adapter as variant_adapter_module
from ocw_workbench.components.adapter import get_component_source_entries
from ocw_workbench.plugins.activation import activate_plugin
from ocw_workbench.plugins.context import PluginContext
from ocw_workbench.plugins.loader import PluginLoader
from ocw_workbench.plugins.registry import ExtensionRegistry, Plugin
from ocw_workbench.plugins.settings import OCW_STRICT_PLUGIN_MODE
from ocw_workbench.templates.adapter import get_template_source_entries
from ocw_workbench.utils.yaml_io import dump_yaml
from ocw_workbench.variants.adapter import get_variant_source_entries


def test_scan_plugins_loads_domain_plugin_from_repo_root() -> None:
    plugins = PluginLoader().scan_plugins()

    plugin_ids = {plugin.plugin_id for plugin in plugins}

    assert "midicontroller" in plugin_ids
    assert "bike_trailer" in plugin_ids
    plugin = next(plugin for plugin in plugins if plugin.plugin_id == "midicontroller")
    assert plugin.plugin_type == "domain"
    assert plugin.domain_type == "midicontroller"
    assert plugin.provides_templates is True
    assert plugin.provides_components is True
    assert plugin.provides_commands is False
    assert plugin.dependencies == ("ocw_kicad",)


def test_loader_load_all_keeps_existing_plugins_and_registers_domain_plugin() -> None:
    registry = PluginLoader().load_all()

    assert registry.has_plugin("midicontroller")
    assert registry.has_plugin("bike_trailer")
    assert registry.has_plugin("basic_templates_pack")
    assert {plugin.plugin_id for plugin in registry.get_domain_plugins()} == {"midicontroller", "bike_trailer"}
    assert registry.get_active_plugin() is not None
    assert registry.get_active_plugin().plugin_id == "midicontroller"


def test_activation_sets_active_domain_plugin() -> None:
    registry = ExtensionRegistry()
    registry.register_plugin(
        Plugin(
            plugin_id="midicontroller",
            name="MIDI Controller",
            version="0.1.0",
            plugin_type="domain",
            dependencies=("ocw_kicad",),
        )
    )

    active = activate_plugin("midicontroller", registry=registry)

    assert active.plugin_id == "midicontroller"
    assert registry.get_active_plugin() == active


def test_activation_rejects_non_domain_plugin() -> None:
    registry = ExtensionRegistry()
    registry.register_plugin(
        Plugin(
            plugin_id="default_exporters",
            name="Default Exporters",
            version="0.1.0",
            plugin_type="exporter",
        )
    )

    with pytest.raises(ValueError, match="not a domain plugin"):
        activate_plugin("default_exporters", registry=registry)


def test_scan_plugins_supports_simple_plugin_yaml(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins" / "demo_domain"
    plugin_dir.mkdir(parents=True)
    dump_yaml(
        plugin_dir / "plugin.yaml",
        {
            "id": "demo_domain",
            "type": "domain",
            "name": "Demo Domain",
            "version": "0.1.0",
            "depends_on": ["dep_a"],
        },
    )

    plugins = PluginLoader(domain_root=tmp_path / "plugins").scan_plugins()

    assert [plugin.plugin_id for plugin in plugins] == ["demo_domain"]
    assert plugins[0].dependencies == ("dep_a",)


def test_template_and_component_adapters_prefer_active_plugin_roots(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugins" / "demo_domain"
    (plugin_root / "templates").mkdir(parents=True)
    (plugin_root / "components").mkdir(parents=True)
    registry = ExtensionRegistry()
    registry.register_plugin(
        Plugin(
            plugin_id="demo_domain",
            name="Demo Domain",
            version="0.1.0",
            plugin_type="domain",
            domain_type="demo_domain",
            provides_templates=True,
            provides_components=True,
            root_path=plugin_root,
        )
    )
    registry.register_source("templates", tmp_path / "global_templates")
    registry.register_source("components", tmp_path / "global_components")
    registry.set_active_plugin("demo_domain")

    context = PluginContext(registry=registry)

    assert context.get_active_domain() == "demo_domain"
    assert context.template_roots()[0] == plugin_root / "templates"
    assert context.component_registries()[0] == plugin_root / "components"


def test_registry_returns_commands_for_active_plugin(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugins" / "demo_domain"
    (plugin_root / "commands").mkdir(parents=True)
    registry = ExtensionRegistry()
    registry.register_plugin(
        Plugin(
            plugin_id="demo_domain",
            name="Demo Domain",
            version="0.1.0",
            plugin_type="domain",
            domain_type="demo_domain",
            provides_commands=True,
            root_path=plugin_root,
        )
    )
    registry.set_active_plugin("demo_domain")

    command_set = registry.get_commands_for_active_plugin()

    assert command_set["plugin_id"] == "demo_domain"
    assert command_set["root"] == str(plugin_root / "commands")


def test_adapters_prefer_midicontroller_shadow_data_from_repo() -> None:
    registry = PluginLoader().load_all()
    activate_plugin("midicontroller")
    active_plugin = registry.get_active_plugin()

    template_sources = get_template_source_entries()
    component_sources = get_component_source_entries()
    variant_sources = get_variant_source_entries()

    assert active_plugin is not None
    assert active_plugin.plugin_id == "midicontroller"
    assert template_sources[0].plugin_id == "midicontroller"
    assert template_sources[0].path == Path("plugins/plugin_midicontroller/templates").resolve()
    assert component_sources[0].plugin_id == "midicontroller"
    assert component_sources[0].path == Path("plugins/plugin_midicontroller/components").resolve()
    assert variant_sources[0].plugin_id == "midicontroller"
    assert variant_sources[0].path == Path("plugins/plugin_midicontroller/variants").resolve()


def test_strict_mode_uses_only_plugin_roots(monkeypatch) -> None:
    activate_plugin("midicontroller")
    monkeypatch.setattr(template_adapter_module, "OCW_STRICT_PLUGIN_MODE", True)
    monkeypatch.setattr(component_adapter_module, "OCW_STRICT_PLUGIN_MODE", True)
    monkeypatch.setattr(variant_adapter_module, "OCW_STRICT_PLUGIN_MODE", True)

    template_sources = get_template_source_entries()
    component_sources = get_component_source_entries()
    variant_sources = get_variant_source_entries()

    assert template_sources[0].plugin_id == "midicontroller"
    assert component_sources[0].plugin_id == "midicontroller"
    assert variant_sources[0].plugin_id == "midicontroller"
    assert all(source.plugin_id is not None for source in template_sources)
    assert all(source.plugin_id is not None for source in component_sources)
    assert all(source.plugin_id is not None for source in variant_sources)


def test_registry_command_metadata_and_mapping(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugins" / "demo_domain"
    commands_root = plugin_root / "commands"
    commands_root.mkdir(parents=True)
    (commands_root / "build_frame.py").write_text("class BuildFrame: pass\n", encoding="utf-8")

    registry = ExtensionRegistry()
    registry.register_plugin(
        Plugin(
            plugin_id="demo_domain",
            name="Demo Domain",
            version="0.1.0",
            plugin_type="domain",
            provides_commands=True,
            root_path=plugin_root,
        )
    )
    registry.set_active_plugin("demo_domain")

    command_set = registry.get_commands_for_active_plugin()

    assert command_set["commands"]["build_frame"]["label"] == "Build Frame"
    assert command_set["commands"]["build_frame"]["icon"] == "default"
    assert command_set["commands"]["build_frame"]["category"] == "plugin"
    assert command_set["commands"]["build_frame"]["plugin_id"] == "demo_domain"
    assert "Build Frame" in command_set["commands"]["build_frame"]["tooltip"]
    assert registry.command_plugin_mapping()["build_frame"] == "demo_domain"

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from ocw_workbench.plugin_api.types import PluginDescriptor, PluginEntrypoints, PluginType
from ocw_workbench.plugin_api.versioning import PLUGIN_API_VERSION, is_api_compatible
from ocw_workbench.utils.yaml_io import load_yaml

PLUGIN_TYPES: set[str] = {
    "component_pack",
    "template_pack",
    "variant_pack",
    "exporter",
    "layout_strategy",
    "constraint_pack",
    "workflow",
    "ui_extension",
}


def load_plugin_manifest(path: str | Path) -> PluginDescriptor:
    file_path = Path(path)
    payload = load_yaml(file_path)
    plugin = payload.get("plugin")
    entrypoints = payload.get("entrypoints", {})
    capabilities = payload.get("capabilities", [])
    dependencies = payload.get("dependencies", [])
    if not isinstance(plugin, dict):
        raise ValueError(f"Plugin manifest is missing 'plugin' section: {file_path}")
    if not isinstance(entrypoints, dict):
        raise ValueError(f"Plugin manifest entrypoints must be a mapping: {file_path}")
    if not isinstance(capabilities, list):
        raise ValueError(f"Plugin manifest capabilities must be a list: {file_path}")
    if not isinstance(dependencies, list):
        raise ValueError(f"Plugin manifest dependencies must be a list: {file_path}")

    plugin_id = _require_str(plugin.get("id"), "plugin.id", file_path)
    name = _require_str(plugin.get("name"), "plugin.name", file_path)
    version = _require_str(plugin.get("version"), "plugin.version", file_path)
    api_version = _require_str(plugin.get("api_version"), "plugin.api_version", file_path)
    plugin_type = _require_str(plugin.get("type"), "plugin.type", file_path)
    if plugin_type not in PLUGIN_TYPES:
        raise ValueError(f"Unsupported plugin type '{plugin_type}' in {file_path}")
    if not is_api_compatible(api_version):
        raise ValueError(
            f"Plugin '{plugin_id}' api_version '{api_version}' is incompatible with core api_version '{PLUGIN_API_VERSION}'"
        )

    return PluginDescriptor(
        plugin_id=plugin_id,
        name=name,
        version=version,
        api_version=api_version,
        plugin_type=cast(PluginType, plugin_type),
        author=_optional_str(plugin.get("author")),
        description=_optional_str(plugin.get("description")),
        capabilities=[str(item) for item in capabilities],
        dependencies=[str(item) for item in dependencies],
        entrypoints=PluginEntrypoints(
            templates=_optional_str(entrypoints.get("templates")),
            variants=_optional_str(entrypoints.get("variants")),
            components=_optional_str(entrypoints.get("components")),
            exporters=_optional_str(entrypoints.get("exporters")),
            layouts=_optional_str(entrypoints.get("layouts")),
            constraints=_optional_str(entrypoints.get("constraints")),
            module=_optional_str(entrypoints.get("module")),
        ),
        non_disableable=bool(plugin.get("non_disableable", False)),
        is_internal="plugins/internal" in str(file_path.parent).replace("\\", "/"),
        root_path=file_path.parent,
    )


def _require_str(value: Any, field: str, path: Path) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing required field '{field}' in {path}")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)

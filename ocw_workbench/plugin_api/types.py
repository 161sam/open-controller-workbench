from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

PluginType = Literal[
    "component_pack",
    "template_pack",
    "variant_pack",
    "exporter",
    "layout_strategy",
    "constraint_pack",
    "workflow",
    "ui_extension",
]

RegistryName = Literal[
    "components",
    "templates",
    "variants",
    "exporters",
    "layout_strategies",
    "constraints",
    "ui_extensions",
]


@dataclass(frozen=True)
class PluginEntrypoints:
    templates: str | None = None
    variants: str | None = None
    components: str | None = None
    exporters: str | None = None
    layouts: str | None = None
    constraints: str | None = None
    module: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "templates": self.templates,
            "variants": self.variants,
            "components": self.components,
            "exporters": self.exporters,
            "layouts": self.layouts,
            "constraints": self.constraints,
            "module": self.module,
        }


@dataclass(frozen=True)
class PluginDescriptor:
    plugin_id: str
    name: str
    version: str
    api_version: str
    plugin_type: PluginType
    author: str | None
    description: str | None
    capabilities: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    entrypoints: PluginEntrypoints = field(default_factory=PluginEntrypoints)
    non_disableable: bool = False
    is_internal: bool = False
    root_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "api_version": self.api_version,
            "type": self.plugin_type,
            "author": self.author,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "dependencies": list(self.dependencies),
            "entrypoints": self.entrypoints.to_dict(),
            "non_disableable": self.non_disableable,
            "is_internal": self.is_internal,
            "root_path": str(self.root_path) if self.root_path is not None else None,
        }

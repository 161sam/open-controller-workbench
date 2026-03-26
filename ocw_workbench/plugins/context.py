from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ocw_workbench.plugins.registry import ExtensionRegistry


@dataclass
class PluginContext:
    registry: ExtensionRegistry
    config: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def register_source(self, registry_name: str, source: str | Path, plugin_id: str | None = None) -> None:
        self.registry.register_source(registry_name, Path(source), plugin_id=plugin_id)

    def register_provider(self, registry_name: str, provider_id: str, provider: Any) -> None:
        self.registry.register_provider(registry_name, provider_id, provider)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

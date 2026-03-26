from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ocw_workbench.plugins.data import alias_candidates, normalize_component_payload
from ocw_workbench.plugins.registry import PluginSource
from ocw_workbench.services.plugin_service import get_plugin_service_revision
from ocw_workbench.utils.yaml_io import load_yaml


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


class ComponentLibraryManager:
    def __init__(self, base_path: str | Path | None = None) -> None:
        self.base_path = Path(base_path) if base_path is not None else None
        self._components_by_id: dict[str, dict[str, Any]] = {}
        self._aliases: dict[str, str] = {}
        self._loaded = False
        self._loaded_revision = -1

    def load_all(self) -> None:
        components_by_id: dict[str, dict[str, Any]] = {}
        aliases: dict[str, str] = {}
        for source_entry in self._source_entries():
            for yaml_file in sorted(source_entry.path.glob("*.yaml")):
                try:
                    loaded = self._load_components_from_file(yaml_file, source_entry.plugin_id)
                except Exception:
                    if source_entry.plugin_id is not None:
                        continue
                    raise
                for component in loaded:
                    component_id = component["id"]
                    if component_id in components_by_id:
                        if source_entry.plugin_id is not None:
                            continue
                        raise ValueError(f"Duplicate component id detected: {component_id}")
                    components_by_id[component_id] = deepcopy(component)
                    for alias in alias_candidates(component_id, source_entry.plugin_id):
                        self._register_alias(aliases, alias, component_id)

        self._components_by_id = components_by_id
        self._aliases = aliases
        self._loaded = True
        self._loaded_revision = 0 if self.base_path is not None else get_plugin_service_revision()

    def _source_entries(self) -> list[PluginSource]:
        if self.base_path is not None:
            if not self.base_path.exists():
                raise FileNotFoundError(f"Component library path not found: {self.base_path}")
            return [PluginSource(plugin_id=None, path=self.base_path)]

        from ocw_workbench.services.plugin_service import get_plugin_service

        sources = get_plugin_service().registry().source_entries("components")
        if sources:
            return sources

        fallback = Path(__file__).resolve().parent / "components"
        if not fallback.exists():
            raise FileNotFoundError(f"Component library path not found: {fallback}")
        return [PluginSource(plugin_id=None, path=fallback)]

    def _validate_component_shape(self, component: dict[str, Any], source: Path) -> None:
        required = [
            "id",
            "category",
            "manufacturer",
            "part_number",
            "description",
            "mechanical",
            "electrical",
            "pcb",
            "ocf",
        ]
        component_id = component.get("id", "<unknown>")
        for field in required:
            if field not in component:
                raise ValueError(
                    f"Missing required field '{field}' in component '{component_id}' from {source}"
                )

    def _ensure_loaded(self) -> None:
        current_revision = 0 if self.base_path is not None else get_plugin_service_revision()
        if not self._loaded or self._loaded_revision != current_revision:
            self.load_all()

    def get_component(self, component_id: str) -> dict[str, Any]:
        self._ensure_loaded()
        component_id = self._aliases.get(component_id, component_id)
        try:
            return deepcopy(self._components_by_id[component_id])
        except KeyError as exc:
            raise KeyError(f"Unknown component id: {component_id}") from exc

    def list_components(self, category: str | None = None) -> list[dict[str, Any]]:
        self._ensure_loaded()
        items = list(self._components_by_id.values())
        if category is not None:
            items = [item for item in items if item.get("category") == category]
        return [deepcopy(item) for item in items]

    def resolve_component(
        self,
        library_ref: str,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        base_component = self.get_component(library_ref)
        if overrides is None:
            return base_component
        return _deep_merge(base_component, overrides)

    def _load_components_from_file(self, yaml_file: Path, plugin_id: str | None) -> list[dict[str, Any]]:
        payload = load_yaml(yaml_file)
        if "components" in payload:
            components = payload.get("components", [])
            if not isinstance(components, list):
                raise ValueError(f"'components' must be a list in {yaml_file}")
            loaded: list[dict[str, Any]] = []
            for component in components:
                if not isinstance(component, dict):
                    raise ValueError(f"Invalid component entry in {yaml_file}: {component!r}")
                component_id = component.get("id")
                if not component_id or not isinstance(component_id, str):
                    raise ValueError(f"Component without valid 'id' in {yaml_file}")
                self._validate_component_shape(component, yaml_file)
                loaded.append(deepcopy(component))
            return loaded

        if plugin_id is None:
            raise ValueError(f"Component file {yaml_file} does not define legacy 'components' list")
        component = normalize_component_payload(payload, yaml_file, plugin_id)
        self._validate_component_shape(component, yaml_file)
        return [component]

    def _register_alias(self, aliases: dict[str, str], alias: str, component_id: str) -> None:
        existing = aliases.get(alias)
        if existing is None:
            aliases[alias] = component_id
            return
        if existing != component_id:
            aliases.pop(alias, None)

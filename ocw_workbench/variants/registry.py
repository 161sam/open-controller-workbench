from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ocw_workbench.plugins.data import alias_candidates
from ocw_workbench.plugins.registry import PluginSource
from ocw_workbench.services.plugin_service import get_plugin_service_revision
from ocw_workbench.variants.loader import VariantLoader


class VariantRegistry:
    def __init__(self, base_path: str | Path | None = None, loader: VariantLoader | None = None) -> None:
        self.base_path = Path(base_path) if base_path is not None else None
        self.loader = loader or VariantLoader()
        self._variants: dict[str, dict[str, Any]] = {}
        self._aliases: dict[str, str] = {}
        self._loaded = False
        self._loaded_revision = -1

    def load_all(self) -> None:
        variants: dict[str, dict[str, Any]] = {}
        aliases: dict[str, str] = {}
        for source_entry in self._source_entries():
            for yaml_file in sorted(source_entry.path.glob("*.yaml")):
                try:
                    variant = self.loader.load(yaml_file, plugin_id=source_entry.plugin_id).to_dict()
                except Exception:
                    if source_entry.plugin_id is not None:
                        continue
                    raise
                variant_id = variant["variant"]["id"]
                if variant_id in variants:
                    if source_entry.plugin_id is not None:
                        continue
                    raise ValueError(f"Duplicate variant id detected: {variant_id}")
                variants[variant_id] = variant
                for alias in alias_candidates(variant_id, source_entry.plugin_id):
                    self._register_alias(aliases, alias, variant_id)

        self._variants = variants
        self._aliases = aliases
        self._loaded = True
        self._loaded_revision = 0 if self.base_path is not None else get_plugin_service_revision()

    def _source_entries(self) -> list[PluginSource]:
        if self.base_path is not None:
            if not self.base_path.exists():
                raise FileNotFoundError(f"Variant library path not found: {self.base_path}")
            return [PluginSource(plugin_id=None, path=self.base_path)]

        from ocw_workbench.services.plugin_service import get_plugin_service

        sources = get_plugin_service().registry().source_entries("variants")
        if sources:
            return sources

        fallback = Path(__file__).resolve().parent / "library"
        if not fallback.exists():
            raise FileNotFoundError(f"Variant library path not found: {fallback}")
        return [PluginSource(plugin_id=None, path=fallback)]

    def _ensure_loaded(self) -> None:
        current_revision = 0 if self.base_path is not None else get_plugin_service_revision()
        if not self._loaded or self._loaded_revision != current_revision:
            self.load_all()

    def list_variants(
        self,
        template_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_loaded()
        items = list(self._variants.values())
        if template_id is not None:
            items = [item for item in items if item["variant"].get("template_id") == template_id]
        if category is not None:
            items = [item for item in items if item["variant"].get("category") == category]
        if tag is not None:
            items = [item for item in items if tag in item["variant"].get("tags", [])]
        return [deepcopy(item) for item in items]

    def get_variant(self, variant_id: str) -> dict[str, Any]:
        self._ensure_loaded()
        variant_id = self._aliases.get(variant_id, variant_id)
        try:
            return deepcopy(self._variants[variant_id])
        except KeyError as exc:
            raise KeyError(f"Unknown variant id: {variant_id}") from exc

    def _register_alias(self, aliases: dict[str, str], alias: str, variant_id: str) -> None:
        existing = aliases.get(alias)
        if existing is None:
            aliases[alias] = variant_id
            return
        if existing != variant_id:
            aliases.pop(alias, None)

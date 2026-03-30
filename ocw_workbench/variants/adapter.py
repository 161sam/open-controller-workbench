from __future__ import annotations

import logging
from pathlib import Path

from ocw_workbench.plugins.registry import PluginSource
from ocw_workbench.plugins.settings import OCW_STRICT_PLUGIN_MODE
from ocw_workbench.services.plugin_service import get_plugin_service

LOGGER = logging.getLogger(__name__)


def get_variant_source_entries(base_path: str | Path | None = None) -> list[PluginSource]:
    if base_path is not None:
        path = Path(base_path)
        if not path.exists():
            raise FileNotFoundError(f"Variant library path not found: {path}")
        return [PluginSource(plugin_id=None, path=path)]

    registry = get_plugin_service().registry()
    sources: list[PluginSource] = []
    active_plugin = registry.get_active_plugin()
    if OCW_STRICT_PLUGIN_MODE and active_plugin is None:
        raise RuntimeError("Strict plugin mode enabled but no active domain plugin is configured for variants")
    if active_plugin is not None:
        plugin_root = active_plugin.variant_root()
        if plugin_root is not None:
            sources.append(PluginSource(plugin_id=active_plugin.plugin_id, path=plugin_root))
            LOGGER.debug("Variant source root: plugin '%s' -> %s", active_plugin.plugin_id, plugin_root)
        elif OCW_STRICT_PLUGIN_MODE:
            raise FileNotFoundError(
                f"Strict plugin mode enabled and no variant root exists for active plugin '{active_plugin.plugin_id}'"
            )
    plugin_pack_sources = list(registry.source_entries("variants"))
    if plugin_pack_sources:
        for source in plugin_pack_sources:
            LOGGER.debug("Variant source root: plugin-pack '%s' -> %s", source.plugin_id, source.path)
    if OCW_STRICT_PLUGIN_MODE and active_plugin is not None:
        plugin_sources_only = [source for source in plugin_pack_sources if source.plugin_id is not None]
        return _dedupe_source_entries(sources + plugin_sources_only)
    return _dedupe_source_entries(sources + plugin_pack_sources)


def _dedupe_source_entries(sources: list[PluginSource]) -> list[PluginSource]:
    deduped: list[PluginSource] = []
    seen: set[tuple[str | None, str]] = set()
    for source in sources:
        key = (source.plugin_id, str(source.path))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped

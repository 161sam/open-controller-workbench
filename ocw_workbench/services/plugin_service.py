from __future__ import annotations

from pathlib import Path

from ocw_workbench.plugins.loader import PluginLoader
from ocw_workbench.plugins.registry import ExtensionRegistry
from ocw_workbench.userdata.plugin_state_store import PluginStatePersistence

_PLUGIN_SERVICE: PluginService | None = None
_PLUGIN_SERVICE_REVISION = 0


class PluginService:
    def __init__(self, loader: PluginLoader | None = None) -> None:
        self.loader = loader or PluginLoader()

    def registry(self) -> ExtensionRegistry:
        return self.loader.load_all()

    def warnings(self) -> list[str]:
        self.loader.load_all()
        return list(self.loader.warnings)

    def component_sources(self) -> list[Path]:
        return self.registry().component_sources()

    def template_sources(self) -> list[Path]:
        return self.registry().template_sources()

    def variant_sources(self) -> list[Path]:
        return self.registry().variant_sources()

    def exporters(self) -> dict[str, object]:
        return self.registry().exporters()

    def layout_strategies(self) -> dict[str, object]:
        return self.registry().layout_strategies()

    def constraints(self) -> dict[str, object]:
        return self.registry().constraints()


def get_plugin_service_revision() -> int:
    return _PLUGIN_SERVICE_REVISION


def get_plugin_service() -> PluginService:
    global _PLUGIN_SERVICE
    if _PLUGIN_SERVICE is None:
        _PLUGIN_SERVICE = PluginService(loader=_build_loader())
    return _PLUGIN_SERVICE


def reset_plugin_service(
    internal_root: str | Path | None = None,
    external_root: str | Path | None = None,
    state_base_dir: str | Path | None = None,
) -> PluginService:
    global _PLUGIN_SERVICE
    global _PLUGIN_SERVICE_REVISION
    _PLUGIN_SERVICE = PluginService(
        loader=_build_loader(internal_root=internal_root, external_root=external_root, state_base_dir=state_base_dir)
    )
    _PLUGIN_SERVICE_REVISION += 1
    return _PLUGIN_SERVICE


def _build_loader(
    internal_root: str | Path | None = None,
    external_root: str | Path | None = None,
    state_base_dir: str | Path | None = None,
) -> PluginLoader:
    persistence = PluginStatePersistence(base_dir=str(state_base_dir) if state_base_dir is not None else None)

    def enabled_resolver(descriptor) -> bool:
        return persistence.is_enabled(descriptor.plugin_id, default=True)

    return PluginLoader(
        internal_root=internal_root,
        external_root=external_root,
        enabled_resolver=enabled_resolver,
    )

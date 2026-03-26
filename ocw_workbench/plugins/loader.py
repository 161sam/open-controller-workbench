from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Callable

from ocw_workbench.plugin_api.types import PluginDescriptor
from ocw_workbench.plugins.context import PluginContext
from ocw_workbench.plugins.hooks import run_module_hooks
from ocw_workbench.plugins.manifest import load_plugin_manifest
from ocw_workbench.plugins.registry import ExtensionRegistry


class PluginLoader:
    def __init__(
        self,
        internal_root: str | Path | None = None,
        external_root: str | Path | None = None,
        enabled_resolver: Callable[[PluginDescriptor], bool] | None = None,
    ) -> None:
        base = Path(__file__).resolve().parent
        self.internal_root = Path(internal_root or (base / "internal"))
        self.external_root = Path(external_root or (base / "external"))
        self.enabled_resolver = enabled_resolver
        self.registry = ExtensionRegistry()
        self.warnings: list[str] = []
        self._loaded = False

    def load_all(self) -> ExtensionRegistry:
        if self._loaded:
            return self.registry

        pending: list[PluginDescriptor] = []
        pending.extend(self._discover_from_root(self.internal_root))
        pending.extend(self._discover_from_root(self.external_root))

        while pending:
            progress = False
            remaining: list[PluginDescriptor] = []
            pending_ids = {descriptor.plugin_id for descriptor in pending}
            for descriptor in pending:
                if not self._is_enabled(descriptor):
                    progress = True
                    continue
                if self._dependencies_missing(descriptor, pending_ids):
                    remaining.append(descriptor)
                    continue
                if self.registry.has_plugin(descriptor.plugin_id):
                    self.warnings.append(f"Skipping duplicate plugin id '{descriptor.plugin_id}'")
                    progress = True
                    continue
                self.registry.register_plugin(descriptor)
                context = PluginContext(
                    registry=self.registry,
                    config={"plugin_id": descriptor.plugin_id},
                    warnings=self.warnings,
                )
                self._register_manifest_entrypoints(descriptor, context)
                self._run_hook_module(descriptor, context)
                progress = True

            if not progress:
                for descriptor in remaining:
                    missing = [
                        dependency for dependency in descriptor.dependencies if not self.registry.has_plugin(dependency)
                    ]
                    self.warnings.append(
                        f"Skipping plugin '{descriptor.plugin_id}' because dependencies are missing: {', '.join(sorted(missing))}"
                    )
                break
            pending = remaining

        self._loaded = True
        return self.registry

    def _is_enabled(self, descriptor: PluginDescriptor) -> bool:
        if descriptor.non_disableable:
            return True
        if self.enabled_resolver is None:
            return True
        return bool(self.enabled_resolver(descriptor))

    def _discover_from_root(self, root: Path) -> list[PluginDescriptor]:
        if not root.exists():
            return []

        descriptors: list[PluginDescriptor] = []
        for plugin_dir in sorted(item for item in root.iterdir() if item.is_dir()):
            manifest_path = self._manifest_path(plugin_dir)
            if not manifest_path.exists():
                self.warnings.append(f"Skipping plugin without manifest: {plugin_dir}")
                continue
            try:
                descriptor = load_plugin_manifest(manifest_path)
            except Exception as exc:
                self.warnings.append(f"Failed to load plugin manifest '{manifest_path}': {exc}")
                continue
            descriptors.append(descriptor)
        return descriptors

    def _dependencies_missing(self, descriptor: PluginDescriptor, pending_ids: set[str]) -> bool:
        missing = []
        for dependency in descriptor.dependencies:
            if self.registry.has_plugin(dependency):
                continue
            missing.append(dependency)
            if dependency in pending_ids:
                return True
        return bool(missing)

    def _register_manifest_entrypoints(self, descriptor: PluginDescriptor, context: PluginContext) -> None:
        mapping = {
            "components": descriptor.entrypoints.components,
            "templates": descriptor.entrypoints.templates,
            "variants": descriptor.entrypoints.variants,
            "exporters": descriptor.entrypoints.exporters,
            "layout_strategies": descriptor.entrypoints.layouts,
            "constraints": descriptor.entrypoints.constraints,
        }
        for registry_name, relative_path in mapping.items():
            if relative_path is None or descriptor.root_path is None:
                continue
            source = (descriptor.root_path / relative_path).resolve()
            if source.exists():
                context.register_source(registry_name, source, plugin_id=descriptor.plugin_id)
            else:
                context.warn(f"Plugin '{descriptor.plugin_id}' entrypoint '{registry_name}' not found: {source}")

    def _run_hook_module(self, descriptor: PluginDescriptor, context: PluginContext) -> None:
        if descriptor.entrypoints.module is None or descriptor.root_path is None:
            return
        module_path = (descriptor.root_path / descriptor.entrypoints.module).resolve()
        if not module_path.exists():
            context.warn(f"Plugin '{descriptor.plugin_id}' hook module not found: {module_path}")
            return
        try:
            module = self._load_module(module_path, descriptor.plugin_id)
        except Exception as exc:
            context.warn(f"Plugin '{descriptor.plugin_id}' failed to import hooks: {exc}")
            return
        run_module_hooks(module, context)

    def _load_module(self, module_path: Path, plugin_id: str) -> ModuleType:
        spec = importlib.util.spec_from_file_location(f"ocw_plugin_{plugin_id}", module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to create spec for {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _manifest_path(self, plugin_dir: Path) -> Path:
        for filename in ("plugin.yaml", "manifest.yaml"):
            path = plugin_dir / filename
            if path.exists():
                return path
        return plugin_dir / "manifest.yaml"

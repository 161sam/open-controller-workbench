from __future__ import annotations

from pathlib import Path
from typing import Any

from ocw_workbench.plugins.loader import PluginLoader
from ocw_workbench.plugins.manifest import load_plugin_manifest
from ocw_workbench.services.plugin_service import get_plugin_service, reset_plugin_service
from ocw_workbench.userdata.plugin_state_store import PluginStateEntry, PluginStatePersistence
from ocw_workbench.utils.yaml_io import load_yaml


class PluginManagerService:
    def __init__(
        self,
        persistence: PluginStatePersistence | None = None,
        internal_root: str | Path | None = None,
        external_root: str | Path | None = None,
    ) -> None:
        self.persistence = persistence or PluginStatePersistence()
        self.internal_root = Path(internal_root) if internal_root is not None else None
        self.external_root = Path(external_root) if external_root is not None else None

    def list_plugins(self, filter_by: str = "all") -> list[dict[str, Any]]:
        self._ensure_active_service()
        registry = get_plugin_service().registry()
        warnings = get_plugin_service().warnings()
        items = [self._build_item(plugin_dir, registry, warnings) for plugin_dir in self._plugin_dirs()]
        items = [item for item in items if self._matches_filter(item, filter_by)]
        return sorted(items, key=self._sort_key)

    def get_plugin(self, plugin_id: str) -> dict[str, Any]:
        for item in self.list_plugins():
            if item["id"] == plugin_id:
                return item
        raise KeyError(f"Unknown plugin id: {plugin_id}")

    def set_enabled(self, plugin_id: str, enabled: bool) -> dict[str, Any]:
        plugin = self.get_plugin(plugin_id)
        if plugin.get("non_disableable") and not enabled:
            raise ValueError(f"Plugin '{plugin_id}' is required and cannot be disabled")
        store = self.persistence.load()
        store.states = [entry for entry in store.states if entry.plugin_id != plugin_id]
        store.states.append(PluginStateEntry(plugin_id=plugin_id, enabled=enabled))
        self.persistence.save(store)
        self.reload_plugins()
        return self.get_plugin(plugin_id)

    def reload_plugins(self) -> list[dict[str, Any]]:
        reset_plugin_service(
            internal_root=self.internal_root,
            external_root=self.external_root,
            state_base_dir=self.persistence.base_dir,
        )
        return self.list_plugins()

    def is_enabled(self, plugin_id: str, default: bool = True) -> bool:
        return self.persistence.is_enabled(plugin_id, default=default)

    def _build_item(self, plugin_dir: Path, registry: Any, warnings: list[str]) -> dict[str, Any]:
        manifest_path = self._manifest_path(plugin_dir)
        raw_plugin = self._raw_plugin(manifest_path)
        plugin_id = str(raw_plugin.get("id") or plugin_dir.name)
        item = {
            "id": plugin_id,
            "name": str(raw_plugin.get("name") or plugin_dir.name),
            "version": str(raw_plugin.get("version") or "-"),
            "api_version": str(raw_plugin.get("api_version") or "-"),
            "type": str(raw_plugin.get("type") or "unknown"),
            "author": raw_plugin.get("author"),
            "description": raw_plugin.get("description"),
            "capabilities": [],
            "dependencies": [],
            "entrypoints": {},
            "status": "error",
            "status_label": "Error",
            "enabled": False,
            "is_internal": "plugins/internal" in str(plugin_dir).replace("\\", "/"),
            "non_disableable": bool(raw_plugin.get("non_disableable", False)),
            "warnings": [],
            "errors": [],
            "plugin_dir": str(plugin_dir),
            "manifest_path": str(manifest_path),
            "is_data_plugin": False,
        }

        if not manifest_path.exists():
            item["errors"].append("Manifest file is missing")
            return item

        try:
            descriptor = load_plugin_manifest(manifest_path)
        except Exception as exc:
            message = str(exc)
            item["errors"].append(message)
            if "incompatible with core api_version" in message.lower():
                item["status"] = "incompatible"
                item["status_label"] = "Incompatible"
            return item

        item.update(
            {
                "id": descriptor.plugin_id,
                "name": descriptor.name,
                "version": descriptor.version,
                "api_version": descriptor.api_version,
                "type": descriptor.plugin_type,
                "author": descriptor.author,
                "description": descriptor.description,
                "capabilities": list(descriptor.capabilities),
                "dependencies": list(descriptor.dependencies),
                "entrypoints": descriptor.entrypoints.to_dict(),
                "is_internal": descriptor.is_internal,
                "non_disableable": descriptor.non_disableable,
                "enabled": descriptor.non_disableable or self.is_enabled(descriptor.plugin_id, default=True),
                "is_data_plugin": _is_data_plugin(plugin_dir, descriptor.entrypoints.to_dict()),
            }
        )
        item["warnings"] = _warnings_for_plugin(descriptor.plugin_id, warnings)

        if not item["enabled"] and not descriptor.non_disableable:
            item["status"] = "disabled"
            item["status_label"] = "Disabled"
            return item

        if registry.has_plugin(descriptor.plugin_id):
            item["status"] = "enabled"
            item["status_label"] = "Enabled"
            return item

        item["errors"].extend(item["warnings"] or ["Plugin was not registered"])
        return item

    def _ensure_active_service(self) -> None:
        if self.internal_root is None and self.external_root is None:
            return
        reset_plugin_service(
            internal_root=self.internal_root,
            external_root=self.external_root,
            state_base_dir=self.persistence.base_dir,
        )

    def _plugin_dirs(self) -> list[Path]:
        loader = PluginLoader(internal_root=self.internal_root, external_root=self.external_root)
        directories: list[Path] = []
        for root in (loader.internal_root, loader.external_root):
            if not root.exists():
                continue
            directories.extend(sorted(item for item in root.iterdir() if item.is_dir()))
        return directories

    def _raw_plugin(self, manifest_path: Path) -> dict[str, Any]:
        try:
            payload = load_yaml(manifest_path)
        except Exception:
            return {}
        plugin = payload.get("plugin", {})
        return plugin if isinstance(plugin, dict) else {}

    def _manifest_path(self, plugin_dir: Path) -> Path:
        for filename in ("plugin.yaml", "manifest.yaml"):
            candidate = plugin_dir / filename
            if candidate.exists():
                return candidate
        return plugin_dir / "manifest.yaml"

    def _matches_filter(self, item: dict[str, Any], filter_by: str) -> bool:
        normalized = (filter_by or "all").lower()
        if normalized == "all":
            return True
        if normalized == "enabled":
            return item["status"] == "enabled"
        if normalized == "disabled":
            return item["status"] == "disabled"
        if normalized == "errors":
            return item["status"] in {"error", "incompatible"}
        return True

    def _sort_key(self, item: dict[str, Any]) -> tuple[int, str]:
        priority = {
            "error": 0,
            "incompatible": 1,
            "enabled": 2,
            "disabled": 3,
        }
        return (priority.get(item["status"], 9), str(item["name"]).lower())


def _warnings_for_plugin(plugin_id: str, warnings: list[str]) -> list[str]:
    return [message for message in warnings if f"'{plugin_id}'" in message or plugin_id in message]


def _is_data_plugin(plugin_dir: Path, entrypoints: dict[str, Any]) -> bool:
    if entrypoints.get("module") not in {None, ""}:
        return False
    blocked_suffixes = {".py", ".pyc", ".so", ".dll", ".dylib", ".exe", ".sh", ".bat"}
    for file_path in plugin_dir.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.name == "__pycache__":
            continue
        if file_path.suffix.lower() in blocked_suffixes:
            return False
    return True

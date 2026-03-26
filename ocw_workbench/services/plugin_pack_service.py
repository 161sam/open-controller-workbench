from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from ocw_workbench.plugins.loader import PluginLoader
from ocw_workbench.plugins.manifest import load_plugin_manifest
from ocw_workbench.services.plugin_manager_service import PluginManagerService

_BLOCKED_SUFFIXES = {".py", ".pyc", ".so", ".dll", ".dylib", ".exe", ".sh", ".bat"}


class PluginPackService:
    def __init__(
        self,
        plugin_manager_service: PluginManagerService | None = None,
        external_root: str | Path | None = None,
    ) -> None:
        self.plugin_manager_service = plugin_manager_service or PluginManagerService()
        self.external_root = Path(external_root) if external_root is not None else PluginLoader().external_root

    def export_plugin_pack(self, plugin_id: str, output_path: str | Path) -> dict[str, Any]:
        plugin = self.plugin_manager_service.get_plugin(plugin_id)
        if not plugin.get("is_data_plugin"):
            raise ValueError(f"Plugin '{plugin_id}' is not a data plugin and cannot be exported as a pack")
        plugin_dir = Path(str(plugin["plugin_dir"]))
        self._validate_plugin_directory(plugin_dir)
        destination = self._zip_destination(output_path, plugin_id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(plugin_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                archive.write(file_path, arcname=file_path.relative_to(plugin_dir).as_posix())
        return {"plugin_id": plugin_id, "zip_path": str(destination)}

    def import_plugin_pack(self, zip_path: str | Path) -> dict[str, Any]:
        archive_path = Path(zip_path)
        if not archive_path.exists():
            raise FileNotFoundError(f"Plugin pack not found: {archive_path}")
        with tempfile.TemporaryDirectory(prefix="ocw-plugin-pack-") as tmpdir:
            staging_root = Path(tmpdir) / "staging"
            staging_root.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive_path, "r") as archive:
                self._validate_archive_members(archive)
                archive.extractall(staging_root)

            plugin_root = self._find_plugin_root(staging_root)
            self._validate_plugin_directory(plugin_root)
            descriptor = load_plugin_manifest(self._manifest_path(plugin_root))
            if descriptor.is_internal:
                raise ValueError(f"Plugin '{descriptor.plugin_id}' must be installed as an external plugin pack")
            existing = self._existing_plugin(descriptor.plugin_id)
            if existing is not None and existing.get("is_internal"):
                raise ValueError(f"Plugin id '{descriptor.plugin_id}' is reserved by an internal plugin")
            installed_path = self.external_root / descriptor.plugin_id
            self.external_root.mkdir(parents=True, exist_ok=True)
            if installed_path.exists():
                shutil.rmtree(installed_path)
            shutil.copytree(plugin_root, installed_path)

        self.plugin_manager_service.reload_plugins()
        plugin = self.plugin_manager_service.get_plugin(descriptor.plugin_id)
        return {"plugin_id": descriptor.plugin_id, "install_path": str(installed_path), "plugin": plugin}

    def _validate_archive_members(self, archive: zipfile.ZipFile) -> None:
        for member in archive.infolist():
            path = Path(member.filename)
            if member.is_dir():
                continue
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"Unsafe archive entry: {member.filename}")
            if path.suffix.lower() in _BLOCKED_SUFFIXES:
                raise ValueError(f"Plugin pack contains blocked file type: {member.filename}")

    def _find_plugin_root(self, staging_root: Path) -> Path:
        manifest = self._manifest_path(staging_root)
        if manifest.exists():
            return staging_root
        subdirs = [item for item in staging_root.iterdir() if item.is_dir()]
        if len(subdirs) == 1:
            manifest = self._manifest_path(subdirs[0])
            if manifest.exists():
                return subdirs[0]
        raise ValueError("Plugin pack must contain plugin.yaml or manifest.yaml at the archive root")

    def _validate_plugin_directory(self, plugin_dir: Path) -> None:
        manifest_path = self._manifest_path(plugin_dir)
        if not manifest_path.exists():
            raise ValueError(f"Plugin directory '{plugin_dir}' is missing plugin.yaml")
        descriptor = load_plugin_manifest(manifest_path)
        entrypoints = descriptor.entrypoints.to_dict()
        if entrypoints.get("module") not in {None, ""}:
            raise ValueError(f"Plugin '{descriptor.plugin_id}' contains a Python module entrypoint and is not allowed")
        for file_path in plugin_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() in _BLOCKED_SUFFIXES:
                raise ValueError(f"Plugin '{descriptor.plugin_id}' contains blocked file '{file_path.name}'")

    def _manifest_path(self, plugin_dir: Path) -> Path:
        for filename in ("plugin.yaml", "manifest.yaml"):
            candidate = plugin_dir / filename
            if candidate.exists():
                return candidate
        return plugin_dir / "plugin.yaml"

    def _zip_destination(self, output_path: str | Path, plugin_id: str) -> Path:
        path = Path(output_path)
        if path.suffix.lower() == ".zip":
            return path
        if path.exists() and path.is_dir():
            return path / f"{plugin_id}.zip"
        if not path.suffix:
            return path / f"{plugin_id}.zip"
        return path.with_suffix(".zip")

    def _existing_plugin(self, plugin_id: str) -> dict[str, Any] | None:
        try:
            return self.plugin_manager_service.get_plugin(plugin_id)
        except KeyError:
            return None

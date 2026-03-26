from __future__ import annotations

from collections import Counter
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any
import zipfile

import yaml

from ocw_workbench.services.plugin_manager_service import PluginManagerService
from ocw_workbench.services.plugin_registry_service import PluginRegistryService
from ocw_workbench.services.template_service import TemplateService
from ocw_workbench.templates.loader import TemplateLoader


class TemplateMarketplaceService:
    def __init__(
        self,
        template_service: TemplateService | None = None,
        plugin_manager_service: PluginManagerService | None = None,
        plugin_registry_service: PluginRegistryService | None = None,
        template_loader: TemplateLoader | None = None,
    ) -> None:
        self.template_service = template_service or TemplateService()
        self.plugin_manager_service = plugin_manager_service or PluginManagerService()
        self.plugin_registry_service = plugin_registry_service or PluginRegistryService()
        self.template_loader = template_loader or TemplateLoader()
        self._remote_cache: dict[tuple[str, str, str], tuple[list[dict[str, Any]], list[str]]] = {}

    def last_registry_url(self) -> str:
        return self.plugin_registry_service.last_registry_url()

    def list_entries(
        self,
        *,
        search: str = "",
        filter_by: str = "all",
        remote_registry_url: str | None = None,
        refresh_remote: bool = False,
    ) -> dict[str, Any]:
        items = self._local_entries()
        warnings: list[str] = []

        remote_url = (remote_registry_url or self.last_registry_url()).strip()
        if filter_by in {"all", "remote"} and remote_url:
            remote_items, remote_warnings = self._remote_entries(remote_url, refresh=refresh_remote)
            items.extend(remote_items)
            warnings.extend(remote_warnings)

        filtered = _filter_items(items, search=search, filter_by=filter_by)
        filtered.sort(key=_sort_key)
        return {
            "entries": filtered,
            "warnings": warnings,
            "remote_url": remote_url,
        }

    def get_entry(
        self,
        entry_id: str,
        *,
        remote_registry_url: str | None = None,
        refresh_remote: bool = False,
    ) -> dict[str, Any]:
        listing = self.list_entries(
            search="",
            filter_by="all",
            remote_registry_url=remote_registry_url,
            refresh_remote=refresh_remote,
        )
        for entry in listing["entries"]:
            if entry["entry_id"] == entry_id:
                return entry
        raise KeyError(f"Unknown template marketplace entry: {entry_id}")

    def can_apply(self, entry: dict[str, Any]) -> bool:
        return bool(entry.get("template_id")) and entry.get("source") == "local"

    def apply_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        if self.can_apply(entry):
            return {
                "template_id": str(entry["template_id"]),
                "source": entry["source"],
            }
        raise ValueError("Remote templates must be imported as data plugins before they can be applied")

    def details_text(self, entry: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"Name: {entry['name']}",
                f"Template ID: {entry.get('template_id') or '-'}",
                f"Components: {entry.get('component_count', 0)}",
                f"Origin: {entry.get('plugin_name') or entry.get('plugin_id') or '-'}",
                f"Source: {entry['source']}",
                f"Preview: {entry.get('preview') or '-'}",
                f"Description: {entry.get('description') or '-'}",
                f"Download: {entry.get('download_url') or '-'}",
            ]
        )

    def _local_entries(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for item in self.template_service.list_templates():
            template = item["template"]
            plugin_id = item.get("source_plugin_id") or _plugin_id_from_template(template["id"])
            plugin = self._plugin(plugin_id)
            entries.append(
                {
                    "entry_id": f"local:{template['id']}",
                    "template_id": template["id"],
                    "name": template["name"],
                    "description": template.get("description") or "",
                    "component_count": len(item.get("components", [])),
                    "preview": _build_preview(item),
                    "plugin_id": plugin_id,
                    "plugin_name": plugin.get("name") if plugin is not None else (plugin_id or "Core"),
                    "source": "local",
                    "download_url": None,
                }
            )
        return entries

    def _remote_entries(self, remote_registry_url: str, refresh: bool) -> tuple[list[dict[str, Any]], list[str]]:
        registry = (
            self.plugin_registry_service.refresh_registry(remote_registry_url)
            if refresh
            else self.plugin_registry_service.load_cached_registry(remote_registry_url)
        )
        warnings = list(registry.get("warnings", []))
        entries: list[dict[str, Any]] = []
        for plugin in registry.get("entries", []):
            plugin_id = str(plugin.get("id") or "")
            version = str(plugin.get("version") or "")
            if not plugin_id or not version:
                continue
            cache_key = (remote_registry_url, plugin_id, version)
            cached = self._remote_cache.get(cache_key)
            if cached is None:
                try:
                    cached = self._inspect_remote_plugin(remote_registry_url, plugin_id)
                except Exception as exc:
                    warnings.append(f"Failed to inspect remote template pack '{plugin_id}': {exc}")
                    continue
                self._remote_cache[cache_key] = cached
            plugin_entries, plugin_warnings = cached
            warnings.extend(plugin_warnings)
            entries.extend(plugin_entries)
        return entries, warnings

    def _inspect_remote_plugin(self, remote_registry_url: str, plugin_id: str) -> tuple[list[dict[str, Any]], list[str]]:
        plugin = self.plugin_registry_service.get_registry_entry(remote_registry_url, plugin_id)
        archive_bytes = self.plugin_registry_service.read_plugin_archive(remote_registry_url, plugin_id)
        warnings: list[str] = []
        entries: list[dict[str, Any]] = []
        with zipfile.ZipFile(BytesIO(archive_bytes), "r") as archive:
            root_prefix = _find_archive_root(archive)
            manifest_payload = _read_yaml_from_archive(archive, root_prefix / "plugin.yaml")
            if manifest_payload is None:
                manifest_payload = _read_yaml_from_archive(archive, root_prefix / "manifest.yaml")
            if manifest_payload is None:
                raise ValueError("plugin.yaml is missing from the archive")
            entrypoints = manifest_payload.get("entrypoints", {})
            capabilities = manifest_payload.get("capabilities", [])
            if not isinstance(entrypoints, dict):
                raise ValueError("plugin manifest entrypoints must be a mapping")
            if not isinstance(capabilities, list):
                raise ValueError("plugin manifest capabilities must be a list")
            templates_root = entrypoints.get("templates")
            if not isinstance(templates_root, str) or not templates_root.strip():
                if "templates" in capabilities:
                    warnings.append(f"Remote pack '{plugin_id}' declares templates but has no template entrypoint")
                return [], warnings
            prefix = root_prefix / PurePosixPath(templates_root.strip())
            for member in sorted(archive.namelist()):
                member_path = PurePosixPath(member)
                if member.endswith("/") or member_path.suffix.lower() != ".yaml":
                    continue
                if prefix not in (member_path, *member_path.parents):
                    continue
                try:
                    payload = _read_yaml_from_archive(archive, member_path)
                    if payload is None:
                        continue
                    model = self.template_loader.load_payload(payload, source=member_path.as_posix(), plugin_id=plugin_id)
                    item = model.to_dict()
                except Exception as exc:
                    warnings.append(f"Skipped remote template '{member_path.name}' from '{plugin_id}': {exc}")
                    continue
                template = item["template"]
                entries.append(
                    {
                        "entry_id": f"remote:{plugin_id}:{template['id']}",
                        "template_id": template["id"],
                        "name": template["name"],
                        "description": template.get("description") or str(plugin.get("description") or ""),
                        "component_count": len(item.get("components", [])),
                        "preview": _build_preview(item),
                        "plugin_id": plugin_id,
                        "plugin_name": str(plugin.get("name") or plugin_id),
                        "source": "remote",
                        "download_url": plugin.get("download_url"),
                    }
                )
        return entries, warnings

    def _plugin(self, plugin_id: str | None) -> dict[str, Any] | None:
        if not plugin_id:
            return None
        try:
            return self.plugin_manager_service.get_plugin(plugin_id)
        except Exception:
            return None


def _filter_items(items: list[dict[str, Any]], *, search: str, filter_by: str) -> list[dict[str, Any]]:
    needle = search.strip().lower()
    result = items
    if filter_by == "local":
        result = [item for item in result if item["source"] == "local"]
    elif filter_by == "remote":
        result = [item for item in result if item["source"] == "remote"]
    if needle:
        result = [
            item
            for item in result
            if needle in str(item.get("name", "")).lower()
            or needle in str(item.get("description", "")).lower()
            or needle in str(item.get("template_id", "")).lower()
            or needle in str(item.get("plugin_name", "")).lower()
        ]
    return result


def _sort_key(entry: dict[str, Any]) -> tuple[int, str, str]:
    return (0 if entry["source"] == "local" else 1, str(entry["name"]).lower(), str(entry["entry_id"]).lower())


def _plugin_id_from_template(template_id: str) -> str | None:
    if "." not in template_id:
        return None
    return template_id.split(".", 1)[0]


def _build_preview(template_payload: dict[str, Any]) -> str:
    controller = template_payload.get("controller", {})
    surface = controller.get("surface") or {}
    shape = surface.get("shape") or surface.get("type") or "rectangle"
    width = surface.get("width", controller.get("width", "-"))
    height = surface.get("height", controller.get("depth", "-"))
    counts = Counter(component.get("type", "component") for component in template_payload.get("components", []))
    summary = ", ".join(f"{component_type} x{count}" for component_type, count in sorted(counts.items()))
    return "\n".join(
        [
            f"Surface: {shape} {width} x {height} mm",
            f"Components: {len(template_payload.get('components', []))}",
            f"Types: {summary or 'none'}",
        ]
    )


def _find_archive_root(archive: zipfile.ZipFile) -> PurePosixPath:
    names = [PurePosixPath(name) for name in archive.namelist() if name and not name.endswith("/")]
    for filename in ("plugin.yaml", "manifest.yaml"):
        if any(path.name == filename and len(path.parts) == 1 for path in names):
            return PurePosixPath(".")
    top_levels = {path.parts[0] for path in names if path.parts}
    if len(top_levels) == 1:
        return PurePosixPath(next(iter(top_levels)))
    return PurePosixPath(".")


def _read_yaml_from_archive(archive: zipfile.ZipFile, path: PurePosixPath) -> dict[str, Any] | None:
    try:
        content = archive.read(path.as_posix())
    except KeyError:
        return None
    payload = yaml.safe_load(content.decode("utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be a mapping: {path.as_posix()}")
    return payload

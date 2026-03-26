from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ocw_workbench.userdata.persistence import _default_base_dir

DEFAULT_PLUGIN_REGISTRY_CACHE_FILENAME = "plugin_registry_cache.json"


@dataclass(frozen=True)
class RemotePluginRegistryEntry:
    plugin_id: str
    version: str
    download_url: str
    description: str = ""
    name: str | None = None
    plugin_type: str | None = None
    author: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "download_url": self.download_url,
            "description": self.description,
            "type": self.plugin_type,
            "author": self.author,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "RemotePluginRegistryEntry | None":
        data = payload if isinstance(payload, dict) else {}
        plugin_id = data.get("id")
        version = data.get("version")
        download_url = data.get("download_url")
        if not isinstance(plugin_id, str) or not plugin_id.strip():
            return None
        if not isinstance(version, str) or not version.strip():
            return None
        if not isinstance(download_url, str) or not download_url.strip():
            return None
        name = data.get("name")
        plugin_type = data.get("type")
        author = data.get("author")
        description = data.get("description")
        return cls(
            plugin_id=plugin_id.strip(),
            version=version.strip(),
            download_url=download_url.strip(),
            description=description.strip() if isinstance(description, str) else "",
            name=name.strip() if isinstance(name, str) and name.strip() else None,
            plugin_type=plugin_type.strip() if isinstance(plugin_type, str) and plugin_type.strip() else None,
            author=author.strip() if isinstance(author, str) and author.strip() else None,
        )


@dataclass
class RemotePluginRegistryCacheEntry:
    url: str
    fetched_at: str
    entries: list[RemotePluginRegistryEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "fetched_at": self.fetched_at,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "RemotePluginRegistryCacheEntry | None":
        data = payload if isinstance(payload, dict) else {}
        url = data.get("url")
        fetched_at = data.get("fetched_at")
        if not isinstance(url, str) or not url.strip():
            return None
        if not isinstance(fetched_at, str) or not fetched_at.strip():
            return None
        raw_entries = data.get("entries", [])
        entries: list[RemotePluginRegistryEntry] = []
        if isinstance(raw_entries, list):
            for value in raw_entries:
                entry = RemotePluginRegistryEntry.from_dict(value if isinstance(value, dict) else None)
                if entry is not None:
                    entries.append(entry)
        return cls(url=url.strip(), fetched_at=fetched_at.strip(), entries=entries)


@dataclass
class RemotePluginRegistryCacheStore:
    registries: list[RemotePluginRegistryCacheEntry] = field(default_factory=list)
    last_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_url": self.last_url,
            "registries": [entry.to_dict() for entry in self.registries],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "RemotePluginRegistryCacheStore":
        data = payload if isinstance(payload, dict) else {}
        raw_registries = data.get("registries", [])
        registries: list[RemotePluginRegistryCacheEntry] = []
        if isinstance(raw_registries, list):
            for value in raw_registries:
                entry = RemotePluginRegistryCacheEntry.from_dict(value if isinstance(value, dict) else None)
                if entry is not None:
                    registries.append(entry)
        last_url = data.get("last_url")
        return cls(
            registries=registries,
            last_url=last_url.strip() if isinstance(last_url, str) else "",
        )


class PluginRegistryCachePersistence:
    def __init__(
        self,
        base_dir: str | None = None,
        filename: str = DEFAULT_PLUGIN_REGISTRY_CACHE_FILENAME,
    ) -> None:
        self.base_dir = Path(base_dir or _default_base_dir())
        self.filename = filename

    @property
    def path(self) -> Path:
        return self.base_dir / self.filename

    def load(self) -> RemotePluginRegistryCacheStore:
        try:
            content = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return RemotePluginRegistryCacheStore()
        except OSError:
            return RemotePluginRegistryCacheStore()
        if not content.strip():
            return RemotePluginRegistryCacheStore()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return RemotePluginRegistryCacheStore()
        return RemotePluginRegistryCacheStore.from_dict(data)

    def save(self, store: RemotePluginRegistryCacheStore) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(store.to_dict(), indent=2, sort_keys=True)
        self.path.write_text(payload + "\n", encoding="utf-8")

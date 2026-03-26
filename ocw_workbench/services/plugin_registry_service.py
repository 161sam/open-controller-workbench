from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import urlopen

import json

from ocw_workbench.userdata.plugin_registry_store import (
    PluginRegistryCachePersistence,
    RemotePluginRegistryCacheEntry,
    RemotePluginRegistryCacheStore,
    RemotePluginRegistryEntry,
)

_ALLOWED_SCHEMES = {"http", "https", "file"}


class PluginRegistryService:
    def __init__(
        self,
        persistence: PluginRegistryCachePersistence | None = None,
        fetcher: Callable[[str], bytes] | None = None,
        downloader: Callable[[str], bytes] | None = None,
    ) -> None:
        self.persistence = persistence or PluginRegistryCachePersistence()
        self._fetcher = fetcher or _read_url_bytes
        self._downloader = downloader or _read_url_bytes

    def last_registry_url(self) -> str:
        return self.persistence.load().last_url

    def load_cached_registry(self, url: str | None = None) -> dict[str, Any]:
        target_url = (url or self.last_registry_url()).strip()
        if not target_url:
            return _result(url="", entries=[], source="empty", warnings=[], errors=[])
        store = self.persistence.load()
        cache_entry = _find_registry(store, target_url)
        if cache_entry is None:
            store.last_url = target_url
            self.persistence.save(store)
            return _result(url=target_url, entries=[], source="empty", warnings=[], errors=[])
        store.last_url = target_url
        self.persistence.save(store)
        return _result(
            url=target_url,
            entries=[entry.to_dict() for entry in cache_entry.entries],
            source="cache",
            fetched_at=cache_entry.fetched_at,
            warnings=[],
            errors=[],
        )

    def refresh_registry(self, url: str) -> dict[str, Any]:
        target_url = url.strip()
        if not target_url:
            raise ValueError("Registry URL is required")
        _validate_url(target_url)
        try:
            payload = self._fetch_registry_payload(target_url)
        except Exception as exc:
            cached = self.load_cached_registry(target_url)
            if cached["entries"]:
                cached["warnings"] = [f"Remote registry fetch failed, showing cached entries: {exc}"]
                cached["source"] = "cache"
                return cached
            raise
        store = self.persistence.load()
        cache_entry = RemotePluginRegistryCacheEntry(
            url=target_url,
            fetched_at=_timestamp_now(),
            entries=payload["entries"],
        )
        store.registries = [entry for entry in store.registries if entry.url != target_url]
        store.registries.append(cache_entry)
        store.last_url = target_url
        self.persistence.save(store)
        return _result(
            url=target_url,
            entries=[entry.to_dict() for entry in payload["entries"]],
            source="remote",
            fetched_at=cache_entry.fetched_at,
            warnings=payload["warnings"],
            errors=[],
        )

    def download_plugin(self, url: str, plugin_id: str, output_path: str | Path) -> dict[str, Any]:
        target_url = url.strip()
        if not target_url:
            raise ValueError("Registry URL is required")
        entry = self._entry_for_plugin(target_url, plugin_id)
        _validate_url(entry.download_url)
        destination = self._download_destination(output_path, entry)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = self._downloader(entry.download_url)
        destination.write_bytes(payload)
        return {
            "plugin_id": entry.plugin_id,
            "download_url": entry.download_url,
            "output_path": str(destination),
        }

    def get_registry_entry(self, url: str, plugin_id: str) -> dict[str, Any]:
        return self._entry_for_plugin(url.strip(), plugin_id).to_dict()

    def read_plugin_archive(self, url: str, plugin_id: str) -> bytes:
        entry = self._entry_for_plugin(url.strip(), plugin_id)
        _validate_url(entry.download_url)
        return self._downloader(entry.download_url)

    def _entry_for_plugin(self, url: str, plugin_id: str) -> RemotePluginRegistryEntry:
        cached = self.load_cached_registry(url)
        if not cached["entries"]:
            cached = self.refresh_registry(url)
        for entry in cached["entries"]:
            if str(entry.get("id")) == plugin_id:
                parsed = RemotePluginRegistryEntry.from_dict(entry)
                if parsed is not None:
                    return parsed
        raise KeyError(f"Unknown remote plugin id: {plugin_id}")

    def _fetch_registry_payload(self, url: str) -> dict[str, Any]:
        raw = self._fetcher(url)
        try:
            data = json.loads(raw.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise ValueError(f"Registry response is not valid UTF-8: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"Registry response is not valid JSON: {exc}") from exc
        if not isinstance(data, list):
            raise ValueError("Registry response must be a JSON list")

        entries: list[RemotePluginRegistryEntry] = []
        warnings: list[str] = []
        seen_ids: set[str] = set()
        for index, value in enumerate(data):
            if not isinstance(value, dict):
                warnings.append(f"Skipped registry entry #{index + 1}: expected an object")
                continue
            entry = RemotePluginRegistryEntry.from_dict(value)
            if entry is None:
                warnings.append(f"Skipped registry entry #{index + 1}: missing required fields")
                continue
            if entry.plugin_id in seen_ids:
                warnings.append(f"Skipped duplicate registry entry '{entry.plugin_id}'")
                continue
            try:
                _validate_url(entry.download_url)
            except ValueError as exc:
                warnings.append(f"Skipped registry entry '{entry.plugin_id}': {exc}")
                continue
            seen_ids.add(entry.plugin_id)
            entries.append(entry)
        return {"entries": entries, "warnings": warnings}

    def _download_destination(self, output_path: str | Path, entry: RemotePluginRegistryEntry) -> Path:
        target = Path(output_path)
        filename = _download_filename(entry)
        if target.suffix:
            return target
        if target.exists() and target.is_dir():
            return target / filename
        return target / filename


def _find_registry(
    store: RemotePluginRegistryCacheStore,
    url: str,
) -> RemotePluginRegistryCacheEntry | None:
    for entry in store.registries:
        if entry.url == url:
            return entry
    return None


def _result(
    *,
    url: str,
    entries: list[dict[str, Any]],
    source: str,
    warnings: list[str],
    errors: list[str],
    fetched_at: str | None = None,
) -> dict[str, Any]:
    return {
        "url": url,
        "entries": entries,
        "source": source,
        "fetched_at": fetched_at,
        "warnings": list(warnings),
        "errors": list(errors),
    }


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _download_filename(entry: RemotePluginRegistryEntry) -> str:
    path = Path(urlparse(entry.download_url).path)
    if path.name:
        return path.name
    return f"{entry.plugin_id}-{entry.version}.zip"


def _validate_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme or '-'}")
    if parsed.scheme in {"http", "https"} and not parsed.netloc:
        raise ValueError(f"Registry URL is missing a host: {value}")
    if parsed.scheme == "file" and not parsed.path:
        raise ValueError(f"File URL is missing a path: {value}")


def _read_url_bytes(url: str) -> bytes:
    with urlopen(url, timeout=10) as response:  # nosec: read-only download path, no execution
        return response.read()

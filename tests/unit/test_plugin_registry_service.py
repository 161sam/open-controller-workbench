from __future__ import annotations

import json
from pathlib import Path

import pytest

from ocw_workbench.services.plugin_registry_service import PluginRegistryService
from ocw_workbench.userdata.plugin_registry_store import PluginRegistryCachePersistence


def _service(
    tmp_path: Path,
    *,
    fetcher=None,
    downloader=None,
) -> PluginRegistryService:
    return PluginRegistryService(
        persistence=PluginRegistryCachePersistence(base_dir=str(tmp_path)),
        fetcher=fetcher,
        downloader=downloader,
    )


def test_refresh_registry_caches_remote_entries(tmp_path: Path) -> None:
    fetcher = lambda _url: json.dumps(
        [
            {
                "id": "basic_pack",
                "name": "Basic Pack",
                "version": "0.1.0",
                "download_url": "https://example.com/basic_pack.zip",
                "description": "Basic data pack",
                "type": "component_pack",
            }
        ]
    ).encode("utf-8")
    service = _service(tmp_path, fetcher=fetcher)

    result = service.refresh_registry("https://example.com/index.json")
    cached = _service(tmp_path).load_cached_registry("https://example.com/index.json")

    assert result["source"] == "remote"
    assert result["entries"][0]["id"] == "basic_pack"
    assert cached["source"] == "cache"
    assert cached["entries"][0]["download_url"] == "https://example.com/basic_pack.zip"
    assert service.last_registry_url() == "https://example.com/index.json"


def test_refresh_registry_skips_invalid_and_duplicate_entries(tmp_path: Path) -> None:
    fetcher = lambda _url: json.dumps(
        [
            {"id": "ok_pack", "version": "0.1.0", "download_url": "https://example.com/ok_pack.zip"},
            {"id": "", "version": "0.1.0", "download_url": "https://example.com/bad.zip"},
            {"id": "ok_pack", "version": "0.2.0", "download_url": "https://example.com/dup.zip"},
            "broken",
        ]
    ).encode("utf-8")
    service = _service(tmp_path, fetcher=fetcher)

    result = service.refresh_registry("https://example.com/index.json")

    assert [entry["id"] for entry in result["entries"]] == ["ok_pack"]
    assert any("missing required fields" in warning for warning in result["warnings"])
    assert any("duplicate registry entry 'ok_pack'" in warning for warning in result["warnings"])
    assert any("expected an object" in warning for warning in result["warnings"])


def test_refresh_registry_falls_back_to_cache_on_error(tmp_path: Path) -> None:
    seeded = _service(
        tmp_path,
        fetcher=lambda _url: json.dumps(
            [
                {
                    "id": "cached_pack",
                    "version": "1.0.0",
                    "download_url": "https://example.com/cached_pack.zip",
                }
            ]
        ).encode("utf-8"),
    )
    seeded.refresh_registry("https://example.com/index.json")
    failing = _service(tmp_path, fetcher=lambda _url: (_ for _ in ()).throw(OSError("network down")))

    result = failing.refresh_registry("https://example.com/index.json")

    assert result["source"] == "cache"
    assert result["entries"][0]["id"] == "cached_pack"
    assert any("showing cached entries" in warning for warning in result["warnings"])


def test_download_plugin_writes_zip_payload(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        fetcher=lambda _url: json.dumps(
            [
                {
                    "id": "basic_pack",
                    "version": "0.1.0",
                    "download_url": "https://example.com/basic_pack.zip",
                }
            ]
        ).encode("utf-8"),
        downloader=lambda _url: b"zip-bytes",
    )
    service.refresh_registry("https://example.com/index.json")

    result = service.download_plugin("https://example.com/index.json", "basic_pack", tmp_path / "downloads")

    archive = Path(result["output_path"])
    assert archive.exists()
    assert archive.read_bytes() == b"zip-bytes"
    assert archive.name == "basic_pack.zip"


def test_corrupt_cache_file_returns_empty_registry(tmp_path: Path) -> None:
    persistence = PluginRegistryCachePersistence(base_dir=str(tmp_path))
    persistence.path.parent.mkdir(parents=True, exist_ok=True)
    persistence.path.write_text("{ broken json", encoding="utf-8")
    service = PluginRegistryService(persistence=persistence)

    result = service.load_cached_registry("https://example.com/index.json")

    assert result["entries"] == []
    assert result["source"] == "empty"


def test_refresh_registry_rejects_unsupported_url_scheme(tmp_path: Path) -> None:
    service = _service(tmp_path, fetcher=lambda _url: b"[]")

    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        service.refresh_registry("ftp://example.com/index.json")

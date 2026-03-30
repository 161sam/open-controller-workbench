from __future__ import annotations

from pathlib import Path

import pytest

from ocw_workbench.services.plugin_manager_service import PluginManagerService
from ocw_workbench.services.plugin_service import reset_plugin_service
from ocw_workbench.userdata.plugin_state_store import PluginStatePersistence
from ocw_workbench.utils.yaml_io import dump_yaml


def _service(tmp_path: Path, internal_root: Path | None = None) -> PluginManagerService:
    return PluginManagerService(
        persistence=PluginStatePersistence(base_dir=str(tmp_path)),
        internal_root=internal_root,
        external_root=tmp_path / "external",
    )


@pytest.fixture(autouse=True)
def _reset_plugin_service_after_test():
    yield
    reset_plugin_service()


def test_plugin_manager_lists_internal_plugins() -> None:
    reset_plugin_service()
    service = PluginManagerService()

    plugins = service.list_plugins()
    ids = {item["id"] for item in plugins}

    assert "default_exporters" in ids
    assert "basic_components_pack" in ids
    assert "basic_templates_pack" in ids


def test_plugin_manager_persists_enable_disable_state(tmp_path: Path) -> None:
    service = _service(tmp_path)

    disabled = service.set_enabled("default_exporters", False)
    reloaded = _service(tmp_path).get_plugin("default_exporters")

    assert disabled["status"] == "disabled"
    assert reloaded["status"] == "disabled"


def test_required_plugin_cannot_be_disabled(tmp_path: Path) -> None:
    internal_root = tmp_path / "internal"
    plugin_dir = internal_root / "required_plugin"
    plugin_dir.mkdir(parents=True)
    dump_yaml(
        plugin_dir / "manifest.yaml",
        {
            "plugin": {
                "id": "required_plugin",
                "name": "Required Plugin",
                "version": "0.1.0",
                "api_version": "1.0",
                "type": "workflow",
                "non_disableable": True,
            },
            "entrypoints": {},
            "capabilities": [],
            "dependencies": [],
        },
    )
    service = _service(tmp_path, internal_root=internal_root)

    with pytest.raises(ValueError, match="cannot be disabled"):
        service.set_enabled("required_plugin", False)


def test_corrupt_plugin_state_file_falls_back_to_defaults(tmp_path: Path) -> None:
    persistence = PluginStatePersistence(base_dir=str(tmp_path))
    persistence.path.parent.mkdir(parents=True, exist_ok=True)
    persistence.path.write_text("{ broken json", encoding="utf-8")
    service = _service(tmp_path)

    plugin = service.get_plugin("default_exporters")

    assert plugin["status"] == "enabled"


def test_invalid_and_incompatible_plugins_are_visible(tmp_path: Path) -> None:
    internal_root = tmp_path / "internal"
    invalid_dir = internal_root / "broken_plugin"
    incompatible_dir = internal_root / "future_plugin"
    invalid_dir.mkdir(parents=True)
    incompatible_dir.mkdir(parents=True)
    (invalid_dir / "manifest.yaml").write_text("not: [valid", encoding="utf-8")
    dump_yaml(
        incompatible_dir / "manifest.yaml",
        {
            "plugin": {
                "id": "future_plugin",
                "name": "Future Plugin",
                "version": "0.1.0",
                "api_version": "2.0",
                "type": "workflow",
            },
            "entrypoints": {},
            "capabilities": [],
            "dependencies": [],
        },
    )

    reset_plugin_service(internal_root=internal_root, external_root=tmp_path / "external")
    service = _service(tmp_path, internal_root=internal_root)
    plugins = {item["id"]: item for item in service.list_plugins()}

    assert plugins["broken_plugin"]["status"] == "error"
    assert plugins["future_plugin"]["status"] == "incompatible"

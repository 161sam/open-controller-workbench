from __future__ import annotations

from pathlib import Path

import pytest

from ocw_workbench.services.plugin_manager_service import PluginManagerService
from ocw_workbench.services.plugin_pack_service import PluginPackService
from ocw_workbench.services.plugin_service import reset_plugin_service
from ocw_workbench.userdata.plugin_state_store import PluginStatePersistence


def _services(tmp_path: Path) -> tuple[PluginManagerService, PluginPackService]:
    persistence = PluginStatePersistence(base_dir=str(tmp_path / "userdata"))
    manager = PluginManagerService(
        persistence=persistence,
        internal_root=Path("ocw_workbench/plugins/internal"),
        external_root=tmp_path / "external",
    )
    pack = PluginPackService(plugin_manager_service=manager, external_root=tmp_path / "external")
    return manager, pack


@pytest.fixture(autouse=True)
def _reset_plugin_service_after_test():
    yield
    reset_plugin_service()


def test_export_data_plugin_pack_creates_zip(tmp_path: Path) -> None:
    reset_plugin_service(
        internal_root=Path("ocw_workbench/plugins/internal"),
        external_root=tmp_path / "external",
        state_base_dir=tmp_path / "userdata",
    )
    _manager, service = _services(tmp_path)

    result = service.export_plugin_pack("basic_components_pack", tmp_path / "packs")

    archive = Path(result["zip_path"])
    assert archive.exists()
    assert archive.suffix == ".zip"


def test_export_rejects_code_plugin_pack(tmp_path: Path) -> None:
    reset_plugin_service(
        internal_root=Path("ocw_workbench/plugins/internal"),
        external_root=tmp_path / "external",
        state_base_dir=tmp_path / "userdata",
    )
    _manager, service = _services(tmp_path)

    with pytest.raises(ValueError, match="not a data plugin"):
        service.export_plugin_pack("default_exporters", tmp_path / "packs")


def test_import_plugin_pack_installs_into_external_root(tmp_path: Path) -> None:
    import zipfile

    archive = tmp_path / "community_pack.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(
            "plugin.yaml",
            "\n".join(
                [
                    "plugin:",
                    "  id: community_pack",
                    "  name: Community Pack",
                    "  version: 0.1.0",
                    "  api_version: '1.0'",
                    "  type: component_pack",
                    "entrypoints:",
                    "  components: components/",
                    "capabilities:",
                    "  - components",
                    "dependencies: []",
                ]
            ),
        )
        handle.writestr(
            "components/knob.yaml",
            "\n".join(
                [
                    "id: community_encoder",
                    "type: encoder",
                    "manufacturer: Test",
                    "mechanical: {}",
                    "electrical: {}",
                    "ui:",
                    "  category: controls",
                ]
            ),
        )

    reset_plugin_service(
        internal_root=Path("ocw_workbench/plugins/internal"),
        external_root=tmp_path / "external",
        state_base_dir=tmp_path / "userdata",
    )
    manager, service = _services(tmp_path)

    imported = service.import_plugin_pack(archive)
    plugins = {item["id"]: item for item in manager.list_plugins()}

    assert imported["plugin_id"] == "community_pack"
    assert plugins["community_pack"]["status"] == "enabled"
    assert (tmp_path / "external" / "community_pack" / "plugin.yaml").exists()


def test_import_rejects_archive_with_python_file(tmp_path: Path) -> None:
    import zipfile

    archive = tmp_path / "bad_pack.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("plugin.yaml", "plugin:\n  id: bad\n  name: Bad\n  version: 0.1.0\n  api_version: '1.0'\n  type: template_pack\nentrypoints: {}\ncapabilities: []\ndependencies: []\n")
        handle.writestr("evil.py", "print('boom')")

    reset_plugin_service(
        internal_root=Path("ocw_workbench/plugins/internal"),
        external_root=tmp_path / "external",
        state_base_dir=tmp_path / "userdata",
    )
    _manager, service = _services(tmp_path)

    with pytest.raises(ValueError, match="blocked file type"):
        service.import_plugin_pack(archive)

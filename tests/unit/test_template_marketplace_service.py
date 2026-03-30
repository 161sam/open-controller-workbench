from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
import zipfile

import pytest

from ocw_workbench.gui.panels.create_panel import CreatePanel
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.plugin_manager_service import PluginManagerService
from ocw_workbench.services.plugin_registry_service import PluginRegistryService
from ocw_workbench.services.plugin_service import reset_plugin_service
from ocw_workbench.services.template_marketplace_service import TemplateMarketplaceService
from ocw_workbench.services.template_service import TemplateService
from ocw_workbench.userdata.plugin_registry_store import PluginRegistryCachePersistence
from ocw_workbench.userdata.plugin_state_store import PluginStatePersistence


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.recompute_count = 0

    def recompute(self) -> None:
        self.recompute_count += 1


@pytest.fixture(autouse=True)
def _reset_plugin_service_after_test():
    yield
    reset_plugin_service()


def _remote_archive_bytes() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "plugin.yaml",
            "\n".join(
                [
                    "plugin:",
                    "  id: remote_templates_pack",
                    "  name: Remote Templates",
                    "  version: 0.2.0",
                    "  api_version: '1.0'",
                    "  type: template_pack",
                    "  description: Remote template pack",
                    "entrypoints:",
                    "  templates: templates/",
                    "capabilities:",
                    "  - templates",
                    "dependencies: []",
                ]
            ),
        )
        archive.writestr(
            "templates/mini.yaml",
            "\n".join(
                [
                    "id: mini_remote",
                    "name: Mini Remote",
                    "description: Compact remote controller",
                    "shape:",
                    "  type: rectangle",
                    "  width: 120",
                    "  height: 80",
                    "components:",
                    "  - ref: enc1",
                    "    component: basic_components_pack.rotary_encoder_12mm",
                    "    position: [20, 20]",
                    "  - ref: btn1",
                    "    component: basic_components_pack.tact_button_6mm",
                    "    position: [60, 20]",
                ]
            ),
        )
    return buffer.getvalue()


def _marketplace_service(tmp_path: Path) -> TemplateMarketplaceService:
    registry_service = PluginRegistryService(
        persistence=PluginRegistryCachePersistence(base_dir=str(tmp_path / "userdata")),
        fetcher=lambda _url: json.dumps(
            [
                {
                    "id": "remote_templates_pack",
                    "name": "Remote Templates",
                    "version": "0.2.0",
                    "download_url": "https://example.com/remote_templates_pack.zip",
                    "description": "Remote template pack",
                    "type": "template_pack",
                }
            ]
        ).encode("utf-8"),
        downloader=lambda _url: _remote_archive_bytes(),
    )
    manager = PluginManagerService(
        persistence=PluginStatePersistence(base_dir=str(tmp_path / "state")),
        internal_root=Path("ocw_workbench/plugins/internal"),
        external_root=Path("ocw_workbench/plugins/external"),
    )
    return TemplateMarketplaceService(
        template_service=TemplateService(),
        plugin_manager_service=manager,
        plugin_registry_service=registry_service,
    )


def _select_combo_by_contains(combo, value: str) -> None:
    for index, item in enumerate(combo.items):
        if value in item:
            combo.setCurrentIndex(index)
            return
    raise AssertionError(f"Missing combo entry containing {value!r}")


def test_marketplace_lists_local_templates_with_plugin_origin(tmp_path: Path) -> None:
    service = _marketplace_service(tmp_path)

    result = service.list_entries(filter_by="local")

    local = {entry["template_id"]: entry for entry in result["entries"]}
    assert "basic_templates_pack.mini_controller" in local
    assert local["basic_templates_pack.mini_controller"]["component_count"] == 3
    assert local["basic_templates_pack.mini_controller"]["plugin_id"] == "basic_templates_pack"
    assert local["basic_templates_pack.mini_controller"]["source"] == "local"


def test_marketplace_loads_remote_templates_from_plugin_pack(tmp_path: Path) -> None:
    service = _marketplace_service(tmp_path)

    result = service.list_entries(
        filter_by="remote",
        remote_registry_url="https://example.com/index.json",
        refresh_remote=True,
    )

    assert [entry["template_id"] for entry in result["entries"]] == ["remote_templates_pack.mini_remote"]
    assert result["entries"][0]["component_count"] == 2
    assert result["entries"][0]["plugin_name"] == "Remote Templates"


def test_marketplace_search_filters_across_local_and_remote(tmp_path: Path) -> None:
    service = _marketplace_service(tmp_path)
    service.list_entries(remote_registry_url="https://example.com/index.json", refresh_remote=True)

    result = service.list_entries(
        search="remote",
        filter_by="all",
        remote_registry_url="https://example.com/index.json",
    )

    assert result["entries"]
    assert all("remote" in entry["name"].lower() or "remote" in entry["description"].lower() for entry in result["entries"])


def test_create_panel_marketplace_applies_local_template(tmp_path: Path) -> None:
    service = _marketplace_service(tmp_path)
    panel = CreatePanel(
        FakeDocument(),
        controller_service=ControllerService(),
        template_marketplace_service=service,
    )

    _select_combo_by_contains(panel.form["marketplace_list"], "basic_templates_pack.mini_controller")
    result = panel.apply_selected_marketplace_template()

    assert result["template_id"] == "basic_templates_pack.mini_controller"
    assert panel.selected_template_id() == "basic_templates_pack.mini_controller"


def test_create_panel_marketplace_rejects_apply_for_remote_template(tmp_path: Path) -> None:
    service = _marketplace_service(tmp_path)
    panel = CreatePanel(
        FakeDocument(),
        controller_service=ControllerService(),
        template_marketplace_service=service,
    )
    panel.form["marketplace_registry_url"].setText("https://example.com/index.json")
    panel.refresh_marketplace(refresh_remote=True)
    _select_combo_by_contains(panel.form["marketplace_list"], "remote_templates_pack.mini_remote")

    with pytest.raises(ValueError, match="must be imported"):
        panel.apply_selected_marketplace_template()

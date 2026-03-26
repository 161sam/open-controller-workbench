from pathlib import Path

import pytest

from ocw_workbench.services.template_editor_service import TemplateEditorService
from ocw_workbench.templates.fcstd_importer import build_imported_template_payload
from ocw_workbench.templates.registry import TemplateRegistry
from ocw_workbench.userdata.persistence import UserDataPersistence


def test_template_editor_validation_accepts_imported_payload():
    payload = build_imported_template_payload(
        template_id="imported_panel",
        name="Imported Panel",
        width=180.0,
        depth=120.0,
        height=35.0,
        source_filename="/tmp/example.FCStd",
        object_name="TopSurface",
        target_ref="TopSurface::Face1",
        rotation_deg=90.0,
        origin={"type": "manual", "offset_x": 2.0, "offset_y": 4.0},
        mounting_holes=[{"id": "mh1", "x": 10.0, "y": 15.0, "diameter": 3.0}],
    )

    result = TemplateEditorService().validate_template(payload)

    assert result["valid"] is True
    assert result["warnings"] == []


def test_template_editor_validation_rejects_invalid_fields():
    payload = build_imported_template_payload(
        template_id="Invalid-ID",
        name="",
        width=0.0,
        depth=120.0,
        height=35.0,
        source_filename="/tmp/example.FCStd",
        object_name="TopSurface",
        target_ref="TopSurface::Face1",
    )
    payload["zones"] = [{"id": "", "x": 0.0, "y": 0.0, "width": -5.0, "height": 10.0}]

    result = TemplateEditorService().validate_template(payload)

    assert result["valid"] is False
    assert any("Template id" in entry for entry in result["errors"])
    assert any("Template name" in entry for entry in result["errors"])
    assert any("Controller width" in entry for entry in result["errors"])
    assert any("Zone" in entry for entry in result["errors"])


def test_template_editor_service_saves_and_registry_reloads(monkeypatch, tmp_path: Path):
    user_base = tmp_path / "userdata"
    monkeypatch.setenv("OCW_USERDATA_DIR", str(user_base))
    service = TemplateEditorService(
        registry=TemplateRegistry(),
        userdata=UserDataPersistence(base_dir=str(user_base)),
    )
    payload = build_imported_template_payload(
        template_id="user_imported",
        name="User Imported",
        width=100.0,
        depth=60.0,
        height=30.0,
        source_filename="/tmp/user.FCStd",
        object_name="Panel",
        target_ref="Panel",
    )
    payload["zones"] = [{"id": "main", "x": 10.0, "y": 10.0, "width": 40.0, "height": 20.0}]

    output_path = service.save_user_template(payload, overwrite=False)
    loaded = service.load_template(output_path)

    assert output_path.exists()
    assert loaded["template"]["id"] == "user_imported"
    assert loaded["metadata"]["editor"]["validated"] is True
    assert loaded["zones"][0]["id"] == "main"

    ids = {item["template"]["id"] for item in TemplateRegistry().list_templates()}
    assert "user_imported" in ids


def test_template_editor_service_requires_explicit_overwrite(monkeypatch, tmp_path: Path):
    user_base = tmp_path / "userdata"
    monkeypatch.setenv("OCW_USERDATA_DIR", str(user_base))
    service = TemplateEditorService(
        registry=TemplateRegistry(),
        userdata=UserDataPersistence(base_dir=str(user_base)),
    )
    payload = build_imported_template_payload(
        template_id="user_imported",
        name="User Imported",
        width=100.0,
        depth=60.0,
        height=30.0,
        source_filename="/tmp/user.FCStd",
        object_name="Panel",
        target_ref="Panel",
    )

    service.save_user_template(payload, overwrite=False)
    with pytest.raises(FileExistsError, match="overwrite"):
        service.save_user_template(payload, overwrite=False)
    output_path = service.save_user_template(payload, overwrite=True)

    assert output_path.exists()

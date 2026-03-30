from pathlib import Path

import pytest

from ocw_workbench.gui.panels.template_inspector_panel import TemplateInspectorPanel
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


def test_template_editor_service_builds_parameter_editor_model_from_template():
    service = TemplateEditorService()
    payload = service.load_template("plugins/plugin_midicontroller/templates/fader_strip.yaml")

    model = service.build_parameter_editor_model(payload)

    assert any(item["id"] == "fader_length" for item in model["definitions"])
    assert model["values"]["fader_length"] == 60
    assert any(item["id"] == "compact_fader" for item in model["presets"])


def test_template_editor_service_applies_parameter_defaults_and_resolves_preview():
    service = TemplateEditorService()
    payload = service.load_template("plugins/plugin_midicontroller/templates/pad_grid_4x4.yaml")

    updated = service.apply_parameter_defaults(
        payload,
        values={"pad_count_x": 8, "pad_count_y": 2, "case_width": 300.0, "case_depth": 110.0},
        preset_id="pad_grid_8x2",
    )
    resolved = service.inspector_preview_payload(
        payload,
        values={"pad_count_x": 8, "pad_count_y": 2, "case_width": 300.0, "case_depth": 110.0},
        preset_id="pad_grid_8x2",
    )

    assert next(item for item in updated["parameters"] if item["id"] == "pad_count_x")["default"] == 8
    assert updated["metadata"]["editor"]["parameter_preset_id"] == "pad_grid_8x2"
    assert resolved["controller"]["width"] == 300.0
    assert resolved["layout"]["config"]["cols"] == 8
    assert len(resolved["components"]) == 16


def test_template_editor_service_save_template_to_path_rejects_non_user_target(monkeypatch, tmp_path: Path):
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

    with pytest.raises(PermissionError, match="Save Template"):
        service.save_template_to_path(payload, tmp_path / "external.yaml", overwrite=True)


def test_template_inspector_panel_maps_parameters_and_can_reset_defaults(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("ocw_workbench.gui.panels.template_inspector_panel.load_qt", lambda: (None, None, None))
    monkeypatch.setattr("ocw_workbench.gui.widgets.parameter_editor.load_qt", lambda: (None, None, None))
    service = TemplateEditorService()
    panel = TemplateInspectorPanel("plugins/plugin_midicontroller/templates/fader_strip.yaml", template_editor_service=service)

    panel.form["parameter_editor"].control_widget("fader_length").setCurrentIndex(0)
    panel.handle_parameter_widget_changed()
    preview = panel.refresh_parameter_preview(publish=False)
    panel.handle_reset_all_clicked()

    assert preview["components"][0]["library_ref"] == "generic_45mm_linear_fader"
    assert panel.form["parameter_editor"].values()["fader_length"] == 60

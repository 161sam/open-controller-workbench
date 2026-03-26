from pathlib import Path

from ocw_workbench.templates.fcstd_importer import (
    BoundingBoxData,
    FCStdTemplateImporter,
    build_imported_template_payload,
    project_bbox_to_template_dimensions,
)
from ocw_workbench.templates.loader import TemplateLoader
from ocw_workbench.templates.registry import TemplateRegistry
from ocw_workbench.userdata.persistence import UserDataPersistence


def test_project_bbox_to_template_dimensions_swaps_for_quarter_turns():
    bbox = BoundingBoxData(xmin=0.0, ymin=0.0, zmin=0.0, xmax=120.0, ymax=80.0, zmax=35.0)

    assert project_bbox_to_template_dimensions(bbox, rotation_deg=0.0) == (120.0, 80.0)
    assert project_bbox_to_template_dimensions(bbox, rotation_deg=90.0) == (80.0, 120.0)
    assert project_bbox_to_template_dimensions(bbox, rotation_deg=180.0) == (120.0, 80.0)


def test_build_imported_template_payload_is_valid_for_loader():
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

    loaded = TemplateLoader().load_payload(payload, source="imported_panel.yaml")

    assert loaded.id == "imported_panel"
    assert loaded.controller["width"] == 180.0
    assert loaded.controller["mounting_holes"][0]["id"] == "mh1"
    assert loaded.metadata["source"]["type"] == "fcstd"
    assert payload["metadata"]["source"]["type"] == "fcstd"


def test_template_registry_loads_user_templates_folder(monkeypatch, tmp_path: Path):
    user_base = tmp_path / "userdata"
    templates_dir = user_base / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
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
    importer = FCStdTemplateImporter(userdata=UserDataPersistence(base_dir=str(user_base)))
    output_path = importer.templates_dir / "user_imported.yaml"
    from ocw_workbench.utils.yaml_io import dump_yaml

    dump_yaml(output_path, payload)
    monkeypatch.setenv("OCW_USERDATA_DIR", str(user_base))

    registry = TemplateRegistry()
    templates = registry.list_templates()
    ids = {item["template"]["id"] for item in templates}
    imported = next(item for item in templates if item["template"]["id"] == "user_imported")

    assert "encoder_module" in ids
    assert "user_imported" in ids
    assert imported["metadata"]["source"]["type"] == "fcstd"
    assert imported["source_path"].endswith("user_imported.yaml")

from __future__ import annotations

from pathlib import Path

from ocw_workbench.services.export_plugin_service import ExportPluginService


def _project() -> dict[str, object]:
    controller = {
        "id": "eurorack_demo",
        "width": 25.4,
        "depth": 128.5,
        "height": 30.0,
        "top_thickness": 3.0,
        "surface": {"shape": "rectangle", "width": 25.4, "height": 128.5},
        "mounting_holes": [{"id": "mh1", "x": 5.0, "y": 10.0, "diameter": 3.2}],
    }
    components = [
        {"id": "enc1", "type": "encoder", "x": 12.7, "y": 40.0, "rotation": 0.0, "library_ref": "alps_ec11e15204a3"},
        {"id": "btn1", "type": "button", "x": 12.7, "y": 80.0, "rotation": 0.0, "library_ref": "omron_b3f_1000"},
    ]
    return {"controller": controller, "components": components}


def test_export_plugin_service_lists_new_exporters() -> None:
    service = ExportPluginService()

    exporters = service.list_exporters()

    assert {"jlcpcb", "mouser_bom", "eurorack_panel", "svg_panel"} <= set(exporters)


def test_jlcpcb_export_writes_bom_and_cpl_csv(tmp_path: Path) -> None:
    result = ExportPluginService().export("jlcpcb", _project(), tmp_path)

    bom_path = Path(result["bom_csv"])
    cpl_path = Path(result["cpl_csv"])
    assert bom_path.exists()
    assert cpl_path.exists()
    assert "LCSC Part #" in bom_path.read_text(encoding="utf-8")
    assert "Designator" in cpl_path.read_text(encoding="utf-8")


def test_mouser_export_writes_expected_csv_columns(tmp_path: Path) -> None:
    result = ExportPluginService().export("mouser_bom", _project(), tmp_path / "mouser.csv")

    content = Path(result["bom_csv"]).read_text(encoding="utf-8")
    assert "Manufacturer Part Number" in content
    assert "Quantity" in content


def test_eurorack_export_computes_hp_and_mounting(tmp_path: Path) -> None:
    result = ExportPluginService().export("eurorack_panel", _project(), tmp_path)

    content = Path(result["output_path"]).read_text(encoding="utf-8")
    assert "width_hp: 5" in content
    assert "height_mm: 128.5" in content
    assert "mounting" in content


def test_svg_panel_export_writes_outline_and_cutouts(tmp_path: Path) -> None:
    result = ExportPluginService().export("svg_panel", _project(), tmp_path / "panel.svg")

    content = Path(result["output_path"]).read_text(encoding="utf-8")
    assert "<svg" in content
    assert "<rect" in content
    assert "<circle" in content

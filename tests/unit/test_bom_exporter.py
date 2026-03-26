from pathlib import Path

from ocw_workbench.exporters.bom_exporter import export_bom_csv, export_bom_yaml


def test_bom_exporters_write_yaml_and_csv(tmp_path: Path):
    bom = {
        "schema_version": "ocf-manufacturing/v1",
        "export_type": "bom",
        "items": [
            {
                "item_id": "bom:test",
                "quantity": 2,
                "manufacturer": "ACME",
                "part_number": "P-1",
                "description": "Test Part",
                "category": "electronics",
                "notes": "note",
            }
        ],
    }

    yaml_path = tmp_path / "controller.bom.yaml"
    csv_path = tmp_path / "controller.bom.csv"
    export_bom_yaml(bom, yaml_path)
    export_bom_csv(bom, csv_path)

    assert yaml_path.exists()
    assert csv_path.exists()
    assert "Test Part" in csv_path.read_text(encoding="utf-8")

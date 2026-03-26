from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ocw_workbench.plugins.context import PluginContext


def register_exporters(context: PluginContext) -> None:
    context.register_provider("exporters", "mouser_bom", export)


def export(project: dict[str, Any], output_path: str | Path) -> dict[str, Any]:
    path = _csv_path(output_path, "mouser_bom.csv")
    warnings: list[str] = []
    rows: list[dict[str, str]] = []
    for item in project.get("bom", {}).get("items", []):
        category = str(item.get("category") or "")
        if category in {"mechanical", "enclosure", "fasteners", "pcb"}:
            continue
        manufacturer = str(item.get("manufacturer") or "")
        part_number = str(item.get("part_number") or "")
        if not manufacturer:
            warnings.append(f"Missing manufacturer for '{item.get('component')}'")
        if not part_number:
            warnings.append(f"Missing part number for '{item.get('component')}'")
        rows.append(
            {
                "Manufacturer": manufacturer,
                "Manufacturer Part Number": part_number,
                "Quantity": str(int(item.get("quantity", 0) or 0)),
                "Description": str(item.get("description") or ""),
                "Mouser Part Number": str(item.get("mouser_part_number") or ""),
            }
        )

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "Manufacturer",
                "Manufacturer Part Number",
                "Quantity",
                "Description",
                "Mouser Part Number",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return {"bom_csv": str(path), "warnings": warnings}


def _csv_path(output_path: str | Path, default_name: str) -> Path:
    path = Path(output_path)
    if path.suffix:
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    path.mkdir(parents=True, exist_ok=True)
    return path / default_name

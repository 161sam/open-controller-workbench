from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

from ocw_workbench.plugins.context import PluginContext


def register_exporters(context: PluginContext) -> None:
    context.register_provider("exporters", "jlcpcb", export)


def export(project: dict[str, Any], output_path: str | Path) -> dict[str, Any]:
    base = _base_path(output_path, "jlcpcb")
    bom_path = base.with_name(f"{base.stem}.bom.csv")
    cpl_path = base.with_name(f"{base.stem}.cpl.csv")
    warnings: list[str] = []

    rows: list[dict[str, str]] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in project.get("component_records", []):
        grouped[str(record.get("library_ref") or record.get("component_id"))].append(record)

    for records in grouped.values():
        first = records[0]
        library_item = first.get("library_item") or {}
        part_number = str(library_item.get("part_number") or "")
        if not part_number:
            warnings.append(f"Missing LCSC Part # for '{first.get('library_ref')}'")
        rows.append(
            {
                "Comment": str(library_item.get("description") or first.get("library_ref") or ""),
                "Designator": ",".join(str(item["designator"]) for item in records),
                "Footprint": str(first.get("footprint") or ""),
                "LCSC Part #": part_number,
            }
        )

    _write_csv(bom_path, ["Comment", "Designator", "Footprint", "LCSC Part #"], rows)

    cpl_rows = [
        {
            "Designator": str(record["designator"]),
            "Mid X": f"{float(record['x_mm']):.2f}mm",
            "Mid Y": f"{float(record['y_mm']):.2f}mm",
            "Layer": "TopLayer",
            "Rotation": f"{float(record['rotation_deg']):.2f}",
        }
        for record in project.get("component_records", [])
        if record.get("footprint")
    ]
    _write_csv(cpl_path, ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"], cpl_rows)
    return {"bom_csv": str(bom_path), "cpl_csv": str(cpl_path), "warnings": warnings}


def _base_path(output_path: str | Path, default_name: str) -> Path:
    path = Path(output_path)
    if path.suffix:
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.with_suffix("")
    path.mkdir(parents=True, exist_ok=True)
    return path / default_name


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

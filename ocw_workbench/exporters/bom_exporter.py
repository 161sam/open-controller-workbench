from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ocw_workbench.utils.yaml_io import dump_yaml


def export_bom_yaml(data: dict[str, Any], path: str | Path) -> None:
    dump_yaml(path, data)


def export_bom_csv(data: dict[str, Any], path: str | Path) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["quantity", "manufacturer", "part_number", "description", "category", "notes"]
    with file_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in data.get("items", []):
            writer.writerow(
                {
                    "quantity": item.get("quantity", 0),
                    "manufacturer": item.get("manufacturer") or "",
                    "part_number": item.get("part_number") or "",
                    "description": item.get("description") or "",
                    "category": item.get("category") or "",
                    "notes": item.get("notes") or "",
                }
            )

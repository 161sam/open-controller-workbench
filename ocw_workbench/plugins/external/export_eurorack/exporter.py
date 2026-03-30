from __future__ import annotations

from pathlib import Path
from typing import Any

from ocw_workbench.plugins.context import PluginContext
from ocw_workbench.utils.yaml_io import dump_yaml

EURORACK_HEIGHT_MM = 128.5
HP_WIDTH_MM = 5.08


def register_exporters(context: PluginContext) -> None:
    context.register_provider("exporters", "eurorack_panel", export)


def export(project: dict[str, Any], output_path: str | Path) -> dict[str, Any]:
    path = _yaml_path(output_path, "eurorack_panel.yaml")
    controller = project.get("controller", {})
    surface = controller.get("surface", {})
    width_mm = float(surface.get("width", controller.get("width", 0.0)) or 0.0)
    height_mm = float(surface.get("height", controller.get("depth", 0.0)) or 0.0)
    width_hp = round(width_mm / HP_WIDTH_MM) if width_mm else 0
    warnings: list[str] = []
    if str(surface.get("shape", "rectangle")) != "rectangle":
        warnings.append("Controller shape is not rectangular; Eurorack mapping may be approximate")
    if height_mm and abs(height_mm - EURORACK_HEIGHT_MM) > 0.5:
        warnings.append(f"Panel height {height_mm:.2f} mm differs from Eurorack standard {EURORACK_HEIGHT_MM:.1f} mm")

    top_part = next((part for part in project.get("manufacturing", {}).get("parts", []) if part.get("part_id") == "top_plate"), {})
    operations = top_part.get("operations", [])
    holes = [item for item in operations if item.get("shape") == "circle" and item.get("type") != "mounting_hole"]
    cutouts = [item for item in operations if item.get("shape") != "circle"]
    mounting = [item for item in operations if item.get("type") == "mounting_hole"]
    payload = {
        "schema_version": "ocf-export-plugin/v1",
        "export_type": "eurorack_panel",
        "width_hp": width_hp,
        "width_mm": width_mm,
        "height_mm": EURORACK_HEIGHT_MM,
        "holes": holes,
        "cutouts": cutouts,
        "mounting": mounting,
        "warnings": warnings,
    }
    dump_yaml(path, payload)
    return {"output_path": str(path), "warnings": warnings}


def _yaml_path(output_path: str | Path, default_name: str) -> Path:
    path = Path(output_path)
    if path.suffix:
        return path
    path.mkdir(parents=True, exist_ok=True)
    return path / default_name

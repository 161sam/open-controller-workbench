from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from ocw_workbench.plugins.context import PluginContext


def register_exporters(context: PluginContext) -> None:
    context.register_provider("exporters", "svg_panel", export)


def export(project: dict[str, Any], output_path: str | Path) -> dict[str, Any]:
    path = _svg_path(output_path, "panel.svg")
    controller = project.get("controller", {})
    surface = controller.get("surface", {})
    width = float(surface.get("width", controller.get("width", 0.0)) or 0.0)
    height = float(surface.get("height", controller.get("depth", 0.0)) or 0.0)
    operations = next(
        (part.get("operations", []) for part in project.get("manufacturing", {}).get("parts", []) if part.get("part_id") == "top_plate"),
        [],
    )
    elements = [
        f'<rect x="0" y="0" width="{width:.2f}" height="{height:.2f}" fill="none" stroke="black" stroke-width="0.4" />'
    ]
    for operation in operations:
        position = operation.get("position", {})
        dims = operation.get("dimensions", {})
        if operation.get("shape") == "circle":
            radius = float(dims.get("diameter_mm", 0.0) or 0.0) / 2.0
            elements.append(
                f'<circle cx="{float(position.get("x_mm", 0.0)):.2f}" cy="{float(position.get("y_mm", 0.0)):.2f}" '
                f'r="{radius:.2f}" fill="none" stroke="black" stroke-width="0.3" />'
            )
        else:
            width_mm = float(dims.get("width_mm", 0.0) or 0.0)
            height_mm = float(dims.get("height_mm", 0.0) or 0.0)
            x = float(position.get("x_mm", 0.0)) - width_mm / 2.0
            y = float(position.get("y_mm", 0.0)) - height_mm / 2.0
            elements.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{width_mm:.2f}" height="{height_mm:.2f}" '
                f'fill="none" stroke="black" stroke-width="0.3" />'
            )
        source_component = operation.get("source_component_id")
        if source_component:
            elements.append(
                f'<text x="{float(position.get("x_mm", 0.0)):.2f}" y="{float(position.get("y_mm", 0.0)) - 2.0:.2f}" '
                f'font-size="3" text-anchor="middle">{escape(str(source_component))}</text>'
            )
    content = "\n  ".join(elements)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.2f}mm" height="{height:.2f}mm" '
        f'viewBox="0 0 {width:.2f} {height:.2f}">\n  {content}\n</svg>\n'
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")
    return {"output_path": str(path), "warnings": []}


def _svg_path(output_path: str | Path, default_name: str) -> Path:
    path = Path(output_path)
    if path.suffix:
        return path
    path.mkdir(parents=True, exist_ok=True)
    return path / default_name

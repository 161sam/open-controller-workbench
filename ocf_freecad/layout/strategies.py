from __future__ import annotations

from typing import Any

from ocf_freecad.layout.grid import grid_positions


def generate_candidates(
    strategy: str,
    zone: dict[str, float],
    config: dict[str, Any],
) -> list[tuple[float, float]]:
    spacing_x = float(config.get("spacing_x_mm", config.get("spacing_mm", 20.0)))
    spacing_y = float(config.get("spacing_y_mm", config.get("spacing_mm", 20.0)))
    padding = float(config.get("padding_mm", 10.0))
    x0 = zone["x"] + padding
    y0 = zone["y"] + padding
    width = max(zone["width"] - (2.0 * padding), 0.0)
    height = max(zone["height"] - (2.0 * padding), 0.0)

    if strategy == "row":
        return [(x, y0 + (height / 2.0 if height > 0 else 0.0)) for x, _ in grid_positions(x0, y0, width, 0.0, spacing_x, 1.0)]
    if strategy == "column":
        return [(x0 + (width / 2.0 if width > 0 else 0.0), y) for _, y in grid_positions(x0, y0, 0.0, height, 1.0, spacing_y)]
    if strategy == "grid":
        return grid_positions(x0, y0, width, height, spacing_x, spacing_y)
    raise ValueError(f"Unsupported layout strategy: {strategy}")

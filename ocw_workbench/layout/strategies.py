from __future__ import annotations

from typing import Any

from ocw_workbench.layout.grid import grid_positions


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
        rows = _optional_positive_int(config.get("rows"))
        cols = _optional_positive_int(config.get("cols"))
        if rows is not None or cols is not None:
            return _bounded_grid_positions(
                zone=zone,
                padding=padding,
                spacing_x=spacing_x,
                spacing_y=spacing_y,
                rows=rows,
                cols=cols,
            )
        return grid_positions(x0, y0, width, height, spacing_x, spacing_y)
    raise ValueError(f"Unsupported layout strategy: {strategy}")


def _optional_positive_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    number = int(value)
    return number if number > 0 else None


def _bounded_grid_positions(
    zone: dict[str, float],
    padding: float,
    spacing_x: float,
    spacing_y: float,
    rows: int | None,
    cols: int | None,
) -> list[tuple[float, float]]:
    usable_x = zone["x"] + padding
    usable_y = zone["y"] + padding
    usable_width = max(zone["width"] - (2.0 * padding), 0.0)
    usable_height = max(zone["height"] - (2.0 * padding), 0.0)
    resolved_cols = cols or max(1, int(usable_width // max(spacing_x, 1.0)) + 1)
    resolved_rows = rows or max(1, int(usable_height // max(spacing_y, 1.0)) + 1)
    x_span = spacing_x * max(resolved_cols - 1, 0)
    y_span = spacing_y * max(resolved_rows - 1, 0)
    start_x = usable_x + max((usable_width - x_span) / 2.0, 0.0)
    start_y = usable_y + max((usable_height - y_span) / 2.0, 0.0)
    return [
        (round(start_x + (column * spacing_x), 6), round(start_y + (row * spacing_y), 6))
        for row in range(resolved_rows)
        for column in range(resolved_cols)
    ]

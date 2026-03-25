from __future__ import annotations


def grid_positions(
    origin_x: float,
    origin_y: float,
    width: float,
    height: float,
    spacing_x: float,
    spacing_y: float,
) -> list[tuple[float, float]]:
    positions: list[tuple[float, float]] = []
    y = origin_y
    while y <= origin_y + height + 1e-9:
        x = origin_x
        while x <= origin_x + width + 1e-9:
            positions.append((round(x, 6), round(y, 6)))
            x += spacing_x
        y += spacing_y
    return positions

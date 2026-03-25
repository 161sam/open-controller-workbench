from __future__ import annotations

from copy import deepcopy

OVERLAY_COLORS = {
    "surface": {"rgb": (0.2, 0.8, 0.85), "line_rgb": (0.1, 0.55, 0.6), "transparency": 88},
    "zone": {"rgb": (0.25, 0.85, 0.75), "line_rgb": (0.1, 0.55, 0.45), "transparency": 84},
    "component": {"rgb": (0.7, 0.74, 0.78), "line_rgb": (0.35, 0.39, 0.45), "transparency": 70},
    "component_selected": {"rgb": (0.18, 0.47, 0.95), "line_rgb": (0.08, 0.23, 0.68), "transparency": 45},
    "component_warning": {"rgb": (0.93, 0.72, 0.16), "line_rgb": (0.72, 0.5, 0.08), "transparency": 45},
    "component_error": {"rgb": (0.89, 0.26, 0.22), "line_rgb": (0.66, 0.12, 0.12), "transparency": 35},
    "keepout": {"rgb": (0.95, 0.42, 0.12), "line_rgb": (0.72, 0.24, 0.08), "transparency": 78},
    "cutout": {"rgb": (0.52, 0.63, 0.86), "line_rgb": (0.23, 0.31, 0.56), "transparency": 82},
    "mounting_hole": {"rgb": (0.96, 0.58, 0.16), "line_rgb": (0.76, 0.31, 0.08), "transparency": 55},
    "finding_label": {"rgb": (0.95, 0.95, 0.95), "line_rgb": (0.2, 0.2, 0.2), "transparency": 0},
}


def overlay_style(kind: str) -> dict[str, object]:
    palette = deepcopy(OVERLAY_COLORS.get(kind, OVERLAY_COLORS["component"]))
    palette["kind"] = kind
    return palette

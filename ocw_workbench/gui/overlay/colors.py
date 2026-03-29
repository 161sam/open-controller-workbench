from __future__ import annotations

from copy import deepcopy

OVERLAY_COLORS = {
    "surface": {"rgb": (0.2, 0.8, 0.85), "line_rgb": (0.1, 0.55, 0.6), "transparency": 88},
    "zone": {"rgb": (0.25, 0.85, 0.75), "line_rgb": (0.1, 0.55, 0.45), "transparency": 84},
    "component": {"rgb": (0.7, 0.74, 0.78), "line_rgb": (0.35, 0.39, 0.45), "transparency": 70},
    "component_hover": {"rgb": (0.66, 0.9, 1.0), "line_rgb": (0.14, 0.52, 0.82), "transparency": 48, "line_width": 5},
    "component_hover_warning": {"rgb": (0.99, 0.86, 0.38), "line_rgb": (0.8, 0.55, 0.06), "transparency": 38, "line_width": 5},
    "component_hover_error": {"rgb": (0.98, 0.54, 0.46), "line_rgb": (0.78, 0.12, 0.12), "transparency": 28, "line_width": 6},
    "component_selected": {"rgb": (0.12, 0.42, 0.98), "line_rgb": (0.05, 0.18, 0.72), "transparency": 18, "line_width": 6},
    "component_selected_secondary": {"rgb": (0.44, 0.74, 1.0), "line_rgb": (0.12, 0.42, 0.76), "transparency": 36, "line_width": 5},
    "component_warning": {"rgb": (0.93, 0.72, 0.16), "line_rgb": (0.72, 0.5, 0.08), "transparency": 45},
    "component_error": {"rgb": (0.89, 0.26, 0.22), "line_rgb": (0.66, 0.12, 0.12), "transparency": 35},
    "component_preview": {"rgb": (0.34, 0.82, 0.95), "line_rgb": (0.08, 0.46, 0.66), "transparency": 76, "draw_style": "Dashdot", "line_width": 4},
    "component_preview_warning": {"rgb": (0.96, 0.8, 0.26), "line_rgb": (0.78, 0.54, 0.08), "transparency": 68, "draw_style": "Dashdot", "line_width": 4},
    "component_preview_error": {"rgb": (0.96, 0.34, 0.3), "line_rgb": (0.76, 0.12, 0.12), "transparency": 60, "draw_style": "Dashdot", "line_width": 5},
    "keepout_preview": {"rgb": (0.95, 0.64, 0.18), "line_rgb": (0.76, 0.38, 0.1), "transparency": 88, "draw_style": "Dashdot"},
    "keepout_preview_warning": {"rgb": (0.98, 0.74, 0.22), "line_rgb": (0.76, 0.53, 0.08), "transparency": 80, "draw_style": "Dashdot"},
    "keepout_preview_error": {"rgb": (0.96, 0.46, 0.28), "line_rgb": (0.72, 0.18, 0.12), "transparency": 74, "draw_style": "Dashdot"},
    "cutout_preview": {"rgb": (0.7, 0.78, 0.96), "line_rgb": (0.3, 0.38, 0.62), "transparency": 88, "draw_style": "Dashdot"},
    "cutout_preview_warning": {"rgb": (0.97, 0.8, 0.45), "line_rgb": (0.72, 0.5, 0.08), "transparency": 80, "draw_style": "Dashdot"},
    "cutout_preview_error": {"rgb": (0.96, 0.55, 0.5), "line_rgb": (0.69, 0.11, 0.1), "transparency": 74, "draw_style": "Dashdot"},
    "preview_label": {"rgb": (0.98, 1.0, 1.0), "line_rgb": (0.1, 0.24, 0.38), "transparency": 0},
    "preview_label_warning": {"rgb": (1.0, 0.96, 0.78), "line_rgb": (0.72, 0.5, 0.08), "transparency": 0},
    "preview_label_error": {"rgb": (1.0, 0.9, 0.9), "line_rgb": (0.66, 0.12, 0.12), "transparency": 0},
    "snap_point_marker": {"rgb": (0.3, 0.92, 0.46), "line_rgb": (0.12, 0.62, 0.24), "transparency": 15, "line_width": 4},
    "snap_edge_marker": {"rgb": (0.28, 0.72, 0.98), "line_rgb": (0.1, 0.44, 0.76), "transparency": 18, "line_width": 4},
    "snap_guide": {"rgb": (0.72, 0.88, 1.0), "line_rgb": (0.28, 0.56, 0.82), "transparency": 0, "line_width": 2, "draw_style": "Dashdot"},
    "axis_lock": {"rgb": (0.98, 0.84, 0.26), "line_rgb": (0.76, 0.54, 0.08), "transparency": 0, "line_width": 3, "draw_style": "Dashdot"},
    "keepout": {"rgb": (0.95, 0.42, 0.12), "line_rgb": (0.72, 0.24, 0.08), "transparency": 78},
    "cutout": {"rgb": (0.52, 0.63, 0.86), "line_rgb": (0.23, 0.31, 0.56), "transparency": 82},
    "mounting_hole": {"rgb": (0.96, 0.58, 0.16), "line_rgb": (0.76, 0.31, 0.08), "transparency": 55},
    "finding_label": {"rgb": (0.95, 0.95, 0.95), "line_rgb": (0.2, 0.2, 0.2), "transparency": 0},
    "measurement_line": {"rgb": (0.14, 0.72, 0.92), "line_rgb": (0.08, 0.46, 0.68), "transparency": 0, "line_width": 3},
    "measurement_line_warning": {"rgb": (0.93, 0.72, 0.16), "line_rgb": (0.72, 0.5, 0.08), "transparency": 0, "line_width": 4},
    "measurement_line_error": {"rgb": (0.89, 0.26, 0.22), "line_rgb": (0.66, 0.12, 0.12), "transparency": 0, "line_width": 5},
    "conflict_line_warning": {"rgb": (0.94, 0.79, 0.18), "line_rgb": (0.75, 0.56, 0.08), "transparency": 0, "line_width": 4},
    "conflict_line_error": {"rgb": (0.92, 0.25, 0.22), "line_rgb": (0.69, 0.11, 0.1), "transparency": 0, "line_width": 5},
    "constraint_label_warning": {"rgb": (1.0, 0.96, 0.78), "line_rgb": (0.72, 0.5, 0.08), "transparency": 0},
    "constraint_label_error": {"rgb": (1.0, 0.9, 0.9), "line_rgb": (0.66, 0.12, 0.12), "transparency": 0},
    "clearance_boundary": {"rgb": (0.22, 0.68, 0.92), "line_rgb": (0.1, 0.45, 0.7), "transparency": 88, "draw_style": "Dashdot"},
    "clearance_boundary_warning": {"rgb": (0.95, 0.78, 0.22), "line_rgb": (0.76, 0.53, 0.08), "transparency": 82, "draw_style": "Dashdot"},
    "clearance_boundary_error": {"rgb": (0.95, 0.38, 0.34), "line_rgb": (0.72, 0.14, 0.14), "transparency": 80, "draw_style": "Dashdot"},
    "legend_text": {"rgb": (0.96, 0.96, 0.96), "line_rgb": (0.25, 0.25, 0.25), "transparency": 0},
}


def overlay_style(kind: str) -> dict[str, object]:
    palette = deepcopy(OVERLAY_COLORS.get(kind, OVERLAY_COLORS["component"]))
    palette["kind"] = kind
    return palette

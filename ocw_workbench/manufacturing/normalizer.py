from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_MANUFACTURING_PROFILE = {
    "schema_version": "ocf-manufacturing/v1",
    "materials": {
        "top_plate": {"material": "acrylic", "thickness_mm": 3.0},
        "bottom_plate": {"material": "birch_plywood", "thickness_mm": 3.0},
        "side_panels": {"material": "birch_plywood", "thickness_mm": 9.0},
        "pcb": {"material": "fr4", "thickness_mm": 1.6},
    },
    "fasteners": {
        "panel_mount_screw": {
            "manufacturer": "Generic",
            "part_number": "M3x8",
            "description": "M3 x 8 mm panel screw",
        },
        "standoff": {
            "manufacturer": "Generic",
            "part_number": "M3-10",
            "description": "M3 10 mm standoff",
        },
    },
    "tolerances": {
        "circular_hole_mm": 0.1,
        "rect_cutout_mm": 0.15,
    },
}


def normalize_profile(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = deepcopy(DEFAULT_MANUFACTURING_PROFILE)
    if overrides is None:
        return profile
    return _deep_merge(profile, overrides)


def recommend_process(material: str, part_type: str, has_complex_cutouts: bool = False) -> str:
    material_lower = material.lower()
    if "acrylic" in material_lower:
        return "laser_cut"
    if "plywood" in material_lower or "wood" in material_lower:
        return "cnc_router" if has_complex_cutouts else "laser_cut_panel"
    if "fr4" in material_lower or part_type == "pcb":
        return "pcb_fabrication"
    return "general_fabrication"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result

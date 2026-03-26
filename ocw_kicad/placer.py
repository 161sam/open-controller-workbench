from __future__ import annotations

from typing import Any

from ocw_kicad.footprint_resolver import resolve_footprint
from ocw_kicad.utils import (
    add_board_item,
    clear_generated_items,
    deg_to_kicad_angle,
    get_required_number,
    get_required_str,
    make_point,
    mark_generated,
    mm_to_iu,
    require_positive,
)


def place_footprint(board: Any, footprint_data: dict[str, Any], pcbnew_module: Any) -> Any | None:
    footprint_name = get_required_str(footprint_data, "footprint")
    x_mm = get_required_number(footprint_data, "x_mm")
    y_mm = get_required_number(footprint_data, "y_mm")
    rotation_deg = float(footprint_data.get("rotation_deg", 0.0))
    side = str(footprint_data.get("side", "top"))

    if side not in {"top", "bottom"}:
        raise ValueError(f"Unknown side: {side}")

    footprint = resolve_footprint(pcbnew_module, footprint_name)
    if footprint is None:
        return None

    position = make_point(mm_to_iu(x_mm, pcbnew_module), mm_to_iu(y_mm, pcbnew_module), pcbnew_module)
    _set_position(footprint, position)
    _set_rotation(footprint, rotation_deg, pcbnew_module)
    _set_side(footprint, position, side, pcbnew_module)
    _set_reference(footprint, footprint_data)
    add_board_item(board, footprint)
    print(f"Placed footprint {footprint_name} at ({x_mm}, {y_mm})")
    return footprint


def place_mounting_holes(board: Any, mounting_holes: list[dict[str, Any]], pcbnew_module: Any) -> int:
    clear_generated_items(board, "mounting_hole")

    placed = 0
    for index, hole_data in enumerate(mounting_holes, start=1):
        if not isinstance(hole_data, dict):
            raise ValueError(f"Invalid mounting hole entry: {hole_data!r}")

        hole = _create_mounting_hole(hole_data, index, pcbnew_module)
        if hole is None:
            continue

        add_board_item(board, mark_generated(hole, "mounting_hole"))
        placed += 1

    return placed


def _set_position(footprint: Any, position: Any) -> None:
    if hasattr(footprint, "SetPosition"):
        footprint.SetPosition(position)
        return
    raise RuntimeError("Footprint object does not support SetPosition")


def _set_rotation(footprint: Any, rotation_deg: float, pcbnew_module: Any) -> None:
    angle = deg_to_kicad_angle(rotation_deg, pcbnew_module)
    if hasattr(footprint, "SetOrientation"):
        footprint.SetOrientation(angle)
        return
    if hasattr(footprint, "SetOrientationDegrees"):
        footprint.SetOrientationDegrees(rotation_deg)
        return
    raise RuntimeError("Footprint object does not support rotation updates")


def _set_side(footprint: Any, position: Any, side: str, pcbnew_module: Any) -> None:
    top_layer = getattr(pcbnew_module, "F_Cu", "F.Cu")
    bottom_layer = getattr(pcbnew_module, "B_Cu", "B.Cu")
    current_layer = footprint.GetLayer() if hasattr(footprint, "GetLayer") else top_layer
    target_layer = top_layer if side == "top" else bottom_layer

    if side == "bottom" and current_layer != bottom_layer and hasattr(footprint, "Flip"):
        footprint.Flip(position, False)

    if hasattr(footprint, "SetLayer"):
        footprint.SetLayer(target_layer)


def _set_reference(footprint: Any, footprint_data: dict[str, Any]) -> None:
    reference = footprint_data.get("reference")
    if isinstance(reference, str) and reference:
        if hasattr(footprint, "SetReference"):
            footprint.SetReference(reference)


def _create_mounting_hole(
    hole_data: dict[str, Any],
    index: int,
    pcbnew_module: Any,
) -> Any | None:
    hole_id = hole_data.get("id") or f"mh{index}"
    x_mm = get_required_number(hole_data, "x_mm")
    y_mm = get_required_number(hole_data, "y_mm")
    diameter_mm = require_positive(get_required_number(hole_data, "diameter_mm"), "diameter_mm")

    footprint_name = f"MountingHole:MountingHole_{_format_diameter(diameter_mm)}mm_NPTH"
    hole = resolve_footprint(pcbnew_module, footprint_name)
    if hole is None:
        print(f"Skipping mounting hole {hole_id}: footprint not found")
        return None

    position = make_point(mm_to_iu(x_mm, pcbnew_module), mm_to_iu(y_mm, pcbnew_module), pcbnew_module)
    _set_position(hole, position)
    _set_side(hole, position, "top", pcbnew_module)
    _set_reference(hole, {"reference": str(hole_id).upper()})
    print(f"Placed mounting hole {str(hole_id).upper()}")
    return hole


def _format_diameter(diameter_mm: float) -> str:
    if diameter_mm.is_integer():
        return str(int(diameter_mm))
    return f"{diameter_mm:.2f}".rstrip("0").rstrip(".")

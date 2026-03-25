from __future__ import annotations

from typing import Any

from ocf_kicad.footprint_resolver import resolve_footprint
from ocf_kicad.utils import deg_to_kicad_angle, get_required_number, get_required_str, make_point, mm_to_iu


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
    board.Add(footprint)
    print(f"Placed footprint {footprint_name} at ({x_mm}, {y_mm})")
    return footprint


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

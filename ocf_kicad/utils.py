from __future__ import annotations

from typing import Any


def mm_to_iu(value_mm: float, pcbnew_module: Any) -> int:
    if not isinstance(value_mm, (int, float)):
        raise ValueError(f"Invalid coordinate value: {value_mm!r}")
    if hasattr(pcbnew_module, "FromMM"):
        return int(pcbnew_module.FromMM(float(value_mm)))
    return int(round(float(value_mm) * 1_000_000))


def deg_to_kicad_angle(value_deg: float, pcbnew_module: Any) -> Any:
    if not isinstance(value_deg, (int, float)):
        raise ValueError(f"Invalid rotation value: {value_deg!r}")
    if hasattr(pcbnew_module, "EDA_ANGLE") and hasattr(pcbnew_module, "DEGREES_T"):
        return pcbnew_module.EDA_ANGLE(float(value_deg), pcbnew_module.DEGREES_T)
    return float(value_deg)


def make_point(x_iu: int, y_iu: int, pcbnew_module: Any) -> Any:
    if hasattr(pcbnew_module, "VECTOR2I"):
        return pcbnew_module.VECTOR2I(x_iu, y_iu)
    if hasattr(pcbnew_module, "wxPoint"):
        return pcbnew_module.wxPoint(x_iu, y_iu)
    return (x_iu, y_iu)


def get_required_str(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing or invalid field '{field}'")
    return value


def get_required_number(payload: dict[str, Any], field: str) -> float:
    value = payload.get(field)
    if not isinstance(value, (int, float)):
        raise ValueError(f"Missing or invalid numeric field '{field}'")
    return float(value)

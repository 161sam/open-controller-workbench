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


def get_optional_number(
    payload: dict[str, Any],
    field: str,
    default: float | None = None,
) -> float | None:
    value = payload.get(field, default)
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        raise ValueError(f"Missing or invalid numeric field '{field}'")
    return float(value)


def require_positive(value: float, field: str) -> float:
    if value <= 0:
        raise ValueError(f"Field '{field}' must be positive")
    return value


def require_non_negative(value: float, field: str) -> float:
    if value < 0:
        raise ValueError(f"Field '{field}' must be non-negative")
    return value


def mark_generated(item: Any, kind: str) -> Any:
    setattr(item, "ocw_generated_kind", kind)
    return item


def is_generated(item: Any, kind: str) -> bool:
    return getattr(item, "ocw_generated_kind", getattr(item, "ocf_generated_kind", None)) == kind


def add_board_item(board: Any, item: Any) -> None:
    if hasattr(board, "Add"):
        board.Add(item)
        return
    raise RuntimeError("Board object does not support Add")


def remove_board_item(board: Any, item: Any) -> None:
    if hasattr(board, "Remove"):
        board.Remove(item)
        return
    items = getattr(board, "items", None)
    if isinstance(items, list) and item in items:
        items.remove(item)
        return
    raise RuntimeError("Board object does not support Remove")


def list_board_items(board: Any) -> list[Any]:
    if hasattr(board, "GetDrawings"):
        drawings = list(board.GetDrawings())
    else:
        drawings = []
    if hasattr(board, "GetFootprints"):
        footprints = list(board.GetFootprints())
    else:
        footprints = []
    if drawings or footprints:
        return drawings + footprints
    items = getattr(board, "items", None)
    if isinstance(items, list):
        return list(items)
    return []


def clear_generated_items(board: Any, kind: str) -> int:
    removed = 0
    for item in list_board_items(board):
        if is_generated(item, kind):
            remove_board_item(board, item)
            removed += 1
    return removed

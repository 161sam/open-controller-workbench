from __future__ import annotations

from typing import Any

from ocw_workbench.freecad_api.metadata import clear_document_data, get_document_data, set_document_data

PREVIEW_METADATA_KEY = "OCWDragPreview"
PREVIEW_SCHEMA_VERSION = 1


def serialize_preview_state(
    *,
    x: float,
    y: float,
    rotation: float = 0.0,
    mode: str = "place",
    template_id: str | None = None,
    component_id: str | None = None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "version": PREVIEW_SCHEMA_VERSION,
        "x": float(x),
        "y": float(y),
        "rotation": float(rotation),
        "mode": str(mode or "place"),
        "snap_enabled": None,
        "grid_mm": None,
        "validation": None,
    }
    if template_id is not None:
        payload["template_id"] = str(template_id)
    if component_id is not None:
        payload["component_id"] = str(component_id)
    if isinstance(validation, dict):
        payload["validation"] = dict(validation)
    return payload


def load_preview_state(doc: Any) -> dict[str, Any] | None:
    payload = get_document_data(doc, PREVIEW_METADATA_KEY)
    if not isinstance(payload, dict):
        return None
    template_id = payload.get("template_id")
    component_id = payload.get("component_id")
    if not isinstance(template_id, str) and not isinstance(component_id, str):
        return None
    try:
        preview = serialize_preview_state(
            x=float(payload.get("x", 0.0)),
            y=float(payload.get("y", 0.0)),
            rotation=float(payload.get("rotation", 0.0)),
            mode=str(payload.get("mode") or "place"),
            template_id=template_id if isinstance(template_id, str) and template_id else None,
            component_id=component_id if isinstance(component_id, str) and component_id else None,
            validation=payload.get("validation") if isinstance(payload.get("validation"), dict) else None,
        )
        preview["version"] = int(payload.get("version", PREVIEW_SCHEMA_VERSION) or PREVIEW_SCHEMA_VERSION)
        preview["snap_enabled"] = (
            bool(payload["snap_enabled"]) if payload.get("snap_enabled") is not None else None
        )
        preview["grid_mm"] = float(payload["grid_mm"]) if payload.get("grid_mm") is not None else None
        return preview
    except Exception:
        return None


def store_preview_state(
    doc: Any,
    template_id: str | None = None,
    *,
    x: float,
    y: float,
    rotation: float = 0.0,
    mode: str = "place",
    component_id: str | None = None,
    snap_enabled: bool | None = None,
    grid_mm: float | None = None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = serialize_preview_state(
        x=x,
        y=y,
        rotation=rotation,
        mode=mode,
        template_id=template_id,
        component_id=component_id,
        validation=validation,
    )
    payload["snap_enabled"] = None if snap_enabled is None else bool(snap_enabled)
    payload["grid_mm"] = None if grid_mm is None else float(grid_mm)
    set_document_data(doc, PREVIEW_METADATA_KEY, payload)
    return payload


def clear_preview_state(doc: Any) -> None:
    clear_document_data(doc, PREVIEW_METADATA_KEY)

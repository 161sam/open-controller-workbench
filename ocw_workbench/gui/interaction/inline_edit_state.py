from __future__ import annotations

from typing import Any

from ocw_workbench.freecad_api.metadata import clear_document_data, get_document_data, set_document_data

INLINE_EDIT_METADATA_KEY = "OCWInlineEditState"
INLINE_EDIT_SCHEMA_VERSION = 1


def serialize_inline_edit_state(
    *,
    component_id: str | None = None,
    hovered_handle_id: str | None = None,
    active_handle_id: str | None = None,
    active_handle_type: str | None = None,
) -> dict[str, Any]:
    return {
        "version": INLINE_EDIT_SCHEMA_VERSION,
        "component_id": component_id,
        "hovered_handle_id": hovered_handle_id,
        "active_handle_id": active_handle_id,
        "active_handle_type": active_handle_type,
    }


def load_inline_edit_state(doc: Any) -> dict[str, Any] | None:
    payload = get_document_data(doc, INLINE_EDIT_METADATA_KEY)
    if not isinstance(payload, dict):
        return None
    return serialize_inline_edit_state(
        component_id=str(payload["component_id"]) if isinstance(payload.get("component_id"), str) else None,
        hovered_handle_id=str(payload["hovered_handle_id"]) if isinstance(payload.get("hovered_handle_id"), str) else None,
        active_handle_id=str(payload["active_handle_id"]) if isinstance(payload.get("active_handle_id"), str) else None,
        active_handle_type=str(payload["active_handle_type"]) if isinstance(payload.get("active_handle_type"), str) else None,
    )


def store_inline_edit_state(
    doc: Any,
    *,
    component_id: str | None = None,
    hovered_handle_id: str | None = None,
    active_handle_id: str | None = None,
    active_handle_type: str | None = None,
) -> dict[str, Any]:
    payload = serialize_inline_edit_state(
        component_id=component_id,
        hovered_handle_id=hovered_handle_id,
        active_handle_id=active_handle_id,
        active_handle_type=active_handle_type,
    )
    set_document_data(doc, INLINE_EDIT_METADATA_KEY, payload)
    return payload


def clear_inline_edit_state(doc: Any) -> None:
    clear_document_data(doc, INLINE_EDIT_METADATA_KEY)

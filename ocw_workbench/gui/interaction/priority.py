from __future__ import annotations

from typing import Any

from ocw_workbench.gui.interaction.tool_manager import get_tool_manager


def active_tool_id() -> str | None:
    return get_tool_manager().current_tool


def has_external_active_tool() -> bool:
    tool_id = active_tool_id()
    return tool_id is not None and not str(tool_id).startswith("inline_edit:")


def handles_visible(*, selection_count: int, ui_settings: dict[str, Any]) -> bool:
    if selection_count != 1:
        return False
    if has_external_active_tool():
        return False
    active_interaction = str(ui_settings.get("active_interaction") or "")
    return active_interaction in {"", "inline_edit"}


def dominant_interaction_layer(
    *,
    selection_count: int,
    ui_settings: dict[str, Any],
    inline_state: dict[str, Any] | None,
) -> str:
    if has_external_active_tool():
        return "tool_active"
    inline_state = inline_state or {}
    if inline_state.get("active_handle_id"):
        return "inline_edit_active"
    if inline_state.get("hovered_handle_id") and handles_visible(selection_count=selection_count, ui_settings=ui_settings):
        return "handle_hover"
    if ui_settings.get("move_component_id"):
        return "manipulation"
    if selection_count == 1:
        return "selection"
    if selection_count > 1:
        return "multi_selection"
    if ui_settings.get("hovered_component_id"):
        return "hover"
    return "idle"


def inline_cursor_role(
    *,
    selection_count: int,
    ui_settings: dict[str, Any],
    inline_state: dict[str, Any] | None,
) -> str:
    if has_external_active_tool():
        return "default"
    inline_state = inline_state or {}
    if inline_state.get("active_handle_id"):
        return "edit_active"
    if handles_visible(selection_count=selection_count, ui_settings=ui_settings):
        return "edit_ready" if inline_state.get("hovered_handle_id") else "pick"
    return "pick"

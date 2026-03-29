from __future__ import annotations

from ocw_workbench.gui.interaction.tool_manager import reset_tool_manager


def test_tool_manager_only_keeps_one_active_tool() -> None:
    tools = reset_tool_manager()
    calls: list[str] = []

    assert tools.activate_tool("place:pad", activator=lambda: True, deactivate=lambda: calls.append("pad")) is True
    assert tools.activate_tool("drag", activator=lambda: True, deactivate=lambda: calls.append("drag")) is True

    assert calls == ["pad"]
    assert tools.current_tool == "drag"


def test_tool_manager_tracks_context_and_escape_cancels() -> None:
    tools = reset_tool_manager()
    calls: list[str] = []

    assert tools.activate_tool(
        "place:wheel",
        activator=lambda: True,
        deactivate=lambda: calls.append("cancel"),
        context={"doc": "demo", "template_id": "wheel"},
    ) is True

    assert tools.current_context == {"doc": "demo", "template_id": "wheel"}
    assert tools.handle_key("ESCAPE") is True
    assert calls == ["cancel"]
    assert tools.current_tool is None
    assert tools.current_context is None


def test_tool_manager_finish_prefers_finish_handler() -> None:
    tools = reset_tool_manager()
    calls: list[str] = []

    assert tools.activate_tool(
        "drag",
        activator=lambda: True,
        deactivate=lambda: calls.append("cancel"),
        finish=lambda: calls.append("finish"),
    ) is True

    tools.finish_active_tool()

    assert calls == ["finish"]
    assert tools.has_active_tool() is False

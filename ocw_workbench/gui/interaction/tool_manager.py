from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ActiveTool:
    tool_id: str
    deactivate: Callable[[], None] | None = None
    finish: Callable[[], None] | None = None
    context: Any | None = None


class ToolManager:
    def __init__(self) -> None:
        self._active: ActiveTool | None = None

    @property
    def current_tool(self) -> str | None:
        return None if self._active is None else self._active.tool_id

    @property
    def current_context(self) -> Any | None:
        return None if self._active is None else self._active.context

    def has_active_tool(self) -> bool:
        return self._active is not None

    def activate_tool(
        self,
        tool_id: str,
        *,
        activator: Callable[[], bool],
        deactivate: Callable[[], None] | None = None,
        finish: Callable[[], None] | None = None,
        context: Any | None = None,
    ) -> bool:
        self.cancel_active_tool()
        started = bool(activator())
        if not started:
            self._active = None
            return False
        self._active = ActiveTool(
            tool_id=tool_id,
            deactivate=deactivate,
            finish=finish,
            context=context,
        )
        return True

    def deactivate_tool(self) -> None:
        self.cancel_active_tool()

    def cancel_active_tool(self) -> None:
        if self._active is None:
            return
        active = self._active
        self._active = None
        if active.deactivate is not None:
            active.deactivate()

    def finish_active_tool(self) -> None:
        if self._active is None:
            return
        active = self._active
        self._active = None
        if active.finish is not None:
            active.finish()
            return
        if active.deactivate is not None:
            active.deactivate()

    def handle_key(self, key: str) -> bool:
        normalized = str(key or "").strip().upper()
        if normalized in {"ESC", "ESCAPE"} and self._active is not None:
            self.cancel_active_tool()
            return True
        return False

    def clear_active_tool(self, tool_id: str | None = None) -> None:
        if self._active is None:
            return
        if tool_id not in {None, self._active.tool_id}:
            return
        self._active = None


_TOOL_MANAGER = ToolManager()


def get_tool_manager() -> ToolManager:
    return _TOOL_MANAGER


def reset_tool_manager() -> ToolManager:
    global _TOOL_MANAGER
    _TOOL_MANAGER = ToolManager()
    return _TOOL_MANAGER

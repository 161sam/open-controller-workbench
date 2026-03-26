from __future__ import annotations

from typing import Any

from ocw_workbench.layout.engine import LayoutEngine


class LayoutService:
    def __init__(self, engine: LayoutEngine | None = None) -> None:
        self.engine = engine or LayoutEngine()

    def place(
        self,
        controller: dict[str, Any] | Any,
        components: list[dict[str, Any] | Any],
        strategy: str = "grid",
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.engine.place(controller, components, strategy=strategy, config=config)

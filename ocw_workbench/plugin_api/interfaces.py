from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


ComponentDefinition = dict[str, Any]
TemplateDefinition = dict[str, Any]
VariantDefinition = dict[str, Any]


@runtime_checkable
class ExporterInterface(Protocol):
    def __call__(self, data: dict[str, Any], path: str) -> dict[str, Any] | None: ...


@runtime_checkable
class LayoutStrategyInterface(Protocol):
    def __call__(self, zone: dict[str, Any], config: dict[str, Any]) -> list[tuple[float, float]]: ...


@runtime_checkable
class ConstraintRuleInterface(Protocol):
    def __call__(
        self,
        controller: dict[str, Any],
        components: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> list[dict[str, Any]]: ...

from __future__ import annotations

from typing import Any

from ocw_workbench.constraints.validator import ConstraintValidator


class ConstraintService:
    def __init__(self, validator: ConstraintValidator | None = None) -> None:
        self.validator = validator or ConstraintValidator()

    def validate(
        self,
        controller: dict[str, Any] | Any,
        components: list[dict[str, Any] | Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.validator.validate(controller, components, config=config).to_dict()

from __future__ import annotations

from ocw_workbench.constraints.models import ComponentArea, ConstraintFinding
from ocw_workbench.constraints.rules import minimum_gap


def ergonomic_proximity_warning(
    first: ComponentArea,
    second: ComponentArea,
    min_distance_mm: float,
) -> ConstraintFinding | None:
    gap = minimum_gap(first, second)
    if gap < min_distance_mm:
        return ConstraintFinding(
            severity="warning",
            rule_id="ergonomic_proximity",
            message=(
                f"Components '{first.component_id}' and '{second.component_id}' are ergonomically too close "
                f"({gap:.2f} mm < {min_distance_mm:.2f} mm)"
            ),
            source_component=first.component_id,
            affected_component=second.component_id,
            details={"gap_mm": round(gap, 3), "recommended_mm": min_distance_mm},
        )
    return None


def ergonomic_type_warning(
    first: ComponentArea,
    second: ComponentArea,
    rule_id: str,
    message: str,
    min_distance_mm: float,
) -> ConstraintFinding | None:
    gap = minimum_gap(first, second)
    if gap < min_distance_mm:
        return ConstraintFinding(
            severity="warning",
            rule_id=rule_id,
            message=message,
            source_component=first.component_id,
            affected_component=second.component_id,
            details={"gap_mm": round(gap, 3), "recommended_mm": min_distance_mm},
        )
    return None

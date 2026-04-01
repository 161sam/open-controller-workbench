from __future__ import annotations

from typing import Any


def component_label(
    component: dict[str, Any],
    severity: str | None = None,
    selected_role: str | None = None,
    hovered: bool = False,
    context_relevant: bool = False,
    manipulated: bool = False,
) -> str:
    base = f"{component['id']} [{component['type']}]"
    if manipulated:
        base = f"{base} #"
    elif selected_role == "primary":
        base = f"{base} *"
    elif selected_role == "secondary":
        base = f"{base} +"
    elif hovered:
        base = f"{base} >"
    elif context_relevant:
        base = f"{base} ~"
    if severity == "error":
        return f"{base} !"
    if severity == "warning":
        return f"{base} ?"
    return base


def zone_label(zone: dict[str, Any]) -> str:
    zone_id = zone.get("id", "zone")
    strategy = zone.get("strategy")
    return f"{zone_id} ({strategy})" if strategy else str(zone_id)


def issue_label(component_id: str, error_count: int, warning_count: int) -> str:
    parts: list[str] = []
    if error_count:
        parts.append(f"E{error_count}")
    if warning_count:
        parts.append(f"W{warning_count}")
    return f"{component_id}: {' / '.join(parts)}"


def measurement_label(current_mm: float, required_mm: float | None = None) -> str:
    current_text = f"{current_mm:.1f}"
    if required_mm is None:
        return f"{current_text} mm"
    return f"{current_text} / {required_mm:.1f} mm"


def constraint_detail_label(title: str, current_mm: float | None = None, required_mm: float | None = None) -> str:
    if current_mm is None:
        return title
    suffix = measurement_label(current_mm, required_mm)
    return f"{title}: {suffix}"

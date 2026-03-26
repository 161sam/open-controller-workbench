from __future__ import annotations

from typing import Any

from ocw_workbench.gui.overlay.colors import overlay_style
from ocw_workbench.gui.overlay.conflict_lines import conflict_items
from ocw_workbench.gui.overlay.distance_markers import measurement_items
from ocw_workbench.gui.overlay.labels import constraint_detail_label
from ocw_workbench.gui.overlay.measurements import (
    bbox_from_shape,
    expanded_shape,
    midpoint,
    nearest_edge_measurement,
    nearest_points_between_boxes,
)
from ocw_workbench.gui.overlay.shapes import circle_item, rect_item, text_item


def build_constraint_overlay(
    surface: dict[str, Any],
    resolved_components: list[dict[str, Any]],
    keepouts: list[dict[str, Any]],
    mounting_holes: list[dict[str, Any]],
    validation: dict[str, Any],
    settings: dict[str, Any],
    selected_component_id: str | None,
    move_component_id: str | None,
) -> dict[str, Any]:
    component_lookup = {component["id"]: component for component in resolved_components}
    component_boxes = {
        component["id"]: bbox_from_shape(
            float(component["x"]),
            float(component["y"]),
            component["resolved_mechanical"].keepout_top.to_dict(),
        )
        for component in resolved_components
    }
    keepout_lookup = {
        feature["component_id"]: bbox_from_shape(float(feature["x"]), float(feature["y"]), feature)
        for feature in keepouts
        if feature["feature"] == "keepout_top"
    }
    hole_lookup = {str(hole.get("id", "mounting_hole")): hole for hole in mounting_holes if isinstance(hole, dict)}
    focus_ids = [component_id for component_id in (move_component_id, selected_component_id) if component_id]
    items: list[dict[str, Any]] = []
    findings = _filtered_findings(validation, settings)
    ordered_findings = _prioritize_findings(findings, focus_ids)

    if settings.get("measurements_enabled", True):
        items.extend(_focused_measurements(surface, component_lookup, component_boxes, focus_ids, settings))

    for finding in ordered_findings:
        items.extend(
            _finding_items(
                finding=finding,
                surface=surface,
                component_lookup=component_lookup,
                component_boxes=component_boxes,
                keepout_lookup=keepout_lookup,
                settings=settings,
                hole_lookup=hole_lookup,
            )
        )

    items.extend(
        _legend(
            settings=settings,
            validation=validation,
        )
    )
    return {
        "items": items,
        "summary": {
            "constraint_item_count": len(items),
            "visible_finding_count": len(ordered_findings),
            "focus_component_id": focus_ids[0] if focus_ids else None,
        },
    }


def _focused_measurements(
    surface: dict[str, Any],
    component_lookup: dict[str, dict[str, Any]],
    component_boxes: dict[str, dict[str, float]],
    focus_ids: list[str],
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    if not focus_ids:
        return []
    component_id = focus_ids[0]
    component = component_lookup.get(component_id)
    box = component_boxes.get(component_id)
    if component is None or box is None:
        return []
    component_type = component["type"]
    required_edge = {
        "encoder": 8.0,
        "fader": 10.0,
        "display": 6.0,
    }.get(component_type, 4.0)
    edge = nearest_edge_measurement(surface, box)
    items = measurement_items(
        item_id=f"measurement:edge:{component_id}",
        start=(float(edge["start_x"]), float(edge["start_y"])),
        end=(float(edge["end_x"]), float(edge["end_y"])),
        current_mm=float(edge["distance"]),
        required_mm=required_edge,
        style=_measurement_style(None),
        label_style=overlay_style("finding_label"),
        source_ids=[component_id],
        severity=None,
        title="Edge",
        include_label=settings.get("constraint_labels_enabled", True),
    )
    clearance = expanded_shape(component["resolved_mechanical"].keepout_top.to_dict(), required_edge)
    items.append(
        _clearance_boundary(
            item_id=f"clearance:edge:{component_id}",
            component=component,
            shape=clearance,
            severity=None,
            source_ids=[component_id],
        )
    )

    nearest_neighbor_id, nearest_gap, first_point, second_point = _nearest_neighbor(component_id, component_boxes)
    if nearest_neighbor_id is not None:
        items.extend(
            measurement_items(
                item_id=f"measurement:neighbor:{component_id}:{nearest_neighbor_id}",
                start=first_point,
                end=second_point,
                current_mm=nearest_gap,
                required_mm=6.0,
                style=_measurement_style(None),
                label_style=overlay_style("finding_label"),
                source_ids=[component_id, nearest_neighbor_id],
                severity=None,
                title="Spacing",
                include_label=settings.get("constraint_labels_enabled", True),
            )
        )
    return items


def _finding_items(
    finding: dict[str, Any],
    surface: dict[str, Any],
    component_lookup: dict[str, dict[str, Any]],
    component_boxes: dict[str, dict[str, float]],
    keepout_lookup: dict[str, dict[str, float]],
    settings: dict[str, Any],
    hole_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    source_id = finding.get("source_component")
    affected_id = finding.get("affected_component")
    severity = str(finding["severity"])
    details = finding.get("details") or {}
    items: list[dict[str, Any]] = []
    source_ids = [item for item in [source_id, affected_id] if isinstance(item, str)]
    show_labels = settings.get("constraint_labels_enabled", True)
    show_lines = settings.get("conflict_lines_enabled", True)
    show_measurements = settings.get("measurements_enabled", True)
    source_component = component_lookup.get(source_id) if isinstance(source_id, str) else None

    if finding["rule_id"] in {"component_spacing", "ergonomic_proximity", "ergonomic_fader_button_proximity", "ergonomic_display_clearance"}:
        if source_id in component_boxes and affected_id in component_boxes:
            first_point, second_point, gap = nearest_points_between_boxes(component_boxes[source_id], component_boxes[affected_id])
            required = _required_distance(details)
            if show_lines:
                items.extend(
                    conflict_items(
                        item_id=f"conflict:{finding['rule_id']}:{source_id}:{affected_id}",
                        start=first_point,
                        end=second_point,
                        label=_constraint_title(finding),
                        style=_conflict_style(severity),
                        label_style=_label_style(severity),
                        source_ids=source_ids,
                        severity=severity,
                        include_label=show_labels,
                    )
                )
            if show_measurements:
                items.extend(
                    measurement_items(
                        item_id=f"distance:{finding['rule_id']}:{source_id}:{affected_id}",
                        start=first_point,
                        end=second_point,
                        current_mm=gap,
                        required_mm=required,
                        style=_measurement_style(severity),
                        label_style=_label_style(severity),
                        source_ids=source_ids,
                        severity=severity,
                        title="Spacing",
                        include_label=show_labels,
                    )
                )
            if source_component is not None and required is not None:
                items.append(
                    _clearance_boundary(
                        item_id=f"clearance:{finding['rule_id']}:{source_id}",
                        component=source_component,
                        shape=expanded_shape(source_component["resolved_mechanical"].keepout_top.to_dict(), required),
                        severity=severity,
                        source_ids=source_ids,
                    )
                )
        return items

    if finding["rule_id"] == "keepout_spacing":
        if source_id in keepout_lookup and affected_id in keepout_lookup:
            first_point, second_point, gap = nearest_points_between_boxes(keepout_lookup[source_id], keepout_lookup[affected_id])
            required = _required_distance(details)
            if show_lines:
                items.extend(
                    conflict_items(
                        item_id=f"conflict:keepout:{source_id}:{affected_id}",
                        start=first_point,
                        end=second_point,
                        label="Keepout overlap",
                        style=_conflict_style(severity),
                        label_style=_label_style(severity),
                        source_ids=source_ids,
                        severity=severity,
                        include_label=show_labels,
                    )
                )
            if show_measurements:
                items.extend(
                    measurement_items(
                        item_id=f"distance:keepout:{source_id}:{affected_id}",
                        start=first_point,
                        end=second_point,
                        current_mm=gap,
                        required_mm=required,
                        style=_measurement_style(severity),
                        label_style=_label_style(severity),
                        source_ids=source_ids,
                        severity=severity,
                        title="Keepout",
                        include_label=show_labels,
                    )
                )
        return items

    if finding["rule_id"] == "mounting_hole_clearance" and source_component is not None and isinstance(affected_id, str):
        box = component_boxes.get(source_id)
        if box is not None:
            start = (box["center_x"], box["center_y"])
            hole = hole_lookup.get(affected_id)
            end = start if hole is None else (float(hole["x"]), float(hole["y"]))
            required = _required_distance(details)
            if show_lines:
                items.extend(
                    conflict_items(
                        item_id=f"conflict:mounting:{source_id}:{affected_id}",
                        start=start,
                        end=end,
                        label="Mounting conflict",
                        style=_conflict_style(severity),
                        label_style=_label_style(severity),
                        source_ids=source_ids,
                        severity=severity,
                        include_label=show_labels,
                    )
                )
            if show_labels:
                items.append(
                    text_item(
                        item_id=f"label:mounting:{source_id}:{affected_id}",
                        x=(start[0] + end[0]) / 2.0,
                        y=(start[1] + end[1]) / 2.0,
                        text=constraint_detail_label("Mounting hole", details.get("gap_mm"), required),
                        style=_label_style(severity),
                        source_ids=source_ids,
                        severity=severity,
                    )
                )
        return items

    if finding["rule_id"] == "edge_distance" and source_component is not None:
        box = component_boxes.get(source_id)
        if box is not None:
            edge = nearest_edge_measurement(surface, box)
            required = _required_distance(details)
            start = (float(edge["start_x"]), float(edge["start_y"]))
            end = (float(edge["end_x"]), float(edge["end_y"]))
            edge_name = str(edge["edge"]).title()
            if show_lines:
                items.extend(
                    conflict_items(
                        item_id=f"conflict:edge:{source_id}:{edge_name.lower()}",
                        start=start,
                        end=end,
                        label="Too close to edge",
                        style=_conflict_style(severity),
                        label_style=_label_style(severity),
                        source_ids=source_ids,
                        severity=severity,
                    )
                )
            if show_measurements:
                items.extend(
                    measurement_items(
                        item_id=f"distance:edge:{source_id}",
                        start=start,
                        end=end,
                        current_mm=float(details.get("distance_mm", edge["distance"])),
                        required_mm=required,
                        style=_measurement_style(severity),
                        label_style=_label_style(severity),
                        source_ids=source_ids,
                        severity=severity,
                        title=edge_name,
                        include_label=show_labels,
                    )
                )
            if required is not None:
                items.append(_edge_clearance_area(surface, edge_name.lower(), required, severity, source_id))
        return items

    if finding["rule_id"] in {"inside_surface_component", "inside_surface_keepout", "inside_surface_cutout"} and source_component is not None:
        box = component_boxes.get(source_id)
        if box is not None and show_labels:
            label_position = midpoint((box["left"], box["top"]), (box["right"], box["top"]))
            items.append(
                text_item(
                    item_id=f"label:outside:{source_id}",
                    x=label_position[0],
                    y=label_position[1] + 3.0,
                    text="Outside surface",
                    style=_label_style(severity),
                    source_ids=source_ids,
                    severity=severity,
                )
            )
        return items

    if show_labels and source_component is not None:
        box = component_boxes.get(source_id)
        if box is not None:
            items.append(
                text_item(
                    item_id=f"label:{finding['rule_id']}:{source_id}",
                    x=box["center_x"],
                    y=box["top"] + 3.0,
                    text=_constraint_title(finding),
                    style=_label_style(severity),
                    source_ids=source_ids,
                    severity=severity,
                )
            )
    return items


def _filtered_findings(validation: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if settings.get("show_errors", True):
        findings.extend(validation.get("errors", []))
    if settings.get("show_warnings", True):
        findings.extend(validation.get("warnings", []))
    return findings


def _prioritize_findings(findings: list[dict[str, Any]], focus_ids: list[str]) -> list[dict[str, Any]]:
    def rank(finding: dict[str, Any]) -> tuple[int, int, str]:
        source_ids = {finding.get("source_component"), finding.get("affected_component")}
        focus_match = any(component_id in source_ids for component_id in focus_ids)
        severity_rank = 0 if finding["severity"] == "error" else 1
        focus_rank = 0 if focus_match else 1
        return (focus_rank, severity_rank, str(finding.get("rule_id", "")))

    ordered = sorted(findings, key=rank)
    if not focus_ids:
        return ordered
    focused = [finding for finding in ordered if any(component_id in {finding.get("source_component"), finding.get("affected_component")} for component_id in focus_ids)]
    if focused:
        return focused + [finding for finding in ordered if finding not in focused and finding["severity"] == "error"][:3]
    return ordered


def _required_distance(details: dict[str, Any]) -> float | None:
    for key in ("required_mm", "recommended_mm", "clearance_mm"):
        if key in details and details[key] is not None:
            return float(details[key])
    return None


def _constraint_title(finding: dict[str, Any]) -> str:
    rule_id = str(finding["rule_id"])
    if rule_id == "component_spacing":
        return "Min spacing violated"
    if rule_id == "keepout_spacing":
        return "Keepout overlap"
    if rule_id == "edge_distance":
        return "Too close to edge"
    if rule_id == "mounting_hole_clearance":
        return "Conflicts with mounting hole"
    if rule_id.startswith("ergonomic"):
        return "Ergonomic warning"
    return str(finding["message"])


def _measurement_style(severity: str | None) -> dict[str, Any]:
    if severity == "error":
        return overlay_style("measurement_line_error")
    if severity == "warning":
        return overlay_style("measurement_line_warning")
    return overlay_style("measurement_line")


def _conflict_style(severity: str) -> dict[str, Any]:
    return overlay_style("conflict_line_error" if severity == "error" else "conflict_line_warning")


def _label_style(severity: str) -> dict[str, Any]:
    return overlay_style("constraint_label_error" if severity == "error" else "constraint_label_warning")


def _clearance_boundary(
    item_id: str,
    component: dict[str, Any],
    shape: dict[str, Any],
    severity: str | None,
    source_ids: list[str],
) -> dict[str, Any]:
    style_kind = "clearance_boundary"
    if severity == "error":
        style_kind = "clearance_boundary_error"
    elif severity == "warning":
        style_kind = "clearance_boundary_warning"
    if shape.get("shape") == "circle":
        return circle_item(
            item_id=item_id,
            x=float(component["x"]),
            y=float(component["y"]),
            diameter=float(shape["diameter"]),
            style=overlay_style(style_kind),
            source_ids=source_ids,
            severity=severity,
        )
    return rect_item(
        item_id=item_id,
        x=float(component["x"]),
        y=float(component["y"]),
        width=float(shape["width"]),
        height=float(shape["height"]),
        style=overlay_style(style_kind),
        rotation=float(component.get("rotation", 0.0) or 0.0),
        source_ids=source_ids,
        severity=severity,
    )


def _edge_clearance_area(surface: dict[str, Any], edge: str, required: float, severity: str, component_id: str) -> dict[str, Any]:
    style_kind = "clearance_boundary_error" if severity == "error" else "clearance_boundary_warning"
    width = float(surface["width"])
    height = float(surface["height"])
    if edge == "left":
        return rect_item(f"clearance:edge:left:{component_id}", required / 2.0, height / 2.0, required, height, overlay_style(style_kind), severity=severity)
    if edge == "right":
        return rect_item(f"clearance:edge:right:{component_id}", width - (required / 2.0), height / 2.0, required, height, overlay_style(style_kind), severity=severity)
    if edge == "bottom":
        return rect_item(f"clearance:edge:bottom:{component_id}", width / 2.0, required / 2.0, width, required, overlay_style(style_kind), severity=severity)
    return rect_item(f"clearance:edge:top:{component_id}", width / 2.0, height - (required / 2.0), width, required, overlay_style(style_kind), severity=severity)


def _nearest_neighbor(component_id: str, component_boxes: dict[str, dict[str, float]]) -> tuple[str | None, float, tuple[float, float], tuple[float, float]]:
    nearest_id: str | None = None
    nearest_gap = 1e9
    nearest_start = (0.0, 0.0)
    nearest_end = (0.0, 0.0)
    first = component_boxes[component_id]
    for other_id, other in component_boxes.items():
        if other_id == component_id:
            continue
        start, end, gap = nearest_points_between_boxes(first, other)
        if gap < nearest_gap:
            nearest_id = other_id
            nearest_gap = gap
            nearest_start = start
            nearest_end = end
    return nearest_id, nearest_gap, nearest_start, nearest_end


def _legend(settings: dict[str, Any], validation: dict[str, Any]) -> list[dict[str, Any]]:
    from ocw_workbench.gui.overlay.legend import build_legend_items

    summary = validation.get("summary", {})
    return build_legend_items(
        settings=settings,
        style=overlay_style("legend_text"),
        error_count=int(summary.get("error_count", 0)),
        warning_count=int(summary.get("warning_count", 0)),
    )

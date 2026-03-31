from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_EDGE_MARGIN_MM = 12.0
DEFAULT_SPACING_MM = 18.0
PRIMARY_PRIORITY = "primary"
SECONDARY_PRIORITY = "secondary"


def build_layout_intelligence(
    state: dict[str, Any],
    *,
    template_payload: dict[str, Any] | None = None,
    template_service: Any | None = None,
    library_service: Any | None = None,
) -> dict[str, Any]:
    template = _resolve_template_payload(state, template_payload=template_payload, template_service=template_service)
    if template is None:
        return {
            "template_id": None,
            "template_name": None,
            "workflow_hint": None,
            "ideal_for": [],
            "next_step": None,
            "layout_zones": [],
            "smart_defaults": {},
            "suggested_additions": [],
            "workflow_card": {},
        }

    metadata = deepcopy(template.get("metadata", {})) if isinstance(template.get("metadata"), dict) else {}
    normalized_additions: list[dict[str, Any]] = []
    for addition in metadata.get("suggested_additions", []):
        if not isinstance(addition, dict):
            continue
        normalized_additions.append(_normalize_suggested_addition(addition))
    workflow_state = evaluate_workflow_state(
        state,
        metadata=metadata,
        additions=normalized_additions,
        library_service=library_service,
    )
    additions = resolve_suggested_additions(
        state,
        additions=normalized_additions,
        workflow_state=workflow_state,
        template_payload=template,
        library_service=library_service,
    )
    workflow_card = build_workflow_card(
        template=template,
        workflow_hint=str(metadata.get("workflow_hint") or ""),
        ideal_for=deepcopy(metadata.get("ideal_for", [])) if isinstance(metadata.get("ideal_for"), list) else [],
        additions=additions,
        workflow_state=workflow_state,
        all_additions=normalized_additions,
    )
    next_step_hint = str(workflow_card.get("next_step_hint") or metadata.get("next_step") or "")

    return {
        "template_id": template.get("template", {}).get("id"),
        "template_name": template.get("template", {}).get("name"),
        "workflow_hint": metadata.get("workflow_hint"),
        "ideal_for": deepcopy(metadata.get("ideal_for", [])) if isinstance(metadata.get("ideal_for"), list) else [],
        "next_step": next_step_hint,
        "layout_zones": deepcopy(metadata.get("layout_zones", [])) if isinstance(metadata.get("layout_zones"), list) else [],
        "smart_defaults": deepcopy(metadata.get("smart_defaults", {})) if isinstance(metadata.get("smart_defaults"), dict) else {},
        "suggested_additions": additions,
        "workflow_state": workflow_state,
        "workflow_card": workflow_card,
    }


def evaluate_workflow_state(
    state: dict[str, Any],
    *,
    metadata: dict[str, Any],
    additions: list[dict[str, Any]],
    library_service: Any | None = None,
) -> dict[str, Any]:
    components = deepcopy(state.get("components", []))
    signals = _evaluate_workflow_signals(components)
    completed_additions: list[str] = []
    for addition in additions:
        addition_id = str(addition.get("id") or "")
        if not addition_id:
            continue
        completed = _suggested_addition_present(addition, components)
        signals[f"addition:{addition_id}"] = completed
        if completed:
            completed_additions.append(addition_id)
    signals["has_display_or_utility_support"] = bool(
        signals.get("has_feedback_display") or signals.get("has_utility_strip")
    )
    signals["has_display_and_navigation_support"] = bool(
        signals.get("has_feedback_display") and signals.get("has_navigation_encoder")
    )
    visible_candidates = [
        addition
        for addition in additions
        if isinstance(addition, dict) and str(addition.get("id") or "") not in completed_additions
    ]
    return {
        "signals": signals,
        "completed_additions": completed_additions,
        "completed_count": len(completed_additions),
        "remaining_count": len(visible_candidates),
        "total_count": len(additions),
        "default_next_step": str(metadata.get("next_step") or ""),
    }


def resolve_suggested_additions(
    state: dict[str, Any],
    *,
    additions: list[dict[str, Any]],
    workflow_state: dict[str, Any],
    template_payload: dict[str, Any],
    library_service: Any | None = None,
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    signals = workflow_state.get("signals", {}) if isinstance(workflow_state, dict) else {}
    for addition in additions:
        if not isinstance(addition, dict):
            continue
        suggestion = deepcopy(addition)
        addition_id = str(suggestion.get("id") or "")
        if not addition_id:
            continue
        if bool(signals.get(f"addition:{addition_id}")):
            continue
        rule_state = _evaluate_action_conditions(suggestion, signals)
        if not rule_state["visible"]:
            continue
        preview_components = build_suggested_addition(
            state,
            addition_id,
            template_payload=template_payload,
            library_service=library_service,
            assign_unique_ids=False,
        )
        suggestion["preview_components"] = preview_components
        if preview_components:
            suggestion["target_zone_id"] = preview_components[0].get("zone_id")
        suggestion["workflow_match"] = {
            "completed": False,
            "requires_met": rule_state["requires_met"],
            "promoted": rule_state["promoted"],
        }
        suggestion["priority"] = rule_state["priority"]
        resolved.append(suggestion)
    resolved.sort(
        key=lambda item: (
            0 if str(item.get("priority") or SECONDARY_PRIORITY) == PRIMARY_PRIORITY else 1,
            _safe_int(item.get("order"), default=200),
            str(item.get("label") or "").lower(),
        )
    )
    return resolved


def suggest_component_placement(
    state: dict[str, Any],
    library_ref: str,
    *,
    component_id: str | None = None,
    template_payload: dict[str, Any] | None = None,
    template_service: Any | None = None,
    library_service: Any | None = None,
) -> dict[str, Any]:
    if library_service is None:
        raise ValueError("library_service is required for layout intelligence")

    template = _resolve_template_payload(state, template_payload=template_payload, template_service=template_service)
    metadata = deepcopy(template.get("metadata", {})) if isinstance(template, dict) and isinstance(template.get("metadata"), dict) else {}
    smart_defaults = deepcopy(metadata.get("smart_defaults", {})) if isinstance(metadata.get("smart_defaults"), dict) else {}
    controller = deepcopy(state.get("controller", {}))
    components = deepcopy(state.get("components", []))
    library_component = library_service.get(library_ref)
    ocf = library_component.get("ocf", {}) if isinstance(library_component.get("ocf"), dict) else {}
    placement_preference = str(ocf.get("placement_preference") or smart_defaults.get("default_placement_preference") or _default_preference_for_role(str(ocf.get("role") or "")))
    anchor = _anchor_for_components(components, controller, library_service, metadata, preferred_role=str(ocf.get("anchors_to_role") or ""))
    zone_id = _target_zone_id(metadata, placement_preference)
    x, y = _position_for_preference(
        placement_preference,
        anchor=anchor,
        controller=controller,
        count=1,
        index=0,
        spacing_mm=float(smart_defaults.get("spacing_mm") or DEFAULT_SPACING_MM),
        edge_margin_mm=float(smart_defaults.get("edge_margin_mm") or DEFAULT_EDGE_MARGIN_MM),
    )
    return {
        "component_id": component_id or str(library_component.get("id") or library_ref).split(".")[-1],
        "library_ref": library_ref,
        "component_type": str(library_component.get("category") or library_component.get("ocf", {}).get("control_type") or "component"),
        "x": x,
        "y": y,
        "rotation": 0.0,
        "zone_id": zone_id,
        "placement_preference": placement_preference,
        "role": str(ocf.get("role") or ""),
        "reason": _reason_for_preference(placement_preference),
    }


def build_suggested_addition(
    state: dict[str, Any],
    addition_id: str,
    *,
    template_payload: dict[str, Any] | None = None,
    template_service: Any | None = None,
    library_service: Any | None = None,
    assign_unique_ids: bool = True,
) -> list[dict[str, Any]]:
    if library_service is None:
        raise ValueError("library_service is required for layout intelligence")
    template = _resolve_template_payload(state, template_payload=template_payload, template_service=template_service)
    if template is None:
        return []
    metadata = template.get("metadata", {})
    if not isinstance(metadata, dict):
        return []
    suggestion = next(
        (
            deepcopy(item)
            for item in metadata.get("suggested_additions", [])
            if isinstance(item, dict) and str(item.get("id") or "") == addition_id
        ),
        None,
    )
    if suggestion is None:
        return []

    smart_defaults = deepcopy(metadata.get("smart_defaults", {})) if isinstance(metadata.get("smart_defaults"), dict) else {}
    controller = deepcopy(state.get("controller", {}))
    components = deepcopy(state.get("components", []))
    existing_ids = {str(component.get("id")) for component in components}
    suggestion_items = suggestion.get("components", [])
    if not isinstance(suggestion_items, list):
        return []
    placement_preference = str(suggestion.get("placement_preference") or "right_of_main")
    anchor = _anchor_for_components(
        components,
        controller,
        library_service,
        metadata,
        preferred_role=str(suggestion.get("target_group_role") or ""),
    )
    spacing_mm = float(suggestion.get("spacing_mm") or smart_defaults.get("spacing_mm") or DEFAULT_SPACING_MM)
    edge_margin_mm = float(smart_defaults.get("edge_margin_mm") or DEFAULT_EDGE_MARGIN_MM)
    zone_id = str(suggestion.get("zone_id") or _target_zone_id(metadata, placement_preference) or "") or None
    group_id = str(suggestion.get("group_id") or addition_id)
    group_role = str(suggestion.get("group_role") or addition_id)

    built: list[dict[str, Any]] = []
    for index, raw_item in enumerate(suggestion_items):
        if not isinstance(raw_item, dict):
            continue
        library_ref = str(raw_item.get("library_ref") or "").strip()
        if not library_ref:
            continue
        library_component = library_service.get(library_ref)
        x, y = _position_for_preference(
            str(raw_item.get("placement_preference") or placement_preference),
            anchor=anchor,
            controller=controller,
            count=len(suggestion_items),
            index=index,
            spacing_mm=float(raw_item.get("spacing_mm") or spacing_mm),
            edge_margin_mm=edge_margin_mm,
        )
        base_id = str(raw_item.get("id") or str(library_ref).split(".")[-1])
        component_id = _unique_component_id(base_id, existing_ids) if assign_unique_ids else base_id
        existing_ids.add(component_id)
        built.append(
            {
                "id": component_id,
                "type": str(raw_item.get("type") or library_component.get("category") or "component"),
                "library_ref": library_ref,
                "x": x,
                "y": y,
                "rotation": float(raw_item.get("rotation", 0.0) or 0.0),
                "zone_id": str(raw_item.get("zone_id") or zone_id or "") or None,
                "group_id": str(raw_item.get("group_id") or group_id),
                "group_role": str(raw_item.get("group_role") or group_role),
                "label": str(raw_item.get("label") or ""),
                "properties": {
                    "suggested_addition_id": addition_id,
                    "placement_preference": str(raw_item.get("placement_preference") or placement_preference),
                },
            }
        )
    return built


def _resolve_template_payload(
    state: dict[str, Any],
    *,
    template_payload: dict[str, Any] | None,
    template_service: Any | None,
) -> dict[str, Any] | None:
    if template_payload is not None:
        return template_payload
    meta = state.get("meta", {}) if isinstance(state.get("meta"), dict) else {}
    template_id = meta.get("template_id") or state.get("template", {}).get("id")
    if not isinstance(template_id, str) or not template_id:
        return None
    if template_service is None:
        return None
    return template_service.get_template(template_id)


def _default_preference_for_role(role: str) -> str:
    normalized = (role or "").strip()
    mapping = {
        "primary_control": "right_of_main",
        "navigation": "right_of_main",
        "utility": "top_row",
        "feedback": "centered_above_group",
    }
    return mapping.get(normalized, "right_of_main")


def _normalize_suggested_addition(addition: dict[str, Any]) -> dict[str, Any]:
    suggestion = deepcopy(addition)
    suggestion.setdefault("label", _humanize_addition_id(str(suggestion.get("id") or "")))
    description = str(suggestion.get("description") or "").strip()
    suggestion["short_label"] = str(suggestion.get("short_label") or suggestion["label"])
    suggestion["tooltip"] = str(suggestion.get("tooltip") or description or suggestion["label"])
    suggestion["category"] = str(suggestion.get("category") or "Next Steps")
    suggestion["group"] = str(suggestion.get("group") or "utility")
    suggestion["icon"] = str(suggestion.get("icon") or "generic.svg")
    suggestion["priority"] = str(suggestion.get("priority") or SECONDARY_PRIORITY)
    suggestion["order"] = _safe_int(suggestion.get("order"), default=200)
    suggestion["command_id"] = str(suggestion.get("command_id") or _command_id_for_addition_id(str(suggestion.get("id") or "")))
    suggestion["status_message"] = str(
        suggestion.get("status_message")
        or f"{suggestion['label']} added."
    )
    for key in ("requires", "excludes", "promote_if"):
        raw = suggestion.get(key, [])
        suggestion[key] = [str(item) for item in raw if isinstance(item, str) and item.strip()] if isinstance(raw, list) else []
    return suggestion


def build_workflow_card(
    *,
    template: dict[str, Any],
    workflow_hint: str,
    ideal_for: list[Any],
    additions: list[dict[str, Any]],
    workflow_state: dict[str, Any],
    all_additions: list[dict[str, Any]],
) -> dict[str, Any]:
    primary_action = next(
        (
            item
            for item in additions
            if isinstance(item, dict) and str(item.get("priority") or SECONDARY_PRIORITY) == PRIMARY_PRIORITY
        ),
        additions[0] if additions else None,
    )
    secondary_actions = [
        item
        for item in additions
        if isinstance(item, dict) and item is not primary_action
    ][:4]
    completed_count = _safe_int(workflow_state.get("completed_count"), default=0)
    total_count = _safe_int(workflow_state.get("total_count"), default=0)
    progress_text = (
        f"{completed_count} of {total_count} typical setup steps completed."
        if total_count > 0
        else ""
    )
    if isinstance(primary_action, dict):
        next_step_hint = str(primary_action.get("description") or primary_action.get("label") or workflow_hint)
    elif total_count > 0 and completed_count >= total_count:
        next_step_hint = "Typical starter additions for this template are already in place."
    else:
        next_step_hint = str(workflow_state.get("default_next_step") or workflow_hint or "")
    short_description = next_step_hint
    if progress_text:
        short_description = f"{short_description} {progress_text}".strip()
    completed_ids = {
        str(item)
        for item in workflow_state.get("completed_additions", [])
        if isinstance(item, str) and item.strip()
    }
    current_action_id = str(primary_action.get("id") or "") if isinstance(primary_action, dict) else ""
    addition_by_id = {
        str(addition.get("id") or ""): addition
        for addition in all_additions
        if isinstance(addition, dict) and str(addition.get("id") or "")
    }
    completed_order = [
        addition_id
        for addition_id in addition_by_id
        if addition_id in completed_ids
    ]
    remaining_order = [
        str(item.get("id") or "")
        for item in additions
        if isinstance(item, dict) and str(item.get("id") or "")
    ]
    step_order = list(completed_order)
    if current_action_id and current_action_id not in step_order:
        step_order.append(current_action_id)
    for addition_id in remaining_order:
        if addition_id and addition_id not in step_order:
            step_order.append(addition_id)
    steps: list[dict[str, Any]] = []
    for addition_id in step_order:
        addition = addition_by_id.get(addition_id)
        if addition is None:
            continue
        status = "open"
        if addition_id in completed_ids:
            status = "completed"
        elif current_action_id and addition_id == current_action_id:
            status = "current"
        steps.append(
            {
                "id": addition_id,
                "label": str(addition.get("label") or addition.get("short_label") or addition_id),
                "short_label": str(addition.get("short_label") or addition.get("label") or addition_id),
                "description": str(addition.get("description") or ""),
                "status": status,
            }
        )
    return {
        "template_title": str(template.get("template", {}).get("name") or template.get("template", {}).get("id") or "-"),
        "short_description": short_description,
        "ideal_for": [str(item) for item in ideal_for if isinstance(item, str) and item.strip()][:3],
        "primary_action": deepcopy(primary_action) if isinstance(primary_action, dict) else None,
        "secondary_actions": deepcopy(secondary_actions),
        "next_step_hint": next_step_hint,
        "progress_text": progress_text,
        "completed_steps": completed_count,
        "total_steps": total_count,
        "steps": steps,
    }


def _humanize_addition_id(addition_id: str) -> str:
    normalized = str(addition_id).replace("_", " ").strip().title()
    return normalized if normalized.startswith("Add ") else f"Add {normalized}"


def _command_id_for_addition_id(addition_id: str) -> str:
    return f"OCW_{_humanize_addition_id(addition_id).replace(' ', '')}"


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _reason_for_preference(preference: str) -> str:
    reasons = {
        "right_of_main": "Placed to the right of the main control area for easy secondary access.",
        "top_row": "Placed as a top-row companion above the main control area.",
        "centered_above_group": "Placed above the main group so feedback stays visually tied to the controls.",
        "bottom_transport_row": "Placed near the lower edge to read like a transport or utility strip.",
        "aligned_with_group": "Placed in line with the current primary group for a predictable extension.",
    }
    return reasons.get(preference, "Placed using the template smart defaults.")


def _evaluate_workflow_signals(components: list[dict[str, Any]]) -> dict[str, bool]:
    return {
        "has_utility_strip": any(_component_matches(component, group_roles={"utility_strip", "channel_utility_extension"}) for component in components),
        "has_feedback_display": any(_component_matches(component, component_types={"display"}, group_roles={"feedback_header"}) for component in components),
        "has_navigation_encoder": any(_component_matches(component, component_types={"encoder"}, group_roles={"navigation_strip", "navigation_header", "navigation_extension"}) for component in components),
        "has_navigation_pair": _count_matching_components(
            components,
            component_types={"encoder"},
            group_roles={"navigation_strip", "navigation_header", "navigation_extension"},
        ) >= 2,
        "has_channel_display": any(_component_matches(component, component_types={"display"}, zone_ids={"top_label_area"}, addition_ids={"channel_display"}) for component in components),
        "has_transport_buttons": any(_component_matches(component, group_roles={"transport_strip"}, addition_ids={"transport_buttons"}) for component in components),
        "has_secondary_encoder_row": any(_component_matches(component, group_roles={"secondary_encoder_row"}, addition_ids={"secondary_encoder_row"}) for component in components),
        "has_top_encoder": any(_component_matches(component, group_roles={"navigation_header"}, addition_ids={"top_encoder"}) for component in components),
    }


def _evaluate_action_conditions(addition: dict[str, Any], signals: dict[str, Any]) -> dict[str, Any]:
    requires = [signal for signal in addition.get("requires", []) if isinstance(signal, str) and signal.strip()]
    excludes = [signal for signal in addition.get("excludes", []) if isinstance(signal, str) and signal.strip()]
    promote_if = [signal for signal in addition.get("promote_if", []) if isinstance(signal, str) and signal.strip()]
    requires_met = all(bool(signals.get(signal)) for signal in requires)
    excluded = any(bool(signals.get(signal)) for signal in excludes)
    promoted = bool(promote_if) and all(bool(signals.get(signal)) for signal in promote_if)
    priority = PRIMARY_PRIORITY if promoted else str(addition.get("priority") or SECONDARY_PRIORITY)
    return {
        "visible": requires_met and not excluded,
        "requires_met": requires_met,
        "promoted": promoted,
        "priority": priority,
    }


def _suggested_addition_present(addition: dict[str, Any], components: list[dict[str, Any]]) -> bool:
    addition_id = str(addition.get("id") or "")
    if addition_id and any(_component_matches(component, addition_ids={addition_id}) for component in components):
        return True
    group_id = str(addition.get("group_id") or "")
    if group_id and any(str(component.get("group_id") or "") == group_id for component in components):
        return True
    group_role = str(addition.get("group_role") or "")
    suggestion_items = addition.get("components", [])
    if not group_role or not isinstance(suggestion_items, list) or not suggestion_items:
        return False
    existing_by_library: dict[str, int] = {}
    for component in components:
        if str(component.get("group_role") or "") != group_role:
            continue
        library_ref = str(component.get("library_ref") or "")
        existing_by_library[library_ref] = existing_by_library.get(library_ref, 0) + 1
    required_by_library: dict[str, int] = {}
    for item in suggestion_items:
        if not isinstance(item, dict):
            continue
        library_ref = str(item.get("library_ref") or "")
        if not library_ref:
            continue
        required_by_library[library_ref] = required_by_library.get(library_ref, 0) + 1
    return bool(required_by_library) and all(existing_by_library.get(library_ref, 0) >= count for library_ref, count in required_by_library.items())


def _component_matches(
    component: dict[str, Any],
    *,
    component_types: set[str] | None = None,
    group_roles: set[str] | None = None,
    zone_ids: set[str] | None = None,
    addition_ids: set[str] | None = None,
) -> bool:
    if not isinstance(component, dict):
        return False
    if component_types is not None and str(component.get("type") or "") not in component_types:
        return False
    if group_roles is not None and str(component.get("group_role") or "") not in group_roles:
        return False
    if zone_ids is not None and str(component.get("zone_id") or "") not in zone_ids:
        return False
    if addition_ids is not None:
        properties = component.get("properties", {})
        addition_id = str(properties.get("suggested_addition_id") or "") if isinstance(properties, dict) else ""
        if addition_id not in addition_ids:
            return False
    return True


def _count_matching_components(
    components: list[dict[str, Any]],
    *,
    component_types: set[str] | None = None,
    group_roles: set[str] | None = None,
    zone_ids: set[str] | None = None,
    addition_ids: set[str] | None = None,
) -> int:
    return sum(
        1
        for component in components
        if _component_matches(
            component,
            component_types=component_types,
            group_roles=group_roles,
            zone_ids=zone_ids,
            addition_ids=addition_ids,
        )
    )


def _anchor_for_components(
    components: list[dict[str, Any]],
    controller: dict[str, Any],
    library_service: Any,
    metadata: dict[str, Any],
    *,
    preferred_role: str,
) -> dict[str, float]:
    smart_defaults = metadata.get("smart_defaults", {}) if isinstance(metadata, dict) else {}
    primary_zone_id = str(smart_defaults.get("primary_zone_id") or "").strip()
    if primary_zone_id:
        zone_anchor = _anchor_from_controller_zone(controller, primary_zone_id)
        if zone_anchor is not None:
            return zone_anchor
    primary_group_role = str(smart_defaults.get("primary_group_role") or "").strip()
    if primary_group_role:
        grouped = [component for component in components if str(component.get("group_role") or "") == primary_group_role]
        if grouped:
            return _component_bbox(grouped, library_service)
    if preferred_role:
        grouped = [component for component in components if str(component.get("group_role") or "") == preferred_role]
        if grouped:
            return _component_bbox(grouped, library_service)
    if components:
        bbox = _component_bbox(components, library_service)
        if bbox["width"] > 1.0 or bbox["height"] > 1.0 or bbox["center_x"] > 1.0 or bbox["center_y"] > 1.0:
            return bbox
    width = float(controller.get("width", controller.get("surface", {}).get("width", 160.0)) or 160.0)
    depth = float(controller.get("depth", controller.get("surface", {}).get("height", 100.0)) or 100.0)
    return {
        "min_x": width * 0.25,
        "max_x": width * 0.75,
        "min_y": depth * 0.25,
        "max_y": depth * 0.75,
        "center_x": width * 0.5,
        "center_y": depth * 0.5,
        "width": width * 0.5,
        "height": depth * 0.5,
    }


def _anchor_from_controller_zone(controller: dict[str, Any], zone_id: str) -> dict[str, float] | None:
    zones = controller.get("layout_zones", [])
    if not isinstance(zones, list):
        return None
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        if str(zone.get("id") or "") != zone_id:
            continue
        x = float(zone.get("x", 0.0) or 0.0)
        y = float(zone.get("y", 0.0) or 0.0)
        width = float(zone.get("width", 0.0) or 0.0)
        height = float(zone.get("height", 0.0) or 0.0)
        return {
            "min_x": x,
            "max_x": x + width,
            "min_y": y,
            "max_y": y + height,
            "center_x": x + (width / 2.0),
            "center_y": y + (height / 2.0),
            "width": width,
            "height": height,
        }
    return None


def _component_bbox(components: list[dict[str, Any]], library_service: Any) -> dict[str, float]:
    min_x = None
    max_x = None
    min_y = None
    max_y = None
    for component in components:
        x = float(component.get("x", 0.0) or 0.0)
        y = float(component.get("y", 0.0) or 0.0)
        half_w, half_h = _component_half_extents(component, library_service)
        left = x - half_w
        right = x + half_w
        top = y - half_h
        bottom = y + half_h
        min_x = left if min_x is None else min(min_x, left)
        max_x = right if max_x is None else max(max_x, right)
        min_y = top if min_y is None else min(min_y, top)
        max_y = bottom if max_y is None else max(max_y, bottom)
    resolved_min_x = float(min_x if min_x is not None else 0.0)
    resolved_max_x = float(max_x if max_x is not None else 0.0)
    resolved_min_y = float(min_y if min_y is not None else 0.0)
    resolved_max_y = float(max_y if max_y is not None else 0.0)
    return {
        "min_x": resolved_min_x,
        "max_x": resolved_max_x,
        "min_y": resolved_min_y,
        "max_y": resolved_max_y,
        "center_x": (resolved_min_x + resolved_max_x) / 2.0,
        "center_y": (resolved_min_y + resolved_max_y) / 2.0,
        "width": resolved_max_x - resolved_min_x,
        "height": resolved_max_y - resolved_min_y,
    }


def _component_half_extents(component: dict[str, Any], library_service: Any) -> tuple[float, float]:
    library_ref = component.get("library_ref")
    if not isinstance(library_ref, str) or not library_ref:
        return (8.0, 8.0)
    library_component = library_service.get(library_ref)
    mechanical = library_component.get("mechanical", {}) if isinstance(library_component.get("mechanical"), dict) else {}
    panel = mechanical.get("panel", {}) if isinstance(mechanical.get("panel"), dict) else {}
    body = mechanical.get("body_size_mm", {}) if isinstance(mechanical.get("body_size_mm"), dict) else {}
    recommended = panel.get("recommended_keepout_top_mm")
    if isinstance(recommended, dict):
        width = float(recommended.get("width", body.get("width", 16.0)) or body.get("width", 16.0) or 16.0)
        height = float(recommended.get("height", body.get("depth", 16.0)) or body.get("depth", 16.0) or 16.0)
        return (width / 2.0, height / 2.0)
    top_diameter = panel.get("recommended_keepout_top_diameter_mm")
    if top_diameter is not None:
        diameter = float(top_diameter or 16.0)
        return (diameter / 2.0, diameter / 2.0)
    width = float(body.get("width", 16.0) or 16.0)
    height = float(body.get("depth", 16.0) or 16.0)
    return (width / 2.0, height / 2.0)


def _position_for_preference(
    preference: str,
    *,
    anchor: dict[str, float],
    controller: dict[str, Any],
    count: int,
    index: int,
    spacing_mm: float,
    edge_margin_mm: float,
) -> tuple[float, float]:
    width = float(controller.get("width", controller.get("surface", {}).get("width", 160.0)) or 160.0)
    depth = float(controller.get("depth", controller.get("surface", {}).get("height", 100.0)) or 100.0)
    center_offset = (index - ((count - 1) / 2.0)) * spacing_mm
    if preference == "top_row":
        return (
            _clamp(anchor["center_x"] + center_offset, edge_margin_mm, width - edge_margin_mm),
            _clamp(anchor["min_y"] - 18.0, edge_margin_mm, depth - edge_margin_mm),
        )
    if preference == "centered_above_group":
        return (
            _clamp(anchor["center_x"] + center_offset, edge_margin_mm, width - edge_margin_mm),
            _clamp(anchor["min_y"] - 20.0, edge_margin_mm, depth - edge_margin_mm),
        )
    if preference == "bottom_transport_row":
        return (
            _clamp(anchor["center_x"] + center_offset, edge_margin_mm, width - edge_margin_mm),
            _clamp(anchor["max_y"] + 18.0, edge_margin_mm, depth - edge_margin_mm),
        )
    if preference == "aligned_with_group":
        return (
            _clamp(anchor["min_x"] + 12.0 + (index * spacing_mm), edge_margin_mm, width - edge_margin_mm),
            _clamp(anchor["center_y"], edge_margin_mm, depth - edge_margin_mm),
        )
    return (
        _clamp(anchor["max_x"] + 20.0, edge_margin_mm, width - edge_margin_mm),
        _clamp(anchor["center_y"] + center_offset, edge_margin_mm, depth - edge_margin_mm),
    )


def _target_zone_id(metadata: dict[str, Any], placement_preference: str) -> str | None:
    layout_zones = metadata.get("layout_zones", []) if isinstance(metadata, dict) else []
    if not isinstance(layout_zones, list):
        return None
    for zone in layout_zones:
        if not isinstance(zone, dict):
            continue
        if str(zone.get("placement_preference") or "") == placement_preference:
            zone_id = str(zone.get("id") or "").strip()
            if zone_id:
                return zone_id
    return None


def _unique_component_id(base_id: str, existing_ids: set[str]) -> str:
    candidate = base_id
    counter = 2
    while candidate in existing_ids:
        candidate = f"{base_id}_{counter}"
        counter += 1
    return candidate


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(float(minimum), min(float(maximum), float(value)))

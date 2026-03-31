from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_EDGE_MARGIN_MM = 12.0
DEFAULT_SPACING_MM = 18.0


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
            "workflow_hint": None,
            "ideal_for": [],
            "next_step": None,
            "layout_zones": [],
            "smart_defaults": {},
            "suggested_additions": [],
        }

    metadata = deepcopy(template.get("metadata", {})) if isinstance(template.get("metadata"), dict) else {}
    additions: list[dict[str, Any]] = []
    for addition in metadata.get("suggested_additions", []):
        if not isinstance(addition, dict):
            continue
        suggestion = deepcopy(addition)
        suggestion.setdefault("label", _humanize_addition_id(str(suggestion.get("id") or "")))
        description = str(suggestion.get("description") or "").strip()
        suggestion["tooltip"] = str(suggestion.get("tooltip") or description or suggestion["label"])
        suggestion["category"] = str(suggestion.get("category") or "Next Steps")
        suggestion["icon"] = str(suggestion.get("icon") or "generic.svg")
        suggestion["order"] = _safe_int(suggestion.get("order"), default=200)
        suggestion["command_id"] = str(suggestion.get("command_id") or _command_id_for_addition_id(str(suggestion.get("id") or "")))
        preview_components = build_suggested_addition(
            state,
            str(suggestion.get("id") or ""),
            template_payload=template,
            library_service=library_service,
            assign_unique_ids=False,
        )
        suggestion["preview_components"] = preview_components
        if preview_components:
            suggestion["target_zone_id"] = preview_components[0].get("zone_id")
        additions.append(suggestion)
    additions.sort(key=lambda item: (_safe_int(item.get("order"), default=200), str(item.get("label") or "").lower()))

    return {
        "template_id": template.get("template", {}).get("id"),
        "workflow_hint": metadata.get("workflow_hint"),
        "ideal_for": deepcopy(metadata.get("ideal_for", [])) if isinstance(metadata.get("ideal_for"), list) else [],
        "next_step": metadata.get("next_step"),
        "layout_zones": deepcopy(metadata.get("layout_zones", [])) if isinstance(metadata.get("layout_zones"), list) else [],
        "smart_defaults": deepcopy(metadata.get("smart_defaults", {})) if isinstance(metadata.get("smart_defaults"), dict) else {},
        "suggested_additions": additions,
    }


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

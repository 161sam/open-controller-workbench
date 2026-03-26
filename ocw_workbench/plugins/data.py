from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


def normalize_component_payload(payload: dict[str, Any], source: Path, plugin_id: str) -> dict[str, Any]:
    component_id = _required_str(payload.get("id"), "id", source)
    component_type = _required_str(payload.get("type"), "type", source)
    ui = payload.get("ui", {})
    if ui is not None and not isinstance(ui, dict):
        raise ValueError(f"Component '{component_id}' field 'ui' must be a mapping in {source}")
    ui = ui if isinstance(ui, dict) else {}
    electrical = _optional_mapping(payload.get("electrical"), "electrical", component_id, source)
    mechanical = _optional_mapping(payload.get("mechanical"), "mechanical", component_id, source)
    pcb = _optional_mapping(payload.get("pcb"), "pcb", component_id, source)
    ocf = _optional_mapping(payload.get("ocf"), "ocf", component_id, source)
    tags = payload.get("tags", [])
    if tags is not None and not isinstance(tags, list):
        raise ValueError(f"Component '{component_id}' field 'tags' must be a list in {source}")
    normalized = {
        "id": qualify_id(plugin_id, component_id),
        "category": str(payload.get("category") or component_type),
        "manufacturer": str(payload.get("manufacturer") or "Unknown"),
        "part_number": str(payload.get("part_number") or ""),
        "description": str(payload.get("description") or ui.get("label") or component_id),
        "tags": [str(item) for item in tags or []],
        "mechanical": _normalize_mechanical(mechanical),
        "electrical": _normalize_electrical(electrical),
        "pcb": pcb,
        "ocf": _normalize_ocf(ocf, component_type, ui),
        "ui": _normalize_component_ui(
            ui,
            category=str(payload.get("category") or component_type),
            description=str(payload.get("description") or ui.get("label") or component_id),
            component_id=qualify_id(plugin_id, component_id),
            tags=[str(item) for item in tags or []],
            source=source,
        ),
    }
    return normalized


def normalize_template_payload(payload: dict[str, Any], source: Path, plugin_id: str) -> dict[str, Any]:
    template_id = _required_str(payload.get("id"), "id", source)
    name = str(payload.get("name") or template_id.replace("_", " ").title())
    description = str(payload.get("description") or name)
    shape = payload.get("shape")
    components = payload.get("components")
    if not isinstance(shape, dict):
        raise ValueError(f"Template '{template_id}' field 'shape' must be a mapping in {source}")
    if not isinstance(components, list):
        raise ValueError(f"Template '{template_id}' field 'components' must be a list in {source}")

    controller = {
        "surface": _normalize_shape(shape, source, f"template '{template_id}'"),
        "width": float(shape.get("width", 160.0)),
        "depth": float(shape.get("height", 100.0)),
        "height": float(payload.get("height", 30.0)),
        "top_thickness": float(payload.get("top_thickness", 3.0)),
        "mounting_holes": deepcopy(payload.get("mounting_holes", [])),
        "reserved_zones": deepcopy(payload.get("reserved_zones", [])),
    }
    normalized_components = [_normalize_template_component(item, source, plugin_id, template_id) for item in components]
    return {
        "template": {
            "id": qualify_id(plugin_id, template_id),
            "name": name,
            "description": description,
            "category": payload.get("category"),
            "tags": deepcopy(payload.get("tags")),
            "version": payload.get("version"),
        },
        "controller": controller,
        "zones": deepcopy(payload.get("zones", [])),
        "components": normalized_components,
        "layout": deepcopy(payload.get("layout", {})),
        "constraints": deepcopy(payload.get("constraints", {})),
        "defaults": deepcopy(payload.get("defaults", {})),
        "firmware": deepcopy(payload.get("firmware", {})),
        "ocf": deepcopy(payload.get("ocf", {})),
    }


def normalize_variant_payload(payload: dict[str, Any], source: Path, plugin_id: str) -> dict[str, Any]:
    variant_id = _required_str(payload.get("id"), "id", source)
    name = str(payload.get("name") or variant_id.replace("_", " ").title())
    description = str(payload.get("description") or name)
    template_id = payload.get("template") or payload.get("template_id")
    if not isinstance(template_id, str) or not template_id:
        raise ValueError(f"Variant '{variant_id}' in {source} is missing a valid 'template' or 'template_id'")
    overrides = payload.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError(f"Variant '{variant_id}' field 'overrides' must be a mapping in {source}")

    normalized_overrides = deepcopy(overrides)
    if isinstance(overrides.get("components"), list):
        updates: dict[str, dict[str, Any]] = {}
        for item in overrides["components"]:
            if not isinstance(item, dict):
                raise ValueError(f"Variant '{variant_id}' has invalid component override in {source}: {item!r}")
            ref = _required_str(item.get("ref"), "overrides.components[].ref", source)
            updates[ref] = _normalize_component_patch(item, plugin_id)
        normalized_overrides["components"] = {"update": updates}
    elif "components" not in normalized_overrides:
        normalized_overrides["components"] = {}
    elif not isinstance(normalized_overrides["components"], dict):
        raise ValueError(f"Variant '{variant_id}' field 'overrides.components' must be a mapping or list in {source}")

    add_items = overrides.get("add", [])
    if add_items:
        if not isinstance(add_items, list):
            raise ValueError(f"Variant '{variant_id}' field 'overrides.add' must be a list in {source}")
        normalized_overrides["components"].setdefault("add", [])
        normalized_overrides["components"]["add"].extend(
            _normalize_variant_add(item, source, plugin_id, variant_id) for item in add_items
        )

    return {
        "variant": {
            "id": qualify_id(plugin_id, variant_id),
            "name": name,
            "description": description,
            "template_id": template_id,
            "category": payload.get("category"),
            "tags": deepcopy(payload.get("tags")),
            "version": payload.get("version"),
        },
        "overrides": normalized_overrides,
    }


def qualify_id(plugin_id: str, value: str) -> str:
    return value if "." in value else f"{plugin_id}.{value}"


def alias_candidates(canonical_id: str, plugin_id: str | None) -> list[str]:
    if plugin_id and canonical_id.startswith(f"{plugin_id}."):
        return [canonical_id[len(plugin_id) + 1 :]]
    return []


def _normalize_shape(shape: dict[str, Any], source: Path, context: str) -> dict[str, Any]:
    shape_type = str(shape.get("type") or shape.get("shape") or "rectangle")
    if shape_type not in {"rectangle", "rounded_rect", "polygon"}:
        raise ValueError(f"{context} has unsupported shape type '{shape_type}' in {source}")
    normalized = {
        "type": shape_type,
        "shape": shape_type,
        "width": float(shape.get("width", 160.0)),
        "height": float(shape.get("height", 100.0)),
    }
    if "corner_radius" in shape:
        normalized["corner_radius"] = float(shape["corner_radius"])
    if "points" in shape:
        normalized["points"] = deepcopy(shape["points"])
    return normalized


def _normalize_template_component(item: Any, source: Path, plugin_id: str, template_id: str) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"Template '{template_id}' has invalid component entry in {source}: {item!r}")
    ref = _required_str(item.get("ref"), "components[].ref", source)
    component_ref = _required_str(item.get("component"), "components[].component", source)
    position = item.get("position", [0.0, 0.0])
    if not isinstance(position, list) or len(position) != 2:
        raise ValueError(f"Template '{template_id}' component '{ref}' requires position [x, y] in {source}")
    return {
        "id": ref,
        "type": str(item.get("type") or "component"),
        "library_ref": qualify_id(plugin_id, component_ref),
        "x": float(position[0]),
        "y": float(position[1]),
        "rotation": float(item.get("rotation", 0.0) or 0.0),
        "zone_id": item.get("zone") or item.get("zone_id"),
    }


def _normalize_component_patch(item: dict[str, Any], plugin_id: str) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    position = item.get("position")
    if position is not None:
        if not isinstance(position, list) or len(position) != 2:
            raise ValueError("Variant component override position must be [x, y]")
        patch["x"] = float(position[0])
        patch["y"] = float(position[1])
    if "rotation" in item:
        patch["rotation"] = float(item["rotation"] or 0.0)
    if "component" in item and item["component"] is not None:
        patch["library_ref"] = qualify_id(plugin_id, str(item["component"]))
    if "type" in item and item["type"] is not None:
        patch["type"] = str(item["type"])
    return patch


def _normalize_variant_add(item: Any, source: Path, plugin_id: str, variant_id: str) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"Variant '{variant_id}' has invalid add entry in {source}: {item!r}")
    ref = _required_str(item.get("ref"), "overrides.add[].ref", source)
    component_ref = _required_str(item.get("component"), "overrides.add[].component", source)
    position = item.get("position", [0.0, 0.0])
    if not isinstance(position, list) or len(position) != 2:
        raise ValueError(f"Variant '{variant_id}' add entry '{ref}' requires position [x, y] in {source}")
    return {
        "id": ref,
        "type": str(item.get("type") or "component"),
        "library_ref": qualify_id(plugin_id, component_ref),
        "x": float(position[0]),
        "y": float(position[1]),
        "rotation": float(item.get("rotation", 0.0) or 0.0),
        "zone_id": item.get("zone") or item.get("zone_id"),
    }


def _normalize_electrical(electrical: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(electrical)
    pins = normalized.get("pins")
    if isinstance(pins, list) and all(isinstance(item, dict) and "name" in item for item in pins):
        normalized["pins"] = [str(item["name"]) for item in pins]
    return normalized


def _normalize_ocf(ocf: dict[str, Any], component_type: str, ui: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(ocf)
    normalized.setdefault("control_type", component_type)
    if "label" in ui and "label" not in normalized:
        normalized["label"] = str(ui["label"])
    if "category" in ui and "ui_category" not in normalized:
        normalized["ui_category"] = str(ui["category"])
    return normalized


def _normalize_component_ui(
    ui: dict[str, Any],
    *,
    category: str,
    description: str,
    component_id: str,
    tags: list[str],
    source: Path,
) -> dict[str, Any]:
    icon = ui.get("icon")
    if icon is not None and not isinstance(icon, str):
        raise ValueError(f"Component '{component_id}' field 'ui.icon' must be a string in {source}")
    ui_tags = ui.get("tags")
    if ui_tags is not None and not isinstance(ui_tags, list):
        raise ValueError(f"Component '{component_id}' field 'ui.tags' must be a list in {source}")
    return {
        "label": str(ui.get("label") or description or component_id),
        "icon": str(icon or "generic.svg"),
        "category": str(ui.get("category") or category),
        "tags": [str(item) for item in (ui_tags or tags)],
    }


def _normalize_mechanical(mechanical: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(mechanical)
    cutout = normalized.get("cutout")
    if isinstance(cutout, dict) and "shape" not in cutout and "type" in cutout:
        cutout["shape"] = cutout["type"]
    keepout = normalized.pop("keepout", None)
    if isinstance(keepout, dict):
        if "shape" not in keepout and "type" in keepout:
            keepout["shape"] = keepout["type"]
        normalized.setdefault("keepout_top", deepcopy(keepout))
        bottom = deepcopy(keepout)
        bottom.setdefault("depth", float(normalized.get("height", 10.0) or 10.0))
        normalized.setdefault("keepout_bottom", bottom)
    for key in ("keepout_top", "keepout_bottom"):
        feature = normalized.get(key)
        if isinstance(feature, dict) and "shape" not in feature and "type" in feature:
            feature["shape"] = feature["type"]
    return normalized


def _optional_mapping(value: Any, field: str, item_id: str, source: Path) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Item '{item_id}' field '{field}' must be a mapping in {source}")
    return deepcopy(value)


def _required_str(value: Any, field: str, source: Path) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing required field '{field}' in {source}")
    return value

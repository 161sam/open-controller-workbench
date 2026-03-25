from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocf_freecad.geometry.primitives import ResolvedMechanical, ShapePrimitive

SUPPORTED_SHAPES = {"circle", "rect", "slot"}


def normalize_mechanical(
    component_type: str,
    mechanical: dict[str, Any],
    component_id: str,
) -> ResolvedMechanical:
    if not isinstance(mechanical, dict):
        raise ValueError(f"Mechanical data for component '{component_id}' must be a mapping")

    cutout = _normalize_feature(
        component_type=component_type,
        feature_name="cutout",
        explicit=mechanical.get("cutout"),
        derived=_derive_feature(component_type, mechanical, "cutout"),
        component_id=component_id,
        require_depth=False,
    )
    keepout_top = _normalize_feature(
        component_type=component_type,
        feature_name="keepout_top",
        explicit=mechanical.get("keepout_top"),
        derived=_derive_feature(component_type, mechanical, "keepout_top"),
        component_id=component_id,
        require_depth=False,
    )
    keepout_bottom = _normalize_feature(
        component_type=component_type,
        feature_name="keepout_bottom",
        explicit=mechanical.get("keepout_bottom"),
        derived=_derive_feature(component_type, mechanical, "keepout_bottom"),
        component_id=component_id,
        require_depth=True,
    )

    mounting = mechanical.get("mounting")
    if mounting is not None and not isinstance(mounting, dict):
        raise ValueError(f"Mounting data for component '{component_id}' must be a mapping")

    return ResolvedMechanical(
        cutout=cutout,
        keepout_top=keepout_top,
        keepout_bottom=keepout_bottom,
        mounting=deepcopy(mounting),
    )


def _normalize_feature(
    component_type: str,
    feature_name: str,
    explicit: Any,
    derived: dict[str, Any] | None,
    component_id: str,
    require_depth: bool,
) -> ShapePrimitive:
    feature_data = explicit if explicit is not None else derived
    if feature_data is None:
        raise ValueError(
            f"Missing mechanical defaults for component '{component_id}' ({component_type}) feature '{feature_name}'"
        )
    if not isinstance(feature_data, dict):
        raise ValueError(
            f"Mechanical feature '{feature_name}' for component '{component_id}' must be a mapping"
        )
    return _shape_from_mapping(
        feature_name=feature_name,
        feature_data=feature_data,
        component_id=component_id,
        require_depth=require_depth,
    )


def _shape_from_mapping(
    feature_name: str,
    feature_data: dict[str, Any],
    component_id: str,
    require_depth: bool,
) -> ShapePrimitive:
    shape = feature_data.get("shape")
    if not isinstance(shape, str):
        raise ValueError(
            f"Mechanical feature '{feature_name}' for component '{component_id}' is missing a valid 'shape'"
        )
    if shape not in SUPPORTED_SHAPES:
        raise ValueError(f"Unsupported {feature_name} shape: {shape}")

    if shape == "circle":
        diameter = _as_positive_number(feature_data.get("diameter"), feature_name, component_id, "diameter")
        depth = _optional_positive_number(feature_data.get("depth"), feature_name, component_id, "depth")
        if require_depth and depth is None:
            raise ValueError(
                f"Mechanical feature '{feature_name}' for component '{component_id}' requires 'depth'"
            )
        return ShapePrimitive(shape=shape, diameter=diameter, depth=depth)

    width = _as_positive_number(feature_data.get("width"), feature_name, component_id, "width")
    height = _as_positive_number(feature_data.get("height"), feature_name, component_id, "height")
    depth = _optional_positive_number(feature_data.get("depth"), feature_name, component_id, "depth")
    if require_depth and depth is None:
        raise ValueError(
            f"Mechanical feature '{feature_name}' for component '{component_id}' requires 'depth'"
        )
    return ShapePrimitive(shape=shape, width=width, height=height, depth=depth)


def _derive_feature(
    component_type: str,
    mechanical: dict[str, Any],
    feature_name: str,
) -> dict[str, Any] | None:
    panel = mechanical.get("panel")
    if not isinstance(panel, dict):
        return None

    if component_type == "encoder":
        return _derive_encoder_feature(panel, feature_name)
    if component_type == "button":
        return _derive_button_feature(panel, feature_name)
    if component_type == "display":
        return _derive_display_feature(panel, feature_name)
    return None


def _derive_encoder_feature(panel: dict[str, Any], feature_name: str) -> dict[str, Any] | None:
    if feature_name == "cutout":
        diameter = panel.get(
            "recommended_hole_diameter_with_tolerance_mm",
            panel.get("recommended_hole_diameter_mm"),
        )
        if diameter is None:
            return None
        return {"shape": "circle", "diameter": diameter}
    if feature_name == "keepout_top":
        diameter = panel.get("recommended_keepout_top_diameter_mm")
        if diameter is None:
            return None
        return {"shape": "circle", "diameter": diameter}
    if feature_name == "keepout_bottom":
        diameter = panel.get("recommended_keepout_bottom_diameter_mm")
        depth = panel.get("recommended_keepout_bottom_depth_mm")
        if diameter is None or depth is None:
            return None
        return {"shape": "circle", "diameter": diameter, "depth": depth}
    return None


def _derive_button_feature(panel: dict[str, Any], feature_name: str) -> dict[str, Any] | None:
    if feature_name == "cutout":
        opening = panel.get("recommended_cap_opening_mm")
        if not isinstance(opening, dict):
            return None
        return {
            "shape": "rect",
            "width": opening.get("width"),
            "height": opening.get("height"),
        }
    if feature_name == "keepout_top":
        keepout = panel.get("recommended_keepout_top_mm")
        if not isinstance(keepout, dict):
            return None
        return {
            "shape": "rect",
            "width": keepout.get("width"),
            "height": keepout.get("height"),
        }
    if feature_name == "keepout_bottom":
        keepout = panel.get("recommended_keepout_bottom_mm")
        if not isinstance(keepout, dict):
            return None
        return {
            "shape": "rect",
            "width": keepout.get("width"),
            "height": keepout.get("height"),
            "depth": keepout.get("depth"),
        }
    return None


def _derive_display_feature(panel: dict[str, Any], feature_name: str) -> dict[str, Any] | None:
    if feature_name == "cutout":
        window = panel.get("recommended_window_mm")
        if not isinstance(window, dict):
            return None
        return {
            "shape": "rect",
            "width": window.get("width"),
            "height": window.get("height"),
        }
    if feature_name == "keepout_top":
        keepout = panel.get("recommended_keepout_top_mm")
        if not isinstance(keepout, dict):
            return None
        return {
            "shape": "rect",
            "width": keepout.get("width"),
            "height": keepout.get("height"),
        }
    if feature_name == "keepout_bottom":
        keepout = panel.get("recommended_keepout_bottom_mm")
        if not isinstance(keepout, dict):
            return None
        return {
            "shape": "rect",
            "width": keepout.get("width"),
            "height": keepout.get("height"),
            "depth": keepout.get("depth"),
        }
    return None


def _as_positive_number(
    value: Any,
    feature_name: str,
    component_id: str,
    field_name: str,
) -> float:
    if not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(
            f"Mechanical feature '{feature_name}' for component '{component_id}' requires a positive '{field_name}'"
        )
    return float(value)


def _optional_positive_number(
    value: Any,
    feature_name: str,
    component_id: str,
    field_name: str,
) -> float | None:
    if value is None:
        return None
    return _as_positive_number(value, feature_name, component_id, field_name)

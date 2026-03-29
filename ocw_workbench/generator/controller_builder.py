from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import logging
from typing import Any

from ocw_workbench.freecad_api import shapes
from ocw_workbench.generator.component_resolver import ComponentResolver
from ocw_workbench.geometry.primitives import Cutout, ResolvedMechanical, ShapePrimitive, SurfacePrimitive
from ocw_workbench.services.fcstd_base_geometry_service import FCStdBaseGeometryService

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BodyBuildPlan:
    surface: SurfacePrimitive
    body_height: float
    cavity_surface: SurfacePrimitive | None
    cavity_offset: tuple[float, float, float] | None
    cavity_height: float | None


@dataclass(frozen=True)
class TopPlateBuildPlan:
    surface: SurfacePrimitive
    z_offset: float
    top_thickness: float
    tongue_surface: SurfacePrimitive | None
    tongue_offset: tuple[float, float, float] | None
    tongue_height: float | None


@dataclass(frozen=True)
class CutoutToolPlan:
    component_id: str
    x: float
    y: float
    rotation: float
    cutout: ShapePrimitive
    cut_height: float
    z_start: float


@dataclass(frozen=True)
class CutoutBooleanPlan:
    tools: list[CutoutToolPlan]
    diagnostics: list[str]


class ControllerBuilder:
    MIN_FEATURE_SIZE = 0.5
    FASTENER_PRESETS = {
        "m2_pan_head": {
            "nominal_diameter": 2.0,
            "clearance_diameter": 2.4,
            "head_diameter": 4.0,
            "head_height": 1.6,
        },
        "m3_pan_head": {
            "nominal_diameter": 3.0,
            "clearance_diameter": 3.2,
            "head_diameter": 5.8,
            "head_height": 2.2,
        },
    }

    def __init__(
        self,
        doc=None,
        component_resolver: ComponentResolver | None = None,
        fcstd_base_geometry_service: FCStdBaseGeometryService | None = None,
    ):
        self.doc = doc
        self.component_resolver = component_resolver or ComponentResolver()
        self.fcstd_base_geometry_service = fcstd_base_geometry_service or FCStdBaseGeometryService()

    def build_body(self, controller):
        plan = self.plan_body_build(controller)
        body_shape = self._build_body_shape(plan)
        return shapes.create_feature(self.doc, "ControllerBody", body_shape)

    def build_top_plate(self, controller):
        plan = self.plan_top_plate_build(controller)
        top_shape = self._build_top_plate_shape(plan, controller=controller)
        return shapes.create_feature(self.doc, "TopPlate", top_shape)

    def build_pcb(self, controller):
        pcb_shape = self._build_pcb_shape(controller)
        return shapes.create_feature(self.doc, "PCB", pcb_shape)

    def describe_pcb_reference(self, controller: Any) -> dict[str, Any]:
        surface = self._pcb_surface(controller)
        return {
            "surface": surface.to_dict(),
            "offset_x": self._pcb_surface_offset_x(controller, surface),
            "offset_y": self._pcb_surface_offset_y(controller, surface),
            "z": self._pcb_z(controller),
            "top_z": self._pcb_top_z(controller),
            "thickness": self._pcb_thickness(controller),
        }

    def describe_mounting_hardware(self, controller: Any) -> list[dict[str, Any]]:
        controller_data = self._controller_to_dict(controller)
        hardware: list[dict[str, Any]] = []
        for hole in controller_data.get("mounting_holes", []):
            if not isinstance(hole, dict):
                continue
            profile = self._mounting_profile(controller_data, hole)
            hole_id = str(hole.get("id") or "mount")
            hardware.append(
                {
                    "id": hole_id,
                    "x": float(hole.get("x", 0.0) or 0.0),
                    "y": float(hole.get("y", 0.0) or 0.0),
                    "hole_diameter": float(profile["hole_diameter"]),
                    "boss_outer_diameter": float(profile["boss_outer_diameter"]),
                    "boss_height": float(profile["boss_height"]),
                    "counterbore_diameter": float(profile["counterbore_diameter"]),
                    "counterbore_depth": float(profile["counterbore_depth"]),
                    "fastener_type": str(profile["fastener_type"]),
                    "screw_diameter": float(profile["screw_diameter"]),
                    "screw_head_diameter": float(profile["screw_head_diameter"]),
                    "screw_head_height": float(profile["screw_head_height"]),
                    "screw_length": float(profile["screw_length"]),
                }
            )
        return hardware

    def build_mounting_support_features(self, controller: Any) -> list[Any]:
        controller_data = self._controller_to_dict(controller)
        supports = []
        for hole in controller_data.get("mounting_holes", []):
            if not isinstance(hole, dict):
                continue
            boss_feature = self._build_mounting_boss_feature(hole, controller_data)
            if boss_feature is not None:
                supports.append(boss_feature)
            screw_feature = self._build_mounting_screw_feature(hole, controller_data)
            if screw_feature is not None:
                supports.append(screw_feature)
        return supports

    def build_component_feature(self, controller: Any, component: Any):
        component_data = self._component_to_dict(component)
        resolved = self.component_resolver.resolve(component_data)
        shape = self._build_component_shape(controller, component_data, resolved)
        component_id = str(component_data.get("id") or "component")
        return shapes.create_feature(self.doc, f"OCW_Component_{component_id}", shape)

    def plan_body_build(self, controller: Any) -> BodyBuildPlan:
        controller_data = self._controller_to_dict(controller)
        surface = self.resolve_surface(controller)
        body_height = self._body_height(controller)
        cavity_surface = None
        cavity_offset = None
        cavity_height = None
        if self._supports_shell_geometry(surface):
            wall = max(float(controller_data.get("wall_thickness", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
            bottom = max(float(controller_data.get("bottom_thickness", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
            cavity_height = body_height - bottom
            if cavity_height > self.MIN_FEATURE_SIZE:
                cavity_surface = self._offset_surface(surface, inset=wall)
                if cavity_surface is not None:
                    cavity_offset = (wall, wall, bottom)
        return BodyBuildPlan(
            surface=surface,
            body_height=body_height,
            cavity_surface=cavity_surface,
            cavity_offset=cavity_offset,
            cavity_height=cavity_height if cavity_surface is not None else None,
        )

    def plan_top_plate_build(self, controller: Any) -> TopPlateBuildPlan:
        controller_data = self._controller_to_dict(controller)
        surface = self.resolve_surface(controller)
        z_offset = self._body_height(controller)
        tongue_surface = None
        tongue_offset = None
        tongue_height = None
        if self._supports_shell_geometry(surface):
            wall = max(float(controller_data.get("wall_thickness", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
            clearance = max(float(controller_data.get("inner_clearance", 0.0) or 0.0), 0.0)
            inset = max(float(controller_data.get("lid_inset", 0.0) or 0.0), 0.0)
            bottom = max(float(controller_data.get("bottom_thickness", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
            body_height = self._body_height(controller)
            tongue_height = min(inset, max(body_height - bottom, 0.0))
            if tongue_height > self.MIN_FEATURE_SIZE:
                tongue_surface = self._offset_surface(surface, inset=wall + clearance)
                if tongue_surface is not None:
                    tongue_offset = (
                        wall + clearance,
                        wall + clearance,
                        max(z_offset - tongue_height, bottom),
                    )
        return TopPlateBuildPlan(
            surface=surface,
            z_offset=z_offset,
            top_thickness=float(controller_data.get("top_thickness", 0.0) or 0.0),
            tongue_surface=tongue_surface,
            tongue_offset=tongue_offset,
            tongue_height=tongue_height if tongue_surface is not None else None,
        )

    def resolve_surface(self, controller: Any) -> SurfacePrimitive:
        controller_data = self._controller_to_dict(controller)
        width = float(controller_data["width"])
        depth = float(controller_data["depth"])
        surface_data = deepcopy(controller_data.get("surface"))

        if surface_data is None:
            return SurfacePrimitive(shape="rectangle", width=width, height=depth)
        if not isinstance(surface_data, dict):
            raise ValueError("Controller surface must be a mapping")

        shape = surface_data.get("shape", "rectangle")
        if shape == "rectangle":
            return SurfacePrimitive(
                shape="rectangle",
                width=float(surface_data.get("width", width)),
                height=float(surface_data.get("height", depth)),
            )
        if shape == "rounded_rect":
            corner_radius = float(surface_data.get("corner_radius", 0.0))
            return SurfacePrimitive(
                shape="rounded_rect",
                width=float(surface_data.get("width", width)),
                height=float(surface_data.get("height", depth)),
                corner_radius=corner_radius,
            )
        if shape == "polygon":
            points = surface_data.get("points")
            if not isinstance(points, list) or len(points) < 3:
                raise ValueError("Polygon controller surface requires at least three points")
            normalized_points = []
            for point in points:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    raise ValueError("Polygon controller surface points must be [x, y] pairs")
                normalized_points.append((float(point[0]), float(point[1])))
            return SurfacePrimitive(
                shape="polygon",
                width=float(surface_data.get("width", width)),
                height=float(surface_data.get("height", depth)),
                points=tuple(normalized_points),
            )
        raise ValueError(f"Unsupported controller surface shape: {shape}")

    def resolve_components(self, components: list[Any]) -> list[dict[str, Any]]:
        return self.component_resolver.resolve_many(components)

    def build_keepouts(self, components: list[Any]) -> list[dict[str, Any]]:
        keepouts: list[dict[str, Any]] = []
        for component in self.resolve_components(components):
            mechanical = component["resolved_mechanical"]
            keepouts.append(
                self._placed_feature(
                    component["id"],
                    component["x"],
                    component["y"],
                    float(component.get("rotation", 0.0) or 0.0),
                    mechanical.keepout_top,
                    "top",
                )
            )
            keepouts.append(
                self._placed_feature(
                    component["id"],
                    component["x"],
                    component["y"],
                    float(component.get("rotation", 0.0) or 0.0),
                    mechanical.keepout_bottom,
                    "bottom",
                )
            )
        return keepouts

    def apply_cutouts(self, base_obj, components):
        plan = self.plan_cutout_boolean(base_obj, components)
        return self.apply_cutout_plan(base_obj, plan)

    def apply_cutout_plan(self, base_obj, plan: CutoutBooleanPlan):
        for diagnostic in plan.diagnostics:
            LOGGER.warning(diagnostic)
        result_shape = base_obj.Shape.copy() if hasattr(base_obj.Shape, "copy") else base_obj.Shape
        tool_shapes = [self._build_cutout_tool_shape(tool) for tool in plan.tools]
        base_obj.Shape = shapes.cut_shape(result_shape, tool_shapes)
        return base_obj

    def plan_cutout_boolean(self, base_obj: Any, components: list[Any]) -> CutoutBooleanPlan:
        resolved_components = self.resolve_components(components)
        cutout_primitives = self.build_cutout_primitives(components)
        diagnostics = self._cutout_diagnostics(cutout_primitives)
        z_start = base_obj.Shape.BoundBox.ZMin
        cut_height = base_obj.Shape.BoundBox.ZLength
        tools = [
            CutoutToolPlan(
                component_id=str(component["id"]),
                x=float(component["x"]),
                y=float(component["y"]),
                rotation=float(component.get("rotation", 0.0) or 0.0),
                cutout=component["resolved_mechanical"].cutout,
                cut_height=float(cut_height),
                z_start=float(z_start),
            )
            for component in resolved_components
        ]
        return CutoutBooleanPlan(tools=tools, diagnostics=diagnostics)

    def build_cutout_primitives(self, components: list[Any]) -> list[dict[str, Any]]:
        cutouts: list[dict[str, Any]] = []
        for component in self.resolve_components(components):
            placed = Cutout(
                x=component["x"],
                y=component["y"],
                shape=component["resolved_mechanical"].cutout,
            )
            cutouts.append(
                {
                    "component_id": component["id"],
                    "feature": "cutout",
                    "rotation": float(component.get("rotation", 0.0) or 0.0),
                    **placed.to_dict(),
                }
            )
        return cutouts

    def _build_body_shape(self, plan: BodyBuildPlan):
        outer_shape = shapes.make_surface_prism_shape(plan.surface, plan.body_height)
        if plan.cavity_surface is None or plan.cavity_offset is None or plan.cavity_height is None:
            return outer_shape
        cavity_shape = shapes.translate_shape(
            shapes.make_surface_prism_shape(plan.cavity_surface, plan.cavity_height),
            x=plan.cavity_offset[0],
            y=plan.cavity_offset[1],
            z=plan.cavity_offset[2],
        )
        return outer_shape.cut(cavity_shape)

    def _build_top_plate_shape(self, plan: TopPlateBuildPlan, controller: Any):
        custom_base = self._custom_fcstd_base_config(controller)
        if custom_base is not None:
            return self.fcstd_base_geometry_service.build_shape_from_config(
                custom_base,
                extrude_height=float(plan.top_thickness),
                z_offset=float(plan.z_offset),
            )
        top_shape = shapes.translate_shape(
            shapes.make_surface_prism_shape(plan.surface, plan.top_thickness),
            z=plan.z_offset,
        )
        if plan.tongue_surface is None or plan.tongue_offset is None or plan.tongue_height is None:
            return top_shape
        lid_tongue = shapes.translate_shape(
            shapes.make_surface_prism_shape(plan.tongue_surface, plan.tongue_height),
            x=plan.tongue_offset[0],
            y=plan.tongue_offset[1],
            z=plan.tongue_offset[2],
        )
        fused = shapes.fuse_shapes([top_shape, lid_tongue])
        return fused if fused is not None else top_shape

    def _build_cutout_tool_shape(self, plan: CutoutToolPlan):
        return self._create_cutout_shape(
            x=plan.x,
            y=plan.y,
            rotation=plan.rotation,
            cutout=plan.cutout,
            cut_height=plan.cut_height,
            z_start=plan.z_start,
        )

    def _create_cutout_shape(
        self,
        x: float,
        y: float,
        rotation: float,
        cutout: ShapePrimitive,
        cut_height: float,
        z_start: float,
    ):
        if cutout.shape == "circle":
            return shapes.translate_shape(
                shapes.make_cylinder_shape(
                    radius=cutout.diameter / 2.0,
                    height=cut_height,
                ),
                x=x,
                y=y,
                z=z_start,
            )
        if cutout.shape in {"rect", "slot"}:
            shape_factory = shapes.make_rect_prism_shape if cutout.shape == "rect" else shapes.make_slot_prism_shape
            prism_shape = shapes.translate_shape(
                shape_factory(
                    width=cutout.width,
                    depth=cutout.height,
                    height=cut_height,
                ),
                x=x - (cutout.width / 2.0),
                y=y - (cutout.height / 2.0),
                z=z_start,
            )
            if float(rotation or 0.0) != 0.0:
                LOGGER.info(
                    "Applying %s degree rotation to cutout at (%.2f, %.2f).",
                    float(rotation),
                    float(x),
                    float(y),
                )
                return shapes.rotate_shape(prism_shape, rotation, center=(x, y, z_start))
            return prism_shape
        LOGGER.warning("Unsupported cutout shape '%s'; rotation fallback not applied.", cutout.shape)
        raise ValueError(f"Unsupported cutout shape: {cutout.shape}")

    def _cutout_diagnostics(self, cutouts: list[dict[str, Any]]) -> list[str]:
        from ocw_workbench.constraints.rules import minimum_gap

        diagnostics: list[str] = []
        areas = [self._cutout_area(cutout) for cutout in cutouts]
        for area in areas:
            if area.shape == "circle" and (area.diameter is None or area.diameter <= self.MIN_FEATURE_SIZE):
                diagnostics.append(
                    f"Cutout for component '{area.component_id}' has invalid diameter {area.diameter!r} mm."
                )
            if area.shape != "circle" and (
                area.width is None
                or area.height is None
                or area.width <= self.MIN_FEATURE_SIZE
                or area.height <= self.MIN_FEATURE_SIZE
            ):
                diagnostics.append(
                    f"Cutout for component '{area.component_id}' has invalid size "
                    f"{area.width!r} x {area.height!r} mm."
                )
        for index, first in enumerate(areas):
            for second in areas[index + 1:]:
                gap = minimum_gap(first, second)
                if gap < 0.0:
                    diagnostics.append(
                        f"Cutouts for components '{first.component_id}' and '{second.component_id}' overlap by "
                        f"{abs(gap):.2f} mm; using a fused composite cut."
                    )
        return diagnostics

    def _cutout_area(self, cutout: dict[str, Any]) -> ComponentArea:
        from ocw_workbench.constraints.models import ComponentArea

        return ComponentArea(
            component_id=str(cutout["component_id"]),
            component_type="cutout",
            x=float(cutout["x"]),
            y=float(cutout["y"]),
            shape=str(cutout["shape"]),
            rotation=float(cutout.get("rotation", 0.0) or 0.0),
            width=float(cutout["width"]) if cutout.get("width") is not None else None,
            height=float(cutout["height"]) if cutout.get("height") is not None else None,
            diameter=float(cutout["diameter"]) if cutout.get("diameter") is not None else None,
            depth=float(cutout["depth"]) if cutout.get("depth") is not None else None,
        )

    def _placed_feature(
        self,
        component_id: str,
        x: float,
        y: float,
        rotation: float,
        shape: ResolvedMechanical | ShapePrimitive,
        layer: str,
    ) -> dict[str, Any]:
        if isinstance(shape, ResolvedMechanical):
            raise TypeError("Expected ShapePrimitive for placed feature generation")
        return {
            "component_id": component_id,
            "feature": f"keepout_{layer}",
            "x": x,
            "y": y,
            "rotation": float(rotation or 0.0),
            **shape.to_dict(),
        }

    def _controller_to_dict(self, controller: Any) -> dict[str, Any]:
        if isinstance(controller, dict):
            return deepcopy(controller)
        if hasattr(controller, "__dict__"):
            return deepcopy(vars(controller))
        raise TypeError(f"Unsupported controller representation: {type(controller)!r}")

    def _component_to_dict(self, component: Any) -> dict[str, Any]:
        if isinstance(component, dict):
            return deepcopy(component)
        if hasattr(component, "__dict__"):
            return deepcopy(vars(component))
        raise TypeError(f"Unsupported component representation: {type(component)!r}")

    def _supports_shell_geometry(self, surface: SurfacePrimitive) -> bool:
        return surface.shape in {"rectangle", "rounded_rect"}

    def _build_component_shape(self, controller: Any, component: dict[str, Any], resolved: dict[str, Any]):
        controller_data = self._controller_to_dict(controller)
        visual_height = self._component_visual_height(component)
        top_z = self._body_height(controller) + float(controller_data.get("top_thickness", 0.0) or 0.0)
        pcb_top_z = self._pcb_top_z(controller)
        top_keepout = resolved["resolved_mechanical"].keepout_top
        visual_mechanical = self._component_visual_mechanical(component)
        component_type = str(component.get("type") or "component")
        x = float(component["x"])
        y = float(component["y"])
        rotation = float(component.get("rotation", 0.0) or 0.0)
        mount_core = self._build_component_mount_core(
            x=x,
            y=y,
            z=pcb_top_z,
            top_z=top_z,
            rotation=rotation,
            resolved=resolved,
        )
        if component_type == "button":
            top_shape = self._build_button_component_shape(
                x=x,
                y=y,
                z=top_z,
                rotation=rotation,
                visual_height=visual_height,
                top_keepout=top_keepout,
                visual_mechanical=visual_mechanical,
                component=component,
            )
            return self._merge_component_shapes(mount_core, top_shape, rotation=rotation, x=x, y=y, z=pcb_top_z)
        if component_type == "encoder":
            top_shape = self._build_encoder_component_shape(
                x=x,
                y=y,
                z=top_z,
                rotation=rotation,
                visual_height=visual_height,
                top_keepout=top_keepout,
                visual_mechanical=visual_mechanical,
            )
            return self._merge_component_shapes(mount_core, top_shape, rotation=rotation, x=x, y=y, z=pcb_top_z)
        if component_type == "display":
            top_shape = self._build_display_component_shape(
                x=x,
                y=y,
                z=top_z,
                rotation=rotation,
                visual_height=visual_height,
                top_keepout=top_keepout,
                visual_mechanical=visual_mechanical,
            )
            return self._merge_component_shapes(mount_core, top_shape, rotation=rotation, x=x, y=y, z=pcb_top_z)
        if component_type == "fader":
            top_shape = self._build_fader_component_shape(
                x=x,
                y=y,
                z=top_z,
                rotation=rotation,
                visual_height=visual_height,
                top_keepout=top_keepout,
                visual_mechanical=visual_mechanical,
                component=component,
            )
            return self._merge_component_shapes(mount_core, top_shape, rotation=rotation, x=x, y=y, z=pcb_top_z)
        if component_type == "pad":
            top_shape = self._build_pad_component_shape(
                x=x,
                y=y,
                z=top_z,
                rotation=rotation,
                visual_height=visual_height,
                top_keepout=top_keepout,
                visual_mechanical=visual_mechanical,
            )
            return self._merge_component_shapes(mount_core, top_shape, rotation=rotation, x=x, y=y, z=pcb_top_z)
        if component_type == "rgb_button":
            top_shape = self._build_rgb_button_component_shape(
                x=x,
                y=y,
                z=top_z,
                rotation=rotation,
                visual_height=visual_height,
                top_keepout=top_keepout,
                visual_mechanical=visual_mechanical,
            )
            return self._merge_component_shapes(mount_core, top_shape, rotation=rotation, x=x, y=y, z=pcb_top_z)
        top_shape = self._build_generic_component_shape(
            x=x,
            y=y,
            z=top_z,
            rotation=rotation,
            visual_height=visual_height,
            top_keepout=top_keepout,
        )
        return self._merge_component_shapes(mount_core, top_shape, rotation=rotation, x=x, y=y, z=pcb_top_z)

    def _build_generic_component_shape(
        self,
        *,
        x: float,
        y: float,
        z: float,
        rotation: float,
        visual_height: float,
        top_keepout: ShapePrimitive,
    ):
        if top_keepout.shape == "circle":
            return shapes.translate_shape(
                shapes.make_cylinder_shape(radius=float(top_keepout.diameter or 0.0) / 2.0, height=visual_height),
                x=x,
                y=y,
                z=z,
            )
        if top_keepout.shape in {"rect", "slot"}:
            shape_factory = shapes.make_rect_prism_shape if top_keepout.shape == "rect" else shapes.make_slot_prism_shape
            placed_shape = shapes.translate_shape(
                shape_factory(
                    width=float(top_keepout.width or 0.0),
                    depth=float(top_keepout.height or 0.0),
                    height=visual_height,
                ),
                x=x - (float(top_keepout.width or 0.0) / 2.0),
                y=y - (float(top_keepout.height or 0.0) / 2.0),
                z=z,
            )
            if rotation != 0.0:
                placed_shape = shapes.rotate_shape(placed_shape, rotation, center=(x, y, z))
            return placed_shape
        raise ValueError(f"Unsupported component keepout shape: {top_keepout.shape}")

    def _build_button_component_shape(
        self,
        *,
        x: float,
        y: float,
        z: float,
        rotation: float,
        visual_height: float,
        top_keepout: ShapePrimitive,
        visual_mechanical: dict[str, Any],
        component: dict[str, Any],
    ):
        body_size = self._mapping(visual_mechanical.get("body_size_mm"))
        panel = self._mapping(visual_mechanical.get("panel"))
        cap_opening = self._mapping(panel.get("recommended_cap_opening_mm"))
        properties = self._mapping(component.get("properties"))
        body_width = self._coalesce_number(body_size.get("width"), top_keepout.width, top_keepout.diameter, default=12.0)
        body_depth = self._coalesce_number(body_size.get("depth"), top_keepout.height, top_keepout.diameter, default=12.0)
        body_height = self._clamp_positive(body_size.get("height"), default=visual_height)
        cap_width = self._clamp_positive(
            properties.get("cap_width"),
            cap_opening.get("width"),
            body_width * 0.7,
            default=max(body_width * 0.7, 4.0),
        )
        cap_depth = self._clamp_positive(
            properties.get("cap_depth"),
            cap_opening.get("height"),
            body_depth * 0.7,
            default=max(body_depth * 0.7, 4.0),
        )
        cap_height = self._clamp_positive(properties.get("cap_height"), body_height * 0.22, default=1.6)
        body = self._make_box_centered(body_width, body_depth, body_height, x=x, y=y, z=z)
        cap = self._make_box_centered(cap_width, cap_depth, cap_height, x=x, y=y, z=z + body_height)
        return self._finalize_component_shape([body, cap], rotation=rotation, x=x, y=y, z=z)

    def _build_pad_component_shape(
        self,
        *,
        x: float,
        y: float,
        z: float,
        rotation: float,
        visual_height: float,
        top_keepout: ShapePrimitive,
        visual_mechanical: dict[str, Any],
    ):
        body_size = self._mapping(visual_mechanical.get("body_size_mm"))
        diffuser = self._mapping(visual_mechanical.get("diffuser_light_area_mm"))
        body_width = self._coalesce_number(body_size.get("width"), top_keepout.width, top_keepout.diameter, default=18.0)
        body_depth = self._coalesce_number(body_size.get("depth"), top_keepout.height, top_keepout.diameter, default=18.0)
        body_height = self._clamp_positive(body_size.get("height"), default=visual_height)
        pad_width = self._clamp_positive(diffuser.get("width"), body_width * 0.7, default=max(body_width * 0.7, 6.0))
        pad_depth = self._clamp_positive(diffuser.get("height"), body_depth * 0.7, default=max(body_depth * 0.7, 6.0))
        pad_height = self._clamp_positive(diffuser.get("thickness"), body_height * 0.18, default=1.4)
        body = self._make_box_centered(body_width, body_depth, body_height, x=x, y=y, z=z)
        pad = self._make_box_centered(pad_width, pad_depth, pad_height, x=x, y=y, z=z + body_height)
        return self._finalize_component_shape([body, pad], rotation=rotation, x=x, y=y, z=z)

    def _build_encoder_component_shape(
        self,
        *,
        x: float,
        y: float,
        z: float,
        rotation: float,
        visual_height: float,
        top_keepout: ShapePrimitive,
        visual_mechanical: dict[str, Any],
    ):
        body_size = self._mapping(visual_mechanical.get("body_size_mm"))
        shaft = self._mapping(visual_mechanical.get("shaft"))
        body_width = self._coalesce_number(body_size.get("width"), top_keepout.diameter, top_keepout.width, default=14.0)
        body_depth = self._coalesce_number(body_size.get("depth"), top_keepout.diameter, top_keepout.height, default=14.0)
        body_height = self._clamp_positive(body_size.get("height"), default=visual_height)
        shaft_diameter = self._clamp_positive(
            shaft.get("diameter_mm"),
            body_width * 0.4,
            body_depth * 0.4,
            default=max(min(body_width, body_depth) * 0.4, 3.0),
        )
        shaft_height = self._clamp_positive(shaft.get("length_mm"), body_height * 0.65, default=max(body_height * 0.65, 4.0))
        body = self._make_box_centered(body_width, body_depth, body_height, x=x, y=y, z=z)
        shaft_shape = self._make_cylinder_centered(shaft_diameter, shaft_height, x=x, y=y, z=z + body_height)
        return self._finalize_component_shape([body, shaft_shape], rotation=rotation, x=x, y=y, z=z)

    def _build_display_component_shape(
        self,
        *,
        x: float,
        y: float,
        z: float,
        rotation: float,
        visual_height: float,
        top_keepout: ShapePrimitive,
        visual_mechanical: dict[str, Any],
    ):
        breakout = self._mapping(visual_mechanical.get("breakout_size_mm"))
        screen_window = self._mapping(visual_mechanical.get("screen_window_mm"))
        body_width = self._coalesce_number(breakout.get("width"), top_keepout.width, default=30.0)
        body_depth = self._coalesce_number(breakout.get("depth"), top_keepout.height, default=15.0)
        body_height = self._clamp_positive(breakout.get("thickness"), default=visual_height)
        screen_width = self._clamp_positive(screen_window.get("width"), body_width * 0.72, default=max(body_width * 0.72, 8.0))
        screen_depth = self._clamp_positive(screen_window.get("height"), body_depth * 0.5, default=max(body_depth * 0.5, 4.0))
        bezel_height = self._clamp_positive(screen_window.get("thickness"), body_height * 0.18, default=1.2)
        board = self._make_box_centered(body_width, body_depth, body_height, x=x, y=y, z=z)
        screen = self._make_box_centered(screen_width, screen_depth, bezel_height, x=x, y=y, z=z + body_height)
        return self._finalize_component_shape([board, screen], rotation=rotation, x=x, y=y, z=z)

    def _build_fader_component_shape(
        self,
        *,
        x: float,
        y: float,
        z: float,
        rotation: float,
        visual_height: float,
        top_keepout: ShapePrimitive,
        visual_mechanical: dict[str, Any],
        component: dict[str, Any],
    ):
        body_size = self._mapping(visual_mechanical.get("body_size_mm"))
        slot_cutout = self._mapping(visual_mechanical.get("slot_cutout"))
        properties = self._mapping(component.get("properties"))
        body_width = self._coalesce_number(body_size.get("width"), top_keepout.width, default=65.0)
        body_depth = self._coalesce_number(body_size.get("depth"), top_keepout.height, default=12.0)
        body_height = self._clamp_positive(body_size.get("height"), default=visual_height)
        cap_width = self._clamp_positive(
            properties.get("cap_width"),
            slot_cutout.get("width_mm"),
            body_depth * 0.55,
            default=max(body_depth * 0.55, 4.0),
        )
        cap_depth = self._clamp_positive(properties.get("cap_depth"), body_depth * 0.7, default=max(body_depth * 0.7, 4.0))
        cap_height = self._clamp_positive(properties.get("cap_height"), body_height * 0.4, default=max(body_height * 0.4, 3.0))
        cap_length = self._clamp_positive(properties.get("cap_length"), body_width * 0.16, default=max(body_width * 0.16, 8.0))
        rail_height = self._clamp_positive(slot_cutout.get("width_mm"), body_height * 0.12, default=0.8)
        rail = self._make_box_centered(body_width * 0.82, rail_height, rail_height, x=x, y=y, z=z + body_height)
        body = self._make_box_centered(body_width, body_depth, body_height, x=x, y=y, z=z)
        cap = self._make_box_centered(cap_length, cap_depth, cap_height, x=x, y=y, z=z + body_height + rail_height)
        return self._finalize_component_shape([body, rail, cap], rotation=rotation, x=x, y=y, z=z)

    def _build_rgb_button_component_shape(
        self,
        *,
        x: float,
        y: float,
        z: float,
        rotation: float,
        visual_height: float,
        top_keepout: ShapePrimitive,
        visual_mechanical: dict[str, Any],
    ):
        body_size = self._mapping(visual_mechanical.get("body_size_mm"))
        diffuser_diameter = self._clamp_positive(
            visual_mechanical.get("diffuser_light_area_diameter_mm"),
            body_size.get("width"),
            top_keepout.diameter * 0.65 if top_keepout.diameter is not None else None,
            default=8.0,
        )
        body_diameter = self._coalesce_number(body_size.get("width"), top_keepout.diameter, default=14.0)
        body_height = self._clamp_positive(body_size.get("height"), default=visual_height)
        diffuser_height = self._clamp_positive(body_height * 0.2, default=1.4)
        body = self._make_cylinder_centered(body_diameter, body_height, x=x, y=y, z=z)
        diffuser = self._make_cylinder_centered(diffuser_diameter, diffuser_height, x=x, y=y, z=z + body_height)
        return self._finalize_component_shape([body, diffuser], rotation=rotation, x=x, y=y, z=z)

    def _component_visual_mechanical(self, component: dict[str, Any]) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        library_ref = component.get("library_ref")
        if isinstance(library_ref, str) and library_ref:
            library_component = self.component_resolver.mechanical_resolver.library_service.get(library_ref)
            mechanical = library_component.get("mechanical", {})
            if isinstance(mechanical, dict):
                merged = deepcopy(mechanical)
        instance_mechanical = component.get("mechanical", {})
        if isinstance(instance_mechanical, dict):
            merged = self._deep_merge(merged, instance_mechanical)
        return merged

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(base)
        for key, value in override.items():
            if isinstance(result.get(key), dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result

    def _make_box_centered(self, width: float, depth: float, height: float, *, x: float, y: float, z: float):
        return shapes.translate_shape(
            shapes.make_box_shape(width, depth, height),
            x=x - (width / 2.0),
            y=y - (depth / 2.0),
            z=z,
        )

    def _make_cylinder_centered(self, diameter: float, height: float, *, x: float, y: float, z: float):
        radius = diameter / 2.0
        return shapes.translate_shape(
            shapes.make_cylinder_shape(radius, height),
            x=x - radius,
            y=y - radius,
            z=z,
        )

    def _finalize_component_shape(self, parts: list[Any], *, rotation: float, x: float, y: float, z: float):
        fused = shapes.fuse_shapes(parts)
        if fused is None:
            raise ValueError("Failed to build component shape")
        if rotation != 0.0:
            return shapes.rotate_shape(fused, rotation, center=(x, y, z))
        return fused

    def _mapping(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _coalesce_number(self, *values: Any, default: float) -> float:
        for value in values:
            if isinstance(value, (int, float)) and float(value) > 0.0:
                return float(value)
        return float(default)

    def _clamp_positive(self, *values: Any, default: float) -> float:
        for value in values:
            if isinstance(value, (int, float)) and float(value) > self.MIN_FEATURE_SIZE:
                return float(value)
        return max(float(default), self.MIN_FEATURE_SIZE)

    def _component_visual_height(self, component: dict[str, Any]) -> float:
        library_ref = component.get("library_ref")
        height = None
        if isinstance(library_ref, str) and library_ref:
            library_component = self.component_resolver.mechanical_resolver.library_service.get(library_ref)
            mechanical = library_component.get("mechanical", {})
            if isinstance(mechanical, dict):
                body_size = mechanical.get("body_size_mm", {})
                if isinstance(body_size, dict):
                    height = body_size.get("height")
        if height is None:
            mechanical = component.get("mechanical", {})
            if isinstance(mechanical, dict):
                body_size = mechanical.get("body_size_mm", {})
                if isinstance(body_size, dict):
                    height = body_size.get("height")
        return max(float(height or 8.0), self.MIN_FEATURE_SIZE)

    def _build_pcb_shape(self, controller: Any):
        surface = self._pcb_surface(controller)
        thickness = self._pcb_thickness(controller)
        z = self._pcb_z(controller)
        return shapes.translate_shape(
            shapes.make_surface_prism_shape(surface, thickness),
            x=self._pcb_surface_offset_x(controller, surface),
            y=self._pcb_surface_offset_y(controller, surface),
            z=z,
        )

    def _build_mounting_boss_feature(self, hole: dict[str, Any], controller_data: dict[str, Any]) -> Any | None:
        profile = self._mounting_profile(controller_data, hole)
        diameter = float(profile["hole_diameter"])
        x = float(hole.get("x", 0.0) or 0.0)
        y = float(hole.get("y", 0.0) or 0.0)
        if diameter <= 0.0:
            return None
        outer_diameter = float(profile["boss_outer_diameter"])
        boss_height = float(profile["boss_height"])
        if boss_height <= self.MIN_FEATURE_SIZE:
            return None
        outer = shapes.translate_shape(
            shapes.make_cylinder_shape(outer_diameter / 2.0, boss_height),
            x=x - (outer_diameter / 2.0),
            y=y - (outer_diameter / 2.0),
            z=0.0,
        )
        inner = shapes.translate_shape(
            shapes.make_cylinder_shape(max(diameter / 2.0, self.MIN_FEATURE_SIZE / 2.0), boss_height),
            x=x - (diameter / 2.0),
            y=y - (diameter / 2.0),
            z=0.0,
        )
        shape = outer.cut(inner)
        counterbore_depth = float(profile["counterbore_depth"])
        counterbore_diameter = float(profile["counterbore_diameter"])
        if (
            counterbore_depth > self.MIN_FEATURE_SIZE
            and counterbore_diameter > diameter
            and counterbore_diameter < outer_diameter
        ):
            recess_height = min(counterbore_depth, boss_height)
            recess = shapes.translate_shape(
                shapes.make_cylinder_shape(counterbore_diameter / 2.0, recess_height),
                x=x - (counterbore_diameter / 2.0),
                y=y - (counterbore_diameter / 2.0),
                z=boss_height - recess_height,
            )
            shape = shape.cut(recess)
        hole_id = str(hole.get("id") or "mount")
        return shapes.create_feature(self.doc, f"OCW_Boss_{hole_id}", shape)

    def _build_mounting_screw_feature(self, hole: dict[str, Any], controller_data: dict[str, Any]) -> Any | None:
        profile = self._mounting_profile(controller_data, hole)
        screw_diameter = float(profile["screw_diameter"])
        screw_head_diameter = float(profile["screw_head_diameter"])
        screw_head_height = float(profile["screw_head_height"])
        screw_length = float(profile["screw_length"])
        if screw_diameter <= 0.0 or screw_length <= self.MIN_FEATURE_SIZE:
            return None
        x = float(hole.get("x", 0.0) or 0.0)
        y = float(hole.get("y", 0.0) or 0.0)
        shaft = shapes.translate_shape(
            shapes.make_cylinder_shape(screw_diameter / 2.0, screw_length),
            x=x - (screw_diameter / 2.0),
            y=y - (screw_diameter / 2.0),
            z=0.0,
        )
        head = shapes.translate_shape(
            shapes.make_cylinder_shape(screw_head_diameter / 2.0, screw_head_height),
            x=x - (screw_head_diameter / 2.0),
            y=y - (screw_head_diameter / 2.0),
            z=max(self._pcb_top_z(controller_data), self.MIN_FEATURE_SIZE),
        )
        shape = shapes.fuse_shapes([shaft, head])
        hole_id = str(hole.get("id") or "mount")
        return shapes.create_feature(self.doc, f"OCW_Screw_{hole_id}", shape)

    def _build_component_mount_core(
        self,
        *,
        x: float,
        y: float,
        z: float,
        top_z: float,
        rotation: float,
        resolved: dict[str, Any],
    ):
        mount_height = max(top_z - z, 0.0)
        if mount_height <= self.MIN_FEATURE_SIZE:
            return None
        cutout = resolved["resolved_mechanical"].cutout
        if cutout.shape == "circle":
            diameter = float(cutout.diameter or 0.0)
            if diameter <= 0.0:
                return None
            return shapes.translate_shape(
                shapes.make_cylinder_shape(radius=diameter / 2.0, height=mount_height),
                x=x - (diameter / 2.0),
                y=y - (diameter / 2.0),
                z=z,
            )
        if cutout.shape in {"rect", "slot"}:
            width = float(cutout.width or 0.0)
            height = float(cutout.height or 0.0)
            if width <= 0.0 or height <= 0.0:
                return None
            shape_factory = shapes.make_rect_prism_shape if cutout.shape == "rect" else shapes.make_slot_prism_shape
            mount_shape = shapes.translate_shape(
                shape_factory(width=width, depth=height, height=mount_height),
                x=x - (width / 2.0),
                y=y - (height / 2.0),
                z=z,
            )
            if rotation != 0.0:
                return shapes.rotate_shape(mount_shape, rotation, center=(x, y, z))
            return mount_shape
        return None

    def _merge_component_shapes(self, mount_core: Any | None, top_shape: Any, *, rotation: float, x: float, y: float, z: float):
        fused = shapes.fuse_shapes([mount_core, top_shape])
        if fused is None:
            raise ValueError("Failed to fuse component shape")
        return fused

    def _pcb_surface(self, controller: Any) -> SurfacePrimitive:
        controller_data = self._controller_to_dict(controller)
        surface = self.resolve_surface(controller)
        inset = self._pcb_inset(controller_data)
        if self._supports_shell_geometry(surface):
            inset_surface = self._offset_surface(surface, inset=inset)
            if inset_surface is not None:
                return inset_surface
        width = max(float(controller_data.get("width", surface.width)) - (2.0 * inset), self.MIN_FEATURE_SIZE)
        depth = max(float(controller_data.get("depth", surface.height)) - (2.0 * inset), self.MIN_FEATURE_SIZE)
        return SurfacePrimitive(shape="rectangle", width=width, height=depth)

    def _pcb_surface_offset_x(self, controller: Any, pcb_surface: SurfacePrimitive) -> float:
        surface = self.resolve_surface(controller)
        return max((float(surface.width) - float(pcb_surface.width)) / 2.0, 0.0)

    def _pcb_surface_offset_y(self, controller: Any, pcb_surface: SurfacePrimitive) -> float:
        surface = self.resolve_surface(controller)
        return max((float(surface.height) - float(pcb_surface.height)) / 2.0, 0.0)

    def _pcb_inset(self, controller: Any) -> float:
        controller_data = self._controller_to_dict(controller)
        explicit = float(controller_data.get("pcb_inset", 0.0) or 0.0)
        minimum = float(controller_data.get("wall_thickness", 0.0) or 0.0) + float(controller_data.get("inner_clearance", 0.0) or 0.0) + 1.0
        return max(explicit, minimum, self.MIN_FEATURE_SIZE)

    def _pcb_thickness(self, controller: Any) -> float:
        controller_data = self._controller_to_dict(controller)
        return max(float(controller_data.get("pcb_thickness", 1.6) or 1.6), self.MIN_FEATURE_SIZE)

    def _pcb_z(self, controller: Any) -> float:
        controller_data = self._controller_to_dict(controller)
        bottom = max(float(controller_data.get("bottom_thickness", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
        standoff = max(float(controller_data.get("pcb_standoff_height", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
        return bottom + standoff

    def _pcb_top_z(self, controller: Any) -> float:
        return self._pcb_z(controller) + self._pcb_thickness(controller)

    def _mounting_profile(self, controller_data: dict[str, Any], hole: dict[str, Any]) -> dict[str, float | str]:
        mounting_defaults = self._mapping(controller_data.get("mounting"))
        fastener_type = str(hole.get("fastener_type") or mounting_defaults.get("fastener_type") or self._default_fastener_type(hole))
        preset = self.FASTENER_PRESETS.get(fastener_type, self.FASTENER_PRESETS["m3_pan_head"])
        hole_diameter = max(float(hole.get("diameter", preset["clearance_diameter"]) or preset["clearance_diameter"]), self.MIN_FEATURE_SIZE)
        boss_height = self._pcb_z(controller_data)
        boss_outer_diameter = max(
            float(hole.get("boss_outer_diameter", mounting_defaults.get("boss_outer_diameter", 0.0)) or 0.0),
            hole_diameter + 3.0,
            6.0,
        )
        screw_diameter = max(
            min(float(preset["nominal_diameter"]), hole_diameter - 0.2),
            self.MIN_FEATURE_SIZE,
        )
        screw_head_diameter = max(
            float(hole.get("screw_head_diameter", mounting_defaults.get("screw_head_diameter", preset["head_diameter"])) or preset["head_diameter"]),
            screw_diameter + 1.0,
        )
        screw_head_height = max(
            float(hole.get("screw_head_height", mounting_defaults.get("screw_head_height", preset["head_height"])) or preset["head_height"]),
            self.MIN_FEATURE_SIZE,
        )
        counterbore_depth = max(float(hole.get("counterbore_depth", mounting_defaults.get("counterbore_depth", 0.0)) or 0.0), 0.0)
        counterbore_diameter = max(
            float(hole.get("counterbore_diameter", mounting_defaults.get("counterbore_diameter", screw_head_diameter)) or screw_head_diameter),
            hole_diameter,
        )
        return {
            "fastener_type": fastener_type,
            "hole_diameter": hole_diameter,
            "boss_outer_diameter": boss_outer_diameter,
            "boss_height": boss_height,
            "counterbore_depth": counterbore_depth,
            "counterbore_diameter": counterbore_diameter,
            "screw_diameter": screw_diameter,
            "screw_head_diameter": screw_head_diameter,
            "screw_head_height": screw_head_height,
            "screw_length": self._pcb_top_z(controller_data),
        }

    def _default_fastener_type(self, hole: dict[str, Any]) -> str:
        diameter = float(hole.get("diameter", 0.0) or 0.0)
        if diameter <= 2.6:
            return "m2_pan_head"
        return "m3_pan_head"

    def _body_height(self, controller: Any) -> float:
        controller_data = self._controller_to_dict(controller)
        top_thickness = max(float(controller_data.get("top_thickness", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
        total_height = max(float(controller_data.get("height", 0.0) or 0.0), top_thickness + self.MIN_FEATURE_SIZE)
        return max(total_height - top_thickness, self.MIN_FEATURE_SIZE)

    def _offset_surface(self, surface: SurfacePrimitive, inset: float) -> SurfacePrimitive | None:
        if inset <= 0.0:
            return surface
        width = float(surface.width) - (2.0 * inset)
        height = float(surface.height) - (2.0 * inset)
        if width <= self.MIN_FEATURE_SIZE or height <= self.MIN_FEATURE_SIZE:
            return None
        if surface.shape == "rounded_rect":
            corner_radius = max(float(surface.corner_radius or 0.0) - inset, 0.0)
            return SurfacePrimitive(
                shape="rounded_rect",
                width=width,
                height=height,
                corner_radius=corner_radius,
            )
        if surface.shape == "rectangle":
            return SurfacePrimitive(shape="rectangle", width=width, height=height)
        return None

    def _custom_fcstd_base_config(self, controller: Any) -> dict[str, Any] | None:
        controller_data = self._controller_to_dict(controller)
        geometry = controller_data.get("geometry")
        if not isinstance(geometry, dict):
            return None
        base = geometry.get("base")
        if not isinstance(base, dict):
            return None
        if str(base.get("type") or "") != "custom_fcstd":
            return None
        return deepcopy(base)


def build_controller(domain_controller):
    return domain_controller

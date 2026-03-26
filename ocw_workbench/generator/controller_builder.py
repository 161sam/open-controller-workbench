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

    def plan_body_build(self, controller: Any) -> BodyBuildPlan:
        surface = self.resolve_surface(controller)
        body_height = self._body_height(controller)
        cavity_surface = None
        cavity_offset = None
        cavity_height = None
        if self._supports_shell_geometry(surface):
            wall = max(float(getattr(controller, "wall_thickness", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
            bottom = max(float(getattr(controller, "bottom_thickness", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
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
        surface = self.resolve_surface(controller)
        z_offset = self._body_height(controller)
        tongue_surface = None
        tongue_offset = None
        tongue_height = None
        if self._supports_shell_geometry(surface):
            wall = max(float(getattr(controller, "wall_thickness", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
            clearance = max(float(getattr(controller, "inner_clearance", 0.0) or 0.0), 0.0)
            inset = max(float(getattr(controller, "lid_inset", 0.0) or 0.0), 0.0)
            bottom = max(float(getattr(controller, "bottom_thickness", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
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
            top_thickness=float(controller.top_thickness),
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

    def _supports_shell_geometry(self, surface: SurfacePrimitive) -> bool:
        return surface.shape in {"rectangle", "rounded_rect"}

    def _body_height(self, controller: Any) -> float:
        top_thickness = max(float(getattr(controller, "top_thickness", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
        total_height = max(float(getattr(controller, "height", 0.0) or 0.0), top_thickness + self.MIN_FEATURE_SIZE)
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

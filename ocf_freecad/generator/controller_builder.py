from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocf_freecad.freecad_api import shapes
from ocf_freecad.generator.component_resolver import ComponentResolver
from ocf_freecad.geometry.primitives import Cutout, ResolvedMechanical, ShapePrimitive, SurfacePrimitive


class ControllerBuilder:
    MIN_FEATURE_SIZE = 0.5

    def __init__(self, doc=None, component_resolver: ComponentResolver | None = None):
        self.doc = doc
        self.component_resolver = component_resolver or ComponentResolver()

    def build_body(self, controller):
        surface = self.resolve_surface(controller)
        body_height = self._body_height(controller)
        outer_shape = shapes.make_surface_prism_shape(surface, body_height)
        body_shape = outer_shape
        if self._supports_shell_geometry(surface):
            cavity_shape = self._body_cavity_shape(controller, surface, body_height)
            if cavity_shape is not None:
                body_shape = outer_shape.cut(cavity_shape)
        return shapes.create_feature(self.doc, "ControllerBody", body_shape)

    def build_top_plate(self, controller):
        surface = self.resolve_surface(controller)
        z_offset = self._body_height(controller)
        top_shape = shapes.translate_shape(
            shapes.make_surface_prism_shape(surface, controller.top_thickness),
            z=z_offset,
        )
        lid_tongue = self._lid_tongue_shape(controller, surface, z_offset)
        if lid_tongue is not None:
            fused = shapes.fuse_shapes([top_shape, lid_tongue])
            if fused is not None:
                top_shape = fused
        return shapes.create_feature(self.doc, "TopPlate", top_shape)

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
                self._placed_feature(component["id"], component["x"], component["y"], mechanical.keepout_top, "top")
            )
            keepouts.append(
                self._placed_feature(
                    component["id"],
                    component["x"],
                    component["y"],
                    mechanical.keepout_bottom,
                    "bottom",
                )
            )
        return keepouts

    def apply_cutouts(self, base_obj, components):
        result_shape = base_obj.Shape.copy() if hasattr(base_obj.Shape, "copy") else base_obj.Shape
        z_start = base_obj.Shape.BoundBox.ZMin
        cut_height = base_obj.Shape.BoundBox.ZLength

        for component in self.resolve_components(components):
            tool = self._create_cutout_shape(
                x=component["x"],
                y=component["y"],
                cutout=component["resolved_mechanical"].cutout,
                cut_height=cut_height,
                z_start=z_start,
            )
            result_shape = result_shape.cut(tool)

        base_obj.Shape = result_shape
        return base_obj

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
                    **placed.to_dict(),
                }
            )
        return cutouts

    def _create_cutout_shape(
        self,
        x: float,
        y: float,
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
        if cutout.shape == "rect":
            return shapes.translate_shape(
                shapes.make_rect_prism_shape(
                    width=cutout.width,
                    depth=cutout.height,
                    height=cut_height,
                ),
                x=x - (cutout.width / 2.0),
                y=y - (cutout.height / 2.0),
                z=z_start,
            )
        raise ValueError(f"Unsupported cutout shape: {cutout.shape}")

    def _placed_feature(
        self,
        component_id: str,
        x: float,
        y: float,
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

    def _body_cavity_shape(self, controller: Any, surface: SurfacePrimitive, body_height: float):
        wall = max(float(getattr(controller, "wall_thickness", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
        bottom = max(float(getattr(controller, "bottom_thickness", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
        inner_width = float(surface.width) - (2.0 * wall)
        inner_height = float(surface.height) - (2.0 * wall)
        cavity_height = body_height - bottom
        if (
            inner_width <= self.MIN_FEATURE_SIZE
            or inner_height <= self.MIN_FEATURE_SIZE
            or cavity_height <= self.MIN_FEATURE_SIZE
        ):
            return None
        inner_surface = self._offset_surface(surface, inset=wall)
        if inner_surface is None:
            return None
        return shapes.translate_shape(
            shapes.make_surface_prism_shape(inner_surface, cavity_height),
            x=wall,
            y=wall,
            z=bottom,
        )

    def _lid_tongue_shape(self, controller: Any, surface: SurfacePrimitive, z_offset: float):
        if not self._supports_shell_geometry(surface):
            return None
        wall = max(float(getattr(controller, "wall_thickness", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
        clearance = max(float(getattr(controller, "inner_clearance", 0.0) or 0.0), 0.0)
        inset = max(float(getattr(controller, "lid_inset", 0.0) or 0.0), 0.0)
        bottom = max(float(getattr(controller, "bottom_thickness", 0.0) or 0.0), self.MIN_FEATURE_SIZE)
        body_height = self._body_height(controller)
        tongue_height = min(inset, max(body_height - bottom, 0.0))
        if tongue_height <= self.MIN_FEATURE_SIZE:
            return None
        tongue_surface = self._offset_surface(surface, inset=wall + clearance)
        if tongue_surface is None:
            return None
        return shapes.translate_shape(
            shapes.make_surface_prism_shape(tongue_surface, tongue_height),
            x=wall + clearance,
            y=wall + clearance,
            z=max(z_offset - tongue_height, bottom),
        )

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


def build_controller(domain_controller):
    return domain_controller

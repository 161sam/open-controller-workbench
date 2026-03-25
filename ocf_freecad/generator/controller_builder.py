from __future__ import annotations

from typing import Any

from ocf_freecad.freecad_api import shapes
from ocf_freecad.generator.component_resolver import ComponentResolver
from ocf_freecad.geometry.primitives import Cutout, ResolvedMechanical, ShapePrimitive


class ControllerBuilder:
    def __init__(self, doc=None, component_resolver: ComponentResolver | None = None):
        self.doc = doc
        self.component_resolver = component_resolver or ComponentResolver()

    def build_body(self, controller):
        return shapes.create_box(
            self.doc,
            "ControllerBody",
            controller.width,
            controller.depth,
            controller.height,
        )

    def build_top_plate(self, controller):
        z_offset = controller.height - controller.top_thickness
        return shapes.create_box(
            self.doc,
            "TopPlate",
            controller.width,
            controller.depth,
            controller.top_thickness,
            z=z_offset,
        )

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
        result = base_obj
        z_start = base_obj.Shape.BoundBox.ZMin
        cut_height = base_obj.Shape.BoundBox.ZLength

        for component in self.resolve_components(components):
            tool = self._create_cutout_tool(
                component_id=component["id"],
                x=component["x"],
                y=component["y"],
                cutout=component["resolved_mechanical"].cutout,
                cut_height=cut_height,
                z_start=z_start,
            )
            result = shapes.cut(result, tool, name=f"{base_obj.Name}_{component['id']}_cut")

        return result

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

    def _create_cutout_tool(
        self,
        component_id: str,
        x: float,
        y: float,
        cutout: ShapePrimitive,
        cut_height: float,
        z_start: float,
    ):
        if self.doc is None:
            raise ValueError("ControllerBuilder requires a document to create FreeCAD cutouts")

        if cutout.shape == "circle":
            return shapes.create_cylinder(
                self.doc,
                f"cutout_{component_id}",
                radius=cutout.diameter / 2.0,
                height=cut_height,
                x=x,
                y=y,
                z=z_start,
            )
        if cutout.shape == "rect":
            return shapes.create_rect_prism(
                self.doc,
                f"cutout_{component_id}",
                width=cutout.width,
                depth=cutout.height,
                height=cut_height,
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


def build_controller(domain_controller):
    return domain_controller

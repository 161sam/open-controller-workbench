from __future__ import annotations

from typing import Any

from ocf_freecad.freecad_api import shapes
from ocf_freecad.services.overlay_service import OverlayService


class OverlayRenderer:
    def __init__(self, overlay_service: OverlayService | None = None) -> None:
        self.overlay_service = overlay_service or OverlayService()

    def refresh(self, doc: Any) -> dict[str, Any]:
        payload = self.overlay_service.build_overlay(doc)
        self.render(doc, payload)
        return payload

    def render(self, doc: Any, payload: dict[str, Any]) -> None:
        setattr(doc, "OCFOverlayState", payload)
        self._clear_overlay(doc)
        if not payload.get("enabled", True):
            return
        if not hasattr(doc, "addObject"):
            return
        z_base = float(payload.get("controller_height", 0.0)) + 0.25
        for index, item in enumerate(payload.get("items", [])):
            geometry = item["geometry"]
            name = self._object_name(item["id"])
            z = z_base + (index * 0.02)
            if item["type"] == "rect":
                obj = shapes.create_rect_prism(
                    doc,
                    name,
                    width=float(geometry["width"]),
                    depth=float(geometry["height"]),
                    height=0.15,
                    x=float(geometry["x"]) - (float(geometry["width"]) / 2.0),
                    y=float(geometry["y"]) - (float(geometry["height"]) / 2.0),
                    z=z,
                )
            elif item["type"] == "circle":
                obj = shapes.create_cylinder(
                    doc,
                    name,
                    radius=float(geometry["diameter"]) / 2.0,
                    height=0.15,
                    x=float(geometry["x"]),
                    y=float(geometry["y"]),
                    z=z,
                )
            else:
                obj = shapes.create_cylinder(
                    doc,
                    name,
                    radius=0.8,
                    height=0.25,
                    x=float(geometry["x"]),
                    y=float(geometry["y"]),
                    z=z,
                )
            obj.Label = self._object_label(item)
            self._apply_style(obj, item["style"])
        if hasattr(doc, "recompute"):
            doc.recompute()

    def _clear_overlay(self, doc: Any) -> None:
        if not hasattr(doc, "Objects") or not hasattr(doc, "removeObject"):
            return
        for obj in list(doc.Objects):
            name = str(getattr(obj, "Name", ""))
            label = str(getattr(obj, "Label", ""))
            if name.startswith("OCF_OVERLAY_") or label.startswith("OCF_OVERLAY_"):
                doc.removeObject(name)

    def _apply_style(self, obj: Any, style: dict[str, Any]) -> None:
        view = getattr(obj, "ViewObject", None)
        if view is None:
            return
        rgb = style.get("rgb")
        line_rgb = style.get("line_rgb")
        if rgb is not None and hasattr(view, "ShapeColor"):
            view.ShapeColor = rgb
        if line_rgb is not None and hasattr(view, "LineColor"):
            view.LineColor = line_rgb
        transparency = style.get("transparency")
        if transparency is not None and hasattr(view, "Transparency"):
            view.Transparency = int(transparency)

    def _object_name(self, item_id: str) -> str:
        sanitized = item_id.replace(":", "_").replace("/", "_").replace(" ", "_")
        return f"OCF_OVERLAY_{sanitized}"

    def _object_label(self, item: dict[str, Any]) -> str:
        label = item.get("label") or item["id"]
        return f"OCF_OVERLAY_{label}"

from __future__ import annotations

import json
import math
from copy import deepcopy
from typing import Any

from ocw_workbench.gui.panels._common import log_to_console

OVERLAY_OBJECT_NAME = "OCW_Overlay"
OVERLAY_OBJECT_LABEL = "OCW Overlay"
LEGACY_OVERLAY_OBJECT_NAMES = ("OCF_Overlay",)
LEGACY_OVERLAY_OBJECT_LABELS = ("OCF Overlay",)
OVERLAY_GROUP_NAME = "OpenController"
PAYLOAD_PROPERTY = "OverlayPayload"
ENABLED_PROPERTY = "OverlayEnabled"
ITEM_COUNT_PROPERTY = "OverlayItemCount"
RENDER_COUNT_PROPERTY = "OverlayRenderCount"
RENDER_PATH_PROPERTY = "OverlayRenderPath"


def get_overlay_object(doc: Any, create: bool = True) -> Any | None:
    existing = _find_overlay_object(doc)
    if existing is not None or not create or not hasattr(doc, "addObject"):
        if existing is not None:
            _ensure_overlay_object(existing)
        return existing
    for object_type in ("App::FeaturePython", "App::Feature"):
        try:
            obj = doc.addObject(object_type, OVERLAY_OBJECT_NAME)
            _ensure_overlay_object(obj)
            return obj
        except Exception:
            continue
    return None


def update_overlay_object(doc: Any, payload: dict[str, Any], stats: dict[str, Any]) -> Any | None:
    obj = get_overlay_object(doc, create=True)
    if obj is None:
        return None
    _ensure_overlay_object(obj)
    proxy = getattr(obj, "Proxy", None)
    if proxy is None or not isinstance(proxy, OverlayProxy):
        proxy = OverlayProxy(obj)
    proxy.set_payload(payload, stats)
    _sync_view_provider(obj, payload, stats)
    return obj


def overlay_render_path(obj: Any | None) -> str:
    if obj is None:
        return "featurepython-missing"
    view = getattr(obj, "ViewObject", None)
    proxy = getattr(view, "Proxy", None) if view is not None else None
    if isinstance(proxy, ViewProviderOverlay) and proxy.coin is not None:
        return "coin"
    return "featurepython-headless"


def clear_legacy_overlay_objects(doc: Any) -> None:
    if not hasattr(doc, "Objects") or not hasattr(doc, "removeObject"):
        return
    for obj in list(doc.Objects):
        name = str(getattr(obj, "Name", ""))
        label = str(getattr(obj, "Label", ""))
        if any(name.startswith(prefix) or label.startswith(prefix) for prefix in ("OCW_OVERLAY_", "OCF_OVERLAY_")):
            doc.removeObject(name)


def _find_overlay_object(doc: Any) -> Any | None:
    if hasattr(doc, "getObject"):
        for name in (OVERLAY_OBJECT_NAME, *LEGACY_OVERLAY_OBJECT_NAMES):
            try:
                obj = doc.getObject(name)
                if obj is not None:
                    return obj
            except Exception:
                continue
    for obj in getattr(doc, "Objects", []):
        if getattr(obj, "Name", None) in (OVERLAY_OBJECT_NAME, *LEGACY_OVERLAY_OBJECT_NAMES):
            return obj
        if getattr(obj, "Label", None) in (OVERLAY_OBJECT_LABEL, *LEGACY_OVERLAY_OBJECT_LABELS):
            return obj
    return None


def _ensure_overlay_object(obj: Any) -> None:
    if hasattr(obj, "Label"):
        obj.Label = OVERLAY_OBJECT_LABEL
    properties = list(getattr(obj, "PropertiesList", []))
    _add_property(obj, properties, "App::PropertyString", PAYLOAD_PROPERTY, "Overlay payload JSON")
    _add_property(obj, properties, "App::PropertyBool", ENABLED_PROPERTY, "Overlay enabled state")
    _add_property(obj, properties, "App::PropertyInteger", ITEM_COUNT_PROPERTY, "Overlay item count")
    _add_property(obj, properties, "App::PropertyInteger", RENDER_COUNT_PROPERTY, "Overlay rendered item count")
    _add_property(obj, properties, "App::PropertyString", RENDER_PATH_PROPERTY, "Overlay render path")
    if getattr(obj, "Proxy", None) is None or not isinstance(getattr(obj, "Proxy", None), OverlayProxy):
        OverlayProxy(obj)
    if hasattr(obj, "setEditorMode"):
        for name in (PAYLOAD_PROPERTY, RENDER_PATH_PROPERTY):
            try:
                obj.setEditorMode(name, 2)
            except Exception:
                continue
    _attach_view_provider(obj)


def _add_property(obj: Any, properties: list[str], type_name: str, name: str, description: str) -> None:
    if name in properties or not hasattr(obj, "addProperty"):
        return
    obj.addProperty(type_name, name, OVERLAY_GROUP_NAME, description)


def _attach_view_provider(obj: Any) -> None:
    view = getattr(obj, "ViewObject", None)
    if view is None:
        return
    proxy = getattr(view, "Proxy", None)
    if isinstance(proxy, ViewProviderOverlay):
        proxy.ensure_attached(view)
        return
    try:
        ViewProviderOverlay(view)
    except Exception as exc:
        log_to_console(f"Overlay view provider setup failed: {exc}", level="warning")


def _sync_view_provider(obj: Any, payload: dict[str, Any], stats: dict[str, Any]) -> None:
    view = getattr(obj, "ViewObject", None)
    if view is None:
        return
    proxy = getattr(view, "Proxy", None)
    if isinstance(proxy, ViewProviderOverlay):
        proxy.update_payload(payload, stats)
    if hasattr(view, "Visibility"):
        view.Visibility = bool(payload.get("enabled", True))


class OverlayProxy:
    def __init__(self, obj: Any) -> None:
        self.Object = obj
        self.payload: dict[str, Any] = {}
        self.stats: dict[str, Any] = {}
        obj.Proxy = self

    def onDocumentRestored(self, obj: Any) -> None:
        self.Object = obj

    def execute(self, _obj: Any) -> None:
        return

    def set_payload(self, payload: dict[str, Any], stats: dict[str, Any]) -> None:
        self.payload = deepcopy(payload)
        self.stats = deepcopy(stats)
        setattr(self.Object, PAYLOAD_PROPERTY, json.dumps(self.payload, sort_keys=True))
        setattr(self.Object, ENABLED_PROPERTY, bool(self.payload.get("enabled", True)))
        setattr(self.Object, ITEM_COUNT_PROPERTY, int(self.stats.get("total_items", 0)))
        setattr(self.Object, RENDER_COUNT_PROPERTY, int(self.stats.get("rendered_items", 0)))
        setattr(self.Object, RENDER_PATH_PROPERTY, str(self.stats.get("render_path", "headless")))

    def __getstate__(self) -> dict[str, Any]:
        return {}

    def __setstate__(self, _state: dict[str, Any]) -> None:
        return


class ViewProviderOverlay:
    def __init__(self, view_object: Any) -> None:
        self.Object = getattr(view_object, "Object", None)
        self.ViewObject = view_object
        self.coin = _load_coin()
        self.root = None
        self.payload_root = None
        view_object.Proxy = self
        self.ensure_attached(view_object)

    def getDisplayModes(self, _obj: Any) -> list[str]:
        return ["Overlay"]

    def getDefaultDisplayMode(self) -> str:
        return "Overlay"

    def setDisplayMode(self, mode: str) -> str:
        return mode

    def onChanged(self, _vp: Any, _prop: str) -> None:
        return

    def updateData(self, obj: Any, prop: str) -> None:
        if prop != PAYLOAD_PROPERTY:
            return
        payload = getattr(obj.Proxy, "payload", {}) if isinstance(getattr(obj, "Proxy", None), OverlayProxy) else {}
        stats = getattr(obj.Proxy, "stats", {}) if isinstance(getattr(obj, "Proxy", None), OverlayProxy) else {}
        self.update_payload(payload, stats)

    def attach(self, view_object: Any) -> None:
        self.ensure_attached(view_object)

    def ensure_attached(self, view_object: Any) -> None:
        if self.coin is None:
            return
        root_node = getattr(view_object, "RootNode", None)
        if root_node is None:
            return
        if self.root is not None:
            return
        self.root = self.coin.SoSeparator()
        self.root.setName("OCWOverlayRoot")
        self.payload_root = self.coin.SoSeparator()
        self.root.addChild(self.payload_root)
        root_node.addChild(self.root)

    def update_payload(self, payload: dict[str, Any], stats: dict[str, Any]) -> None:
        if self.coin is None or self.payload_root is None:
            return
        self.payload_root.removeAllChildren()
        if not payload.get("enabled", True):
            return
        z_base = float(payload.get("controller_height", 0.0)) + 0.25
        for index, item in enumerate(payload.get("items", [])):
            node = self._item_node(item, z_base + (index * 0.005))
            if node is not None:
                self.payload_root.addChild(node)

    def _item_node(self, item: dict[str, Any], z: float) -> Any | None:
        item_type = str(item.get("type", ""))
        geometry = item.get("geometry", {})
        if item_type == "rect":
            return self._rect_node(item, geometry, z)
        if item_type == "slot":
            return self._slot_node(item, geometry, z)
        if item_type == "circle":
            return self._circle_node(item, geometry, z)
        if item_type == "line":
            return self._line_node(item, geometry, z)
        if item_type == "text_marker":
            return self._text_node(item, geometry, z)
        return None

    def _rect_node(self, item: dict[str, Any], geometry: dict[str, Any], z: float) -> Any | None:
        width = float(geometry.get("width", 0.0) or 0.0)
        height = float(geometry.get("height", 0.0) or 0.0)
        if width <= 1e-6 or height <= 1e-6:
            return None
        x = float(geometry["x"])
        y = float(geometry["y"])
        rotation = float(geometry.get("rotation", 0.0) or 0.0)
        half_w = width / 2.0
        half_h = height / 2.0
        corners = [
            _rotate_point(x - half_w, y - half_h, x, y, rotation, z),
            _rotate_point(x + half_w, y - half_h, x, y, rotation, z),
            _rotate_point(x + half_w, y + half_h, x, y, rotation, z),
            _rotate_point(x - half_w, y + half_h, x, y, rotation, z),
            _rotate_point(x - half_w, y - half_h, x, y, rotation, z),
        ]
        return self._polyline_node(corners, item.get("style", {}))

    def _circle_node(self, item: dict[str, Any], geometry: dict[str, Any], z: float) -> Any | None:
        diameter = float(geometry.get("diameter", 0.0) or 0.0)
        if diameter <= 1e-6:
            return None
        radius = diameter / 2.0
        x = float(geometry["x"])
        y = float(geometry["y"])
        points = []
        for step in range(33):
            angle = (math.pi * 2.0 * step) / 32.0
            points.append((x + (math.cos(angle) * radius), y + (math.sin(angle) * radius), z))
        return self._polyline_node(points, item.get("style", {}))

    def _slot_node(self, item: dict[str, Any], geometry: dict[str, Any], z: float) -> Any | None:
        width = float(geometry.get("width", 0.0) or 0.0)
        height = float(geometry.get("height", 0.0) or 0.0)
        if width <= 1e-6 or height <= 1e-6:
            return None
        x = float(geometry["x"])
        y = float(geometry["y"])
        rotation = float(geometry.get("rotation", 0.0) or 0.0)
        major = max(width, height)
        minor = min(width, height)
        radius = minor / 2.0
        center_offset = max(0.0, (major / 2.0) - radius)
        points = []
        for step in range(17):
            angle = (math.pi / 2.0) - ((math.pi * step) / 16.0)
            points.append(
                _rotate_point(
                    x + center_offset + (math.cos(angle) * radius),
                    y + (math.sin(angle) * radius),
                    x,
                    y,
                    rotation,
                    z,
                )
            )
        for step in range(17):
            angle = (-math.pi / 2.0) - ((math.pi * step) / 16.0)
            points.append(
                _rotate_point(
                    x - center_offset + (math.cos(angle) * radius),
                    y + (math.sin(angle) * radius),
                    x,
                    y,
                    rotation,
                    z,
                )
            )
        if points:
            points.append(points[0])
        return self._polyline_node(points, item.get("style", {}))

    def _line_node(self, item: dict[str, Any], geometry: dict[str, Any], z: float) -> Any | None:
        start_x = float(geometry.get("start_x", 0.0) or 0.0)
        start_y = float(geometry.get("start_y", 0.0) or 0.0)
        end_x = float(geometry.get("end_x", 0.0) or 0.0)
        end_y = float(geometry.get("end_y", 0.0) or 0.0)
        if math.hypot(end_x - start_x, end_y - start_y) <= 1e-6:
            return None
        return self._polyline_node([(start_x, start_y, z), (end_x, end_y, z)], item.get("style", {}))

    def _text_node(self, item: dict[str, Any], geometry: dict[str, Any], z: float) -> Any | None:
        label = str(item.get("label", "") or "")
        if not label:
            return None
        sep = self.coin.SoSeparator()
        sep.addChild(self._base_color(item.get("style", {})))
        translation = self.coin.SoTranslation()
        translation.translation.setValue(float(geometry["x"]), float(geometry["y"]), z)
        sep.addChild(translation)
        font = self.coin.SoFont()
        font.size = 12.0
        sep.addChild(font)
        text = self.coin.SoText2()
        text.string.setValue(label)
        sep.addChild(text)
        return sep

    def _polyline_node(self, points: list[tuple[float, float, float]], style: dict[str, Any]) -> Any:
        sep = self.coin.SoSeparator()
        sep.addChild(self._draw_style(style))
        sep.addChild(self._base_color(style))
        coords = self.coin.SoCoordinate3()
        for index, point in enumerate(points):
            coords.point.set1Value(index, point[0], point[1], point[2])
        sep.addChild(coords)
        line = self.coin.SoLineSet()
        line.numVertices.set1Value(0, len(points))
        sep.addChild(line)
        return sep

    def _draw_style(self, style: dict[str, Any]) -> Any:
        draw_style = self.coin.SoDrawStyle()
        draw_style.lineWidth = float(style.get("line_width", 2.0) or 2.0)
        return draw_style

    def _base_color(self, style: dict[str, Any]) -> Any:
        color = self.coin.SoBaseColor()
        rgb = style.get("rgb") or style.get("line_rgb") or (0.2, 0.8, 0.7)
        color.rgb.setValue(float(rgb[0]), float(rgb[1]), float(rgb[2]))
        return color

    def __getstate__(self) -> dict[str, Any]:
        return {}

    def __setstate__(self, _state: dict[str, Any]) -> None:
        return


def _load_coin() -> Any | None:
    try:
        from pivy import coin

        return coin
    except Exception:
        try:
            import FreeCADGui as Gui

            return getattr(Gui, "coin", None)
        except Exception:
            return None


def _rotate_point(x: float, y: float, center_x: float, center_y: float, angle_deg: float, z: float) -> tuple[float, float, float]:
    if angle_deg == 0.0:
        return (x, y, z)
    radians = math.radians(angle_deg)
    dx = x - center_x
    dy = y - center_y
    return (
        center_x + (dx * math.cos(radians)) - (dy * math.sin(radians)),
        center_y + (dx * math.sin(radians)) + (dy * math.cos(radians)),
        z,
    )

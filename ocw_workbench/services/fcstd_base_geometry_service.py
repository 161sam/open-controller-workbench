from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any

from ocw_workbench.services._logging import log_to_console


class FCStdBaseGeometryService:
    def build_shape_from_config(
        self,
        config: dict[str, Any],
        *,
        extrude_height: float | None = None,
        z_offset: float = 0.0,
    ) -> Any:
        if not isinstance(config, dict):
            raise ValueError("custom_fcstd geometry config must be a mapping")
        fcstd_path = str(config.get("filename") or "").strip()
        target_ref = str(config.get("target_ref") or "").strip()
        if not fcstd_path:
            raise ValueError("custom_fcstd geometry is missing a source filename")
        if not target_ref:
            raise ValueError("custom_fcstd geometry is missing a target reference")
        with self._opened_document(fcstd_path) as doc:
            target = self._resolve_target(doc, target_ref)
            shape = self._shape_from_target(target["shape_or_feature"], extrude_height=extrude_height)
            return self._transform_shape(shape, config=config, z_offset=z_offset)

    @contextmanager
    def _opened_document(self, fcstd_path: str | Path):
        try:
            import FreeCAD as App
        except ImportError as exc:
            raise RuntimeError("FreeCAD runtime is required for custom_fcstd base geometry") from exc
        path = str(Path(fcstd_path))
        if not hasattr(App, "openDocument"):
            raise RuntimeError("FreeCAD does not provide openDocument() in this environment")
        doc = App.openDocument(path)
        try:
            yield doc
        finally:
            if hasattr(App, "closeDocument") and getattr(doc, "Name", None):
                try:
                    App.closeDocument(doc.Name)
                except Exception as exc:
                    log_to_console(f"Failed to close temporary FCStd document '{doc.Name}': {exc}", level="warning")

    def _resolve_target(self, doc: Any, target_ref: str) -> dict[str, Any]:
        object_name, _, suffix = str(target_ref).partition("::")
        obj = self._find_object(doc, object_name)
        shape = getattr(obj, "Shape", None)
        if not suffix:
            if shape is None:
                raise ValueError(f"FCStd object '{object_name}' does not expose a shape")
            return {"object_name": object_name, "shape_or_feature": shape}
        if suffix.startswith("Face") and shape is not None:
            index = int(suffix[4:]) - 1
            return {"object_name": object_name, "shape_or_feature": shape.Faces[index]}
        raise ValueError(f"Unsupported FCStd target reference '{target_ref}'")

    def _find_object(self, doc: Any, object_name: str) -> Any:
        if hasattr(doc, "getObject"):
            found = doc.getObject(object_name)
            if found is not None:
                return found
        for obj in getattr(doc, "Objects", []):
            if getattr(obj, "Name", None) == object_name:
                return obj
        raise KeyError(f"Unknown FCStd object '{object_name}'")

    def _shape_from_target(self, target: Any, *, extrude_height: float | None) -> Any:
        shape = getattr(target, "copy", None)
        base_shape = target.copy() if callable(shape) else target
        if extrude_height is None:
            return base_shape
        if not hasattr(base_shape, "extrude"):
            raise ValueError("Selected custom_fcstd target cannot be extruded")
        try:
            import FreeCAD as App
        except ImportError as exc:
            raise RuntimeError("FreeCAD runtime is required for custom_fcstd extrusion") from exc
        return base_shape.extrude(App.Vector(0.0, 0.0, float(extrude_height)))

    def _transform_shape(self, shape: Any, *, config: dict[str, Any], z_offset: float) -> Any:
        from ocw_workbench.freecad_api import shapes

        origin = deepcopy(config.get("origin", {})) if isinstance(config.get("origin"), dict) else {}
        offset_x = float(origin.get("offset_x", 0.0) or 0.0)
        offset_y = float(origin.get("offset_y", 0.0) or 0.0)
        reference_x = float(origin.get("x", 0.0) or 0.0)
        reference_y = float(origin.get("y", 0.0) or 0.0)
        translated = shapes.translate_shape(
            shape,
            x=offset_x - reference_x,
            y=offset_y - reference_y,
            z=float(z_offset),
        )
        rotation_deg = float(config.get("rotation_deg", 0.0) or 0.0)
        if rotation_deg != 0.0:
            translated = shapes.rotate_shape(
                translated,
                rotation_deg,
                center=(float(offset_x), float(offset_y), float(z_offset)),
            )
        return translated

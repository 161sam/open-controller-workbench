from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ocw_workbench.userdata.persistence import UserDataPersistence
from ocw_workbench.utils.yaml_io import dump_yaml


@dataclass(frozen=True)
class BoundingBoxData:
    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float

    @property
    def xlen(self) -> float:
        return float(self.xmax - self.xmin)

    @property
    def ylen(self) -> float:
        return float(self.ymax - self.ymin)

    @property
    def zlen(self) -> float:
        return float(self.zmax - self.zmin)


def project_bbox_to_template_dimensions(bbox: BoundingBoxData, rotation_deg: float = 0.0) -> tuple[float, float]:
    rotation = int(round(float(rotation_deg))) % 360
    if rotation in {90, 270}:
        return (float(bbox.ylen), float(bbox.xlen))
    return (float(bbox.xlen), float(bbox.ylen))


def build_imported_template_payload(
    *,
    template_id: str,
    name: str,
    width: float,
    depth: float,
    height: float,
    source_filename: str,
    object_name: str,
    target_ref: str,
    rotation_deg: float = 0.0,
    origin: dict[str, Any] | None = None,
    mounting_holes: list[dict[str, Any]] | None = None,
    use_source_as_base_geometry: bool = False,
) -> dict[str, Any]:
    description = f"Imported from {Path(source_filename).name}"
    geometry = {}
    if use_source_as_base_geometry:
        geometry = {
            "base": {
                "type": "custom_fcstd",
                "filename": str(source_filename),
                "object_name": str(object_name),
                "target_ref": str(target_ref),
                "rotation_deg": float(rotation_deg),
                "origin": origin or {"type": "manual", "offset_x": 0.0, "offset_y": 0.0},
                "projection": "top_plate",
            }
        }
    return {
        "template": {
            "id": str(template_id),
            "name": str(name),
            "description": description,
            "category": "imported",
            "tags": ["fcstd", "user"],
            "version": "user",
        },
        "controller": {
            "id": str(template_id),
            "width": float(width),
            "depth": float(depth),
            "height": float(height),
            "top_thickness": 3.0,
            "surface": {
                "type": "rectangle",
                "shape": "rectangle",
                "width": float(width),
                "height": float(depth),
            },
            "mounting_holes": list(mounting_holes or []),
            "reserved_zones": [],
            "layout_zones": [],
            "geometry": geometry,
        },
        "zones": [],
        "components": [],
        "layout": {},
        "constraints": {},
        "defaults": {},
        "firmware": {},
        "ocf": {},
        "metadata": {
            "source": {
                "type": "fcstd",
                "filename": str(source_filename),
                "object_name": str(object_name),
                "target_ref": str(target_ref),
                "rotation_deg": float(rotation_deg),
                "origin": origin or {"type": "manual", "offset_x": 0.0, "offset_y": 0.0},
            }
        },
    }


class FCStdTemplateImporter:
    def __init__(self, userdata: UserDataPersistence | None = None) -> None:
        self.userdata = userdata or UserDataPersistence()

    @property
    def templates_dir(self) -> Path:
        return self.userdata.templates_dir

    def list_targets(self, fcstd_path: str | Path) -> list[dict[str, str]]:
        with self._opened_document(fcstd_path) as doc:
            targets: list[dict[str, str]] = []
            for obj in getattr(doc, "Objects", []):
                name = str(getattr(obj, "Name", ""))
                label = str(getattr(obj, "Label", name))
                if not name:
                    continue
                targets.append({"id": name, "label": label, "kind": "object"})
                for index, _vertex in enumerate(self._vertices_for_object(obj), start=1):
                    targets.append({"id": f"{name}::Vertex{index}", "label": f"{label} / Vertex {index}", "kind": "vertex"})
                shape = getattr(obj, "Shape", None)
                faces = getattr(shape, "Faces", []) if shape is not None else []
                for index, _face in enumerate(faces, start=1):
                    targets.append({"id": f"{name}::Face{index}", "label": f"{label} / Face {index}", "kind": "face"})
            return targets

    def import_template(
        self,
        *,
        fcstd_path: str | Path,
        target_ref: str,
        template_id: str,
        name: str,
        rotation_deg: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        height_override: float | None = None,
        origin_ref: str | None = None,
        use_source_as_base_geometry: bool = False,
    ) -> Path:
        with self._opened_document(fcstd_path) as doc:
            target = self._resolve_target(doc, target_ref)
            bbox = self._bbox_data(target["shape_or_feature"])
            width, depth = project_bbox_to_template_dimensions(bbox, rotation_deg=rotation_deg)
            overall_bbox = self._document_bbox(doc)
            height = float(height_override if height_override is not None else overall_bbox.zlen)
            origin = self._origin_payload(doc, origin_ref=origin_ref, offset_x=offset_x, offset_y=offset_y)
            mounting_holes = self._detect_mounting_holes(doc, offset_x=offset_x, offset_y=offset_y)
            payload = build_imported_template_payload(
                template_id=_slugify(template_id),
                name=name,
                width=width,
                depth=depth,
                height=max(height, 1.0),
                source_filename=str(fcstd_path),
                object_name=target["object_name"],
                target_ref=target_ref,
                rotation_deg=rotation_deg,
                origin=origin,
                mounting_holes=mounting_holes,
                use_source_as_base_geometry=use_source_as_base_geometry,
            )
            output_path = self.templates_dir / f"{_slugify(template_id)}.yaml"
            dump_yaml(output_path, payload)
            return output_path

    @contextmanager
    def _opened_document(self, fcstd_path: str | Path):
        try:
            import FreeCAD as App
        except ImportError as exc:
            raise RuntimeError("FreeCAD runtime is required for FCStd import") from exc
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
                except Exception:
                    pass

    def _resolve_target(self, doc: Any, target_ref: str) -> dict[str, Any]:
        object_name, _, suffix = str(target_ref).partition("::")
        obj = self._find_object(doc, object_name)
        shape = getattr(obj, "Shape", None)
        if not suffix:
            return {"object_name": object_name, "shape_or_feature": obj}
        if suffix.startswith("Face") and shape is not None:
            index = int(suffix[4:]) - 1
            return {"object_name": object_name, "shape_or_feature": shape.Faces[index]}
        raise ValueError(f"Unsupported target reference '{target_ref}'")

    def _origin_payload(self, doc: Any, origin_ref: str | None, offset_x: float, offset_y: float) -> dict[str, Any]:
        if not origin_ref:
            return {"type": "manual", "offset_x": float(offset_x), "offset_y": float(offset_y)}
        object_name, _, suffix = origin_ref.partition("::")
        obj = self._find_object(doc, object_name)
        if suffix.startswith("Vertex"):
            index = int(suffix[6:]) - 1
            vertex = self._vertices_for_object(obj)[index]
            return {
                "type": "vertex",
                "reference": origin_ref,
                "x": float(getattr(vertex, "X", 0.0)),
                "y": float(getattr(vertex, "Y", 0.0)),
                "offset_x": float(offset_x),
                "offset_y": float(offset_y),
            }
        return {"type": "manual", "offset_x": float(offset_x), "offset_y": float(offset_y)}

    def _detect_mounting_holes(self, doc: Any, offset_x: float, offset_y: float) -> list[dict[str, Any]]:
        holes: list[dict[str, Any]] = []
        for obj in getattr(doc, "Objects", []):
            name = str(getattr(obj, "Name", ""))
            label = str(getattr(obj, "Label", name)).lower()
            if "hole" not in label and "mount" not in label:
                continue
            bbox = self._bbox_data(obj)
            diameter = (bbox.xlen + bbox.ylen) / 2.0
            if diameter <= 0.0:
                continue
            holes.append(
                {
                    "id": name or f"mh{len(holes) + 1}",
                    "x": ((bbox.xmin + bbox.xmax) / 2.0) - float(offset_x),
                    "y": ((bbox.ymin + bbox.ymax) / 2.0) - float(offset_y),
                    "diameter": diameter,
                }
            )
        return holes

    def _document_bbox(self, doc: Any) -> BoundingBoxData:
        boxes = [self._bbox_data(obj) for obj in getattr(doc, "Objects", []) if self._has_bound_box(obj)]
        if not boxes:
            raise ValueError("Imported FCStd document does not expose any usable bounding boxes")
        return BoundingBoxData(
            xmin=min(item.xmin for item in boxes),
            ymin=min(item.ymin for item in boxes),
            zmin=min(item.zmin for item in boxes),
            xmax=max(item.xmax for item in boxes),
            ymax=max(item.ymax for item in boxes),
            zmax=max(item.zmax for item in boxes),
        )

    def _bbox_data(self, obj: Any) -> BoundingBoxData:
        bound_box = getattr(getattr(obj, "Shape", obj), "BoundBox", None)
        if bound_box is None:
            raise ValueError("Selected FCStd target does not expose a bounding box")
        return BoundingBoxData(
            xmin=float(getattr(bound_box, "XMin")),
            ymin=float(getattr(bound_box, "YMin")),
            zmin=float(getattr(bound_box, "ZMin")),
            xmax=float(getattr(bound_box, "XMax")),
            ymax=float(getattr(bound_box, "YMax")),
            zmax=float(getattr(bound_box, "ZMax")),
        )

    def _find_object(self, doc: Any, object_name: str) -> Any:
        if hasattr(doc, "getObject"):
            found = doc.getObject(object_name)
            if found is not None:
                return found
        for obj in getattr(doc, "Objects", []):
            if getattr(obj, "Name", None) == object_name:
                return obj
        raise KeyError(f"Unknown FCStd object '{object_name}'")

    def _vertices_for_object(self, obj: Any) -> list[Any]:
        shape = getattr(obj, "Shape", None)
        vertices = getattr(shape, "Vertexes", None) if shape is not None else None
        if isinstance(vertices, list):
            return vertices
        if vertices is None:
            return []
        try:
            return list(vertices)
        except Exception:
            return []

    def _has_bound_box(self, obj: Any) -> bool:
        return getattr(getattr(obj, "Shape", obj), "BoundBox", None) is not None


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value).strip())
    compact = "_".join(part for part in cleaned.split("_") if part)
    return compact or "imported_template"

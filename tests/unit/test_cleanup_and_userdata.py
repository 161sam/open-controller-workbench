from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from ocw_workbench.generator.controller_builder import ControllerBuilder
from ocw_workbench.userdata.persistence import _default_base_dir


class FakeShapePrimitive:
    def __init__(self, shape: str, diameter: float | None = None, width: float | None = None, height: float | None = None) -> None:
        self.shape = shape
        self.diameter = diameter
        self.width = width
        self.height = height

    def to_dict(self) -> dict[str, float | str]:
        data = {"shape": self.shape}
        if self.diameter is not None:
            data["diameter"] = self.diameter
        if self.width is not None:
            data["width"] = self.width
        if self.height is not None:
            data["height"] = self.height
        return data


class FakeShape:
    def __init__(self, name: str = "shape") -> None:
        self.name = name
        self.BoundBox = SimpleNamespace(ZMin=0.0, ZLength=3.0)
        self.cut_inputs = []
        self.fuse_inputs = []

    def cut(self, _other):
        result = FakeShape("cut-result")
        result.cut_inputs = [_other]
        return result

    def fuse(self, other):
        result = FakeShape("fuse-result")
        result.fuse_inputs = [self, other]
        return result


class FakeBaseObject:
    def __init__(self) -> None:
        self.Name = "TopPlate"
        self.Shape = FakeShape("base")
        self.Document = SimpleNamespace(addObject=self._add_object)
        self.created = []

    def _add_object(self, _type_name: str, name: str):
        obj = SimpleNamespace(Name=name, Shape=None)
        self.created.append(obj)
        return obj


def test_apply_cutouts_uses_in_memory_shapes(monkeypatch):
    builder = ControllerBuilder(doc="doc")
    monkeypatch.setattr(
        builder,
        "resolve_components",
        lambda _components: [
                {
                    "id": "enc1",
                    "x": 10.0,
                    "y": 20.0,
                    "resolved_mechanical": SimpleNamespace(cutout=FakeShapePrimitive(shape="circle", diameter=8.0)),
                }
            ],
        )
    monkeypatch.setattr(
        "ocw_workbench.generator.controller_builder.shapes.make_cylinder_shape",
        lambda radius, height: SimpleNamespace(radius=radius, height=height, copy=lambda: SimpleNamespace(translate=lambda *_args: None)),
    )
    monkeypatch.setattr(
        "ocw_workbench.generator.controller_builder.shapes.translate_shape",
        lambda shape, x=0, y=0, z=0: SimpleNamespace(shape=shape, x=x, y=y, z=z),
    )

    base = FakeBaseObject()
    result = builder.apply_cutouts(base, components=["ignored"])

    assert result is base
    assert result.Shape.name == "cut-result"
    assert len(base.created) == 0


def test_apply_cutouts_uses_single_composite_cut(monkeypatch):
    builder = ControllerBuilder(doc="doc")
    monkeypatch.setattr(
        builder,
        "resolve_components",
        lambda _components: [
                {
                    "id": "a",
                    "x": 10.0,
                    "y": 20.0,
                    "rotation": 0.0,
                    "resolved_mechanical": SimpleNamespace(cutout=FakeShapePrimitive(shape="circle", diameter=8.0)),
                },
                {
                    "id": "b",
                    "x": 40.0,
                    "y": 50.0,
                    "rotation": 0.0,
                    "resolved_mechanical": SimpleNamespace(cutout=FakeShapePrimitive(shape="circle", diameter=8.0)),
                },
            ],
        )
    tool_shapes = [FakeShape("tool-a"), FakeShape("tool-b")]
    monkeypatch.setattr(
        builder,
        "_create_cutout_shape",
        lambda **_kwargs: tool_shapes.pop(0),
    )

    base = FakeBaseObject()
    result = builder.apply_cutouts(base, components=["ignored"])

    assert result is base
    assert result.Shape.name == "cut-result"
    assert len(result.Shape.cut_inputs) == 1
    assert result.Shape.cut_inputs[0].name == "fuse-result"


def test_apply_cutouts_warns_when_rect_cutouts_overlap(monkeypatch):
    builder = ControllerBuilder(doc="doc")
    monkeypatch.setattr(
        builder,
        "build_cutout_primitives",
        lambda _components: [
            {
                "component_id": "pad1",
                "feature": "cutout",
                "shape": "rect",
                "x": 20.0,
                "y": 20.0,
                "width": 30.0,
                "height": 30.0,
                "rotation": 0.0,
            },
            {
                "component_id": "pad2",
                "feature": "cutout",
                "shape": "rect",
                "x": 35.0,
                "y": 20.0,
                "width": 30.0,
                "height": 30.0,
                "rotation": 0.0,
            },
        ],
    )
    monkeypatch.setattr(
        builder,
        "resolve_components",
        lambda _components: [
            {
                "id": "pad1",
                "x": 20.0,
                "y": 20.0,
                "rotation": 0.0,
                "resolved_mechanical": SimpleNamespace(cutout=SimpleNamespace(shape="rect", width=30.0, height=30.0)),
            },
            {
                "id": "pad2",
                "x": 35.0,
                "y": 20.0,
                "rotation": 0.0,
                "resolved_mechanical": SimpleNamespace(cutout=SimpleNamespace(shape="rect", width=30.0, height=30.0)),
            },
        ],
    )
    monkeypatch.setattr(
        builder,
        "_create_cutout_shape",
        lambda **_kwargs: FakeShape("tool"),
    )
    warnings = []
    monkeypatch.setattr("ocw_workbench.generator.controller_builder.LOGGER.warning", lambda message, *args: warnings.append(message % args if args else message))

    base = FakeBaseObject()
    builder.apply_cutouts(base, components=["ignored"])

    assert any("overlap" in warning for warning in warnings)


def test_cutout_boolean_plan_collects_tools_and_diagnostics(monkeypatch):
    builder = ControllerBuilder(doc="doc")
    base = FakeBaseObject()
    monkeypatch.setattr(
        builder,
        "build_cutout_primitives",
        lambda _components: [
            {
                "component_id": "pad1",
                "feature": "cutout",
                "shape": "rect",
                "x": 20.0,
                "y": 20.0,
                "width": 30.0,
                "height": 30.0,
                "rotation": 0.0,
            },
            {
                "component_id": "pad2",
                "feature": "cutout",
                "shape": "rect",
                "x": 35.0,
                "y": 20.0,
                "width": 30.0,
                "height": 30.0,
                "rotation": 0.0,
            },
        ],
    )
    monkeypatch.setattr(
        builder,
        "resolve_components",
        lambda _components: [
            {
                "id": "pad1",
                "x": 20.0,
                "y": 20.0,
                "rotation": 0.0,
                "resolved_mechanical": SimpleNamespace(cutout=SimpleNamespace(shape="rect", width=30.0, height=30.0)),
            },
            {
                "id": "pad2",
                "x": 35.0,
                "y": 20.0,
                "rotation": 0.0,
                "resolved_mechanical": SimpleNamespace(cutout=SimpleNamespace(shape="rect", width=30.0, height=30.0)),
            },
        ],
    )

    plan = builder.plan_cutout_boolean(base, components=["ignored"])

    assert [tool.component_id for tool in plan.tools] == ["pad1", "pad2"]
    assert plan.tools[0].cut_height == 3.0
    assert plan.tools[0].z_start == 0.0
    assert any("overlap" in diagnostic for diagnostic in plan.diagnostics)


def test_overlay_renderer_materializes_single_overlay_object(monkeypatch):
    from ocw_workbench.gui.overlay.renderer import OverlayRenderer

    created = []

    class FakeOverlayObject:
        def __init__(self, name: str) -> None:
            self.Name = name
            self.Label = name
            self.PropertiesList = []
            self.ViewObject = SimpleNamespace(Object=self, Proxy=None)

        def addProperty(self, _type_name: str, name: str, _group: str, _doc: str) -> None:
            if name not in self.PropertiesList:
                self.PropertiesList.append(name)
                setattr(self, name, "")

        def setEditorMode(self, _name: str, _mode: int) -> None:
            return

    class FakeDoc:
        def __init__(self) -> None:
            self.Objects = []
            self.recompute_count = 0

        def addObject(self, _type_name: str, name: str):
            obj = FakeOverlayObject(name)
            self.Objects.append(obj)
            created.append(obj)
            return obj

        def removeObject(self, name: str) -> None:
            self.Objects = [obj for obj in self.Objects if obj.Name != name]

        def recompute(self) -> None:
            self.recompute_count += 1

    doc = FakeDoc()
    renderer = OverlayRenderer()
    payload = renderer.render(
        doc,
        {
            "enabled": True,
            "controller_height": 10.0,
            "items": [
                {"id": "surface", "type": "rect", "geometry": {"x": 10.0, "y": 10.0, "width": 20.0, "height": 10.0}, "style": {}},
                {"id": "line", "type": "line", "geometry": {"start_x": 0.0, "start_y": 0.0, "end_x": 5.0, "end_y": 5.0}, "style": {}},
            ],
        },
    )

    assert len(created) == 1
    assert len(doc.Objects) == 1
    assert created[0].Name == "OCW_Overlay"
    assert json.loads(created[0].OverlayPayload)["summary"]["render_item_count"] == 2
    assert payload["summary"]["render_path"] == "featurepython-headless"
    assert payload["summary"]["render_item_count"] == 2
    assert payload["summary"]["dropped_item_count"] == 0
    assert doc.recompute_count == 0


def test_overlay_renderer_drops_degenerate_and_text_items(monkeypatch):
    from ocw_workbench.gui.overlay.renderer import OverlayRenderer

    class FakeOverlayObject:
        def __init__(self, name: str) -> None:
            self.Name = name
            self.Label = name
            self.PropertiesList = []
            self.ViewObject = SimpleNamespace(Object=self, Proxy=None)

        def addProperty(self, _type_name: str, name: str, _group: str, _doc: str) -> None:
            if name not in self.PropertiesList:
                self.PropertiesList.append(name)
                setattr(self, name, "")

        def setEditorMode(self, _name: str, _mode: int) -> None:
            return

    class FakeDoc:
        def __init__(self) -> None:
            self.Objects = [SimpleNamespace(Name="OCW_OVERLAY_old", Label="OCW_OVERLAY_old")]

        def addObject(self, _type_name: str, name: str):
            obj = FakeOverlayObject(name)
            self.Objects.append(obj)
            return obj

        def removeObject(self, name: str) -> None:
            self.Objects = [obj for obj in self.Objects if obj.Name != name]

        def recompute(self) -> None:
            return

    doc = FakeDoc()
    renderer = OverlayRenderer()
    payload = renderer.render(
        doc,
        {
            "enabled": True,
            "controller_height": 8.0,
            "items": [
                {"id": "surface", "type": "rect", "geometry": {"x": 10.0, "y": 10.0, "width": 20.0, "height": 10.0}, "style": {}},
                {"id": "bad-rect", "type": "rect", "geometry": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 10.0}, "style": {}},
                {"id": "bad-circle", "type": "circle", "geometry": {"x": 0.0, "y": 0.0, "diameter": 0.0}, "style": {}},
                {"id": "bad-line", "type": "line", "geometry": {"start_x": 1.0, "start_y": 1.0, "end_x": 1.0, "end_y": 1.0}, "style": {}},
                {"id": "label", "type": "text_marker", "geometry": {"x": 5.0, "y": 5.0}, "style": {}, "label": "Hello"},
            ],
        },
    )

    assert len(doc.Objects) == 1
    assert doc.Objects[0].Name == "OCW_Overlay"
    assert payload["summary"]["render_item_count"] == 2
    assert payload["summary"]["dropped_item_count"] == 3
    assert payload["summary"]["render_path"] == "featurepython-headless"
    assert payload["summary"]["dropped_reasons"] == {
        "degenerate_rect": 1,
        "degenerate_circle": 1,
        "degenerate_line": 1,
    }


def test_overlay_renderer_accepts_slot_and_drops_degenerate_slot():
    from ocw_workbench.gui.overlay.renderer import OverlayRenderer

    class FakeOverlayObject:
        def __init__(self, name: str) -> None:
            self.Name = name
            self.Label = name
            self.PropertiesList = []
            self.ViewObject = SimpleNamespace(Object=self, Proxy=None)

        def addProperty(self, _type_name: str, name: str, _group: str, _doc: str) -> None:
            if name not in self.PropertiesList:
                self.PropertiesList.append(name)
                setattr(self, name, "")

        def setEditorMode(self, _name: str, _mode: int) -> None:
            return

    class FakeDoc:
        def __init__(self) -> None:
            self.Objects = []

        def addObject(self, _type_name: str, name: str):
            obj = FakeOverlayObject(name)
            self.Objects.append(obj)
            return obj

        def getObject(self, name: str):
            for obj in self.Objects:
                if obj.Name == name:
                    return obj
            return None

        def removeObject(self, name: str) -> None:
            self.Objects = [obj for obj in self.Objects if obj.Name != name]

        def recompute(self) -> None:
            return

    doc = FakeDoc()
    renderer = OverlayRenderer()
    payload = renderer.render(
        doc,
        {
            "enabled": True,
            "controller_height": 8.0,
            "items": [
                {"id": "slot", "type": "slot", "geometry": {"x": 20.0, "y": 20.0, "width": 53.0, "height": 2.2, "rotation": 90.0}, "style": {}},
                {"id": "bad-slot", "type": "slot", "geometry": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 2.2, "rotation": 0.0}, "style": {}},
            ],
        },
    )

    assert len(doc.Objects) == 1
    assert payload["summary"]["render_item_count"] == 1
    assert payload["summary"]["dropped_item_count"] == 1
    assert payload["summary"]["dropped_reasons"] == {"degenerate_slot": 1}


def test_overlay_renderer_rotates_rect_items(monkeypatch):
    from ocw_workbench.gui.overlay.object import _rotate_point

    assert _rotate_point(4.0, 2.0, 2.0, 2.0, 90.0, 1.0) == (2.0, 4.0, 1.0)


def test_overlay_renderer_reuses_single_overlay_object_for_large_payload():
    from ocw_workbench.gui.overlay.renderer import OverlayRenderer

    class FakeOverlayObject:
        def __init__(self, name: str) -> None:
            self.Name = name
            self.Label = name
            self.PropertiesList = []
            self.ViewObject = SimpleNamespace(Object=self, Proxy=None)

        def addProperty(self, _type_name: str, name: str, _group: str, _doc: str) -> None:
            if name not in self.PropertiesList:
                self.PropertiesList.append(name)
                setattr(self, name, "")

        def setEditorMode(self, _name: str, _mode: int) -> None:
            return

    class FakeDoc:
        def __init__(self) -> None:
            self.Objects = []

        def addObject(self, _type_name: str, name: str):
            obj = FakeOverlayObject(name)
            self.Objects.append(obj)
            return obj

        def getObject(self, name: str):
            for obj in self.Objects:
                if obj.Name == name:
                    return obj
            return None

        def removeObject(self, name: str) -> None:
            self.Objects = [obj for obj in self.Objects if obj.Name != name]

        def recompute(self) -> None:
            return

    items = [
        {"id": f"line:{index}", "type": "line", "geometry": {"start_x": float(index), "start_y": 0.0, "end_x": float(index), "end_y": 10.0}, "style": {}}
        for index in range(320)
    ]
    doc = FakeDoc()
    renderer = OverlayRenderer()

    first = renderer.render(doc, {"enabled": True, "controller_height": 10.0, "items": items})
    second = renderer.render(doc, {"enabled": True, "controller_height": 10.0, "items": items})

    assert len(doc.Objects) == 1
    assert doc.Objects[0].Name == "OCW_Overlay"
    assert first["summary"]["render_item_count"] == 320
    assert second["summary"]["render_item_count"] == 320


def test_userdata_base_dir_uses_home_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("OCW_USERDATA_DIR", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setitem(sys.modules, "FreeCAD", None)

    base_dir = _default_base_dir()

    assert base_dir == str(tmp_path / ".local" / "state" / "open-controller-workbench")

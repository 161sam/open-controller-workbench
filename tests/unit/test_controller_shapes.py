from types import SimpleNamespace

from ocf_freecad.domain.component import Component
from ocf_freecad.domain.controller import Controller
from ocf_freecad.generator.controller_builder import ControllerBuilder


class FakeShape:
    def __init__(self, kind: str, **data) -> None:
        self.kind = kind
        self.data = dict(data)
        self.cut_tools = []
        self.fused = []
        self.translations = []

    def copy(self):
        clone = FakeShape(self.kind, **self.data)
        clone.cut_tools = list(self.cut_tools)
        clone.fused = list(self.fused)
        clone.translations = list(self.translations)
        return clone

    def translate(self, vector) -> None:
        self.translations.append((vector.x, vector.y, vector.z))

    def cut(self, other):
        result = FakeShape("cut", base=self, tool=other)
        result.cut_tools = [other]
        return result

    def fuse(self, other):
        result = FakeShape("fuse", left=self, right=other)
        result.fused = [self, other]
        return result


class FakeVector:
    def __init__(self, x: float, y: float, z: float) -> None:
        self.x = x
        self.y = y
        self.z = z


class FakeDoc:
    def __init__(self) -> None:
        self.created = []

    def addObject(self, _type_name: str, name: str):
        obj = SimpleNamespace(Name=name, Label=name, Shape=None)
        self.created.append(obj)
        return obj


def test_body_uses_hollow_shell_geometry(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "FreeCAD", SimpleNamespace(Vector=FakeVector))
    monkeypatch.setattr("ocf_freecad.generator.controller_builder.shapes.make_surface_prism_shape", _fake_make_surface_prism_shape)
    doc = FakeDoc()
    builder = ControllerBuilder(doc=doc)
    controller = Controller(
        "rect",
        120,
        80,
        30,
        3,
        wall_thickness=3,
        bottom_thickness=4,
        lid_inset=2,
    )

    body = builder.build_body(controller)

    assert body.Name == "ControllerBody"
    assert body.Shape.kind == "cut"
    cavity = body.Shape.data["tool"]
    assert cavity.kind == "rectangle"
    assert cavity.data["width"] == 114
    assert cavity.data["height"] == 74
    assert cavity.data["prism_height"] == 23
    assert cavity.translations == [(3, 3, 4)]


def test_top_plate_adds_inner_lid_tongue(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "FreeCAD", SimpleNamespace(Vector=FakeVector))
    monkeypatch.setattr("ocf_freecad.generator.controller_builder.shapes.make_surface_prism_shape", _fake_make_surface_prism_shape)
    doc = FakeDoc()
    builder = ControllerBuilder(doc=doc)
    controller = Controller(
        "rect",
        120,
        80,
        30,
        3,
        wall_thickness=3,
        bottom_thickness=3,
        lid_inset=2,
        inner_clearance=0.5,
    )

    top = builder.build_top_plate(controller)

    assert top.Name == "TopPlate"
    assert top.Shape.kind == "fuse"
    lid_tongue = top.Shape.data["right"]
    assert lid_tongue.kind == "rectangle"
    assert lid_tongue.data["width"] == 113.0
    assert lid_tongue.data["height"] == 73.0
    assert lid_tongue.data["prism_height"] == 2
    assert lid_tongue.translations == [(3.5, 3.5, 25)]


def test_rounded_rect_surface_is_used_for_shell(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "FreeCAD", SimpleNamespace(Vector=FakeVector))
    monkeypatch.setattr("ocf_freecad.generator.controller_builder.shapes.make_surface_prism_shape", _fake_make_surface_prism_shape)
    doc = FakeDoc()
    builder = ControllerBuilder(doc=doc)
    controller = Controller(
        "rounded",
        120,
        80,
        30,
        3,
        wall_thickness=4,
        surface={"shape": "rounded_rect", "corner_radius": 8},
    )

    body = builder.build_body(controller)

    assert body.Shape.kind == "cut"
    outer = body.Shape.data["base"]
    inner = body.Shape.data["tool"]
    assert outer.kind == "rounded_rect"
    assert outer.data["corner_radius"] == 8
    assert inner.kind == "rounded_rect"
    assert inner.data["corner_radius"] == 4


def test_cutouts_remain_relative_to_controller_coordinates():
    builder = ControllerBuilder(doc=None)
    component = Component(
        id="enc1",
        type="encoder",
        x=40,
        y=30,
        library_ref="alps_ec11e15204a3",
    )

    cutouts = builder.build_cutout_primitives([component])

    assert cutouts[0]["x"] == 40
    assert cutouts[0]["y"] == 30
    assert cutouts[0]["shape"] == "circle"


def test_polygon_surface_falls_back_to_solid_prism(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "FreeCAD", SimpleNamespace(Vector=FakeVector))
    monkeypatch.setattr("ocf_freecad.generator.controller_builder.shapes.make_surface_prism_shape", _fake_make_surface_prism_shape)
    doc = FakeDoc()
    builder = ControllerBuilder(doc=doc)
    controller = Controller(
        "poly",
        120,
        80,
        30,
        3,
        surface={"shape": "polygon", "points": [[0, 0], [120, 0], [100, 80], [0, 80]]},
    )

    body = builder.build_body(controller)

    assert body.Shape.kind == "polygon"
    assert body.Shape.data["prism_height"] == 27


def _fake_make_surface_prism_shape(surface, height):
    data = surface.to_dict()
    data["prism_height"] = height
    return FakeShape(surface.shape, **data)

from types import SimpleNamespace

import pytest

from ocw_workbench.domain.component import Component
from ocw_workbench.domain.controller import Controller
from ocw_workbench.generator.controller_builder import ControllerBuilder


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
    monkeypatch.setattr("ocw_workbench.generator.controller_builder.shapes.make_surface_prism_shape", _fake_make_surface_prism_shape)
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


def test_body_build_plan_exposes_outer_and_cavity_stages():
    builder = ControllerBuilder(doc=None)
    controller = Controller(
        "rect",
        120,
        80,
        30,
        3,
        wall_thickness=3,
        bottom_thickness=4,
    )

    plan = builder.plan_body_build(controller)

    assert plan.surface.shape == "rectangle"
    assert plan.body_height == 27
    assert plan.cavity_surface is not None
    assert plan.cavity_surface.width == 114
    assert plan.cavity_surface.height == 74
    assert plan.cavity_offset == (3, 3, 4)
    assert plan.cavity_height == 23


def test_top_plate_adds_inner_lid_tongue(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "FreeCAD", SimpleNamespace(Vector=FakeVector))
    monkeypatch.setattr("ocw_workbench.generator.controller_builder.shapes.make_surface_prism_shape", _fake_make_surface_prism_shape)
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


def test_top_plate_build_plan_exposes_lid_tongue_stage():
    builder = ControllerBuilder(doc=None)
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

    plan = builder.plan_top_plate_build(controller)

    assert plan.surface.shape == "rectangle"
    assert plan.z_offset == 27
    assert plan.top_thickness == 3.0
    assert plan.tongue_surface is not None
    assert plan.tongue_surface.width == 113.0
    assert plan.tongue_surface.height == 73.0
    assert plan.tongue_offset == (3.5, 3.5, 25.0)
    assert plan.tongue_height == 2


def test_custom_fcstd_base_geometry_is_used_for_top_plate():
    service_calls = []

    class FakeFCStdService:
        def build_shape_from_config(self, config, *, extrude_height, z_offset):
            service_calls.append((config, extrude_height, z_offset))
            return FakeShape("custom_fcstd_top_plate", config=config, extrude_height=extrude_height, z_offset=z_offset)

    doc = FakeDoc()
    builder = ControllerBuilder(doc=doc, fcstd_base_geometry_service=FakeFCStdService())
    controller = Controller(
        "custom",
        120,
        80,
        30,
        3,
        surface={"shape": "rectangle", "width": 120.0, "height": 80.0},
    )
    controller.geometry = {
        "base": {
            "type": "custom_fcstd",
            "filename": "/tmp/source.FCStd",
            "target_ref": "Top::Face1",
            "origin": {"type": "manual", "offset_x": 0.0, "offset_y": 0.0},
        }
    }

    top = builder.build_top_plate(controller)

    assert top.Shape.kind == "custom_fcstd_top_plate"
    assert service_calls == [(
        controller.geometry["base"],
        3.0,
        27.0,
    )]


def test_rounded_rect_surface_is_used_for_shell(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "FreeCAD", SimpleNamespace(Vector=FakeVector))
    monkeypatch.setattr("ocw_workbench.generator.controller_builder.shapes.make_surface_prism_shape", _fake_make_surface_prism_shape)
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


def test_custom_fcstd_base_geometry_failure_bubbles_clean_error():
    class FailingFCStdService:
        def build_shape_from_config(self, config, *, extrude_height, z_offset):
            raise FileNotFoundError(config["filename"])

    builder = ControllerBuilder(doc=None, fcstd_base_geometry_service=FailingFCStdService())
    controller = Controller(
        "custom",
        120,
        80,
        30,
        3,
        surface={"shape": "rectangle", "width": 120.0, "height": 80.0},
    )
    controller.geometry = {
        "base": {
            "type": "custom_fcstd",
            "filename": "/tmp/missing.FCStd",
            "target_ref": "Top::Face1",
        }
    }

    with pytest.raises(FileNotFoundError, match="missing.FCStd"):
        builder.build_top_plate(controller)


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


def test_rect_cutout_shape_rotates_around_component_center(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "FreeCAD", SimpleNamespace(Vector=FakeVector))
    rotate_calls = []
    builder = ControllerBuilder(doc=None)

    monkeypatch.setattr("ocw_workbench.generator.controller_builder.shapes.make_rect_prism_shape", lambda width, depth, height: FakeShape("rect_cutout", width=width, depth=depth, height=height))
    monkeypatch.setattr("ocw_workbench.generator.controller_builder.shapes.translate_shape", lambda shape, x=0, y=0, z=0: FakeShape("translated", shape=shape, x=x, y=y, z=z))
    monkeypatch.setattr(
        "ocw_workbench.generator.controller_builder.shapes.rotate_shape",
        lambda shape, angle_deg, center=(0, 0, 0), axis=(0, 0, 1): rotate_calls.append((angle_deg, center, axis)) or FakeShape("rotated", shape=shape, angle=angle_deg, center=center),
    )

    shape = builder._create_cutout_shape(
        x=40.0,
        y=30.0,
        rotation=90.0,
        cutout=SimpleNamespace(shape="rect", width=12.0, height=8.0),
        cut_height=3.0,
        z_start=27.0,
    )

    assert shape.kind == "rotated"
    assert rotate_calls == [(90.0, (40.0, 30.0, 27.0), (0, 0, 1))]


def test_rect_cutout_shape_without_rotation_stays_unrotated(monkeypatch):
    builder = ControllerBuilder(doc=None)
    rotate_calls = []

    monkeypatch.setattr("ocw_workbench.generator.controller_builder.shapes.make_rect_prism_shape", lambda width, depth, height: FakeShape("rect_cutout", width=width, depth=depth, height=height))
    monkeypatch.setattr("ocw_workbench.generator.controller_builder.shapes.translate_shape", lambda shape, x=0, y=0, z=0: FakeShape("translated", shape=shape, x=x, y=y, z=z))
    monkeypatch.setattr(
        "ocw_workbench.generator.controller_builder.shapes.rotate_shape",
        lambda shape, angle_deg, center=(0, 0, 0), axis=(0, 0, 1): rotate_calls.append((angle_deg, center, axis)) or FakeShape("rotated", shape=shape),
    )

    shape = builder._create_cutout_shape(
        x=40.0,
        y=30.0,
        rotation=0.0,
        cutout=SimpleNamespace(shape="rect", width=12.0, height=8.0),
        cut_height=3.0,
        z_start=27.0,
    )

    assert shape.kind == "translated"
    assert rotate_calls == []


def test_slot_cutout_shape_uses_slot_factory_and_rotates(monkeypatch):
    builder = ControllerBuilder(doc=None)
    rotate_calls = []

    monkeypatch.setattr("ocw_workbench.generator.controller_builder.shapes.make_slot_prism_shape", lambda width, depth, height: FakeShape("slot_cutout", width=width, depth=depth, height=height))
    monkeypatch.setattr("ocw_workbench.generator.controller_builder.shapes.translate_shape", lambda shape, x=0, y=0, z=0: FakeShape("translated", shape=shape, x=x, y=y, z=z))
    monkeypatch.setattr(
        "ocw_workbench.generator.controller_builder.shapes.rotate_shape",
        lambda shape, angle_deg, center=(0, 0, 0), axis=(0, 0, 1): rotate_calls.append((angle_deg, center, axis)) or FakeShape("rotated", shape=shape, angle=angle_deg, center=center),
    )

    shape = builder._create_cutout_shape(
        x=60.0,
        y=25.0,
        rotation=90.0,
        cutout=SimpleNamespace(shape="slot", width=53.0, height=2.2),
        cut_height=3.0,
        z_start=27.0,
    )

    assert shape.kind == "rotated"
    assert shape.data["shape"].data["shape"].kind == "slot_cutout"
    assert rotate_calls == [(90.0, (60.0, 25.0, 27.0), (0, 0, 1))]


def test_polygon_surface_falls_back_to_solid_prism(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "FreeCAD", SimpleNamespace(Vector=FakeVector))
    monkeypatch.setattr("ocw_workbench.generator.controller_builder.shapes.make_surface_prism_shape", _fake_make_surface_prism_shape)
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

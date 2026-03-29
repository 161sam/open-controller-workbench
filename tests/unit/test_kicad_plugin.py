from __future__ import annotations

from pathlib import Path

import pytest

import ocw_kicad_plugin
from ocw_kicad.board import create_board_outline
from ocw_kicad.keepout_renderer import render_keepouts
from ocw_kicad.loader import load_layout
from ocw_kicad.placer import place_mounting_holes
from ocw_kicad.plugin import build_roundtrip_import_descriptor, import_layout


class FakeFootprint:
    def __init__(self, library_name: str, footprint_name: str) -> None:
        self.kind = "footprint"
        self.library_name = library_name
        self.footprint_name = footprint_name
        self.position = None
        self.rotation = None
        self.layer = "F.Cu"
        self.reference = None
        self.flipped = False

    def SetPosition(self, position) -> None:
        self.position = position

    def SetOrientation(self, angle) -> None:
        self.rotation = angle

    def SetLayer(self, layer) -> None:
        self.layer = layer

    def GetLayer(self):
        return self.layer

    def Flip(self, position, _mirror) -> None:
        self.flipped = True
        self.position = position

    def SetReference(self, reference: str) -> None:
        self.reference = reference


class FakeShape:
    def __init__(self, _board) -> None:
        self.kind = "shape"
        self.shape = None
        self.layer = None
        self.start = None
        self.end = None
        self.center = None
        self.angle = None

    def SetShape(self, shape) -> None:
        self.shape = shape

    def SetLayer(self, layer) -> None:
        self.layer = layer

    def SetStart(self, point) -> None:
        self.start = point

    def SetEnd(self, point) -> None:
        self.end = point

    def SetCenter(self, point) -> None:
        self.center = point

    def SetArcAngleAndEnd(self, angle) -> None:
        self.angle = angle


class FakeBoard:
    def __init__(self) -> None:
        self.items = []

    def Add(self, item) -> None:
        self.items.append(item)

    def Remove(self, item) -> None:
        self.items.remove(item)

    def GetDrawings(self):
        return [item for item in self.items if getattr(item, "kind", None) == "shape"]

    def GetFootprints(self):
        return [item for item in self.items if getattr(item, "kind", None) == "footprint"]


class FakeAngle:
    def __init__(self, value: float, _unit: str) -> None:
        self.value = value


class FakePcbnew:
    F_Cu = "F.Cu"
    B_Cu = "B.Cu"
    Edge_Cuts = "Edge.Cuts"
    Dwgs_User = "Dwgs.User"
    F_CrtYd = "F.CrtYd"
    SHAPE_T_SEGMENT = "segment"
    SHAPE_T_ARC = "arc"
    SHAPE_T_CIRCLE = "circle"
    SHAPE_T_RECT = "rect"
    DEGREES_T = "degrees"

    def __init__(self) -> None:
        self._board = FakeBoard()
        self.refreshed = False

    def EDA_ANGLE(self, value: float, unit: str):
        return FakeAngle(value, unit)

    def FromMM(self, value: float) -> int:
        return int(round(value * 1_000_000))

    def VECTOR2I(self, x: int, y: int):
        return (x, y)

    def GetBoard(self):
        return self._board

    def FootprintLoad(self, library_name: str, footprint_name: str):
        known = {
            ("RotaryEncoder_Alps", "EC11E_Vertical"),
            ("Button_Switch_THT", "SW_PUSH_6mm"),
            ("MountingHole", "MountingHole_3mm_NPTH"),
        }
        if (library_name, footprint_name) not in known:
            return None
        return FakeFootprint(library_name, footprint_name)

    def PCB_SHAPE(self, board):
        return FakeShape(board)

    def Refresh(self) -> None:
        self.refreshed = True


def test_load_layout_valid_fixture():
    payload = load_layout("tests/fixtures/controller.kicad.layout.yaml")

    assert payload["board"]["name"] == "TestBoard"
    assert len(payload["footprints"]) == 2
    assert len(payload["mounting_holes"]) == 2
    assert len(payload["keepouts"]) == 2
    assert payload["mechanical_stackup"] == {}
    assert payload["mounting"] == {}
    assert payload["roundtrip"] == {}


def test_roundtrip_descriptor_uses_defaults_for_basic_layout():
    descriptor = build_roundtrip_import_descriptor("tests/fixtures/controller.kicad.layout.yaml")

    assert descriptor["import_strategy"] == "kicad_stepup_board_import"
    assert descriptor["component_reference_key"] == "component_id"
    assert descriptor["coordinate_system"] == "ocw_top_left_mm"


def test_import_layout_creates_outline_holes_keepouts_and_footprints():
    pcbnew = FakePcbnew()

    board = import_layout("tests/fixtures/controller.kicad.layout.yaml", pcbnew_module=pcbnew)
    footprints = board.GetFootprints()
    drawings = board.GetDrawings()

    assert board is pcbnew.GetBoard()
    assert len(footprints) == 4
    assert len(drawings) == 13
    assert footprints[0].reference == "MH1"
    assert footprints[1].reference == "MH2"
    assert footprints[2].reference == "ENC1"
    assert footprints[2].position == (40_000_000, 30_000_000)
    assert footprints[3].layer == "B.Cu"
    assert footprints[3].flipped is True
    assert pcbnew.refreshed is True


def test_board_outline_cleanup_is_idempotent():
    pcbnew = FakePcbnew()
    board = pcbnew.GetBoard()
    layout = load_layout("tests/fixtures/controller.kicad.layout.yaml")

    create_board_outline(board, layout["board"], pcbnew)
    create_board_outline(board, layout["board"], pcbnew)

    assert len(board.GetDrawings()) == 8


def test_mounting_holes_cleanup_is_idempotent():
    pcbnew = FakePcbnew()
    board = pcbnew.GetBoard()
    layout = load_layout("tests/fixtures/controller.kicad.layout.yaml")

    placed_first = place_mounting_holes(board, layout["mounting_holes"], pcbnew)
    placed_second = place_mounting_holes(board, layout["mounting_holes"], pcbnew)
    holes = [item for item in board.GetFootprints() if item.reference.startswith("MH")]

    assert placed_first == 2
    assert placed_second == 2
    assert len(holes) == 2


def test_keepout_cleanup_is_idempotent():
    pcbnew = FakePcbnew()
    board = pcbnew.GetBoard()
    layout = load_layout("tests/fixtures/controller.kicad.layout.yaml")

    rendered_first = render_keepouts(board, layout["keepouts"], pcbnew)
    rendered_second = render_keepouts(board, layout["keepouts"], pcbnew)

    assert rendered_first == 2
    assert rendered_second == 2
    assert len(board.GetDrawings()) == 5


def test_import_layout_skips_unknown_footprint(tmp_path: Path):
    layout_path = tmp_path / "missing.yaml"
    layout_path.write_text(
        "\n".join(
            [
                "board:",
                "  width_mm: 20.0",
                "  height_mm: 10.0",
                "footprints:",
                "  - footprint: \"Missing:Thing\"",
                "    x_mm: 10.0",
                "    y_mm: 15.0",
                "    side: \"top\"",
                "mounting_holes: []",
                "keepouts: []",
            ]
        ),
        encoding="utf-8",
    )
    pcbnew = FakePcbnew()

    board = import_layout(str(layout_path), pcbnew_module=pcbnew)

    assert len(board.GetFootprints()) == 0
    assert len(board.GetDrawings()) == 4


def test_import_layout_rejects_unknown_side(tmp_path: Path):
    layout_path = tmp_path / "bad_side.yaml"
    layout_path.write_text(
        "\n".join(
            [
                "board:",
                "  width_mm: 20.0",
                "  height_mm: 10.0",
                "footprints:",
                "  - footprint: \"RotaryEncoder_Alps:EC11E_Vertical\"",
                "    x_mm: 10.0",
                "    y_mm: 15.0",
                "    side: \"left\"",
                "mounting_holes: []",
                "keepouts: []",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown side: left"):
        import_layout(str(layout_path), pcbnew_module=FakePcbnew())


def test_import_layout_rejects_invalid_coordinates(tmp_path: Path):
    layout_path = tmp_path / "bad_coord.yaml"
    layout_path.write_text(
        "\n".join(
            [
                "board:",
                "  width_mm: 20.0",
                "  height_mm: 10.0",
                "footprints:",
                "  - footprint: \"RotaryEncoder_Alps:EC11E_Vertical\"",
                "    x_mm: \"bad\"",
                "    y_mm: 15.0",
                "    side: \"top\"",
                "mounting_holes: []",
                "keepouts: []",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Missing or invalid numeric field 'x_mm'"):
        import_layout(str(layout_path), pcbnew_module=FakePcbnew())


def test_import_layout_rejects_negative_dimensions(tmp_path: Path):
    layout_path = tmp_path / "bad_board.yaml"
    layout_path.write_text(
        "\n".join(
            [
                "board:",
                "  width_mm: -1.0",
                "  height_mm: 10.0",
                "footprints: []",
                "mounting_holes: []",
                "keepouts: []",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Field 'width_mm' must be positive"):
        import_layout(str(layout_path), pcbnew_module=FakePcbnew())


def test_import_layout_warns_and_skips_unknown_keepout_shape(tmp_path: Path, capsys):
    layout_path = tmp_path / "bad_keepout.yaml"
    layout_path.write_text(
        "\n".join(
            [
                "board:",
                "  width_mm: 10.0",
                "  height_mm: 10.0",
                "footprints: []",
                "mounting_holes: []",
                "keepouts:",
                "  - id: bad1",
                "    type: triangle",
            ]
        ),
        encoding="utf-8",
    )

    board = import_layout(str(layout_path), pcbnew_module=FakePcbnew())
    captured = capsys.readouterr()

    assert "Skipping keepout bad1: invalid shape 'triangle'" in captured.out
    assert len(board.GetDrawings()) == 4


def test_console_import_alias_exposes_import_layout():
    assert ocw_kicad_plugin.import_layout is import_layout

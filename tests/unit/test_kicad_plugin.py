from __future__ import annotations

from pathlib import Path

import pytest

import ocf_kicad_plugin
from ocf_kicad.loader import load_layout
from ocf_kicad.plugin import import_layout


class FakeFootprint:
    def __init__(self, library_name: str, footprint_name: str) -> None:
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


class FakeBoard:
    def __init__(self) -> None:
        self.items = []

    def Add(self, item) -> None:
        self.items.append(item)


class FakePcbnew:
    F_Cu = "F.Cu"
    B_Cu = "B.Cu"

    def __init__(self) -> None:
        self._board = FakeBoard()
        self.refreshed = False

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
        }
        if (library_name, footprint_name) not in known:
            return None
        return FakeFootprint(library_name, footprint_name)

    def Refresh(self) -> None:
        self.refreshed = True


def test_load_layout_valid_fixture():
    payload = load_layout("tests/fixtures/controller.kicad.layout.yaml")

    assert payload["board"]["name"] == "TestBoard"
    assert len(payload["footprints"]) == 2


def test_import_layout_places_expected_number_of_footprints():
    pcbnew = FakePcbnew()

    board = import_layout("tests/fixtures/controller.kicad.layout.yaml", pcbnew_module=pcbnew)

    assert board is pcbnew.GetBoard()
    assert len(board.items) == 2
    assert board.items[0].reference == "ENC1"
    assert board.items[0].position == (40_000_000, 30_000_000)
    assert board.items[1].layer == "B.Cu"
    assert board.items[1].flipped is True
    assert pcbnew.refreshed is True


def test_import_layout_skips_unknown_footprint(tmp_path: Path):
    layout_path = tmp_path / "missing.yaml"
    layout_path.write_text(
        "\n".join(
            [
                "board: {}",
                "footprints:",
                "  - footprint: \"Missing:Thing\"",
                "    x_mm: 10.0",
                "    y_mm: 15.0",
                "    side: \"top\"",
            ]
        ),
        encoding="utf-8",
    )
    pcbnew = FakePcbnew()

    board = import_layout(str(layout_path), pcbnew_module=pcbnew)

    assert len(board.items) == 0


def test_import_layout_rejects_unknown_side(tmp_path: Path):
    layout_path = tmp_path / "bad_side.yaml"
    layout_path.write_text(
        "\n".join(
            [
                "board: {}",
                "footprints:",
                "  - footprint: \"RotaryEncoder_Alps:EC11E_Vertical\"",
                "    x_mm: 10.0",
                "    y_mm: 15.0",
                "    side: \"left\"",
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
                "board: {}",
                "footprints:",
                "  - footprint: \"RotaryEncoder_Alps:EC11E_Vertical\"",
                "    x_mm: \"bad\"",
                "    y_mm: 15.0",
                "    side: \"top\"",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Missing or invalid numeric field 'x_mm'"):
        import_layout(str(layout_path), pcbnew_module=FakePcbnew())


def test_console_import_alias_exposes_import_layout():
    assert ocf_kicad_plugin.import_layout is import_layout

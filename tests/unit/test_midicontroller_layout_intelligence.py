from __future__ import annotations

import pytest

from ocw_workbench.plugins.activation import activate_plugin
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.plugin_service import reset_plugin_service
from ocw_workbench.templates.generator import TemplateGenerator
from ocw_workbench.templates.registry import TemplateRegistry
from plugins.plugin_midicontroller.layout_intelligence import (
    build_layout_intelligence,
    build_suggested_addition,
    suggest_component_placement,
)


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.recompute_count = 0
        self.transactions: list[tuple[str, str | None]] = []

    def recompute(self) -> None:
        self.recompute_count += 1

    def openTransaction(self, label: str) -> None:
        self.transactions.append(("open", label))

    def commitTransaction(self) -> None:
        self.transactions.append(("commit", None))

    def abortTransaction(self) -> None:
        self.transactions.append(("abort", None))


@pytest.fixture(autouse=True)
def _activate_midicontroller():
    reset_plugin_service()
    activate_plugin("midicontroller")
    yield
    reset_plugin_service()


def test_midicontroller_templates_expose_layout_intelligence_metadata() -> None:
    templates = {item["template"]["id"]: item for item in TemplateRegistry().list_templates()}

    pad_grid = templates["pad_grid_4x4"]["metadata"]
    encoder_bank = templates["encoder_module"]["metadata"]

    assert pad_grid["smart_defaults"]["primary_group_role"] == "performance_pad_matrix"
    assert [item["id"] for item in pad_grid["suggested_additions"]] == [
        "utility_strip_right",
        "navigation_encoder_pair",
        "display_header",
    ]
    assert [item["id"] for item in encoder_bank["layout_zones"]] == [
        "encoder_bank",
        "display_header",
        "utility_row",
    ]


def test_build_layout_intelligence_returns_preview_additions_for_pad_grid() -> None:
    project = TemplateGenerator().generate_from_template("pad_grid_4x4")
    state = {
        "controller": project["controller"],
        "components": project["components"],
        "meta": {"template_id": "pad_grid_4x4", "plugin_id": "midicontroller"},
    }

    intelligence = build_layout_intelligence(
        state,
        template_payload=TemplateRegistry().get_template("pad_grid_4x4"),
        template_service=None,
        library_service=ControllerService().library_service,
    )

    suggestions = {item["id"]: item for item in intelligence["suggested_additions"]}
    assert intelligence["workflow_hint"].startswith("Use this when the pads")
    assert intelligence["workflow_card"]["template_title"] == "Finger Drum Pad Grid"
    assert intelligence["workflow_card"]["primary_action"]["id"] == "utility_strip_right"
    assert [item["id"] for item in intelligence["workflow_card"]["secondary_actions"]] == [
        "navigation_encoder_pair",
        "display_header",
    ]
    assert suggestions["utility_strip_right"]["target_zone_id"] == "right_utility_strip"
    assert suggestions["utility_strip_right"]["command_id"] == "OCW_AddUtilityStrip"
    assert suggestions["utility_strip_right"]["tooltip"].startswith("Add a right-side utility strip")
    assert len(suggestions["utility_strip_right"]["preview_components"]) == 3
    assert suggestions["display_header"]["preview_components"][0]["y"] < suggestions["utility_strip_right"]["preview_components"][0]["y"]


def test_suggest_component_placement_prefers_contextual_zone_for_display() -> None:
    project = TemplateGenerator().generate_from_template("encoder_module")
    service = ControllerService()
    state = {
        "controller": project["controller"],
        "components": project["components"],
        "meta": {"template_id": "encoder_module", "plugin_id": "midicontroller"},
    }

    suggestion = suggest_component_placement(
        state,
        "adafruit_oled_096_i2c_ssd1306",
        template_payload=TemplateRegistry().get_template("encoder_module"),
        library_service=service.library_service,
    )

    assert suggestion["placement_preference"] == "centered_above_group"
    assert suggestion["zone_id"] == "display_header"
    assert suggestion["y"] <= 10.0
    assert "feedback stays visually tied" in suggestion["reason"]


def test_build_suggested_addition_creates_deterministic_channel_strip_components() -> None:
    project = TemplateGenerator().generate_from_template("fader_strip")
    service = ControllerService()
    state = {
        "controller": project["controller"],
        "components": project["components"],
        "meta": {"template_id": "fader_strip", "plugin_id": "midicontroller"},
    }

    addition = build_suggested_addition(
        state,
        "channel_display",
        template_payload=TemplateRegistry().get_template("fader_strip"),
        library_service=service.library_service,
    )

    assert [component["id"] for component in addition] == ["display"]
    assert addition[0]["zone_id"] == "top_label_area"
    assert addition[0]["group_role"] == "feedback_header"
    assert addition[0]["y"] <= 10.0


def test_controller_service_exposes_layout_intelligence_in_ui_context() -> None:
    service = ControllerService()
    doc = FakeDocument()

    service.create_from_template(doc, "pad_grid_4x4")
    context = service.get_ui_context(doc)

    assert context["layout_intelligence"]["template_id"] == "pad_grid_4x4"
    assert context["layout_intelligence"]["suggested_additions"]
    assert context["layout_intelligence"]["layout_zones"][0]["id"] == "main_pad_surface"


def test_controller_service_can_apply_midicontroller_suggested_addition() -> None:
    service = ControllerService()
    doc = FakeDocument()

    service.create_from_template(doc, "pad_grid_4x4")
    before = len(service.get_state(doc)["components"])
    state = service.apply_suggested_addition(doc, "utility_strip_right")
    after = len(state["components"])

    added = [component for component in state["components"] if component.get("group_role") == "utility_strip"]
    assert after == before + 3
    assert [component["id"] for component in added] == ["shift", "scene", "mode"]
    assert all(component["zone_id"] == "right_utility_strip" for component in added)

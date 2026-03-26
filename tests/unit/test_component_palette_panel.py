from ocw_workbench.gui.panels.component_palette_panel import ComponentPaletteModel
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.recompute_count = 0

    def recompute(self) -> None:
        self.recompute_count += 1


def test_component_palette_model_filters_search_category_and_favorites():
    model = ComponentPaletteModel(
        [
            {
                "id": "enc1",
                "category": "encoder",
                "manufacturer": "Generic",
                "part_number": "EC11",
                "description": "Rotary encoder",
                "tags": ["encoder"],
                "ui": {"label": "Encoder", "category": "controls", "tags": ["rotate"], "icon": "encoder.svg"},
            },
            {
                "id": "disp1",
                "category": "display",
                "manufacturer": "Generic",
                "part_number": "OLED",
                "description": "OLED display",
                "tags": ["display"],
                "ui": {"label": "Display", "category": "displays", "tags": ["screen"], "icon": "display.svg"},
            },
        ]
    )

    controls = model.filter_components(category="controls")
    search_hits = model.filter_components(search_text="screen")
    favorites = model.filter_components(favorites_only=True, favorite_ids={"disp1"})

    assert model.categories() == ["controls", "displays"]
    assert [item["id"] for item in controls] == ["enc1"]
    assert [item["id"] for item in search_hits] == ["disp1"]
    assert [item["id"] for item in favorites] == ["disp1"]


def test_interaction_service_sets_active_component_template_without_document_sync():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo"})

    def fail_update_document(*_args, **_kwargs):
        raise AssertionError("Document sync should not be triggered for palette selection")

    controller_service.update_document = fail_update_document  # type: ignore[method-assign]
    recomputes_before = doc.recompute_count

    settings = interaction_service.set_active_component_template(doc, "omron_b3f_1000")
    favorite_settings = interaction_service.toggle_favorite_component_template(doc, "omron_b3f_1000")

    assert settings["active_component_template_id"] == "omron_b3f_1000"
    assert "omron_b3f_1000" in favorite_settings["favorite_component_template_ids"]
    assert controller_service.get_state(doc)["meta"]["ui"]["active_component_template_id"] == "omron_b3f_1000"
    assert doc.recompute_count == recomputes_before

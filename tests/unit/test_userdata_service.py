from pathlib import Path

from ocw_workbench.gui.panels.create_panel import CreatePanel
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.template_service import TemplateService
from ocw_workbench.services.userdata_service import MAX_RECENTS, UserDataService
from ocw_workbench.services.variant_service import VariantService
from ocw_workbench.userdata.persistence import UserDataPersistence


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.recompute_count = 0

    def recompute(self) -> None:
        self.recompute_count += 1


def _service(tmp_path: Path) -> UserDataService:
    persistence = UserDataPersistence(base_dir=str(tmp_path))
    return UserDataService(
        persistence=persistence,
        template_service=TemplateService(),
        variant_service=VariantService(),
        controller_service=ControllerService(),
    )


def test_favorite_toggle_persists_and_reloads(tmp_path: Path):
    service = _service(tmp_path)

    service.toggle_favorite("template", "encoder_module", name="4 Encoder Module")
    reloaded = _service(tmp_path)
    favorites = reloaded.list_favorites()

    assert len(favorites) == 1
    assert favorites[0].reference_id == "encoder_module"
    assert favorites[0].type == "template"


def test_recent_entries_are_ordered_and_limited(tmp_path: Path):
    service = _service(tmp_path)

    valid_templates = [
        "encoder_module",
        "transport_module",
        "display_nav_module",
        "fader_strip",
        "pad_grid_4x4",
    ]
    for index in range(MAX_RECENTS + 3):
        template_id = valid_templates[index % len(valid_templates)]
        service.record_recent(template_id=template_id, variant_id=None, name=f"Recent {index}")

    recents = service.list_recents()

    assert len(recents) <= len(valid_templates)
    assert recents[0].name == f"Recent {MAX_RECENTS + 2}"


def test_preset_saves_and_loads_with_variant_reference(tmp_path: Path):
    service = _service(tmp_path)

    preset = service.save_preset(
        name="Display Right",
        template_id="display_nav_module",
        variant_id="display_nav_right",
        grid_mm=2.0,
        layout_strategy="grid",
    )
    reloaded = _service(tmp_path).get_preset(preset.id)

    assert reloaded.template_id == "display_nav_module"
    assert reloaded.variant_id == "display_nav_right"
    assert reloaded.grid_mm == 2.0


def test_invalid_userdata_file_falls_back_to_defaults(tmp_path: Path):
    persistence = UserDataPersistence(base_dir=str(tmp_path))
    persistence.path.parent.mkdir(parents=True, exist_ok=True)
    persistence.path.write_text("{ invalid json", encoding="utf-8")

    service = _service(tmp_path)

    assert service.list_favorites() == []
    assert service.list_recents() == []
    assert service.list_presets() == []


def test_missing_template_and_variant_references_are_filtered_out(tmp_path: Path):
    persistence = UserDataPersistence(base_dir=str(tmp_path))
    persistence.save(
        persistence.load().__class__.from_dict(
            {
                "favorites": [{"id": "template:missing", "type": "template", "reference_id": "missing_template"}],
                "recents": [{"id": "missing:default", "type": "recent", "template_id": "missing_template"}],
                "presets": [{"id": "bad", "type": "preset", "name": "Bad", "template_id": "missing_template"}],
            }
        )
    )
    service = _service(tmp_path)

    assert service.list_favorites() == []
    assert service.list_recents() == []
    assert service.list_presets() == []


def test_create_panel_uses_recents_favorites_and_presets(tmp_path: Path):
    doc = FakeDocument()
    service = _service(tmp_path)
    panel = CreatePanel(
        doc,
        controller_service=ControllerService(),
        template_service=TemplateService(),
        variant_service=VariantService(),
        userdata_service=service,
    )

    panel.handle_template_changed()
    panel.toggle_template_favorite()
    panel.form["presets_widget"].parts["name"].setText("My Encoder Start")
    panel.save_current_preset()
    panel.create_controller()
    panel.refresh()

    assert service.list_favorites()
    assert service.list_recents()
    assert service.list_presets()

from ocw_workbench.gui.interaction.view_place_preview import load_preview_state
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.document_sync_service import SyncMode
from ocw_workbench.services.interaction_service import InteractionService


class FakeDocument:
    def __init__(self) -> None:
        self.Objects = []
        self.recompute_count = 0
        self.transactions = []

    def recompute(self) -> None:
        self.recompute_count += 1

    def openTransaction(self, label: str) -> None:
        self.transactions.append(("open", label))

    def commitTransaction(self) -> None:
        self.transactions.append(("commit", None))

    def abortTransaction(self) -> None:
        self.transactions.append(("abort", None))


def test_add_component_preview_uses_visual_only_sync_and_metadata():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0})
    calls = []

    def record_update_document(*_args, **kwargs):
        calls.append(kwargs)

    controller_service.update_document = record_update_document  # type: ignore[method-assign]
    before_state = controller_service.get_state(doc)
    before_recomputes = doc.recompute_count

    payload = interaction_service.add_component_preview(doc, "omron_b3f_1000", target_x=12.2, target_y=18.7)

    assert payload["mode"] == "place"
    assert payload["validation"]["status"] == "Valid placement"
    assert load_preview_state(doc) == payload
    assert controller_service.get_state(doc) == before_state
    assert calls == [{"mode": SyncMode.VISUAL_ONLY, "recompute": False}]
    assert doc.recompute_count == before_recomputes
    assert doc.transactions == []


def test_move_component_preview_uses_visual_only_sync_and_metadata():
    doc = FakeDocument()
    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    controller_service.create_controller(doc, {"id": "demo", "width": 100.0, "depth": 80.0})
    controller_service.add_component(doc, "omron_b3f_1000", component_id="btn1", x=20.0, y=20.0)
    calls = []
    before_transactions = list(doc.transactions)

    def record_update_document(*_args, **kwargs):
        calls.append(kwargs)

    controller_service.update_document = record_update_document  # type: ignore[method-assign]
    before_state = controller_service.get_state(doc)
    before_recomputes = doc.recompute_count

    payload = interaction_service.move_component_preview(doc, "btn1", target_x=37.2, target_y=18.4)

    assert payload["mode"] == "move"
    assert payload["component_id"] == "btn1"
    assert payload["validation"]["status"] == "Valid placement"
    assert load_preview_state(doc) == payload
    assert controller_service.get_state(doc) == before_state
    assert calls == [{"mode": SyncMode.VISUAL_ONLY, "recompute": False}]
    assert doc.recompute_count == before_recomputes
    assert doc.transactions == before_transactions

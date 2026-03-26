from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.template_service import TemplateService
from ocw_workbench.services.variant_service import VariantService
from ocw_workbench.userdata.models import FavoriteEntry, PresetEntry, RecentEntry
from ocw_workbench.userdata.persistence import UserDataPersistence
from ocw_workbench.userdata.store import UserDataStore

MAX_RECENTS = 10


class UserDataService:
    def __init__(
        self,
        persistence: UserDataPersistence | None = None,
        template_service: TemplateService | None = None,
        variant_service: VariantService | None = None,
        controller_service: ControllerService | None = None,
    ) -> None:
        self.persistence = persistence or UserDataPersistence()
        self.template_service = template_service or TemplateService()
        self.variant_service = variant_service or VariantService()
        self.controller_service = controller_service or ControllerService()

    def load_store(self) -> UserDataStore:
        return self.persistence.load()

    def list_favorites(self) -> list[FavoriteEntry]:
        store = self.load_store()
        return [entry for entry in store.favorites if self._is_resolvable_favorite(entry)]

    def is_favorite(self, entry_type: str, reference_id: str) -> bool:
        return any(entry.type == entry_type and entry.reference_id == reference_id for entry in self.list_favorites())

    def toggle_favorite(self, entry_type: str, reference_id: str, name: str | None = None) -> list[FavoriteEntry]:
        store = self.load_store()
        existing = next(
            (entry for entry in store.favorites if entry.type == entry_type and entry.reference_id == reference_id),
            None,
        )
        if existing is not None:
            store.favorites = [
                entry
                for entry in store.favorites
                if not (entry.type == entry_type and entry.reference_id == reference_id)
            ]
        else:
            store.favorites.append(
                FavoriteEntry(
                    id=f"{entry_type}:{reference_id}",
                    type=entry_type,
                    name=name,
                    reference_id=reference_id,
                    updated_at=_timestamp(),
                )
            )
        self.persistence.save(store)
        return self.list_favorites()

    def list_recents(self) -> list[RecentEntry]:
        store = self.load_store()
        entries = [entry for entry in store.recents if self._is_resolvable_recent(entry)]
        return sorted(entries, key=lambda entry: entry.last_used_at or "", reverse=True)

    def record_recent(self, template_id: str, variant_id: str | None = None, name: str | None = None) -> list[RecentEntry]:
        store = self.load_store()
        recent_id = f"{template_id}:{variant_id or 'default'}"
        existing = next((entry for entry in store.recents if entry.id == recent_id), None)
        if existing is not None:
            use_count = existing.use_count + 1
            store.recents = [entry for entry in store.recents if entry.id != recent_id]
        else:
            use_count = 1
        store.recents.insert(
            0,
            RecentEntry(
                id=recent_id,
                type="recent",
                template_id=template_id,
                variant_id=variant_id,
                name=name,
                last_used_at=_timestamp(),
                use_count=use_count,
            ),
        )
        store.recents = store.recents[:MAX_RECENTS]
        self.persistence.save(store)
        return self.list_recents()

    def list_presets(self) -> list[PresetEntry]:
        store = self.load_store()
        entries = [entry for entry in store.presets if self._is_resolvable_preset(entry)]
        return sorted(entries, key=lambda entry: (entry.name.lower(), entry.updated_at or ""))

    def save_preset(
        self,
        name: str,
        template_id: str,
        variant_id: str | None = None,
        grid_mm: float | None = None,
        layout_strategy: str | None = None,
        overrides: dict[str, Any] | None = None,
        description: str | None = None,
    ) -> PresetEntry:
        preset_id = _slugify(name)
        store = self.load_store()
        entry = PresetEntry(
            id=preset_id,
            type="preset",
            name=name,
            description=description,
            template_id=template_id,
            variant_id=variant_id,
            grid_mm=grid_mm,
            layout_strategy=layout_strategy,
            overrides=deepcopy(overrides) if overrides is not None else {},
            updated_at=_timestamp(),
        )
        store.presets = [item for item in store.presets if item.id != preset_id]
        store.presets.append(entry)
        self.persistence.save(store)
        return entry

    def get_preset(self, preset_id: str) -> PresetEntry:
        for entry in self.list_presets():
            if entry.id == preset_id:
                return entry
        raise KeyError(f"Unknown preset id: {preset_id}")

    def preset_from_document(
        self,
        doc: Any,
        name: str,
        template_id: str,
        variant_id: str | None,
    ) -> PresetEntry:
        context = self.controller_service.get_ui_context(doc)
        ui = context.get("ui") or {}
        layout = context.get("layout") or {}
        return self.save_preset(
            name=name,
            template_id=template_id,
            variant_id=variant_id,
            grid_mm=float(ui.get("grid_mm", 1.0)),
            layout_strategy=layout.get("strategy"),
            overrides={},
        )

    def resolve_template_name(self, template_id: str) -> str:
        template = self.template_service.get_template(template_id)
        return str(template["template"]["name"])

    def resolve_variant_name(self, variant_id: str) -> str:
        variant = self.variant_service.get_variant(variant_id)
        return str(variant["variant"]["name"])

    def _is_resolvable_favorite(self, entry: FavoriteEntry) -> bool:
        try:
            if entry.type == "template" and entry.reference_id:
                self.template_service.get_template(entry.reference_id)
                return True
            if entry.type == "variant" and entry.reference_id:
                self.variant_service.get_variant(entry.reference_id)
                return True
        except Exception:
            return False
        return False

    def _is_resolvable_recent(self, entry: RecentEntry) -> bool:
        try:
            self.template_service.get_template(entry.template_id)
            if entry.variant_id is not None:
                self.variant_service.get_variant(entry.variant_id)
            return True
        except Exception:
            return False

    def _is_resolvable_preset(self, entry: PresetEntry) -> bool:
        try:
            if entry.template_id is None:
                return False
            self.template_service.get_template(entry.template_id)
            if entry.variant_id is not None:
                self.variant_service.get_variant(entry.variant_id)
            return True
        except Exception:
            return False


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    compact = "-".join(part for part in cleaned.split("-") if part)
    return compact or "preset"

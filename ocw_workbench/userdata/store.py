from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ocw_workbench.userdata.models import FavoriteEntry, PresetEntry, RecentEntry


@dataclass
class UserDataStore:
    favorites: list[FavoriteEntry] = field(default_factory=list)
    recents: list[RecentEntry] = field(default_factory=list)
    presets: list[PresetEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "favorites": [entry.to_dict() for entry in self.favorites],
            "recents": [entry.to_dict() for entry in self.recents],
            "presets": [entry.to_dict() for entry in self.presets],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "UserDataStore":
        data = payload if isinstance(payload, dict) else {}
        return cls(
            favorites=[_favorite_from_dict(item) for item in _as_list(data.get("favorites"))],
            recents=[_recent_from_dict(item) for item in _as_list(data.get("recents"))],
            presets=[_preset_from_dict(item) for item in _as_list(data.get("presets"))],
        )


def _favorite_from_dict(value: dict[str, Any]) -> FavoriteEntry:
    item = value if isinstance(value, dict) else {}
    return FavoriteEntry(
        id=str(item.get("id", "")),
        type=str(item.get("type", "template")),
        name=_optional_str(item.get("name")),
        reference_id=_optional_str(item.get("reference_id")),
        updated_at=_optional_str(item.get("updated_at")),
    )


def _recent_from_dict(value: dict[str, Any]) -> RecentEntry:
    item = value if isinstance(value, dict) else {}
    return RecentEntry(
        id=str(item.get("id", "")),
        type=str(item.get("type", "recent")),
        template_id=str(item.get("template_id", "")),
        variant_id=_optional_str(item.get("variant_id")),
        name=_optional_str(item.get("name")),
        last_used_at=_optional_str(item.get("last_used_at")),
        use_count=int(item.get("use_count", 1) or 1),
    )


def _preset_from_dict(value: dict[str, Any]) -> PresetEntry:
    item = value if isinstance(value, dict) else {}
    overrides = item.get("overrides", {})
    return PresetEntry(
        id=str(item.get("id", "")),
        type=str(item.get("type", "preset")),
        name=str(item.get("name", "")),
        description=_optional_str(item.get("description")),
        template_id=_optional_str(item.get("template_id")),
        variant_id=_optional_str(item.get("variant_id")),
        grid_mm=float(item["grid_mm"]) if item.get("grid_mm") is not None else None,
        layout_strategy=_optional_str(item.get("layout_strategy")),
        overrides=overrides if isinstance(overrides, dict) else {},
        updated_at=_optional_str(item.get("updated_at")),
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]

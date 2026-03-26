from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FavoriteEntry:
    id: str
    type: str
    name: str | None = None
    reference_id: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "reference_id": self.reference_id,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class RecentEntry:
    id: str
    type: str
    template_id: str
    variant_id: str | None = None
    name: str | None = None
    last_used_at: str | None = None
    use_count: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "template_id": self.template_id,
            "variant_id": self.variant_id,
            "name": self.name,
            "last_used_at": self.last_used_at,
            "use_count": self.use_count,
        }


@dataclass(frozen=True)
class PresetEntry:
    id: str
    type: str
    name: str
    description: str | None = None
    template_id: str | None = None
    variant_id: str | None = None
    grid_mm: float | None = None
    layout_strategy: str | None = None
    overrides: dict[str, Any] = field(default_factory=dict)
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "template_id": self.template_id,
            "variant_id": self.variant_id,
            "grid_mm": self.grid_mm,
            "layout_strategy": self.layout_strategy,
            "overrides": self.overrides,
            "updated_at": self.updated_at,
        }

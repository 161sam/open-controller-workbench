from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VariantModel:
    id: str
    name: str
    description: str
    template_id: str
    overrides: dict[str, Any]
    category: str | None = None
    tags: list[str] | None = None
    version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        variant: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "template_id": self.template_id,
        }
        if self.category is not None:
            variant["category"] = self.category
        if self.tags is not None:
            variant["tags"] = self.tags
        if self.version is not None:
            variant["version"] = self.version
        return {
            "variant": variant,
            "overrides": self.overrides,
        }

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TemplateModel:
    id: str
    name: str
    description: str
    controller: dict[str, Any]
    zones: list[dict[str, Any]]
    components: list[dict[str, Any]]
    layout: dict[str, Any]
    constraints: dict[str, Any]
    defaults: dict[str, Any]
    firmware: dict[str, Any]
    ocf: dict[str, Any]
    category: str | None = None
    tags: list[str] | None = None
    version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        template: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }
        if self.category is not None:
            template["category"] = self.category
        if self.tags is not None:
            template["tags"] = self.tags
        if self.version is not None:
            template["version"] = self.version
        return {
            "template": template,
            "controller": self.controller,
            "zones": self.zones,
            "components": self.components,
            "layout": self.layout,
            "constraints": self.constraints,
            "defaults": self.defaults,
            "firmware": self.firmware,
            "ocf": self.ocf,
        }

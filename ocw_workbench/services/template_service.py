from __future__ import annotations

from typing import Any

from ocw_workbench.templates.generator import TemplateGenerator
from ocw_workbench.templates.registry import TemplateRegistry
from ocw_workbench.templates.resolver import TemplateResolver


class TemplateService:
    def __init__(
        self,
        registry: TemplateRegistry | None = None,
        resolver: TemplateResolver | None = None,
        generator: TemplateGenerator | None = None,
    ) -> None:
        self.registry = registry or TemplateRegistry()
        self.resolver = resolver or TemplateResolver()
        self.generator = generator or TemplateGenerator(self.registry, self.resolver)

    def list_templates(self, category: str | None = None) -> list[dict[str, Any]]:
        return self.registry.list_templates(category=category)

    def get_template(self, template_id: str) -> dict[str, Any]:
        return self.registry.get_template(template_id)

    def resolve_template(self, template_id: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.resolver.resolve(self.registry.get_template(template_id), overrides=overrides)

    def generate_from_template(self, template_id: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.generator.generate_from_template(template_id, overrides=overrides)

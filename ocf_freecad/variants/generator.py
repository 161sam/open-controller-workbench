from __future__ import annotations

from typing import Any

from ocf_freecad.templates.generator import TemplateGenerator
from ocf_freecad.variants.registry import VariantRegistry
from ocf_freecad.variants.resolver import VariantResolver


class VariantGenerator:
    def __init__(
        self,
        registry: VariantRegistry | None = None,
        resolver: VariantResolver | None = None,
        template_generator: TemplateGenerator | None = None,
    ) -> None:
        self.registry = registry or VariantRegistry()
        self.resolver = resolver or VariantResolver()
        self.template_generator = template_generator or TemplateGenerator()

    def generate_from_variant(
        self,
        variant_id: str,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        variant = self.registry.get_variant(variant_id)
        resolved = self.resolver.resolve(variant, runtime_overrides=overrides)
        return self.template_generator.build_project_from_resolved_template(resolved)

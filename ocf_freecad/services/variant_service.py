from __future__ import annotations

from typing import Any

from ocf_freecad.variants.generator import VariantGenerator
from ocf_freecad.variants.registry import VariantRegistry
from ocf_freecad.variants.resolver import VariantResolver


class VariantService:
    def __init__(
        self,
        registry: VariantRegistry | None = None,
        resolver: VariantResolver | None = None,
        generator: VariantGenerator | None = None,
    ) -> None:
        self.registry = registry or VariantRegistry()
        self.resolver = resolver or VariantResolver()
        self.generator = generator or VariantGenerator(self.registry, self.resolver)

    def list_variants(
        self,
        template_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.registry.list_variants(template_id=template_id, category=category, tag=tag)

    def get_variant(self, variant_id: str) -> dict[str, Any]:
        return self.registry.get_variant(variant_id)

    def resolve_variant(self, variant_id: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.resolver.resolve(self.registry.get_variant(variant_id), runtime_overrides=overrides)

    def generate_from_variant(self, variant_id: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.generator.generate_from_variant(variant_id, overrides=overrides)

from __future__ import annotations

from typing import Any

from ocw_workbench.library.manager import ComponentLibraryManager


class LibraryService:
    def __init__(self, manager: ComponentLibraryManager | None = None) -> None:
        self.manager = manager or ComponentLibraryManager()

    def get(self, component_id: str) -> dict[str, Any]:
        return self.manager.get_component(component_id)

    def list_by_category(self, category: str | None = None) -> list[dict[str, Any]]:
        return self.manager.list_components(category=category)

    def resolve(
        self,
        library_ref: str,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.manager.resolve_component(library_ref, overrides)

    def get_mechanical_defaults(self, library_ref: str) -> dict[str, Any]:
        component = self.get(library_ref)
        mechanical = component.get("mechanical", {})
        if not isinstance(mechanical, dict):
            raise ValueError(f"Library component '{library_ref}' has invalid mechanical defaults")
        return mechanical

    def get_electrical_defaults(self, library_ref: str) -> dict[str, Any]:
        component = self.get(library_ref)
        electrical = component.get("electrical", {})
        if not isinstance(electrical, dict):
            raise ValueError(f"Library component '{library_ref}' has invalid electrical defaults")
        return electrical

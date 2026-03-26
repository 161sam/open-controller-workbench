from __future__ import annotations

from typing import Any

from ocw_workbench.library.manager import ComponentLibraryManager

library_manager = ComponentLibraryManager()


def get_component(component_id: str) -> dict[str, Any]:
    return library_manager.get_component(component_id)


def list_components(category: str | None = None) -> list[dict[str, Any]]:
    return library_manager.list_components(category=category)


def resolve_component(
    library_ref: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return library_manager.resolve_component(library_ref=library_ref, overrides=overrides)

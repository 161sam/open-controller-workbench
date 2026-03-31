from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.commands.factory import PluginCommandSpec
from ocw_workbench.gui.runtime import component_icon_path, show_error, show_info
from ocw_workbench.services.controller_service import ControllerService


class ApplySuggestedAdditionCommand(BaseCommand):
    """Apply a plugin-provided suggested addition to the active controller."""

    def __init__(self, addition_id: str, spec: PluginCommandSpec | None = None) -> None:
        self.addition_id = addition_id
        self.spec = spec
        self.controller_service = ControllerService()

    def GetResources(self) -> dict:
        label = self.spec.label if self.spec is not None else self.addition_id.replace("_", " ").title()
        tooltip = self.spec.tooltip if self.spec is not None else f"Apply the suggested addition '{self.addition_id}'."
        category = self.spec.category if self.spec is not None else "Next Steps"
        icon = self.spec.icon if self.spec is not None else "generic.svg"
        return {
            "MenuText": label,
            "ToolTip": tooltip,
            "Pixmap": component_icon_path(icon),
            "Category": category,
        }

    def IsActive(self) -> bool:
        try:
            import FreeCAD as App

            doc = App.ActiveDocument
            if doc is None:
                return False
            context = self.controller_service.get_ui_context(doc)
            layout = context.get("layout_intelligence", {})
            additions = layout.get("suggested_additions", []) if isinstance(layout, dict) else []
            return any(str(item.get("id") or "") == self.addition_id for item in additions if isinstance(item, dict))
        except Exception:
            return False

    def Activated(self) -> None:
        try:
            import FreeCAD as App

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            state = self.controller_service.apply_suggested_addition(doc, self.addition_id)
            added_count = len(
                [
                    component
                    for component in state.get("components", [])
                    if isinstance(component, dict)
                    and str(component.get("properties", {}).get("suggested_addition_id") or "") == self.addition_id
                ]
            )
            title = self.spec.label if self.spec is not None else self.addition_id.replace("_", " ").title()
            message = f"Added {added_count or 1} suggested component(s) using '{self.addition_id}'."
            show_info(title, message)
        except Exception as exc:
            title = self.spec.label if self.spec is not None else self.addition_id.replace("_", " ").title()
            show_error(title, exc)

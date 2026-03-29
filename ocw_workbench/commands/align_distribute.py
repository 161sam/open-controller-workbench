from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.runtime import show_error, show_info


class SelectionArrangeCommand(BaseCommand):
    ICON_NAME = "align_left"

    def __init__(self, operation: str) -> None:
        self.operation = operation

    def icon_name(self) -> str:
        return _command_icon_name(self.operation)

    def GetResources(self):
        menu_text, tooltip = _command_text(self.operation)
        return self.resources(menu_text, tooltip)

    def IsActive(self):
        required_selection = 3 if self.operation.startswith("distribute_") else 2
        return self._has_selection(required_selection)

    def Activated(self):
        menu_text, _tooltip = _command_text(self.operation)
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import apply_selection_arrangement_direct

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            result = apply_selection_arrangement_direct(doc, self.operation)
            if result["moved_count"] <= 0:
                show_info(menu_text, f"{menu_text} left {result['selected_count']} selected components unchanged.")
            else:
                show_info(menu_text, f"{menu_text} applied to {result['selected_count']} selected components.")
        except Exception as exc:
            show_error(menu_text, exc)


def _command_text(operation: str) -> tuple[str, str]:
    labels = {
        "align_left": ("Align Left", "Align selected component centers to the left-most selected X position."),
        "align_center_x": ("Align Center X", "Align selected component centers to the horizontal selection midpoint."),
        "align_right": ("Align Right", "Align selected component centers to the right-most selected X position."),
        "align_top": ("Align Top", "Align selected component centers to the top-most selected Y position."),
        "align_center_y": ("Align Center Y", "Align selected component centers to the vertical selection midpoint."),
        "align_bottom": ("Align Bottom", "Align selected component centers to the bottom-most selected Y position."),
        "distribute_horizontal": (
            "Distribute Horizontally",
            "Evenly distribute selected component centers along X, keeping the outer-most selected components fixed.",
        ),
        "distribute_vertical": (
            "Distribute Vertically",
            "Evenly distribute selected component centers along Y, keeping the outer-most selected components fixed.",
        ),
    }
    if operation not in labels:
        raise ValueError(f"Unsupported arrangement operation: {operation}")
    return labels[operation]


def _command_icon_name(operation: str) -> str:
    icon_names = {
        "align_left": "align_left",
        "align_center_x": "align_center_x",
        "align_right": "align_right",
        "align_top": "align_top",
        "align_center_y": "align_center_y",
        "align_bottom": "align_bottom",
        "distribute_horizontal": "distribute_horizontal",
        "distribute_vertical": "distribute_vertical",
    }
    if operation not in icon_names:
        raise ValueError(f"Unsupported arrangement operation: {operation}")
    return icon_names[operation]

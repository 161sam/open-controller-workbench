from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.runtime import show_error, show_info


class DuplicateSelectionCommand(BaseCommand):
    ICON_NAME = "duplicate_selected"

    def GetResources(self):
        return self.resources(
            "Duplicate Selected",
            "Duplicate the current selection once with an immediate default offset.",
        )

    def IsActive(self):
        return self._has_selection()

    def Activated(self):
        title = "Duplicate Selected"
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import duplicate_selection_once_direct

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            values = _default_duplicate_values(doc)
            result = duplicate_selection_once_direct(doc, offset_x=values["offset_x"], offset_y=values["offset_y"])
            show_info(
                title,
                f"Created {result['created_count']} duplicated components at +{values['offset_x']:.1f} mm, +{values['offset_y']:.1f} mm.",
            )
        except Exception as exc:
            show_error(title, exc)


class LinearArrayCommand(BaseCommand):
    ICON_NAME = "array_horizontal"

    def __init__(self, axis: str) -> None:
        self.axis = axis

    def icon_name(self) -> str:
        return "array_horizontal" if self.axis == "x" else "array_vertical"

    def GetResources(self):
        title = "Array Horizontally" if self.axis == "x" else "Array Vertically"
        tooltip = "Create a linear array from the current selection with immediate defaults."
        return self.resources(title, tooltip)

    def IsActive(self):
        return self._has_selection(1)

    def Activated(self):
        title = "Array Horizontally" if self.axis == "x" else "Array Vertically"
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import array_selection_linear_direct

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            values = _default_linear_array_values(doc, self.axis)
            result = array_selection_linear_direct(doc, axis=self.axis, count=values["count"], spacing=values["spacing"])
            show_info(
                title,
                f"Created {result['created_count']} array components with {values['spacing']:.1f} mm spacing.",
            )
        except Exception as exc:
            show_error(title, exc)


class GridArrayCommand(BaseCommand):
    ICON_NAME = "grid_array"

    def GetResources(self):
        return self.resources(
            "Grid Array",
            "Create a grid array from the current selection with immediate defaults.",
        )

    def IsActive(self):
        return self._has_selection()

    def Activated(self):
        title = "Grid Array"
        try:
            import FreeCAD as App

            from ocw_workbench.workbench import array_selection_grid_direct

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            values = _default_grid_array_values(doc)
            result = array_selection_grid_direct(
                doc,
                rows=values["rows"],
                cols=values["cols"],
                spacing_x=values["spacing_x"],
                spacing_y=values["spacing_y"],
            )
            show_info(
                title,
                f"Created {result['created_count']} grid-array components with {values['spacing_x']:.1f} x {values['spacing_y']:.1f} mm spacing.",
            )
        except Exception as exc:
            show_error(title, exc)


def _default_duplicate_values(doc) -> dict[str, float]:
    spacing_x, spacing_y = _selection_spacing(doc)
    return {"offset_x": spacing_x, "offset_y": 0.0}


def _default_linear_array_values(doc, axis: str) -> dict[str, float]:
    spacing_x, spacing_y = _selection_spacing(doc)
    return {
        "count": 3,
        "spacing": spacing_x if axis == "x" else spacing_y,
    }


def _default_grid_array_values(doc) -> dict[str, float]:
    spacing_x, spacing_y = _selection_spacing(doc)
    return {
        "rows": 2,
        "cols": 2,
        "spacing_x": spacing_x,
        "spacing_y": spacing_y,
    }


def _selection_spacing(doc) -> tuple[float, float]:
    from ocw_workbench.services.controller_service import ControllerService
    from ocw_workbench.services.interaction_service import InteractionService

    controller_service = ControllerService()
    interaction_service = InteractionService(controller_service)
    selected = _selected_components(doc, controller_service)
    settings = interaction_service.get_settings(doc)
    grid_mm = float(settings.get("grid_mm", 1.0) or 1.0)
    margin = max(grid_mm * 4.0, 10.0)
    if not selected:
        return (20.0, 20.0)
    xs = [float(component.get("x", 0.0) or 0.0) for component in selected]
    ys = [float(component.get("y", 0.0) or 0.0) for component in selected]
    span_x = max(xs) - min(xs) if len(xs) > 1 else 0.0
    span_y = max(ys) - min(ys) if len(ys) > 1 else 0.0
    spacing_x = max(20.0, span_x + margin)
    spacing_y = max(20.0, span_y + margin)
    return (spacing_x, spacing_y)


def _selected_components(doc, controller_service) -> list[dict[str, object]]:
    state = controller_service.get_state(doc)
    by_id = {component["id"]: component for component in state["components"]}
    selected_ids = controller_service.get_selected_component_ids(doc)
    return [by_id[component_id] for component_id in selected_ids if component_id in by_id]

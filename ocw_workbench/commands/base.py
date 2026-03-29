from __future__ import annotations

from ocw_workbench.gui.runtime import icon_path


class BaseCommand:
    ICON_NAME = "default"

    def icon_name(self) -> str:
        return self.ICON_NAME

    def resources(self, menu_text: str, tooltip: str, accel: str | None = None) -> dict[str, str]:
        payload = {
            "MenuText": menu_text,
            "ToolTip": tooltip,
            "Pixmap": icon_path(self.icon_name()),
        }
        if accel:
            payload["Accel"] = accel
        return payload

    def GetResources(self):
        return self.resources("Base Command", "Base Command")

    def IsActive(self):
        return True

    @staticmethod
    def _has_controller() -> bool:
        """Return True when an active FreeCAD document with an OCW controller exists."""
        try:
            import FreeCAD as App
            from ocw_workbench.freecad_api.metadata import get_document_data
            doc = App.ActiveDocument
            if doc is None:
                return False
            # Fast path: check runtime cache; avoids disk read
            return isinstance(get_document_data(doc, "OCWStateCache"), dict)
        except Exception:
            return False

    @staticmethod
    def _selection_count() -> int:
        """Return the number of selected components in the active OCW document."""
        try:
            import FreeCAD as App
            from ocw_workbench.freecad_api.metadata import get_document_data
            doc = App.ActiveDocument
            if doc is None:
                return 0
            state = get_document_data(doc, "OCWStateCache")
            if not isinstance(state, dict):
                return 0
            selected_ids = state.get("meta", {}).get("selected_ids", [])
            if isinstance(selected_ids, list):
                return len([component_id for component_id in selected_ids if isinstance(component_id, str) and component_id])
            return 1 if state.get("meta", {}).get("selection") is not None else 0
        except Exception:
            return 0

    @classmethod
    def _has_selection(cls, min_count: int = 1) -> bool:
        """Return True when an active controller exists and enough components are selected."""
        try:
            return cls._selection_count() >= max(1, int(min_count))
        except Exception:
            return False

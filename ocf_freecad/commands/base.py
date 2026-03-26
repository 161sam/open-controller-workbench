from __future__ import annotations

from ocf_freecad.gui.runtime import icon_path


class BaseCommand:
    ICON_NAME = "default"

    def resources(self, menu_text: str, tooltip: str, accel: str | None = None) -> dict[str, str]:
        payload = {
            "MenuText": menu_text,
            "ToolTip": tooltip,
            "Pixmap": icon_path(self.ICON_NAME),
        }
        if accel:
            payload["Accel"] = accel
        return payload

    def GetResources(self):
        return self.resources("Base Command", "Base Command")

    def IsActive(self):
        return True

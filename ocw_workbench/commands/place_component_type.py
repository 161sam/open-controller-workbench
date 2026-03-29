from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.gui.runtime import component_icon_path, show_error, show_info

# Default library reference per component type.
# Used when no specific variant is pre-selected.
_TYPE_DEFAULTS: dict[str, str] = {
    "button":     "omron_b3f_1000",
    "encoder":    "alps_ec11e15204a3",
    "fader":      "generic_45mm_linear_fader",
    "pad":        "generic_mpc_pad_30mm",
    "display":    "adafruit_oled_096_i2c_ssd1306",
    "rgb_button": "generic_rgb_arcade_button_24mm",
}

# Icon filename per component type (in resources/icons/components/).
_TYPE_ICONS: dict[str, str] = {
    "button":     "button.svg",
    "encoder":    "encoder.svg",
    "fader":      "fader.svg",
    "pad":        "pad.svg",
    "display":    "display.svg",
    "rgb_button": "generic.svg",
}

_TYPE_LABELS: dict[str, str] = {
    "button":     "Button",
    "encoder":    "Encoder",
    "fader":      "Fader",
    "pad":        "Pad",
    "display":    "Display",
    "rgb_button": "RGB Button",
}


class PlaceComponentTypeCommand(BaseCommand):
    """Start placement mode for a specific component type.

    Activating the command immediately enters 3D placement mode using the
    default variant for the type. No dock or form is required upfront.
    """

    def __init__(self, component_type: str) -> None:
        self.component_type = component_type
        self.default_library_ref = _TYPE_DEFAULTS.get(component_type, component_type)

    def icon_name(self) -> str:
        # Overridden: use component icon, not workbench action icon.
        return ""

    def GetResources(self) -> dict:
        label = _TYPE_LABELS.get(self.component_type, self.component_type.title())
        icon = component_icon_path(_TYPE_ICONS.get(self.component_type))
        return {
            "MenuText": f"Place {label}",
            "ToolTip": f"Place a {label} on the controller. Click in the 3D view to position it.",
            "Pixmap": icon,
        }

    def IsActive(self) -> bool:
        return self._has_controller()

    def Activated(self) -> None:
        try:
            import FreeCAD as App
            from ocw_workbench.workbench import start_place_mode_direct

            doc = App.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")
            started = start_place_mode_direct(doc, self.default_library_ref)
            if started:
                label = _TYPE_LABELS.get(self.component_type, self.component_type.title())
                show_info(
                    f"Place {label}",
                    f"Click in the 3D view to place a {label}. Press ESC to cancel.",
                )
        except Exception as exc:
            label = _TYPE_LABELS.get(self.component_type, self.component_type.title())
            show_error(f"Place {label}", exc)

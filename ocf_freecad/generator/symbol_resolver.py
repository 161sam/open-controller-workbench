from __future__ import annotations

from copy import deepcopy
from typing import Any


class SymbolResolver:
    def resolve(self, component: dict[str, Any]) -> dict[str, Any]:
        role = component.get("role")
        component_type = component.get("type")

        if role == "incremental_encoder" or component_type == "encoder":
            return {
                "name": "rotary_encoder",
                "description": "Incremental rotary encoder",
                "pins": ["A", "B", "C"],
            }
        if role == "momentary_switch" or component_type == "button":
            return {
                "name": "switch",
                "description": "Momentary switch",
                "pins": ["1", "2"],
            }
        if role == "oled_display" or component_type == "display":
            return {
                "name": "oled_display",
                "description": "I2C OLED display",
                "pins": ["VCC", "GND", "SDA", "SCL", "RST"],
            }
        if role == "connector":
            return {
                "name": "connector",
                "description": "Generic connector",
                "pins": [],
            }
        return {
            "name": "generic_component",
            "description": "Fallback symbol",
            "pins": [],
        }

    def for_mcu(self, controller_mcu: dict[str, Any] | None, used_pins: list[str]) -> dict[str, Any]:
        mcu = deepcopy(controller_mcu) if isinstance(controller_mcu, dict) else {}
        return {
            "name": "mcu",
            "description": mcu.get("family", "Logical MCU endpoint"),
            "pins": used_pins,
        }

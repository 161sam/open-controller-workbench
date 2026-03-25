from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocf_freecad.generator.symbol_resolver import SymbolResolver


class SchematicBuilder:
    def __init__(self, symbol_resolver: SymbolResolver | None = None) -> None:
        self.symbol_resolver = symbol_resolver or SymbolResolver()

    def build(self, electrical_mapping: dict[str, Any]) -> dict[str, Any]:
        self._validate_mapping(electrical_mapping)

        warnings = deepcopy(electrical_mapping.get("warnings", []))
        buses = deepcopy(electrical_mapping.get("buses", {}))
        electrical_components = deepcopy(electrical_mapping.get("components", []))
        electrical_nets = deepcopy(electrical_mapping.get("nets", []))
        electrical_assignments = deepcopy(electrical_mapping.get("assignments", []))
        components: list[dict[str, Any]] = []
        symbols: list[dict[str, Any]] = []
        pins: list[dict[str, Any]] = []
        connections: list[dict[str, Any]] = []
        nets_map: dict[str, dict[str, Any]] = {}
        bus_entries: list[dict[str, Any]] = []
        power = {"nets": []}
        mcu_endpoints: dict[str, str] = {}

        mcu_component = self._build_mcu_component(electrical_mapping, electrical_assignments, buses, warnings)
        if mcu_component is not None:
            components.append(mcu_component["component"])
            symbols.append(mcu_component["symbol"])
            pins.extend(mcu_component["pins"])
            mcu_endpoints = mcu_component["endpoints"]

        for component in electrical_components:
            built = self._build_component(component, electrical_nets, warnings)
            components.append(built["component"])
            symbols.append(built["symbol"])
            pins.extend(built["pins"])
            for connection in built["connections"]:
                self._append_connection(connections, nets_map, connection["net"], connection["connect"])

        self._add_assignment_connections(
            components,
            electrical_assignments,
            connections,
            nets_map,
            mcu_endpoints,
            warnings,
        )
        self._add_bus_entries(buses, electrical_components, electrical_nets, bus_entries)
        self._add_power_entries(power, components, warnings)

        return {
            "schema_version": "1.0",
            "export_type": "controller.schematic",
            "meta": deepcopy(electrical_mapping.get("meta", {})),
            "components": components,
            "symbols": symbols,
            "pins": pins,
            "connections": connections,
            "nets": list(nets_map.values()),
            "buses": bus_entries,
            "power": power,
            "warnings": warnings,
        }

    def _validate_mapping(self, electrical_mapping: dict[str, Any]) -> None:
        required = ["components", "assignments", "nets", "buses", "controller"]
        for field in required:
            if field not in electrical_mapping:
                raise ValueError(f"Missing required electrical mapping field '{field}'")

    def _build_mcu_component(
        self,
        electrical_mapping: dict[str, Any],
        assignments: list[dict[str, Any]],
        buses: dict[str, Any],
        warnings: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        controller = electrical_mapping.get("controller", {})
        controller_mcu = controller.get("controller_mcu")
        used_pins: list[str] = []

        for assignment in assignments:
            logical_pin = assignment.get("logical_pin")
            if isinstance(logical_pin, str):
                used_pins.append(logical_pin)

        for bus in buses.values():
            if isinstance(bus, dict):
                pins_cfg = bus.get("pins", {})
                if isinstance(pins_cfg, dict):
                    for logical_pin in pins_cfg.values():
                        if isinstance(logical_pin, str):
                            used_pins.append(logical_pin)

        unique_pins = list(dict.fromkeys(used_pins))
        if controller_mcu is None:
            warnings.append(
                {
                    "code": "missing_mcu",
                    "message": "No controller MCU defined for schematic export",
                }
            )
            return None

        symbol = self.symbol_resolver.for_mcu(controller_mcu, unique_pins)
        component = {
            "id": "mcu",
            "type": "mcu",
            "role": "controller_mcu",
            "library_ref": None,
            "symbol": symbol["name"],
            "electrical_role": "controller_mcu",
            "pins": unique_pins,
            "net_mapping": {},
        }
        pins = [
            {
                "component": "mcu",
                "pin": pin_name,
                "net": None,
                "direction": "bidirectional",
            }
            for pin_name in unique_pins
        ]
        return {
            "component": component,
            "symbol": {
                "component": "mcu",
                "name": symbol["name"],
                "description": symbol["description"],
                "pins": symbol["pins"],
            },
            "pins": pins,
            "endpoints": {pin_name: pin_name for pin_name in unique_pins},
        }

    def _build_component(
        self,
        component: dict[str, Any],
        electrical_nets: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        symbol = self.symbol_resolver.resolve(component)
        component_id = component["id"]
        pin_entries = self._pin_entries_for_component(component, electrical_nets)
        net_mapping = {pin["pin"]: pin["net"] for pin in pin_entries if pin["net"] is not None}

        if symbol["name"] == "generic_component":
            warnings.append(
                {
                    "component_id": component_id,
                    "code": "unknown_component_type",
                    "message": f"Unknown component type for schematic symbol: '{component_id}'",
                }
            )

        built_component = {
            "id": component_id,
            "type": component.get("type"),
            "role": component.get("role"),
            "library_ref": component.get("library_ref"),
            "symbol": symbol["name"],
            "electrical_role": component.get("role"),
            "pins": [pin["pin"] for pin in pin_entries],
            "net_mapping": net_mapping,
        }
        connections = []
        for pin in pin_entries:
            if pin["net"] is None:
                warnings.append(
                    {
                        "component_id": component_id,
                        "code": "unconnected_pin",
                        "message": f"Component '{component_id}' has unconnected pin '{pin['pin']}'",
                    }
                )
                continue
            connections.append(
                {
                    "net": pin["net"],
                    "connect": {"component": component_id, "pin": pin["pin"]},
                }
            )

        return {
            "component": built_component,
            "symbol": {
                "component": component_id,
                "name": symbol["name"],
                "description": symbol["description"],
                "pins": symbol["pins"],
            },
            "pins": pin_entries,
            "connections": connections,
        }

    def _pin_entries_for_component(
        self,
        component: dict[str, Any],
        electrical_nets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        role = component.get("role")
        component_id = component["id"]
        net_map = {
            net["signal"]: net["net_name"]
            for net in electrical_nets
            if net.get("component_id") == component_id
        }
        mapping = {
            "incremental_encoder": [("A", "a"), ("B", "b"), ("C", "common")],
            "momentary_switch": [("1", "switch_a"), ("2", "switch_b")],
            "oled_display": [("VCC", "vcc"), ("GND", "gnd"), ("SDA", "sda"), ("SCL", "scl"), ("RST", "rst")],
        }
        pin_entries = []
        for pin_name, signal_name in mapping.get(role, []):
            pin_entries.append(
                {
                    "component": component_id,
                    "pin": pin_name,
                    "signal": signal_name,
                    "net": net_map.get(signal_name),
                    "direction": self._pin_direction(signal_name),
                }
            )
        return pin_entries

    def _pin_direction(self, signal_name: str) -> str:
        if signal_name in {"vcc", "gnd"}:
            return "power"
        if signal_name in {"sda", "scl"}:
            return "bidirectional"
        return "input"

    def _append_connection(
        self,
        connections: list[dict[str, Any]],
        nets_map: dict[str, dict[str, Any]],
        net_name: str,
        connect: dict[str, Any],
    ) -> None:
        entry = next((item for item in connections if item["net"] == net_name), None)
        if entry is None:
            entry = {"net": net_name, "connects": []}
            connections.append(entry)
        entry["connects"].append(connect)
        net_type = self._classify_net(net_name)
        if net_name not in nets_map:
            nets_map[net_name] = {"name": net_name, "type": net_type, "connected_pins": []}
        nets_map[net_name]["connected_pins"].append(connect)

    def _classify_net(self, net_name: str) -> str:
        if net_name == "net.gnd":
            return "ground"
        if net_name == "net.3v3":
            return "power"
        if ".sda" in net_name or ".scl" in net_name:
            return "bus"
        return "signal"

    def _add_assignment_connections(
        self,
        components: list[dict[str, Any]],
        assignments: list[dict[str, Any]],
        connections: list[dict[str, Any]],
        nets_map: dict[str, dict[str, Any]],
        mcu_endpoints: dict[str, str],
        warnings: list[dict[str, Any]],
    ) -> None:
        component_lookup = {component["id"]: component for component in components}
        for assignment in assignments:
            component_id = assignment["component_id"]
            component = component_lookup.get(component_id)
            if component is None:
                continue

            strategy = assignment.get("strategy")
            if strategy == "direct_gpio":
                logical_pin = assignment.get("logical_pin")
                signal_name = assignment.get("signal")
                net_name = component["net_mapping"].get(self._logical_pin_name(component["role"], signal_name))
                if net_name is None or not isinstance(logical_pin, str):
                    continue
                if "mcu" not in {entry["component"] for entry in nets_map[net_name]["connected_pins"]} and logical_pin in mcu_endpoints:
                    self._append_connection(
                        connections,
                        nets_map,
                        net_name,
                        {"component": "mcu", "pin": logical_pin},
                    )
                continue

            if strategy == "matrix":
                row = assignment.get("row")
                col = assignment.get("col")
                if row is not None:
                    self._append_connection(
                        connections,
                        nets_map,
                        f"matrix.row{row}",
                        {"component": component_id, "pin": "1"},
                    )
                if col is not None:
                    self._append_connection(
                        connections,
                        nets_map,
                        f"matrix.col{col}",
                        {"component": component_id, "pin": "2"},
                    )
                continue

            if strategy == "i2c":
                bus_id = assignment.get("bus")
                if bus_id is None:
                    warnings.append(
                        {
                            "component_id": component_id,
                            "code": "missing_bus",
                            "message": f"Component '{component_id}' has no resolved bus connection",
                        }
                    )

    def _logical_pin_name(self, role: str, signal_name: str | None) -> str:
        mapping = {
            "incremental_encoder": {"a": "A", "b": "B", "common": "C"},
            "momentary_switch": {"switch_a": "1", "switch_b": "2"},
            "oled_display": {"vcc": "VCC", "gnd": "GND", "sda": "SDA", "scl": "SCL", "rst": "RST"},
        }
        if signal_name is None:
            return ""
        return mapping.get(role, {}).get(signal_name, signal_name)

    def _add_bus_entries(
        self,
        buses: dict[str, Any],
        components: list[dict[str, Any]],
        electrical_nets: list[dict[str, Any]],
        bus_entries: list[dict[str, Any]],
    ) -> None:
        component_ids_by_bus: dict[str, list[str]] = {}
        for component in components:
            for assignment in component.get("assignments", []):
                bus_id = assignment.get("bus")
                if isinstance(bus_id, str):
                    component_ids_by_bus.setdefault(bus_id, []).append(component["id"])

        for bus_id, bus_data in buses.items():
            if not isinstance(bus_data, dict):
                continue
            shared_nets = []
            if bus_data.get("type") == "i2c":
                shared_nets = [f"{bus_id}.sda", f"{bus_id}.scl"]
            bus_entries.append(
                {
                    "id": bus_id,
                    "type": bus_data.get("type"),
                    "connected_components": component_ids_by_bus.get(bus_id, []),
                    "shared_nets": shared_nets,
                }
            )

    def _add_power_entries(
        self,
        power: dict[str, Any],
        components: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
    ) -> None:
        power_nets = set()
        for component in components:
            if component["role"] != "oled_display":
                continue
            mapping = component["net_mapping"]
            if "VCC" not in mapping:
                warnings.append(
                    {
                        "component_id": component["id"],
                        "code": "missing_power_connection",
                        "message": f"Component '{component['id']}' is missing VCC connection",
                    }
                )
            if "GND" not in mapping:
                warnings.append(
                    {
                        "component_id": component["id"],
                        "code": "missing_power_connection",
                        "message": f"Component '{component['id']}' is missing GND connection",
                    }
                )
            power_nets.update(net for pin, net in mapping.items() if pin in {"VCC", "GND"} and isinstance(net, str))

        for net_name in sorted(power_nets):
            power["nets"].append({"name": net_name, "type": "ground" if net_name == "net.gnd" else "power"})

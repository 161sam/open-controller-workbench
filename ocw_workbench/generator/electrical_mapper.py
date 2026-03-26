from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocw_workbench.generator.electrical_resolver import ElectricalResolver


class ElectricalMapper:
    def __init__(self, electrical_resolver: ElectricalResolver | None = None) -> None:
        self.electrical_resolver = electrical_resolver or ElectricalResolver()

    def map_controller(
        self,
        controller: dict[str, Any] | Any,
        components: list[dict[str, Any] | Any],
        firmware: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        controller_data = _as_dict(controller)
        firmware_data = deepcopy(firmware) if firmware is not None else {}
        io_strategy_cfg = deepcopy(firmware_data.get("io_strategy", {}))
        buses = deepcopy(firmware_data.get("buses", {}))
        warnings: list[dict[str, Any]] = []
        resolved_components: list[dict[str, Any]] = []
        all_signals: list[dict[str, Any]] = []
        assignments: list[dict[str, Any]] = []
        nets: list[dict[str, Any]] = []
        used_i2c_addresses: dict[tuple[str, str], str] = {}
        gpio_slots: dict[str, int] = {}

        for component in components:
            component_data = _as_dict(component)
            resolved = self.electrical_resolver.resolve(component_data)
            component_id = resolved["component_id"]
            role = resolved["role"]
            component_warnings = deepcopy(resolved["warnings"])
            warnings.extend(_scope_warnings(component_id, component_warnings))

            strategy = self._resolve_io_strategy(component_data, resolved, io_strategy_cfg, warnings)
            component_assignments = self._build_assignments(
                component_data,
                resolved,
                strategy,
                buses,
                gpio_slots,
                used_i2c_addresses,
                warnings,
            )
            resolved_components.append(
                {
                    "id": component_id,
                    "type": resolved["component_type"],
                    "library_ref": resolved["library_ref"],
                    "role": role,
                    "io_strategy": strategy,
                    "electrical": deepcopy(resolved["electrical"]),
                    "signals": deepcopy(resolved["signals"]),
                    "assignments": deepcopy(component_assignments),
                }
            )
            all_signals.extend(deepcopy(resolved["signals"]))
            assignments.extend(component_assignments)
            nets.extend(self._build_nets(component_id, role, resolved["signals"], strategy, component_assignments))

        return {
            "schema_version": "1.0",
            "export_type": "controller.electrical",
            "meta": deepcopy(meta) if meta is not None else {},
            "controller": {
                "id": controller_data.get("id"),
                "width": controller_data.get("width"),
                "depth": controller_data.get("depth"),
                "height": controller_data.get("height"),
                "top_thickness": controller_data.get("top_thickness"),
                "controller_mcu": deepcopy(firmware_data.get("controller_mcu")),
            },
            "io_strategy": io_strategy_cfg,
            "buses": buses,
            "components": resolved_components,
            "signals": all_signals,
            "assignments": assignments,
            "nets": nets,
            "warnings": warnings,
        }

    def _resolve_io_strategy(
        self,
        component_data: dict[str, Any],
        resolved: dict[str, Any],
        io_strategy_cfg: dict[str, Any],
        warnings: list[dict[str, Any]],
    ) -> str:
        component_id = resolved["component_id"]
        role = resolved["role"]
        explicit = component_data.get("io_strategy") or resolved["electrical"].get("io_strategy")
        if explicit is not None:
            if explicit not in {"direct_gpio", "matrix", "i2c"}:
                raise ValueError(f"Unsupported io strategy: {explicit}")
            return explicit

        role_defaults = {
            "incremental_encoder": "direct_gpio",
            "momentary_switch": "direct_gpio",
            "oled_display": "i2c",
            "mechanical_only": "direct_gpio",
            "connector": "direct_gpio",
            "unknown": "direct_gpio",
        }
        config_key = role
        if config_key in io_strategy_cfg and isinstance(io_strategy_cfg[config_key], str):
            strategy = io_strategy_cfg[config_key]
        elif resolved["component_type"] in io_strategy_cfg and isinstance(io_strategy_cfg[resolved["component_type"]], str):
            strategy = io_strategy_cfg[resolved["component_type"]]
        elif isinstance(io_strategy_cfg.get("default"), str):
            strategy = io_strategy_cfg["default"]
        else:
            strategy = role_defaults[role]
            warnings.append(
                {
                    "component_id": component_id,
                    "code": "missing_io_strategy",
                    "message": f"Component '{component_id}' is missing io strategy, using fallback '{strategy}'",
                }
            )

        if strategy not in {"direct_gpio", "matrix", "i2c"}:
            raise ValueError(f"Unsupported io strategy: {strategy}")
        return strategy

    def _build_assignments(
        self,
        component_data: dict[str, Any],
        resolved: dict[str, Any],
        strategy: str,
        buses: dict[str, Any],
        gpio_slots: dict[str, int],
        used_i2c_addresses: dict[tuple[str, str], str],
        warnings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        component_id = resolved["component_id"]
        role = resolved["role"]
        electrical = resolved["electrical"]
        pins_override = component_data.get("pins") or electrical.get("pins")
        assignments: list[dict[str, Any]] = []

        if strategy == "direct_gpio":
            for signal in resolved["signals"]:
                if signal["name"] in {"common", "switch_b", "vcc", "gnd"}:
                    continue
                pin_name = signal["name"]
                logical_pin = None
                if isinstance(pins_override, dict):
                    logical_pin = pins_override.get(pin_name)
                if logical_pin is None:
                    next_slot = gpio_slots.get(component_id, 0)
                    logical_pin = f"gpio_slot_{next_slot}"
                    gpio_slots[component_id] = next_slot + 1
                assignments.append(
                    {
                        "component_id": component_id,
                        "strategy": strategy,
                        "signal": signal["name"],
                        "logical_pin": logical_pin,
                    }
                )
            return assignments

        if strategy == "matrix":
            row = component_data.get("row", electrical.get("row"))
            col = component_data.get("col", electrical.get("col"))
            if row is None or col is None:
                warnings.append(
                    {
                        "component_id": component_id,
                        "code": "missing_matrix_assignment",
                        "message": f"Button component '{component_id}' is configured for matrix but no row/col assigned",
                    }
                )
            assignments.append(
                {
                    "component_id": component_id,
                    "strategy": strategy,
                    "row": row,
                    "col": col,
                }
            )
            return assignments

        if strategy == "i2c":
            bus_id = component_data.get("bus", electrical.get("bus"))
            address = component_data.get("address", electrical.get("address"))
            if address is None:
                options = electrical.get("address_options", [])
                if isinstance(options, list) and options:
                    address = options[0]
            if bus_id is None:
                available_i2c = [bus_name for bus_name, bus in buses.items() if isinstance(bus, dict) and bus.get("type") == "i2c"]
                if available_i2c:
                    bus_id = available_i2c[0]
                else:
                    warnings.append(
                        {
                            "component_id": component_id,
                            "code": "missing_i2c_bus",
                            "message": f"Missing i2c bus for display component '{component_id}'",
                        }
                    )
            if bus_id is not None and address is not None:
                key = (str(bus_id), str(address))
                if key in used_i2c_addresses:
                    warnings.append(
                        {
                            "component_id": component_id,
                            "code": "conflicting_i2c_address",
                            "message": (
                                f"Component '{component_id}' conflicts on bus '{bus_id}' "
                                f"with address '{address}' already used by '{used_i2c_addresses[key]}'"
                            ),
                        }
                    )
                else:
                    used_i2c_addresses[key] = component_id
            assignments.append(
                {
                    "component_id": component_id,
                    "strategy": strategy,
                    "bus": bus_id,
                    "address": address,
                }
            )
            return assignments

        warnings.append(
            {
                "component_id": component_id,
                "code": "unknown_io_strategy",
                "message": f"Unknown io strategy for component '{component_id}': {strategy}",
            }
        )
        return assignments

    def _build_nets(
        self,
        component_id: str,
        role: str,
        signals: list[dict[str, Any]],
        strategy: str,
        assignments: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        nets: list[dict[str, Any]] = []
        for signal in signals:
            name = signal["name"]
            net_name = signal["net_name"]
            if name == "gnd":
                net_name = "net.gnd"
            elif name == "vcc":
                net_name = "net.3v3"
            elif strategy == "i2c" and name in {"sda", "scl"}:
                bus_id = assignments[0].get("bus")
                if bus_id is not None:
                    net_name = f"{bus_id}.{name}"
            nets.append(
                {
                    "component_id": component_id,
                    "signal": name,
                    "net_name": net_name,
                    "role": role,
                }
            )
        return nets


def _as_dict(value: dict[str, Any] | Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    if hasattr(value, "__dict__"):
        return deepcopy(vars(value))
    raise TypeError(f"Unsupported value representation: {type(value)!r}")


def _scope_warnings(component_id: str, warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scoped = []
    for warning in warnings:
        entry = deepcopy(warning)
        entry.setdefault("component_id", component_id)
        scoped.append(entry)
    return scoped

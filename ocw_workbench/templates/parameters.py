from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


_PATH_TOKEN_RE = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)(\[(?P<key>[^\]]+)\])?$")
_PARAMETER_REFERENCE_RE = re.compile(r"\$\{parameters\.([A-Za-z_][A-Za-z0-9_]*)\}")


class TemplateParameterResolver:
    SUPPORTED_TYPES = {"int", "float", "bool", "enum", "string"}
    SUPPORTED_CONTROLS = {"input", "slider", "select", "toggle", "button_group"}

    def build_ui_model(
        self,
        template: dict[str, Any],
        *,
        values: dict[str, Any] | None = None,
        preset_id: str | None = None,
    ) -> dict[str, Any]:
        definitions = self.normalize_definitions(template)
        presets = self.normalize_presets(template)
        resolved_values, sources = self.resolve_values(
            definitions,
            presets=presets,
            values=values,
            preset_id=preset_id,
        )
        return {
            "definitions": definitions,
            "presets": presets,
            "values": resolved_values,
            "sources": sources,
            "preset_id": preset_id if preset_id in {item["id"] for item in presets} else None,
            "controls": self.build_controls(definitions, resolved_values, sources=sources),
        }

    def apply(
        self,
        template: dict[str, Any],
        *,
        values: dict[str, Any] | None = None,
        preset_id: str | None = None,
    ) -> dict[str, Any]:
        resolved = deepcopy(template)
        ui_model = self.build_ui_model(resolved, values=values, preset_id=preset_id)
        resolved["resolved_parameters"] = {
            "values": deepcopy(ui_model["values"]),
            "sources": deepcopy(ui_model["sources"]),
            "preset_id": ui_model["preset_id"],
        }
        self._apply_bindings(resolved, ui_model["values"])
        self._resolve_parameter_references(resolved, ui_model["values"])
        return resolved

    def normalize_definitions(self, template: dict[str, Any]) -> list[dict[str, Any]]:
        raw = template.get("parameters", [])
        if raw in (None, {}):
            return []
        if not isinstance(raw, list):
            raise ValueError("Template field 'parameters' must be a list")
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("Template parameter definition must be a mapping")
            parameter_id = str(item.get("id") or "").strip()
            if not parameter_id:
                raise ValueError("Template parameter is missing a valid 'id'")
            if parameter_id in seen:
                raise ValueError(f"Duplicate template parameter id: {parameter_id}")
            seen.add(parameter_id)
            parameter_type = str(item.get("type") or "").strip().lower() or "string"
            if parameter_type not in self.SUPPORTED_TYPES:
                raise ValueError(f"Unsupported template parameter type '{parameter_type}' for '{parameter_id}'")
            label = str(item.get("label") or parameter_id.replace("_", " ").title())
            control = str(item.get("control") or self._default_control(parameter_type)).strip().lower()
            if control not in self.SUPPORTED_CONTROLS:
                raise ValueError(f"Unsupported template parameter control '{control}' for '{parameter_id}'")
            options = self._normalize_options(parameter_id, parameter_type, item.get("options"))
            default = self._coerce_value(parameter_id, parameter_type, item.get("default"), options=options)
            minimum = item.get("min")
            maximum = item.get("max")
            step = item.get("step")
            if parameter_type in {"int", "float"}:
                minimum = self._coerce_number_field(parameter_id, "min", parameter_type, minimum)
                maximum = self._coerce_number_field(parameter_id, "max", parameter_type, maximum)
                step = self._coerce_number_field(parameter_id, "step", parameter_type, step)
                if minimum is not None and maximum is not None and minimum > maximum:
                    raise ValueError(f"Template parameter '{parameter_id}' has min greater than max")
                if minimum is not None and default < minimum:
                    raise ValueError(f"Template parameter '{parameter_id}' default is smaller than min")
                if maximum is not None and default > maximum:
                    raise ValueError(f"Template parameter '{parameter_id}' default is greater than max")
            normalized.append(
                {
                    "id": parameter_id,
                    "label": label,
                    "type": parameter_type,
                    "default": default,
                    "min": minimum,
                    "max": maximum,
                    "step": step,
                    "control": control,
                    "unit": str(item.get("unit") or "").strip() or None,
                    "help": str(item.get("help") or "").strip() or None,
                    "options": options,
                }
            )
        return normalized

    def normalize_presets(self, template: dict[str, Any]) -> list[dict[str, Any]]:
        raw = template.get("parameter_presets", [])
        if raw in (None, {}):
            return []
        if not isinstance(raw, list):
            raise ValueError("Template field 'parameter_presets' must be a list")
        definitions = {item["id"]: item for item in self.normalize_definitions(template)}
        presets: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("Template parameter preset must be a mapping")
            preset_id = str(item.get("id") or "").strip()
            if not preset_id:
                raise ValueError("Template parameter preset is missing a valid 'id'")
            if preset_id in seen:
                raise ValueError(f"Duplicate template parameter preset id: {preset_id}")
            seen.add(preset_id)
            values = item.get("values", {})
            if not isinstance(values, dict):
                raise ValueError(f"Template parameter preset '{preset_id}' field 'values' must be a mapping")
            coerced_values: dict[str, Any] = {}
            for parameter_id, value in values.items():
                definition = definitions.get(parameter_id)
                if definition is None:
                    raise ValueError(f"Template parameter preset '{preset_id}' references unknown parameter '{parameter_id}'")
                coerced_values[parameter_id] = self._coerce_value(
                    parameter_id,
                    definition["type"],
                    value,
                    options=definition.get("options"),
                )
            presets.append(
                {
                    "id": preset_id,
                    "name": str(item.get("name") or preset_id.replace("_", " ").title()),
                    "description": str(item.get("description") or "").strip() or None,
                    "values": coerced_values,
                }
            )
        return presets

    def build_controls(
        self,
        definitions: list[dict[str, Any]],
        values: dict[str, Any],
        *,
        sources: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        controls: list[dict[str, Any]] = []
        source_lookup = sources or {}
        for definition in definitions:
            controls.append(
                {
                    "id": definition["id"],
                    "label": definition["label"],
                    "control": definition["control"],
                    "type": definition["type"],
                    "value": deepcopy(values.get(definition["id"], definition["default"])),
                    "min": definition.get("min"),
                    "max": definition.get("max"),
                    "step": definition.get("step"),
                    "unit": definition.get("unit"),
                    "help": definition.get("help"),
                    "options": deepcopy(definition.get("options") or []),
                    "source": source_lookup.get(definition["id"], "default"),
                }
            )
        return controls

    def resolve_values(
        self,
        definitions: list[dict[str, Any]],
        *,
        presets: list[dict[str, Any]] | None = None,
        values: dict[str, Any] | None = None,
        preset_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        definition_lookup = {item["id"]: item for item in definitions}
        resolved = {item["id"]: deepcopy(item["default"]) for item in definitions}
        sources = {item["id"]: "default" for item in definitions}
        preset_lookup = {item["id"]: item for item in presets or []}
        if preset_id is not None:
            preset = preset_lookup.get(preset_id)
            if preset is None:
                raise KeyError(f"Unknown template parameter preset id: {preset_id}")
            for parameter_id, value in preset["values"].items():
                resolved[parameter_id] = deepcopy(value)
                sources[parameter_id] = "preset"
        if values:
            if not isinstance(values, dict):
                raise ValueError("Template parameter values must be a mapping")
            for parameter_id, value in values.items():
                definition = definition_lookup.get(parameter_id)
                if definition is None:
                    continue
                resolved[parameter_id] = self._coerce_value(
                    parameter_id,
                    definition["type"],
                    value,
                    options=definition.get("options"),
                )
                sources[parameter_id] = "user"
        for definition in definitions:
            parameter_id = definition["id"]
            resolved[parameter_id] = self._clamp_if_needed(definition, resolved[parameter_id])
        return resolved, sources

    def _apply_bindings(self, template: dict[str, Any], values: dict[str, Any]) -> None:
        bindings = template.get("parameter_bindings", {})
        if bindings in (None, {}):
            return
        if not isinstance(bindings, dict):
            raise ValueError("Template field 'parameter_bindings' must be a mapping")
        for item in bindings.get("values", []):
            if not isinstance(item, dict):
                raise ValueError("Template parameter binding entry must be a mapping")
            target = str(item.get("target") or "").strip()
            parameter_id = str(item.get("parameter") or "").strip()
            if not target or not parameter_id:
                raise ValueError("Template parameter value binding requires 'target' and 'parameter'")
            bound_value = deepcopy(values[parameter_id])
            value_map = item.get("value_map")
            if isinstance(value_map, dict):
                mapped = self._mapped_value(value_map, bound_value)
                if mapped is not None:
                    bound_value = deepcopy(mapped)
            self._set_path_value(template, target, bound_value)
        component_grids = bindings.get("component_grids", [])
        if component_grids:
            if not isinstance(component_grids, list):
                raise ValueError("Template parameter bindings field 'component_grids' must be a list")
            generated_components: list[dict[str, Any]] = []
            for item in component_grids:
                generated_components.extend(self._build_component_grid(item, values))
            existing_components = template.get("components", [])
            template["components"] = list(existing_components) + generated_components

    def _build_component_grid(self, binding: dict[str, Any], values: dict[str, Any]) -> list[dict[str, Any]]:
        if not isinstance(binding, dict):
            raise ValueError("Template component grid binding must be a mapping")
        component = binding.get("component")
        if not isinstance(component, dict):
            raise ValueError("Template component grid binding requires a 'component' mapping")
        count_x_parameter = str(binding.get("count_x_parameter") or "").strip()
        count_y_parameter = str(binding.get("count_y_parameter") or "").strip()
        if not count_x_parameter or not count_y_parameter:
            raise ValueError("Template component grid binding requires count_x_parameter and count_y_parameter")
        count_x = int(values[count_x_parameter])
        count_y = int(values[count_y_parameter])
        id_prefix = str(binding.get("id_prefix") or "item")
        start_index = int(binding.get("start_index", 1) or 1)
        group_id = str(binding.get("group_id") or id_prefix)
        group_role = str(binding.get("group_role") or "").strip() or None
        label_pattern = str(binding.get("label_pattern") or "").strip() or None
        generated: list[dict[str, Any]] = []
        next_index = start_index
        for row_index in range(count_y):
            for column_index in range(count_x):
                item = deepcopy(component)
                item["id"] = f"{id_prefix}{next_index}"
                item.setdefault("row", row_index)
                item.setdefault("col", column_index)
                item.setdefault("group_id", group_id)
                if group_role is not None:
                    item.setdefault("group_role", group_role)
                if label_pattern is not None:
                    item.setdefault(
                        "label",
                        label_pattern.format(
                            index=next_index,
                            row=row_index + 1,
                            col=column_index + 1,
                            row_index=row_index,
                            col_index=column_index,
                        ),
                    )
                generated.append(item)
                next_index += 1
        return generated

    def _set_path_value(self, payload: dict[str, Any], path: str, value: Any) -> None:
        tokens = path.split(".")
        cursor: Any = payload
        for token in tokens[:-1]:
            cursor = self._resolve_path_step(cursor, token)
        final_name, final_key = self._parse_path_token(tokens[-1])
        if final_key is None:
            if not isinstance(cursor, dict):
                raise ValueError(f"Cannot assign path '{path}' on non-mapping container")
            cursor[final_name] = deepcopy(value)
            return
        target = cursor.get(final_name) if isinstance(cursor, dict) else None
        if not isinstance(target, list):
            raise ValueError(f"Path '{path}' does not reference a list container")
        item = self._find_list_item(target, final_key)
        item.clear()
        if isinstance(value, dict):
            item.update(deepcopy(value))
            return
        raise ValueError(f"Path '{path}' requires mapping value for indexed assignment")

    def _resolve_path_step(self, cursor: Any, token: str) -> Any:
        name, key = self._parse_path_token(token)
        if not isinstance(cursor, dict):
            raise ValueError(f"Cannot resolve token '{token}' on non-mapping container")
        target = cursor.get(name)
        if key is None:
            if not isinstance(target, dict):
                raise ValueError(f"Path token '{token}' does not reference a mapping")
            return target
        if not isinstance(target, list):
            raise ValueError(f"Path token '{token}' does not reference a list")
        return self._find_list_item(target, key)

    def _find_list_item(self, items: list[Any], key: str) -> dict[str, Any]:
        for item in items:
            if isinstance(item, dict) and str(item.get("id") or "") == key:
                return item
        raise ValueError(f"Unknown list item id '{key}' in parameter binding path")

    def _parse_path_token(self, token: str) -> tuple[str, str | None]:
        match = _PATH_TOKEN_RE.match(token.strip())
        if match is None:
            raise ValueError(f"Invalid parameter binding path token '{token}'")
        return match.group("name"), match.group("key")

    def _resolve_parameter_references(self, template: dict[str, Any], parameters: dict[str, Any]) -> None:
        for field in ("controller", "zones", "components", "layout", "constraints", "defaults", "firmware", "ocf", "metadata"):
            if field in template:
                template[field] = self._resolve_reference_value(template[field], parameters, path=field)

    def _resolve_reference_value(self, value: Any, parameters: dict[str, Any], *, path: str) -> Any:
        if isinstance(value, dict):
            return {
                key: self._resolve_reference_value(item, parameters, path=f"{path}.{key}")
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                self._resolve_reference_value(item, parameters, path=f"{path}[{index}]")
                for index, item in enumerate(value)
            ]
        if not isinstance(value, str):
            return value
        exact_match = _PARAMETER_REFERENCE_RE.fullmatch(value.strip())
        if exact_match is not None:
            parameter_id = exact_match.group(1)
            if parameter_id not in parameters:
                raise ValueError(f"Unknown parameter reference '{parameter_id}' at {path}")
            return deepcopy(parameters[parameter_id])

        def replace(match: re.Match[str]) -> str:
            parameter_id = match.group(1)
            if parameter_id not in parameters:
                raise ValueError(f"Unknown parameter reference '{parameter_id}' at {path}")
            return str(parameters[parameter_id])

        return _PARAMETER_REFERENCE_RE.sub(replace, value)

    def _normalize_options(self, parameter_id: str, parameter_type: str, raw: Any) -> list[dict[str, Any]]:
        if parameter_type != "enum":
            return []
        if not isinstance(raw, list) or not raw:
            raise ValueError(f"Enum template parameter '{parameter_id}' requires a non-empty 'options' list")
        options: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict):
                value = item.get("value")
                label = str(item.get("label") or value)
            else:
                value = item
                label = str(item)
            options.append({"value": value, "label": label})
        return options

    def _coerce_value(
        self,
        parameter_id: str,
        parameter_type: str,
        value: Any,
        *,
        options: list[dict[str, Any]] | None = None,
    ) -> Any:
        if parameter_type == "int":
            return int(value)
        if parameter_type == "float":
            return float(value)
        if parameter_type == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "1", "yes", "on"}:
                    return True
                if lowered in {"false", "0", "no", "off"}:
                    return False
            return bool(value)
        if parameter_type == "string":
            return str(value)
        if parameter_type == "enum":
            option_values = [item["value"] for item in options or []]
            if value not in option_values:
                raise ValueError(f"Enum template parameter '{parameter_id}' has unsupported value '{value}'")
            return value
        raise ValueError(f"Unsupported template parameter type '{parameter_type}' for '{parameter_id}'")

    def _coerce_number_field(self, parameter_id: str, field_name: str, parameter_type: str, value: Any) -> Any:
        if value is None:
            return None
        if parameter_type == "int":
            return int(value)
        return float(value)

    def _clamp_if_needed(self, definition: dict[str, Any], value: Any) -> Any:
        if definition["type"] not in {"int", "float"}:
            return value
        minimum = definition.get("min")
        maximum = definition.get("max")
        bounded = value
        if minimum is not None and bounded < minimum:
            bounded = minimum
        if maximum is not None and bounded > maximum:
            bounded = maximum
        if definition["type"] == "int":
            return int(bounded)
        return float(bounded)

    def _default_control(self, parameter_type: str) -> str:
        return {
            "int": "input",
            "float": "input",
            "bool": "toggle",
            "enum": "select",
            "string": "input",
        }[parameter_type]

    def _mapped_value(self, value_map: dict[str, Any], value: Any) -> Any:
        candidates = [value]
        if isinstance(value, bool):
            candidates.extend([str(value).lower(), str(value)])
        else:
            candidates.append(str(value))
        for candidate in candidates:
            if candidate in value_map:
                return value_map[candidate]
        return None

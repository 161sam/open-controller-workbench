from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ocw_workbench.library.manager import ComponentLibraryManager
from ocw_workbench.services.plugin_service import get_plugin_service
from ocw_workbench.services.template_service import TemplateService


@dataclass(frozen=True)
class PluginCommandSpec:
    id: str
    command_id: str
    command_type: str
    label: str
    tooltip: str
    icon: str
    category: str
    component: str | None = None
    addition_id: str | None = None
    library_ref: str | None = None
    plugin_id: str | None = None
    toolbar: bool = True
    order: int = 1000

    @property
    def menu_text(self) -> str:
        return self.label

    @property
    def dialog_title(self) -> str:
        return self.label

    @property
    def start_message(self) -> str:
        noun = self.label.replace("Place ", "", 1)
        return f"Click in the 3D view to place a {noun}. Press ESC to cancel."

    @property
    def toolbar_name(self) -> str:
        return f"OCW {self.category}"


def iter_plugin_command_specs(active_plugin_only: bool = True) -> tuple[PluginCommandSpec, ...]:
    commands = _merged_command_metadata(active_plugin_only=active_plugin_only)
    specs: list[PluginCommandSpec] = []
    for command_id, metadata in commands.items():
        if not isinstance(metadata, dict):
            continue
        specs.append(_build_spec(command_id, metadata))
    return tuple(sorted(specs, key=lambda spec: (spec.order, spec.category.lower(), spec.label.lower(), spec.command_id)))


def plugin_command_specs_by_component(active_plugin_only: bool = True) -> dict[str, PluginCommandSpec]:
    return {
        spec.component: spec
        for spec in iter_plugin_command_specs(active_plugin_only=active_plugin_only)
        if spec.component is not None
    }


def component_toolbar_command_ids() -> list[str]:
    return [
        spec.command_id
        for spec in iter_plugin_command_specs()
        if spec.command_type == "place_component" and spec.toolbar
    ]


def component_toolbar_groups(active_plugin_id: str | None = None) -> list[tuple[str, list[str]]]:
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for spec in iter_plugin_command_specs():
        if spec.command_type != "place_component":
            continue
        if not spec.toolbar:
            continue
        if active_plugin_id not in {None, "", spec.plugin_id}:
            continue
        if spec.toolbar_name not in grouped:
            grouped[spec.toolbar_name] = []
            order.append(spec.toolbar_name)
        grouped[spec.toolbar_name].append(spec.command_id)
    return [(toolbar_name, grouped[toolbar_name]) for toolbar_name in order]


def command_specs_by_command_id() -> dict[str, PluginCommandSpec]:
    return {spec.command_id: spec for spec in iter_plugin_command_specs()}


def build_plugin_commands(active_plugin_only: bool = True) -> dict[str, Any]:
    commands: dict[str, Any] = {}
    for spec in iter_plugin_command_specs(active_plugin_only=active_plugin_only):
        commands[spec.command_id] = create_freecad_command(spec)
    return commands


def create_freecad_command(spec: PluginCommandSpec) -> Any:
    if spec.command_type == "place_component" and spec.component is not None:
        from ocw_workbench.commands.place_component_type import PlaceComponentTypeCommand

        return PlaceComponentTypeCommand(spec.component, spec=spec)
    if spec.command_type == "apply_suggested_addition" and spec.addition_id is not None:
        from ocw_workbench.commands.apply_suggested_addition import ApplySuggestedAdditionCommand

        return ApplySuggestedAdditionCommand(spec.addition_id, spec=spec)
    raise KeyError(f"Unsupported plugin command type: {spec.command_type}")


def _merged_command_metadata(active_plugin_only: bool = True) -> dict[str, dict[str, Any]]:
    commands = _auto_generated_command_metadata(active_plugin_only=active_plugin_only)
    for command_id, metadata in _explicit_command_metadata(active_plugin_only=active_plugin_only).items():
        if isinstance(metadata, dict):
            commands[str(command_id)] = metadata
    return commands


def _explicit_command_metadata(active_plugin_only: bool = True) -> dict[str, dict[str, Any]]:
    plugin_service = get_plugin_service()
    if active_plugin_only:
        command_set = plugin_service.get_commands_for_active_plugin()
        return command_set.get("commands", {}) if isinstance(command_set, dict) else {}

    merged: dict[str, dict[str, Any]] = {}
    registry = plugin_service.registry()
    for command_set in registry.command_sets().values():
        if not isinstance(command_set, dict):
            continue
        commands = command_set.get("commands", {})
        if not isinstance(commands, dict):
            continue
        for command_id, metadata in commands.items():
            if isinstance(metadata, dict):
                merged[str(command_id)] = metadata
    return merged


def _auto_generated_command_metadata(active_plugin_only: bool = True) -> dict[str, dict[str, Any]]:
    if not active_plugin_only:
        return {}
    plugin_service = get_plugin_service()
    registry = plugin_service.registry()
    active_plugin = registry.get_active_plugin()
    if active_plugin is None:
        return {}
    commands: dict[str, dict[str, Any]] = {}
    for component in ComponentLibraryManager().list_components():
        metadata = _build_standard_place_command_metadata(component, plugin_id=active_plugin.plugin_id)
        if metadata is None:
            continue
        command_id = str(metadata["command_id"])
        existing = commands.get(command_id)
        if existing is None or int(metadata.get("order", 1000)) < int(existing.get("order", 1000)):
            commands[command_id] = metadata
    for metadata in _build_suggested_addition_command_metadata(plugin_id=active_plugin.plugin_id):
        command_id = str(metadata["command_id"])
        existing = commands.get(command_id)
        if existing is None or int(metadata.get("order", 1000)) < int(existing.get("order", 1000)):
            commands[command_id] = metadata
    return commands


def _build_suggested_addition_command_metadata(*, plugin_id: str) -> list[dict[str, Any]]:
    templates = TemplateService().list_templates()
    additions: dict[str, dict[str, Any]] = {}
    for entry in templates:
        template = entry.get("template", {})
        metadata = entry.get("metadata", {})
        if not isinstance(template, dict) or not isinstance(metadata, dict):
            continue
        template_id = str(template.get("id") or "").strip()
        if not template_id:
            continue
        for raw_addition in metadata.get("suggested_additions", []):
            if not isinstance(raw_addition, dict):
                continue
            addition_id = str(raw_addition.get("id") or "").strip()
            if not addition_id:
                continue
            command_id = str(raw_addition.get("command_id") or _command_id_for_suggested_addition(addition_id))
            merged_template_ids = [template_id]
            existing = additions.get(command_id)
            if existing is not None:
                merged_template_ids = sorted(
                    {
                        *(str(value) for value in existing.get("template_ids", []) if isinstance(value, str)),
                        template_id,
                    }
                )
            additions[command_id] = {
                "id": str(raw_addition.get("id") or addition_id),
                "command_id": command_id,
                "type": "apply_suggested_addition",
                "addition_id": addition_id,
                "label": str(raw_addition.get("label") or _humanize_suggested_addition_id(addition_id)),
                "tooltip": str(
                    raw_addition.get("tooltip")
                    or raw_addition.get("description")
                    or f"Apply the suggested MIDI layout step '{addition_id}'."
                ),
                "icon": str(raw_addition.get("icon") or "generic.svg"),
                "category": str(raw_addition.get("category") or "Next Steps"),
                "plugin_id": plugin_id,
                "toolbar": bool(raw_addition.get("toolbar", False)),
                "order": _metadata_order(raw_addition.get("order"), default=150),
                "template_ids": merged_template_ids,
            }
    return list(additions.values())


def _build_standard_place_command_metadata(component: dict[str, Any], *, plugin_id: str) -> dict[str, Any] | None:
    ui = component.get("ui", {})
    if not isinstance(ui, dict):
        return None
    command = ui.get("command", {})
    if not isinstance(command, dict) or not bool(command.get("placeable")):
        return None
    component_type = _component_type(component)
    if component_type is None:
        return None
    command_id = str(command.get("command_id") or _command_id_for_component_type(component_type))
    label = _ensure_place_label(str(command.get("label") or ui.get("label") or component_type.replace("_", " ").title()))
    description = str(component.get("description") or ui.get("label") or component.get("id") or component_type)
    tooltip = str(command.get("tooltip") or description)
    if label not in tooltip:
        tooltip = f"{label}. {tooltip}"
    return {
        "id": str(command.get("id") or f"place_{component_type}"),
        "command_id": command_id,
        "type": "place_component",
        "component": component_type,
        "category": str(command.get("category") or ui.get("category") or component.get("category") or "Components"),
        "icon": str(command.get("icon") or ui.get("icon") or "generic.svg"),
        "label": label,
        "tooltip": tooltip,
        "library_ref": str(component["id"]),
        "plugin_id": plugin_id,
        "toolbar": bool(command.get("toolbar", True)),
        "order": _metadata_order(command.get("order"), default=1000),
    }


def _build_spec(command_key: str, metadata: dict[str, Any]) -> PluginCommandSpec:
    label = str(metadata.get("label") or _humanize_command_id(command_key))
    tooltip = str(metadata.get("tooltip") or label)
    if label not in tooltip:
        tooltip = f"{label}. {tooltip}"
    component = str(metadata.get("component")) if metadata.get("component") is not None else None
    addition_id = str(metadata.get("addition_id")) if metadata.get("addition_id") is not None else None
    return PluginCommandSpec(
        id=str(metadata.get("id") or command_key),
        command_id=str(metadata.get("command_id") or _default_command_id(metadata, command_key)),
        command_type=str(metadata.get("type") or "plugin"),
        label=label,
        tooltip=tooltip,
        icon=str(metadata.get("icon") or "generic.svg"),
        category=str(metadata.get("category") or "Plugin"),
        component=component,
        addition_id=addition_id,
        library_ref=str(metadata.get("library_ref")) if metadata.get("library_ref") is not None else None,
        plugin_id=str(metadata.get("plugin_id")) if metadata.get("plugin_id") is not None else None,
        toolbar=bool(metadata.get("toolbar", metadata.get("type") == "place_component")),
        order=_metadata_order(metadata.get("order"), default=1000),
    )


def _humanize_command_id(command_id: str) -> str:
    return str(command_id).replace("_", " ").strip().title() or "Plugin Command"


def _default_command_id(metadata: dict[str, Any], command_key: str) -> str:
    component = metadata.get("component")
    if isinstance(component, str) and component:
        return _command_id_for_component_type(component)
    addition_id = metadata.get("addition_id")
    if isinstance(addition_id, str) and addition_id:
        return _command_id_for_suggested_addition(addition_id)
    return f"OCW_{_humanize_command_id(command_key).replace(' ', '')}"


def _component_type(component: dict[str, Any]) -> str | None:
    value = component.get("type")
    if isinstance(value, str) and value.strip():
        return value.strip()
    ocf = component.get("ocf", {})
    if isinstance(ocf, dict):
        control_type = ocf.get("control_type")
        if isinstance(control_type, str) and control_type.strip():
            return control_type.strip()
    category = component.get("category")
    if isinstance(category, str) and category.strip():
        return category.strip()
    return None


def _command_id_for_component_type(component_type: str) -> str:
    suffix = component_type.replace("_", " ").title().replace(" ", "")
    return f"OCW_Place{suffix}"


def _command_id_for_suggested_addition(addition_id: str) -> str:
    suffix = _humanize_suggested_addition_id(addition_id).replace(" ", "")
    return f"OCW_{suffix}"


def _humanize_suggested_addition_id(addition_id: str) -> str:
    normalized = str(addition_id).replace("_", " ").strip().title()
    return normalized if normalized.startswith("Add ") else f"Add {normalized}"


def _ensure_place_label(label: str) -> str:
    normalized = label.strip() or "Component"
    return normalized if normalized.startswith("Place ") else f"Place {normalized}"


def _metadata_order(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

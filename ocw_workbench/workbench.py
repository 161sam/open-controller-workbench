from __future__ import annotations

import traceback
from typing import Any

try:
    import FreeCAD as App
except ImportError:
    App = None

try:
    import FreeCADGui as Gui
except ImportError:
    Gui = None

from ocw_workbench.gui.interaction.lifecycle import InteractionSessionManager
from ocw_workbench.gui.interaction.view_drag_controller import ViewDragController
from ocw_workbench.gui.interaction.view_pick_controller import ViewPickController
from ocw_workbench.gui.interaction.view_place_controller import ViewPlaceController
from ocw_workbench.gui.docking import create_or_reuse_dock, focus_dock, remove_dock
from ocw_workbench.gui.feedback import apply_status_message, format_toggle_message, format_validation_message
from ocw_workbench.gui.overlay.renderer import OverlayRenderer
from ocw_workbench.gui.panels._common import FallbackLabel, load_qt, log_exception, log_to_console, set_label_text, set_size_policy
from ocw_workbench.gui.panels._common import build_panel_container
from ocw_workbench.gui.panels.component_palette_panel import ComponentPalettePanel
from ocw_workbench.gui.panels.components_panel import ComponentsPanel
from ocw_workbench.gui.panels.constraints_panel import ConstraintsPanel
from ocw_workbench.gui.panels.create_panel import CreatePanel
from ocw_workbench.gui.panels.info_panel import InfoPanel
from ocw_workbench.gui.panels.layout_panel import LayoutPanel
from ocw_workbench.gui.panels.plugin_manager_panel import PluginManagerPanel
from ocw_workbench.gui.runtime import component_icon_path, icon_path
from ocw_workbench.freecad_api.metadata import get_document_data
from ocw_workbench.freecad_api.state import has_persisted_state
from ocw_workbench.services.alignment_service import AlignmentService
from ocw_workbench.services.component_pattern_service import ComponentPatternService
from ocw_workbench.services.component_transform_service import ComponentTransformService
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService
from ocw_workbench.services.overlay_service import OverlayService
from ocw_workbench.services.userdata_service import MAX_FAVORITE_COMPONENTS, UserDataService

_ACTIVE_WORKBENCH: ProductWorkbenchPanel | None = None
_ACTIVE_DOCK: Any | None = None
_ACTIVE_COMPONENT_PALETTE: ComponentPalettePanel | None = None
_ACTIVE_COMPONENT_PALETTE_DOCK: Any | None = None
_FAVORITE_COMMAND_IDS = [f"OCW_FavoriteComponent_{index + 1}" for index in range(MAX_FAVORITE_COMPONENTS)]
_FAVORITE_MORE_COMMAND_ID = "OCW_OpenComponentPaletteMore"
_WORKBENCH_TITLE = "Open Controller Workbench"
_WORKFLOW_STEPS: tuple[tuple[str, str], ...] = (
    ("create", "Template"),
    ("components", "Components"),
    ("layout", "Layout"),
    ("constraints", "Validate"),
    ("plugins", "Plugins"),
)
_WORKFLOW_STEP_INDEX = {panel_name: index for index, (panel_name, _label) in enumerate(_WORKFLOW_STEPS)}
_WORKFLOW_STEP_LABELS = [label for _panel_name, label in _WORKFLOW_STEPS]


class _FallbackStack:
    def __init__(self) -> None:
        self._index: int = 0

    def currentIndex(self) -> int:
        return self._index

    def setCurrentIndex(self, index: int) -> None:
        self._index = int(index)


class _FallbackStepButton:
    def __init__(self, label: str) -> None:
        self.text = label
        self._checked: bool = False

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, value: bool) -> None:
        self._checked = bool(value)

    def setProperty(self, _name: str, _value: Any) -> None:
        pass

    def setText(self, value: str) -> None:
        self.text = value

    def update(self) -> None:
        pass


def _emit_runtime_traceback(context: str, exc: Exception) -> None:
    details = traceback.format_exc()
    if details.strip() == "NoneType: None":
        details = f"{exc.__class__.__name__}: {exc}"
    log_to_console(f"{context}: {exc.__class__.__name__}: {exc}", level="error")
    log_to_console("[OCW TRACEBACK START]", level="error")
    log_to_console(details.rstrip(), level="error")
    log_to_console("[OCW TRACEBACK END]", level="error")


class _UnavailablePluginManagerPanel:
    def __init__(self, widget: Any, error_message: str) -> None:
        self.widget = widget
        self.error_message = error_message

    def refresh(self) -> list[dict[str, Any]]:
        return []

    def enable_selected_plugin(self) -> dict[str, Any]:
        raise RuntimeError(self.error_message)

    def disable_selected_plugin(self) -> dict[str, Any]:
        raise RuntimeError(self.error_message)

    def reload_plugins(self) -> list[dict[str, Any]]:
        raise RuntimeError(self.error_message)


class _LoggedCommand:
    def __init__(self, command_id: str, command: Any) -> None:
        self.command_id = command_id
        self.command = command

    def Activated(self) -> Any:
        log_to_console(f"Command '{self.command_id}' activated.")
        result = self.command.Activated()
        log_to_console(f"Command '{self.command_id}' completed.")
        return result

    def GetResources(self) -> Any:
        return self.command.GetResources()

    def IsActive(self) -> Any:
        if hasattr(self.command, "IsActive"):
            return self.command.IsActive()
        return True


class _FavoriteComponentCommand:
    def __init__(self, slot_index: int, userdata_service: UserDataService | None = None) -> None:
        self.slot_index = slot_index
        svc = userdata_service or UserDataService()
        favorite_ids = svc.list_favorite_component_ids()
        self._component: dict[str, Any] | None = None
        if slot_index < len(favorite_ids):
            component_id = favorite_ids[slot_index]
            try:
                from ocw_workbench.services.library_service import LibraryService
                self._component = LibraryService().get(component_id)
            except Exception:
                pass

    def GetResources(self) -> dict[str, str]:
        component = self._component
        if component is None:
            return {
                "MenuText": f"Favorite {self.slot_index + 1}",
                "ToolTip": "No favorite component assigned.",
                "Pixmap": icon_path("default"),
            }
        ui = component.get("ui", {})
        label = str(ui.get("label") or component["id"])
        return {
            "MenuText": label,
            "ToolTip": f"Prepare '{component['id']}' for placement.",
            "Pixmap": component_icon_path(ui.get("icon")),
        }

    def IsActive(self) -> bool:
        return self._component is not None

    def Activated(self) -> None:
        component = self._component
        if component is None:
            ensure_component_palette_ui()
            return
        try:
            import FreeCAD as App

            doc = App.ActiveDocument or App.newDocument("Controller")
            palette = ensure_component_palette_ui(doc)
            palette.select_component_template(component["id"])
            start_component_place_mode(doc, component["id"])
            focus_dock(_ACTIVE_COMPONENT_PALETTE_DOCK)
            log_to_console(f"Favorite component '{component['id']}' entered placement mode.")
        except Exception as exc:
            from ocw_workbench.gui.runtime import show_error

            show_error("Favorite Component", exc)


class OpenControllerWorkbench((Gui.Workbench if Gui is not None else object)):
    MenuText = _WORKBENCH_TITLE
    ToolTip = "Create and refine modular controllers in the Open Controller Workbench."
    Icon = icon_path("workbench")

    def GetClassName(self) -> str:
        return "Gui::PythonWorkbench"

    def Initialize(self) -> None:
        if Gui is None:
            return
        from ocw_workbench.commands.add_component import AddComponentCommand
        from ocw_workbench.commands.align_distribute import SelectionArrangeCommand
        from ocw_workbench.commands.apply_layout import ApplyLayoutCommand
        from ocw_workbench.commands.component_patterns import DuplicateSelectionCommand, GridArrayCommand, LinearArrayCommand
        from ocw_workbench.commands.create_from_template import CreateFromTemplateCommand
        from ocw_workbench.commands.disable_plugin import DisablePluginCommand
        from ocw_workbench.commands.drag_move_component import DragMoveComponentCommand
        from ocw_workbench.commands.enable_plugin import EnablePluginCommand
        from ocw_workbench.commands.import_template_from_fcstd import ImportTemplateFromFCStdCommand
        from ocw_workbench.commands.open_plugin_manager import OpenPluginManagerCommand
        from ocw_workbench.commands.open_component_palette import OpenComponentPaletteCommand
        from ocw_workbench.commands.reload_plugins import ReloadPluginsCommand
        from ocw_workbench.commands.select_component import SelectComponentCommand
        from ocw_workbench.commands.selection_transform import SelectionTransformCommand
        from ocw_workbench.commands.show_constraint_overlay import ShowConstraintOverlayCommand
        from ocw_workbench.commands.snap_to_grid import SnapToGridCommand
        from ocw_workbench.commands.toggle_conflict_lines import ToggleConflictLinesCommand
        from ocw_workbench.commands.toggle_constraint_labels import ToggleConstraintLabelsCommand
        from ocw_workbench.commands.toggle_measurements import ToggleMeasurementsCommand
        from ocw_workbench.commands.toggle_overlay import ToggleOverlayCommand
        from ocw_workbench.commands.validate_constraints import ValidateConstraintsCommand
        from ocw_workbench.commands.place_component_type import PlaceComponentTypeCommand

        Gui.addCommand("OCW_CreateController", _LoggedCommand("OCW_CreateController", CreateFromTemplateCommand()))
        Gui.addCommand("OCW_AddComponent", _LoggedCommand("OCW_AddComponent", AddComponentCommand()))
        Gui.addCommand("OCW_ImportTemplateFromFCStd", _LoggedCommand("OCW_ImportTemplateFromFCStd", ImportTemplateFromFCStdCommand()))
        Gui.addCommand("OCW_ApplyLayout", _LoggedCommand("OCW_ApplyLayout", ApplyLayoutCommand()))
        Gui.addCommand("OCW_SelectComponent", _LoggedCommand("OCW_SelectComponent", SelectComponentCommand()))
        Gui.addCommand("OCW_ValidateConstraints", _LoggedCommand("OCW_ValidateConstraints", ValidateConstraintsCommand()))
        Gui.addCommand("OCW_ToggleOverlay", _LoggedCommand("OCW_ToggleOverlay", ToggleOverlayCommand()))
        Gui.addCommand("OCW_ShowConstraintOverlay", _LoggedCommand("OCW_ShowConstraintOverlay", ShowConstraintOverlayCommand()))
        Gui.addCommand("OCW_DragMoveComponent", _LoggedCommand("OCW_DragMoveComponent", DragMoveComponentCommand()))
        Gui.addCommand("OCW_SnapToGrid", _LoggedCommand("OCW_SnapToGrid", SnapToGridCommand()))
        Gui.addCommand("OCW_DuplicateSelected", _LoggedCommand("OCW_DuplicateSelected", DuplicateSelectionCommand()))
        Gui.addCommand("OCW_ArrayHorizontal", _LoggedCommand("OCW_ArrayHorizontal", LinearArrayCommand("x")))
        Gui.addCommand("OCW_ArrayVertical", _LoggedCommand("OCW_ArrayVertical", LinearArrayCommand("y")))
        Gui.addCommand("OCW_GridArray", _LoggedCommand("OCW_GridArray", GridArrayCommand()))
        Gui.addCommand("OCW_RotateCW90", _LoggedCommand("OCW_RotateCW90", SelectionTransformCommand("rotate_cw_90")))
        Gui.addCommand("OCW_RotateCCW90", _LoggedCommand("OCW_RotateCCW90", SelectionTransformCommand("rotate_ccw_90")))
        Gui.addCommand("OCW_Rotate180", _LoggedCommand("OCW_Rotate180", SelectionTransformCommand("rotate_180")))
        Gui.addCommand("OCW_MirrorHorizontal", _LoggedCommand("OCW_MirrorHorizontal", SelectionTransformCommand("mirror_horizontal")))
        Gui.addCommand("OCW_MirrorVertical", _LoggedCommand("OCW_MirrorVertical", SelectionTransformCommand("mirror_vertical")))
        Gui.addCommand("OCW_AlignLeft", _LoggedCommand("OCW_AlignLeft", SelectionArrangeCommand("align_left")))
        Gui.addCommand("OCW_AlignCenterX", _LoggedCommand("OCW_AlignCenterX", SelectionArrangeCommand("align_center_x")))
        Gui.addCommand("OCW_AlignRight", _LoggedCommand("OCW_AlignRight", SelectionArrangeCommand("align_right")))
        Gui.addCommand("OCW_AlignTop", _LoggedCommand("OCW_AlignTop", SelectionArrangeCommand("align_top")))
        Gui.addCommand("OCW_AlignCenterY", _LoggedCommand("OCW_AlignCenterY", SelectionArrangeCommand("align_center_y")))
        Gui.addCommand("OCW_AlignBottom", _LoggedCommand("OCW_AlignBottom", SelectionArrangeCommand("align_bottom")))
        Gui.addCommand(
            "OCW_DistributeHorizontally",
            _LoggedCommand("OCW_DistributeHorizontally", SelectionArrangeCommand("distribute_horizontal")),
        )
        Gui.addCommand(
            "OCW_DistributeVertically",
            _LoggedCommand("OCW_DistributeVertically", SelectionArrangeCommand("distribute_vertical")),
        )
        Gui.addCommand("OCW_ToggleMeasurements", _LoggedCommand("OCW_ToggleMeasurements", ToggleMeasurementsCommand()))
        Gui.addCommand("OCW_ToggleConflictLines", _LoggedCommand("OCW_ToggleConflictLines", ToggleConflictLinesCommand()))
        Gui.addCommand("OCW_ToggleConstraintLabels", _LoggedCommand("OCW_ToggleConstraintLabels", ToggleConstraintLabelsCommand()))
        Gui.addCommand("OCW_OpenPluginManager", _LoggedCommand("OCW_OpenPluginManager", OpenPluginManagerCommand()))
        Gui.addCommand("OCW_OpenComponentPalette", _LoggedCommand("OCW_OpenComponentPalette", OpenComponentPaletteCommand()))
        Gui.addCommand("OCW_EnablePlugin", _LoggedCommand("OCW_EnablePlugin", EnablePluginCommand()))
        Gui.addCommand("OCW_DisablePlugin", _LoggedCommand("OCW_DisablePlugin", DisablePluginCommand()))
        Gui.addCommand("OCW_ReloadPlugins", _LoggedCommand("OCW_ReloadPlugins", ReloadPluginsCommand()))
        for _ctype in ("button", "encoder", "fader", "pad", "display", "rgb_button"):
            _cmd_id = f"OCW_Place{_ctype.replace('_', ' ').title().replace(' ', '')}"
            Gui.addCommand(_cmd_id, _LoggedCommand(_cmd_id, PlaceComponentTypeCommand(_ctype)))
        refresh_favorite_component_commands()
        Gui.addCommand(
            _FAVORITE_MORE_COMMAND_ID,
            _LoggedCommand(_FAVORITE_MORE_COMMAND_ID, OpenComponentPaletteCommand()),
        )

        project_commands = ["OCW_CreateController", "OCW_ImportTemplateFromFCStd"]
        place_type_commands = [
            "OCW_PlaceButton",
            "OCW_PlaceEncoder",
            "OCW_PlaceFader",
            "OCW_PlacePad",
            "OCW_PlaceDisplay",
            "OCW_PlaceRgbButton",
            "OCW_OpenComponentPalette",
        ]
        component_commands = [
            "OCW_AddComponent",
            "OCW_OpenComponentPalette",
        ]
        layout_commands = [
            "OCW_ApplyLayout",
            "OCW_DragMoveComponent",
            "OCW_SnapToGrid",
            "OCW_DuplicateSelected",
            "OCW_ArrayHorizontal",
            "OCW_ArrayVertical",
            "OCW_GridArray",
            "OCW_RotateCW90",
            "OCW_RotateCCW90",
            "OCW_Rotate180",
            "OCW_MirrorHorizontal",
            "OCW_MirrorVertical",
            "OCW_AlignLeft",
            "OCW_AlignCenterX",
            "OCW_AlignRight",
            "OCW_AlignTop",
            "OCW_AlignCenterY",
            "OCW_AlignBottom",
            "OCW_DistributeHorizontally",
            "OCW_DistributeVertically",
        ]
        validate_commands = [
            "OCW_ValidateConstraints",
            "OCW_ToggleOverlay",
            "OCW_ShowConstraintOverlay",
            "OCW_ToggleMeasurements",
            "OCW_ToggleConflictLines",
            "OCW_ToggleConstraintLabels",
        ]
        view_commands = [
            "OCW_ToggleOverlay",
            "OCW_ToggleMeasurements",
            "OCW_ToggleConflictLines",
            "OCW_ToggleConstraintLabels",
        ]
        plugin_commands = [
            "OCW_OpenPluginManager",
        ]
        plugin_advanced_commands = [
            "OCW_EnablePlugin",
            "OCW_DisablePlugin",
            "OCW_ReloadPlugins",
        ]
        self.appendToolbar("OCW Project", project_commands)
        self.appendToolbar("OCW Components", place_type_commands)
        self.appendToolbar("OCW Favorites", _FAVORITE_COMMAND_IDS + [_FAVORITE_MORE_COMMAND_ID])
        self.appendToolbar("OCW Layout", layout_commands)
        self.appendToolbar("OCW Validate", [validate_commands[0], validate_commands[2]])
        self.appendToolbar("OCW View", view_commands)
        self.appendToolbar("OCW Plugins", plugin_commands)
        self.appendMenu(
            "OCW",
            project_commands + place_type_commands + layout_commands + validate_commands[:1] + plugin_commands,
        )
        self.appendMenu("OCW/Create", project_commands)
        self.appendMenu("OCW/Components", place_type_commands)
        self.appendMenu("OCW/Layout", layout_commands)
        self.appendMenu("OCW/View", validate_commands[1:])
        self.appendMenu("OCW/Validate", validate_commands[:1] + validate_commands[2:])
        self.appendMenu("OCW/Plugins", plugin_commands)
        self.appendMenu("OCW/Plugins/Advanced", plugin_advanced_commands)

    def Activated(self) -> None:
        if App is None:
            return
        try:
            doc = App.ActiveDocument or App.newDocument("Controller")
            _bootstrap_document_if_needed(doc)
            ensure_workbench_ui(doc, focus="create")
            log_to_console("Workbench activated.")
        except Exception as exc:
            log_exception("Workbench activation failed", exc)

    def Deactivated(self) -> None:
        return


class ProductWorkbenchPanel:
    def __init__(self, doc: Any, controller_service: ControllerService | None = None) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.interaction_service = InteractionService(self.controller_service)
        self.alignment_service = AlignmentService()
        self.pattern_service = ComponentPatternService()
        self.transform_service = ComponentTransformService()
        self.overlay_service = OverlayService(self.controller_service)
        self.overlay_renderer = OverlayRenderer(self.overlay_service)
        self.interaction_manager = InteractionSessionManager()
        self.place_controller = ViewPlaceController(
            controller_service=self.controller_service,
            interaction_service=self.interaction_service,
            overlay_renderer=self.overlay_renderer,
            on_status=self.set_status,
            on_finished=self._handle_interaction_finished,
            on_committed=self._handle_placement_committed,
        )
        self.drag_controller = ViewDragController(
            controller_service=self.controller_service,
            interaction_service=self.interaction_service,
            overlay_renderer=self.overlay_renderer,
            on_status=self.set_status,
            on_finished=self._handle_interaction_finished,
        )
        self.pick_controller = ViewPickController(
            controller_service=self.controller_service,
            overlay_renderer=self.overlay_renderer,
            on_status=self.set_status,
            on_finished=self._handle_pick_finished,
            on_selected=self._handle_pick_selected,
        )
        self.form = self._build_shell()
        self.widget = self.form["widget"]
        self.create_panel = CreatePanel(
            doc,
            controller_service=self.controller_service,
            on_created=self._handle_created,
            on_status=self.set_status,
        )
        self.layout_panel = LayoutPanel(
            doc,
            controller_service=self.controller_service,
            interaction_service=self.interaction_service,
            on_applied=self._handle_layout_applied,
            on_overlay_changed=self.refresh_overlay,
            on_status=self.set_status,
        )
        self.components_panel = ComponentsPanel(
            doc,
            controller_service=self.controller_service,
            interaction_service=self.interaction_service,
            on_selection_changed=self._handle_selection_changed,
            on_components_changed=self._handle_components_changed,
            on_status=self.set_status,
            on_drag_requested=self.start_drag_mode,
        )
        self.constraints_panel = ConstraintsPanel(
            doc,
            controller_service=self.controller_service,
            on_selection_changed=self._handle_selection_changed,
            on_validated=self._handle_validated,
            on_status=self.set_status,
        )
        self.info_panel = InfoPanel(
            doc,
            controller_service=self.controller_service,
            on_updated=self._handle_controller_updated,
            on_status=self.set_status,
        )
        self.plugin_manager_panel = self._build_plugin_manager_panel()
        self._mount_panels()
        self.refresh_all()
        self.focus_panel("create")
        self.pick_controller.start(self.doc)

    def refresh_all(self) -> None:
        self.create_panel.refresh()
        self.layout_panel.refresh()
        self.components_panel.refresh()
        self.constraints_panel.refresh()
        self.info_panel.refresh()
        self.plugin_manager_panel.refresh()
        self.refresh_overlay()
        self._update_context_summary()

    def focus_panel(self, panel_name: str) -> None:
        normalized_panel = "create" if panel_name == "info" else panel_name
        step_index = _WORKFLOW_STEP_INDEX.get(normalized_panel)
        content_host = self.form.get("content_host")
        if step_index is not None and content_host is not None and hasattr(content_host, "setCurrentIndex"):
            content_host.setCurrentIndex(step_index)
        self._update_stepper_state(normalized_panel)
        widget = {
            "create": self.create_panel.widget,
            "components": self.components_panel.widget,
            "layout": self.layout_panel.widget,
            "constraints": self.constraints_panel.widget,
            "info": self.info_panel.widget,
            "plugins": self.plugin_manager_panel.widget,
        }.get(panel_name)
        if widget is not None and hasattr(widget, "setFocus"):
            widget.setFocus()
        self._update_context_summary(active_panel=normalized_panel)

    def set_status(self, message: str, level: str | None = None) -> None:
        if level is None:
            lower = message.lower()
            if lower.startswith("could not") or lower.startswith("validation found"):
                level = "error"
            elif "created" in lower or "updated controller geometry" in lower or "validation passed" in lower:
                level = "success"
            elif "warning" in lower:
                level = "warning"
            else:
                level = "info"
        apply_status_message(self.form["status"], message, level=level)
        set_label_text(self.form["overlay_status"], self._overlay_status_text())
        self._update_context_summary()

    def refresh_overlay(self) -> dict[str, Any]:
        payload = self.overlay_renderer.refresh(self.doc)
        set_label_text(self.form["overlay_status"], self._overlay_status_text(payload))
        self._update_context_summary()
        return payload

    def refresh_context_panels(self, refresh_components: bool = False) -> None:
        self.layout_panel.refresh()
        self.constraints_panel.refresh()
        self.info_panel.refresh()
        if refresh_components:
            self.components_panel.refresh()

    def toggle_overlay(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_overlay(self.doc)
        self.refresh_overlay()
        self.layout_panel.refresh()
        self.constraints_panel.refresh()
        self.set_status(
            format_toggle_message(
                "Overlay",
                settings["overlay_enabled"],
                "Shows layout guides without changing model geometry.",
            )
        )
        return settings

    def toggle_constraint_overlay(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_constraint_overlay(self.doc)
        self.refresh_overlay()
        self.layout_panel.refresh()
        self.constraints_panel.refresh()
        self.set_status(
            format_toggle_message(
                "Issue overlay",
                settings["show_constraints"],
                "Shows validation issues in the 3D view.",
            )
        )
        return settings

    def toggle_measurements(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_measurements(self.doc)
        self.refresh_overlay()
        self.layout_panel.refresh()
        self.constraints_panel.refresh()
        self.set_status(
            format_toggle_message(
                "Measurement guides",
                settings["measurements_enabled"],
                "Helps check spacing while refining placement.",
            )
        )
        return settings

    def toggle_conflict_lines(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_conflict_lines(self.doc)
        self.refresh_overlay()
        self.layout_panel.refresh()
        self.constraints_panel.refresh()
        self.set_status(
            format_toggle_message(
                "Conflict lines",
                settings["conflict_lines_enabled"],
                "Shows visual conflict paths only.",
            )
        )
        return settings

    def toggle_constraint_labels(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_constraint_labels(self.doc)
        self.refresh_overlay()
        self.layout_panel.refresh()
        self.constraints_panel.refresh()
        self.set_status(
            format_toggle_message(
                "Issue labels",
                settings["constraint_labels_enabled"],
                "Shows issue names next to overlay markers.",
            )
        )
        return settings

    def snap_selection_to_grid(self) -> dict[str, Any]:
        result = self.interaction_service.snap_selected_component(self.doc)
        self.refresh_context_panels(refresh_components=True)
        self.refresh_overlay()
        self.focus_panel("components")
        self.set_status(f"Snapped '{result['component_id']}' to the current grid.")
        return result

    def apply_selection_arrangement(self, operation: str) -> dict[str, Any]:
        state = self.controller_service.get_state(self.doc)
        selected_ids = self.controller_service.get_selected_component_ids(self.doc)
        selected_components = [component for component in state["components"] if component["id"] in selected_ids]
        plan = self.alignment_service.build_updates(selected_components, operation)
        if plan["updates_by_component"]:
            self.controller_service.bulk_update_components(
                self.doc,
                plan["updates_by_component"],
                transaction_name=plan["transaction_name"],
            )
            self.refresh_context_panels(refresh_components=True)
            self.refresh_overlay()
        self.focus_panel("components")
        count = len(selected_components)
        moved_count = int(plan.get("moved_count", 0))
        if moved_count <= 0:
            self.set_status(f"{self._arrangement_label(operation)} left {count} selected components unchanged.")
        else:
            self.set_status(f"{self._arrangement_label(operation)} applied to {count} selected components.")
        return {
            "operation": operation,
            "selected_count": count,
            "moved_count": moved_count,
            "plan": plan,
        }

    def apply_selection_transform(self, operation: str) -> dict[str, Any]:
        state = self.controller_service.get_state(self.doc)
        selected_ids = self.controller_service.get_selected_component_ids(self.doc)
        selected_components = [component for component in state["components"] if component["id"] in selected_ids]
        plan = self.transform_service.build_updates(selected_components, operation)
        if plan["updates_by_component"]:
            self.controller_service.bulk_update_components(
                self.doc,
                plan["updates_by_component"],
                transaction_name=plan["transaction_name"],
            )
            self.refresh_context_panels(refresh_components=True)
            self.refresh_overlay()
        self.focus_panel("components")
        count = len(selected_components)
        moved_count = int(plan.get("moved_count", 0))
        if moved_count <= 0:
            self.set_status(f"{self._transform_label(operation)} left {count} selected components unchanged.")
        else:
            self.set_status(f"{self._transform_label(operation)} applied to {count} selected components.")
        return {
            "operation": operation,
            "selected_count": count,
            "moved_count": moved_count,
            "plan": plan,
        }

    def duplicate_selection_once(self, *, offset_x: float, offset_y: float) -> dict[str, Any]:
        return self._apply_selection_pattern(
            self.pattern_service.duplicate_once(
                self._selected_components_in_order(),
                self.controller_service.get_state(self.doc)["components"],
                offset_x=offset_x,
                offset_y=offset_y,
            )
        )

    def array_selection_linear(self, *, axis: str, count: int, spacing: float) -> dict[str, Any]:
        return self._apply_selection_pattern(
            self.pattern_service.linear_array(
                self._selected_components_in_order(),
                self.controller_service.get_state(self.doc)["components"],
                axis=axis,
                count=count,
                spacing=spacing,
            )
        )

    def array_selection_grid(self, *, rows: int, cols: int, spacing_x: float, spacing_y: float) -> dict[str, Any]:
        return self._apply_selection_pattern(
            self.pattern_service.grid_array(
                self._selected_components_in_order(),
                self.controller_service.get_state(self.doc)["components"],
                rows=rows,
                cols=cols,
                spacing_x=spacing_x,
                spacing_y=spacing_y,
            )
        )

    def enable_selected_plugin(self) -> dict[str, Any]:
        result = self.plugin_manager_panel.enable_selected_plugin()
        self.refresh_all()
        self.focus_panel("plugins")
        return result

    def disable_selected_plugin(self) -> dict[str, Any]:
        result = self.plugin_manager_panel.disable_selected_plugin()
        self.refresh_all()
        self.focus_panel("plugins")
        return result

    def reload_plugins(self) -> list[dict[str, Any]]:
        result = self.plugin_manager_panel.reload_plugins()
        self.refresh_all()
        self.focus_panel("plugins")
        return result

    def accept(self) -> bool:
        self.refresh_all()
        return True

    def reject(self) -> bool:
        self.interaction_manager.cancel_active(reason="cancel", publish_status=False)
        return True

    def start_place_mode(self, template_id: str) -> bool:
        self.pick_controller.cancel(publish_status=False)
        self.interaction_manager.cancel_active(reason="switch", publish_status=False)
        started = self.place_controller.start(self.doc, template_id)
        if started:
            self.interaction_manager.activate("place", self.doc, self.place_controller.cancel)
        return started

    def start_drag_mode(self) -> bool:
        self.pick_controller.cancel(publish_status=False)
        self.interaction_manager.cancel_active(reason="switch", publish_status=False)
        started = self.drag_controller.start(self.doc)
        if started:
            self.interaction_manager.activate("drag", self.doc, self.drag_controller.cancel)
        return started

    def handle_document_context_changed(self, doc: Any | None) -> None:
        self.interaction_manager.handle_document_changed(doc)

    def handle_document_closed(self) -> None:
        self.interaction_manager.handle_document_closed(self.doc)

    def _build_shell(self) -> dict[str, Any]:
        _qtcore, _qtgui, qtwidgets = load_qt()
        if qtwidgets is None:
            _fallback_stack = _FallbackStack()
            _fallback_buttons = {
                panel_name: _FallbackStepButton(label)
                for panel_name, label in _WORKFLOW_STEPS
            }
            return {
                "widget": object(),
                "title": FallbackLabel(_WORKBENCH_TITLE),
                "context_summary": FallbackLabel("Template | 0 components | grid 1.0 mm | validation clear"),
                "status": FallbackLabel("Workbench ready."),
                "overlay_status": FallbackLabel("Overlay ready."),
                "header_bar": object(),
                "stepper_bar": object(),
                "content_host": _fallback_stack,
                "stack": _fallback_stack,
                "footer_bar": object(),
                "step_buttons": _fallback_buttons,
                "step_flow_markers": [],
                "step_button_labels": dict(_WORKFLOW_STEPS),
                "primary_navigation": "stepper",
                "navigation_items": list(_WORKFLOW_STEP_LABELS),
                "navigation_count": 1,
                "active_step": "create",
            }

        widget = qtwidgets.QWidget()
        if hasattr(widget, "setMinimumSize"):
            widget.setMinimumSize(0, 0)
        if hasattr(widget, "setObjectName"):
            widget.setObjectName("OCWWorkbenchShell")
        root = qtwidgets.QVBoxLayout(widget)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)
        widget.setStyleSheet(_workbench_shell_stylesheet())

        header_box = qtwidgets.QFrame()
        if hasattr(header_box, "setObjectName"):
            header_box.setObjectName("OCWHeaderBar")
        header_layout = qtwidgets.QVBoxLayout(header_box)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(4)

        title = qtwidgets.QLabel(_WORKBENCH_TITLE)
        if hasattr(title, "setObjectName"):
            title.setObjectName("OCWHeaderTitle")
        context_summary = qtwidgets.QLabel("Create | 0 components | grid 1.0 mm | validation clear")
        if hasattr(context_summary, "setObjectName"):
            context_summary.setObjectName("OCWContextSummary")
        context_summary.setWordWrap(True)

        status = qtwidgets.QLabel("Workbench ready.")
        status.setWordWrap(True)
        if hasattr(status, "setObjectName"):
            status.setObjectName("OCWStatusText")
        overlay_status = qtwidgets.QLabel("Overlay ready.")
        overlay_status.setWordWrap(True)
        if hasattr(overlay_status, "setObjectName"):
            overlay_status.setObjectName("OCWOverlayText")

        header_layout.addWidget(title)
        header_layout.addWidget(context_summary)

        stepper_box = qtwidgets.QFrame()
        if hasattr(stepper_box, "setObjectName"):
            stepper_box.setObjectName("OCWStepperBar")
        stepper_layout = qtwidgets.QHBoxLayout(stepper_box)
        stepper_layout.setContentsMargins(12, 0, 12, 0)
        stepper_layout.setSpacing(6)
        step_buttons: dict[str, Any] = {}
        step_button_labels = dict(_WORKFLOW_STEPS)
        step_flow_markers: list[Any] = []
        for index, (panel_name, label) in enumerate(_WORKFLOW_STEPS):
            button = qtwidgets.QPushButton(label)
            if hasattr(button, "setObjectName"):
                button.setObjectName("OCWStepButton")
            if hasattr(button, "setCheckable"):
                button.setCheckable(True)
            if hasattr(button, "setProperty"):
                button.setProperty("active", panel_name == "create")
                button.setProperty("done", False)
                button.setProperty("future", panel_name != "create")
                button.setProperty("disabled_step", False)
            if hasattr(button, "clicked"):
                button.clicked.connect(lambda _checked=False, target=panel_name: self.focus_panel(target))
            set_size_policy(button, horizontal="expanding", vertical="preferred")
            stepper_layout.addWidget(button, 1)
            step_buttons[panel_name] = button
            if index >= len(_WORKFLOW_STEPS) - 1:
                continue
            flow_label = qtwidgets.QLabel("››")
            if hasattr(flow_label, "setObjectName"):
                flow_label.setObjectName("OCWStepFlow")
            stepper_layout.addWidget(flow_label)
            step_flow_markers.append(flow_label)

        # The stepper is the only primary navigation. Content pages stay in a
        # stacked host so existing panels can be reused without tab chrome.
        content_host = qtwidgets.QStackedWidget()
        if hasattr(content_host, "setObjectName"):
            content_host.setObjectName("OCWStepContentHost")
        set_size_policy(content_host, horizontal="preferred", vertical="expanding")
        create_page, create_layout = _step_page(qtwidgets)
        components_page, components_layout = _step_page(qtwidgets)
        layout_page, layout_layout = _step_page(qtwidgets)
        validate_page, validate_layout = _step_page(qtwidgets)
        plugins_page, plugins_layout = _step_page(qtwidgets)
        for layout in (create_layout, components_layout, layout_layout, validate_layout, plugins_layout):
            layout.setSpacing(8)
        content_host.addWidget(create_page)
        content_host.addWidget(components_page)
        content_host.addWidget(layout_page)
        content_host.addWidget(validate_page)
        content_host.addWidget(plugins_page)
        if hasattr(content_host, "setCurrentIndex"):
            content_host.setCurrentIndex(0)

        footer = qtwidgets.QFrame()
        if hasattr(footer, "setObjectName"):
            footer.setObjectName("OCWFooterBar")
        footer_layout = qtwidgets.QVBoxLayout(footer)
        footer_layout.setContentsMargins(12, 8, 12, 8)
        footer_layout.setSpacing(4)
        footer_layout.addWidget(status)
        footer_layout.addWidget(overlay_status)

        root.addWidget(header_box)
        root.addWidget(stepper_box)
        root.addWidget(content_host, 1)
        root.addWidget(footer)
        return {
            "widget": widget,
            "title": title,
            "context_summary": context_summary,
            "status": status,
            "overlay_status": overlay_status,
            "header_bar": header_box,
            "stepper_bar": stepper_box,
            "step_flow_markers": step_flow_markers,
            "step_button_labels": step_button_labels,
            "content_host": content_host,
            "footer_bar": footer,
            "step_buttons": step_buttons,
            "stack": content_host,
            "primary_navigation": "stepper",
            "navigation_items": list(_WORKFLOW_STEP_LABELS),
            "navigation_count": 1,
            "active_step": "create",
            "create_layout": create_layout,
            "components_layout": components_layout,
            "layout_layout": layout_layout,
            "validate_layout": validate_layout,
            "plugins_layout": plugins_layout,
        }

    def _mount_panels(self) -> None:
        if "create_layout" not in self.form:
            return
        create_splitter = _section_splitter(
            "vertical",
            [self.create_panel.widget, self.info_panel.widget],
            stretch_factors=[3, 2],
        )
        self.form["create_layout"].addWidget(create_splitter, 1)
        self.form["components_layout"].addWidget(self.components_panel.widget, 1)
        self.form["layout_layout"].addWidget(self.layout_panel.widget, 1)
        self.form["validate_layout"].addWidget(self.constraints_panel.widget, 1)
        self.form["plugins_layout"].addWidget(self.plugin_manager_panel.widget, 1)

    def _handle_created(self, _state: dict[str, Any]) -> None:
        self.refresh_context_panels(refresh_components=True)
        self.refresh_overlay()
        self.focus_panel("create")
        self.set_status("Controller created. Next use Components or Auto Place to refine the layout.")

    def _handle_layout_applied(self, _result: dict[str, Any]) -> None:
        self.refresh_context_panels(refresh_components=True)
        report = self.constraints_panel.validate()
        self.refresh_overlay()
        self.focus_panel("constraints")
        message, level = format_validation_message(report)
        self.set_status(message, level=level)

    def _handle_components_changed(self, _state: dict[str, Any]) -> None:
        self.refresh_context_panels(refresh_components=False)
        report = self.constraints_panel.validate()
        self.refresh_overlay()
        self.focus_panel("components")
        message, level = format_validation_message(report)
        self.set_status(f"Components updated. {message}", level=level)

    def _handle_controller_updated(self, _state: dict[str, Any]) -> None:
        self.refresh_context_panels(refresh_components=True)
        self.refresh_overlay()
        self.focus_panel("create")
        self.set_status("Controller updated. Re-run validation if dimensions changed.")

    def _handle_selection_changed(self, _component_id: str | None) -> None:
        self.info_panel.refresh()
        self.refresh_overlay()
        context = self.controller_service.get_ui_context(self.doc)
        selection_count = int(context.get("selection_count", 0))
        if selection_count <= 0:
            self.set_status("Selection cleared.")
            return
        label = "component" if selection_count == 1 else "components"
        self.set_status(f"{selection_count} {label} selected.")

    def _handle_validated(self, _report: dict[str, Any]) -> None:
        self.info_panel.refresh()
        self.refresh_overlay()
        message, level = format_validation_message(_report)
        self.set_status(message, level=level)

    def _handle_plugins_changed(self) -> None:
        self.create_panel.refresh()
        self.layout_panel.refresh()
        self.components_panel.refresh()
        self.constraints_panel.refresh()
        self.info_panel.refresh()

    def _build_plugin_manager_panel(self) -> Any:
        try:
            return PluginManagerPanel(
                on_status=self.set_status,
                on_plugins_changed=self._handle_plugins_changed,
            )
        except Exception as exc:
            tb = traceback.format_exc()
            _emit_runtime_traceback("Plugin manager panel failed to initialize", exc)
            log_exception("Plugin manager panel failed to initialize", exc)
            error_message = "Plugins panel unavailable. Check the report view for details."
            self.set_status(error_message)
            return _UnavailablePluginManagerPanel(
                _build_unavailable_panel_widget(
                    "Plugins unavailable",
                    "The plugin manager could not be loaded. Core workbench panels remain available.",
                    f"{exc.__class__.__name__}: {exc}",
                    traceback_text=tb,
                ),
                error_message,
            )

    def _handle_placement_committed(self, state: dict[str, Any]) -> None:
        try:
            self.refresh_context_panels(refresh_components=True)
        except Exception as exc:
            log_exception("Failed to refresh UI after placement commit", exc)

    def _handle_interaction_finished(self, controller: Any) -> None:
        self.interaction_manager.clear(controller.cancel)
        try:
            self.refresh_context_panels(refresh_components=True)
        except Exception as exc:
            log_exception("Failed to refresh UI after interaction finished", exc)
        self.pick_controller.start(self.doc)

    def _handle_pick_finished(self, controller: Any) -> None:
        pass

    def _handle_pick_selected(self, component_id: str) -> None:
        try:
            self.components_panel.refresh()
            self.focus_panel("components")
        except Exception as exc:
            log_exception("Failed to refresh UI after pick selection", exc)

    def _selected_components_in_order(self) -> list[dict[str, Any]]:
        state = self.controller_service.get_state(self.doc)
        by_id = {component["id"]: component for component in state["components"]}
        selected_ids = self.controller_service.get_selected_component_ids(self.doc)
        return [by_id[component_id] for component_id in selected_ids if component_id in by_id]

    def _apply_selection_pattern(self, plan: dict[str, Any]) -> dict[str, Any]:
        state = self.controller_service.add_components(
            self.doc,
            plan["new_components"],
            primary_id=plan["new_ids"][0] if plan["new_ids"] else None,
            transaction_name=plan["transaction_name"],
        )
        self.refresh_context_panels(refresh_components=True)
        self.refresh_overlay()
        self.focus_panel("components")
        created_count = len(plan["new_ids"])
        self.set_status(f"{self._pattern_label(plan['kind'])} created {created_count} components.")
        return {
            "kind": plan["kind"],
            "created_count": created_count,
            "new_ids": list(plan["new_ids"]),
            "state": state,
        }

    def _arrangement_label(self, operation: str) -> str:
        labels = {
            "align_left": "Align left",
            "align_center_x": "Align center X",
            "align_right": "Align right",
            "align_top": "Align top",
            "align_center_y": "Align center Y",
            "align_bottom": "Align bottom",
            "distribute_horizontal": "Distribute horizontally",
            "distribute_vertical": "Distribute vertically",
        }
        return labels.get(operation, "Arrange selection")

    def _transform_label(self, operation: str) -> str:
        labels = {
            "rotate_cw_90": "Rotate +90",
            "rotate_ccw_90": "Rotate -90",
            "rotate_180": "Rotate 180",
            "mirror_horizontal": "Mirror horizontally",
            "mirror_vertical": "Mirror vertically",
        }
        return labels.get(operation, "Transform selection")

    def _pattern_label(self, kind: str) -> str:
        labels = {
            "duplicate": "Duplicate",
            "array_horizontal": "Horizontal array",
            "array_vertical": "Vertical array",
            "grid_array": "Grid array",
        }
        return labels.get(kind, "Pattern")

    def _overlay_status_text(self, payload: dict[str, Any] | None = None) -> str:
        current = payload or get_document_data(self.doc, "OCWOverlayState", {})
        settings = self.interaction_service.get_settings(self.doc)
        summary = current.get("summary", {})
        return (
            f"Overlay {'on' if settings['overlay_enabled'] else 'off'}"
            f" | Constraints {'on' if settings['show_constraints'] else 'off'}"
            f" | Meas {'on' if settings['measurements_enabled'] else 'off'}"
            f" | Lines {'on' if settings['conflict_lines_enabled'] else 'off'}"
            f" | Labels {'on' if settings['constraint_labels_enabled'] else 'off'}"
            f" | Grid {settings['grid_mm']} mm"
            f" | Items {summary.get('item_count', 0)}"
        )

    def _update_context_summary(self, active_panel: str | None = None) -> None:
        label = self.form.get("context_summary")
        if label is None:
            return
        context = self.controller_service.get_ui_context(self.doc)
        validation = context.get("validation")
        summary = validation.get("summary", {}) if isinstance(validation, dict) else {}
        ui = context.get("ui", {}) if isinstance(context.get("ui"), dict) else {}
        pieces = [
            _panel_title(active_panel or self._active_panel_name()),
            f"{int(context.get('component_count', 0))} components",
            f"grid {context.get('grid_mm', 1.0)} mm",
        ]
        active_interaction = str(ui.get("active_interaction") or "").strip().lower()
        if active_interaction == "drag":
            pieces.append("drag active")
        elif active_interaction == "place":
            pieces.append("place active")
        if int(summary.get("error_count", 0)) > 0:
            pieces.append(f"{int(summary.get('error_count', 0))} errors")
        elif int(summary.get("warning_count", 0)) > 0:
            pieces.append(f"{int(summary.get('warning_count', 0))} warnings")
        else:
            pieces.append("validation clear")
        set_label_text(label, " | ".join(pieces))

    def _active_panel_name(self) -> str:
        content_host = self.form.get("content_host") or self.form.get("stack")
        if content_host is not None and hasattr(content_host, "currentIndex"):
            mapping = {index: panel_name for index, (panel_name, _label) in enumerate(_WORKFLOW_STEPS)}
            return mapping.get(int(content_host.currentIndex()), "create")
        return "create"

    def _update_stepper_state(self, active_panel: str) -> None:
        self.form["active_step"] = active_panel
        active_index = _WORKFLOW_STEP_INDEX.get(active_panel, 0)
        for panel_name, button in self.form.get("step_buttons", {}).items():
            button_index = _WORKFLOW_STEP_INDEX.get(panel_name, 0)
            is_active = panel_name == active_panel
            is_done = button_index < active_index
            is_future = button_index > active_index
            if hasattr(button, "setChecked"):
                button.setChecked(is_active)
            if hasattr(button, "setProperty"):
                button.setProperty("active", is_active)
                button.setProperty("done", is_done)
                button.setProperty("future", is_future)
                button.setProperty("disabled_step", False)
            base_label = self.form.get("step_button_labels", {}).get(panel_name, panel_name.title())
            if hasattr(button, "setText"):
                button.setText(f"✓ {base_label}" if is_done else str(base_label))
            style = getattr(button, "style", None)
            if callable(style):
                style_obj = style()
                if style_obj is not None:
                    if hasattr(style_obj, "unpolish"):
                        style_obj.unpolish(button)
                    if hasattr(style_obj, "polish"):
                        style_obj.polish(button)
            if hasattr(button, "update"):
                button.update()
        for index, marker in enumerate(self.form.get("step_flow_markers", [])):
            if hasattr(marker, "setProperty"):
                marker.setProperty("done", index < active_index)
                marker.setProperty("active", index == max(active_index - 1, 0) and active_index > 0)
                marker.setProperty("future", index >= active_index)
            if hasattr(marker, "update"):
                marker.update()


def ensure_workbench_ui(doc: Any | None = None, focus: str = "create") -> ProductWorkbenchPanel:
    global _ACTIVE_DOCK
    global _ACTIVE_WORKBENCH

    if doc is None and App is not None:
        doc = App.ActiveDocument or App.newDocument("Controller")
    if doc is None:
        raise RuntimeError("No active FreeCAD document")
    _bootstrap_document_if_needed(doc)
    try:
        if _ACTIVE_WORKBENCH is not None:
            _ACTIVE_WORKBENCH.handle_document_context_changed(doc)
        if _ACTIVE_WORKBENCH is None or _ACTIVE_WORKBENCH.doc is not doc:
            _ACTIVE_WORKBENCH = ProductWorkbenchPanel(doc)
            _ACTIVE_DOCK = _show_in_dock(_ACTIVE_WORKBENCH)
        else:
            _ACTIVE_WORKBENCH.refresh_all()
            _show_existing_dock(_ACTIVE_DOCK)
        _ACTIVE_WORKBENCH.focus_panel(focus)
        log_to_console(
            f"Workbench UI ready for document '{getattr(doc, 'Name', '<unnamed>')}' with focus '{focus}'."
        )
        return _ACTIVE_WORKBENCH
    except Exception as exc:
        _ACTIVE_WORKBENCH = None
        tb = traceback.format_exc()
        _emit_runtime_traceback("Failed to build Open Controller Workbench UI", exc)
        log_exception("Failed to build Open Controller Workbench UI", exc)
        _ACTIVE_DOCK = _show_fallback_dock(exc, traceback_text=tb)
        raise RuntimeError(f"Open Controller Workbench UI setup failed: {exc}") from exc


def _show_in_dock(panel: ProductWorkbenchPanel) -> Any | None:
    dock = create_or_reuse_dock(_WORKBENCH_TITLE, panel.widget)
    if dock is None:
        log_to_console("Qt dock support unavailable; Open Controller Workbench dock not created.", level="warning")
    return dock


def _show_existing_dock(dock: Any | None) -> None:
    focus_dock(dock)


def _show_fallback_dock(exc: Exception, *, traceback_text: str | None = None) -> Any | None:
    widget = _build_unavailable_panel_widget(
        _WORKBENCH_TITLE,
        "The Workbench UI could not be loaded. Check the FreeCAD report view for details.",
        f"{exc.__class__.__name__}: {exc}",
        traceback_text=traceback_text,
    )
    if widget is None:
        return None
    log_to_console("Showing fallback Open Controller Workbench dock after UI build failure.", level="warning")
    return create_or_reuse_dock(_WORKBENCH_TITLE, widget)


def _build_unavailable_panel_widget(
    title_text: str,
    message_text: str,
    details_text: str,
    *,
    traceback_text: str | None = None,
) -> Any | None:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return None
    widget, layout = build_panel_container(qtwidgets)
    title = qtwidgets.QLabel(title_text)
    title.setStyleSheet("font-weight: 600;")
    message = qtwidgets.QLabel(message_text)
    message.setWordWrap(True)
    details = qtwidgets.QLabel(details_text)
    details.setWordWrap(True)
    layout.addWidget(title)
    layout.addWidget(message)
    layout.addWidget(details)
    if hasattr(qtwidgets, "QPlainTextEdit"):
        traceback_view = qtwidgets.QPlainTextEdit()
        if hasattr(traceback_view, "setReadOnly"):
            traceback_view.setReadOnly(True)
        if hasattr(traceback_view, "setLineWrapMode"):
            traceback_view.setLineWrapMode(qtwidgets.QPlainTextEdit.NoWrap)
        if hasattr(traceback_view, "setPlainText"):
            traceback_view.setPlainText(traceback_text or details_text)
        if hasattr(traceback_view, "setMinimumHeight"):
            traceback_view.setMinimumHeight(220)
        if hasattr(traceback_view, "setPlaceholderText") and not traceback_text:
            traceback_view.setPlaceholderText("No traceback captured.")
        if hasattr(traceback_view, "setObjectName"):
            traceback_view.setObjectName("OCWFailureTraceback")
        layout.addWidget(traceback_view)
    return widget


def _step_page(qtwidgets: Any) -> tuple[Any, Any]:
    return build_panel_container(qtwidgets, spacing=12, margins=(12, 12, 12, 12))


def _section_splitter(orientation: str, widgets: list[Any], stretch_factors: list[int] | None = None) -> Any:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None or _qtcore is None or not hasattr(qtwidgets, "QSplitter"):
        return widgets[0] if widgets else object()
    splitter = qtwidgets.QSplitter(
        _qtcore.Qt.Vertical if orientation == "vertical" else _qtcore.Qt.Horizontal
    )
    if hasattr(splitter, "setChildrenCollapsible"):
        splitter.setChildrenCollapsible(False)
    if hasattr(splitter, "setHandleWidth"):
        splitter.setHandleWidth(8)
    for index, widget in enumerate(widgets):
        splitter.addWidget(widget)
        if stretch_factors and index < len(stretch_factors):
            splitter.setStretchFactor(index, stretch_factors[index])
    return splitter


def _panel_title(panel_name: str) -> str:
    normalized_panel = "create" if panel_name == "info" else panel_name
    return dict(_WORKFLOW_STEPS).get(normalized_panel, "Create")


def _workbench_shell_stylesheet() -> str:
    from pathlib import Path
    qss_path = Path(__file__).resolve().parents[1] / "resources" / "ui" / "workbench_shell.qss"
    try:
        return qss_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _bootstrap_document_if_needed(doc: Any) -> None:
    if not _document_needs_bootstrap(doc):
        return
    service = ControllerService()
    service.create_controller(
        doc,
        {
            "id": str(getattr(doc, "Name", "controller")).lower(),
        },
    )
    log_to_console(
        f"Bootstrapped default controller geometry in document '{getattr(doc, 'Name', '<unnamed>')}'."
    )


def _document_needs_bootstrap(doc: Any) -> bool:
    if has_persisted_state(doc):
        return False
    objects = list(getattr(doc, "Objects", []))
    if not objects:
        return True
    return False


def reset_workbench_dock() -> bool:
    global _ACTIVE_DOCK
    global _ACTIVE_WORKBENCH

    if _ACTIVE_WORKBENCH is not None:
        _ACTIVE_WORKBENCH.handle_document_closed()
    _ACTIVE_WORKBENCH = None
    removed = remove_dock()
    _ACTIVE_DOCK = None
    if removed:
        log_to_console("Open Controller dock reset.")
    else:
        log_to_console("Open Controller dock reset requested but no dock was present.", level="warning")
    return removed


def ensure_component_palette_ui(doc: Any | None = None) -> ComponentPalettePanel:
    global _ACTIVE_COMPONENT_PALETTE
    global _ACTIVE_COMPONENT_PALETTE_DOCK

    if doc is None and App is not None:
        doc = App.ActiveDocument or App.newDocument("Controller")
    if doc is None:
        raise RuntimeError("No active FreeCAD document")
    _bootstrap_document_if_needed(doc)
    if _ACTIVE_COMPONENT_PALETTE is None or _ACTIVE_COMPONENT_PALETTE.doc is not doc:
        _ACTIVE_COMPONENT_PALETTE = ComponentPalettePanel(doc)
        _ACTIVE_COMPONENT_PALETTE_DOCK = create_or_reuse_dock(
            "Component Palette",
            _ACTIVE_COMPONENT_PALETTE.widget,
            object_name="OCWComponentPaletteDock",
        )
    else:
        _ACTIVE_COMPONENT_PALETTE.refresh()
        focus_dock(_ACTIVE_COMPONENT_PALETTE_DOCK)
    log_to_console(
        f"Component palette ready for document '{getattr(doc, 'Name', '<unnamed>')}'."
    )
    return _ACTIVE_COMPONENT_PALETTE


def refresh_favorite_component_commands() -> None:
    if Gui is None:
        return
    for slot_index, command_id in enumerate(_FAVORITE_COMMAND_IDS):
        Gui.addCommand(
            command_id,
            _LoggedCommand(command_id, _FavoriteComponentCommand(slot_index)),
        )


def start_component_place_mode(doc: Any | None, template_id: str) -> bool:
    if doc is None and App is not None:
        doc = App.ActiveDocument or App.newDocument("Controller")
    if doc is None:
        return False
    workbench = ensure_workbench_ui(doc, focus="components")
    return workbench.start_place_mode(template_id)


def start_place_mode_direct(doc: Any, template_id: str) -> bool:
    """Start placement mode without requiring the dock to be open.

    If the workbench dock is already open for this document, delegates to it
    so the interaction manager and controllers are shared. Otherwise creates a
    lightweight placement session using a standalone set of controllers and
    refreshes the dock (if open) after each commit.
    """
    if _ACTIVE_WORKBENCH is not None and _ACTIVE_WORKBENCH.doc is doc:
        return _ACTIVE_WORKBENCH.start_place_mode(template_id)

    # Dock not open: create a minimal placement session without dock.
    try:
        from ocw_workbench.gui.interaction.view_place_controller import ViewPlaceController
        from ocw_workbench.gui.overlay.renderer import OverlayRenderer
        from ocw_workbench.services.controller_service import ControllerService
        from ocw_workbench.services.interaction_service import InteractionService
        from ocw_workbench.services.overlay_service import OverlayService

        cs = ControllerService()
        interactions = InteractionService(cs)
        overlay = OverlayRenderer(OverlayService(cs))

        def _on_committed(state: Any) -> None:
            _refresh_active_workbench_if_open(doc)

        def _on_finished(controller: Any) -> None:
            _refresh_active_workbench_if_open(doc)

        controller = ViewPlaceController(
            controller_service=cs,
            interaction_service=interactions,
            overlay_renderer=overlay,
            on_committed=_on_committed,
            on_finished=_on_finished,
        )
        started = controller.start(doc, template_id)
        if started:
            log_to_console(f"Direct placement mode started for '{template_id}'.")
        return started
    except Exception as exc:
        log_exception("Failed to start direct placement mode", exc)
        return False


def _refresh_active_workbench_if_open(doc: Any) -> None:
    """Refresh the workbench dock if it is currently open for this document."""
    if _ACTIVE_WORKBENCH is not None and _ACTIVE_WORKBENCH.doc is doc:
        try:
            _ACTIVE_WORKBENCH.refresh_context_panels(refresh_components=True)
        except Exception as exc:
            log_exception("Failed to refresh workbench after direct placement", exc)


def start_component_drag_mode(doc: Any | None) -> bool:
    if doc is None and App is not None:
        doc = App.ActiveDocument or App.newDocument("Controller")
    if doc is None:
        return False
    workbench = ensure_workbench_ui(doc, focus="components")
    return workbench.start_drag_mode()

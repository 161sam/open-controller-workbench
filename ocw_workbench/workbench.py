from __future__ import annotations

from typing import Any

try:
    import FreeCAD as App
except ImportError:
    App = None

try:
    import FreeCADGui as Gui
except ImportError:
    Gui = None

from ocw_workbench.gui.interaction.move_tool import MoveTool
from ocw_workbench.gui.docking import create_or_reuse_dock, focus_dock, remove_dock
from ocw_workbench.gui.feedback import apply_status_message, format_toggle_message, format_validation_message
from ocw_workbench.gui.overlay.renderer import OverlayRenderer
from ocw_workbench.gui.panels._common import FallbackLabel, load_qt, log_exception, log_to_console, set_label_text, set_size_policy
from ocw_workbench.gui.panels.components_panel import ComponentsPanel
from ocw_workbench.gui.panels.constraints_panel import ConstraintsPanel
from ocw_workbench.gui.panels.create_panel import CreatePanel
from ocw_workbench.gui.panels.info_panel import InfoPanel
from ocw_workbench.gui.panels.layout_panel import LayoutPanel
from ocw_workbench.gui.panels.plugin_manager_panel import PluginManagerPanel
from ocw_workbench.gui.runtime import icon_path
from ocw_workbench.freecad_api.metadata import get_document_data
from ocw_workbench.freecad_api.state import has_persisted_state
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService
from ocw_workbench.services.overlay_service import OverlayService

_ACTIVE_WORKBENCH: ProductWorkbenchPanel | None = None
_ACTIVE_DOCK: Any | None = None


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


class OpenControllerWorkbench((Gui.Workbench if Gui is not None else object)):
    MenuText = "Open Controller Workbench"
    ToolTip = "Design modular MIDI controllers in the Open Controller Workbench."
    Icon = icon_path("workbench")

    def GetClassName(self) -> str:
        return "Gui::PythonWorkbench"

    def Initialize(self) -> None:
        if Gui is None:
            return
        from ocw_workbench.commands.add_component import AddComponentCommand
        from ocw_workbench.commands.apply_layout import ApplyLayoutCommand
        from ocw_workbench.commands.create_from_template import CreateFromTemplateCommand
        from ocw_workbench.commands.disable_plugin import DisablePluginCommand
        from ocw_workbench.commands.enable_plugin import EnablePluginCommand
        from ocw_workbench.commands.move_component_interactive import MoveComponentInteractiveCommand
        from ocw_workbench.commands.open_plugin_manager import OpenPluginManagerCommand
        from ocw_workbench.commands.reload_plugins import ReloadPluginsCommand
        from ocw_workbench.commands.select_component import SelectComponentCommand
        from ocw_workbench.commands.show_constraint_overlay import ShowConstraintOverlayCommand
        from ocw_workbench.commands.snap_to_grid import SnapToGridCommand
        from ocw_workbench.commands.toggle_conflict_lines import ToggleConflictLinesCommand
        from ocw_workbench.commands.toggle_constraint_labels import ToggleConstraintLabelsCommand
        from ocw_workbench.commands.toggle_measurements import ToggleMeasurementsCommand
        from ocw_workbench.commands.toggle_overlay import ToggleOverlayCommand
        from ocw_workbench.commands.validate_constraints import ValidateConstraintsCommand

        Gui.addCommand("OCW_CreateController", _LoggedCommand("OCW_CreateController", CreateFromTemplateCommand()))
        Gui.addCommand("OCW_AddComponent", _LoggedCommand("OCW_AddComponent", AddComponentCommand()))
        Gui.addCommand("OCW_ApplyLayout", _LoggedCommand("OCW_ApplyLayout", ApplyLayoutCommand()))
        Gui.addCommand("OCW_SelectComponent", _LoggedCommand("OCW_SelectComponent", SelectComponentCommand()))
        Gui.addCommand("OCW_ValidateConstraints", _LoggedCommand("OCW_ValidateConstraints", ValidateConstraintsCommand()))
        Gui.addCommand("OCW_ToggleOverlay", _LoggedCommand("OCW_ToggleOverlay", ToggleOverlayCommand()))
        Gui.addCommand("OCW_ShowConstraintOverlay", _LoggedCommand("OCW_ShowConstraintOverlay", ShowConstraintOverlayCommand()))
        Gui.addCommand("OCW_MoveComponentInteractive", _LoggedCommand("OCW_MoveComponentInteractive", MoveComponentInteractiveCommand()))
        Gui.addCommand("OCW_SnapToGrid", _LoggedCommand("OCW_SnapToGrid", SnapToGridCommand()))
        Gui.addCommand("OCW_ToggleMeasurements", _LoggedCommand("OCW_ToggleMeasurements", ToggleMeasurementsCommand()))
        Gui.addCommand("OCW_ToggleConflictLines", _LoggedCommand("OCW_ToggleConflictLines", ToggleConflictLinesCommand()))
        Gui.addCommand("OCW_ToggleConstraintLabels", _LoggedCommand("OCW_ToggleConstraintLabels", ToggleConstraintLabelsCommand()))
        Gui.addCommand("OCW_OpenPluginManager", _LoggedCommand("OCW_OpenPluginManager", OpenPluginManagerCommand()))
        Gui.addCommand("OCW_EnablePlugin", _LoggedCommand("OCW_EnablePlugin", EnablePluginCommand()))
        Gui.addCommand("OCW_DisablePlugin", _LoggedCommand("OCW_DisablePlugin", DisablePluginCommand()))
        Gui.addCommand("OCW_ReloadPlugins", _LoggedCommand("OCW_ReloadPlugins", ReloadPluginsCommand()))

        project_commands = ["OCW_CreateController"]
        component_commands = [
            "OCW_AddComponent",
            "OCW_SelectComponent",
        ]
        layout_commands = [
            "OCW_ApplyLayout",
            "OCW_MoveComponentInteractive",
            "OCW_SnapToGrid",
        ]
        validate_commands = [
            "OCW_ValidateConstraints",
            "OCW_ToggleOverlay",
            "OCW_ShowConstraintOverlay",
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
        self.appendToolbar("OCW Components", component_commands)
        self.appendToolbar("OCW Layout", layout_commands)
        self.appendToolbar("OCW Validate", validate_commands[:3])
        self.appendToolbar("OCW Tools", plugin_commands)
        self.appendMenu(
            "OCW",
            project_commands + component_commands + layout_commands + validate_commands[:1] + plugin_commands,
        )
        self.appendMenu("OCW/Create", project_commands)
        self.appendMenu("OCW/Components", component_commands)
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
        self.overlay_service = OverlayService(self.controller_service)
        self.overlay_renderer = OverlayRenderer(self.overlay_service)
        self.move_tool = MoveTool(
            interaction_service=self.interaction_service,
            controller_service=self.controller_service,
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
        self.plugin_manager_panel = PluginManagerPanel(
            on_status=self.set_status,
            on_plugins_changed=self._handle_plugins_changed,
        )
        self._mount_panels()
        self.refresh_all()
        self.focus_panel("create")

    def refresh_all(self) -> None:
        self.create_panel.refresh()
        self.layout_panel.refresh()
        self.components_panel.refresh()
        self.constraints_panel.refresh()
        self.info_panel.refresh()
        self.plugin_manager_panel.refresh()
        self.refresh_overlay()

    def focus_panel(self, panel_name: str) -> None:
        tab_index = {
            "create": 0,
            "info": 0,
            "layout": 1,
            "constraints": 1,
            "components": 2,
            "plugins": 3,
        }.get(panel_name)
        tabs = self.form.get("tabs")
        if tab_index is not None and tabs is not None and hasattr(tabs, "setCurrentIndex"):
            tabs.setCurrentIndex(tab_index)
        widget = {
            "create": self.create_panel.widget,
            "layout": self.layout_panel.widget,
            "components": self.components_panel.widget,
            "constraints": self.constraints_panel.widget,
            "info": self.info_panel.widget,
            "plugins": self.plugin_manager_panel.widget,
        }.get(panel_name)
        if widget is not None and hasattr(widget, "setFocus"):
            widget.setFocus()
        titles = {
            "create": "Create",
            "layout": "Layout",
            "components": "Components",
            "constraints": "Constraints",
            "info": "Info",
            "plugins": "Plugins",
        }
        self.set_status(f"{titles.get(panel_name, 'Workbench')} panel active.")

    def set_status(self, message: str) -> None:
        level = "error" if message.lower().startswith("could not") or message.lower().startswith("validation found") else "info"
        if "created" in message.lower() or "updated controller geometry" in message.lower() or "validation passed" in message.lower():
            level = "success"
        if "warning" in message.lower():
            level = "warning"
        apply_status_message(self.form["status"], message, level=level)
        set_label_text(self.form["overlay_status"], self._overlay_status_text())

    def refresh_overlay(self) -> dict[str, Any]:
        payload = self.overlay_renderer.refresh(self.doc)
        set_label_text(self.form["overlay_status"], self._overlay_status_text(payload))
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
                "Use it to inspect helpers without changing model geometry.",
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
                "Constraint checks",
                settings["show_constraints"],
                "Switch this on when you want issues highlighted directly in the 3D view.",
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
                "Helpful for checking spacing during placement refinement.",
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
                "These guides only visualize conflicts and do not change the model.",
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
                "Enable labels when you need readable issue names next to the overlay markers.",
            )
        )
        return settings

    def arm_move_for_selection(self) -> dict[str, Any]:
        settings = self.move_tool.arm(self.doc)
        self.components_panel.refresh()
        self.info_panel.refresh()
        self.refresh_overlay()
        self.focus_panel("components")
        self.set_status(
            f"Pick In 3D is ready for '{settings['move_component_id']}'. Click in the view or return to the Components tab to edit X/Y directly."
        )
        return settings

    def move_to(self, x: float, y: float) -> dict[str, Any]:
        result = self.move_tool.move_to(self.doc, x, y)
        self.refresh_context_panels(refresh_components=True)
        self.refresh_overlay()
        self.focus_panel("components")
        self.set_status(
            f"Moved '{result['component_id']}' to {result['x']:.2f}, {result['y']:.2f} mm. Validation and overlay were refreshed."
        )
        return result

    def snap_selection_to_grid(self) -> dict[str, Any]:
        result = self.interaction_service.snap_selected_component(self.doc)
        self.refresh_context_panels(refresh_components=True)
        self.refresh_overlay()
        self.focus_panel("components")
        self.set_status(f"Snapped '{result['component_id']}' to the current grid. Review the overlay for the updated placement.")
        return result

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
        return True

    def _build_shell(self) -> dict[str, Any]:
        _qtcore, _qtgui, qtwidgets = load_qt()
        if qtwidgets is None:
            return {
                "widget": object(),
                "status": FallbackLabel("Open Controller workbench ready."),
                "overlay_status": FallbackLabel("Overlay ready."),
            }

        widget = qtwidgets.QWidget()
        if hasattr(widget, "setMinimumSize"):
            widget.setMinimumSize(0, 0)
        root = qtwidgets.QVBoxLayout(widget)
        title = qtwidgets.QLabel("Open Controller Studio")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        subtitle = qtwidgets.QLabel("Create, lay out, validate and refine controllers without leaving the workbench.")
        subtitle.setWordWrap(True)
        status = qtwidgets.QLabel("Open Controller workbench ready.")
        status.setWordWrap(True)
        overlay_status = qtwidgets.QLabel("Overlay ready.")
        overlay_status.setWordWrap(True)
        tabs = qtwidgets.QTabWidget()
        if hasattr(tabs, "setUsesScrollButtons"):
            tabs.setUsesScrollButtons(True)
        set_size_policy(tabs, horizontal="preferred", vertical="expanding")
        create_page = qtwidgets.QWidget()
        create_layout = qtwidgets.QVBoxLayout(create_page)
        layout_page = qtwidgets.QWidget()
        layout_layout = qtwidgets.QVBoxLayout(layout_page)
        components_page = qtwidgets.QWidget()
        components_layout = qtwidgets.QVBoxLayout(components_page)
        plugins_page = qtwidgets.QWidget()
        plugins_layout = qtwidgets.QVBoxLayout(plugins_page)
        for layout in (create_layout, layout_layout, components_layout, plugins_layout):
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)
        tabs.addTab(create_page, "Create")
        tabs.addTab(layout_page, "Layout")
        tabs.addTab(components_page, "Components")
        tabs.addTab(plugins_page, "Plugins")
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(overlay_status)
        root.addWidget(tabs, 1)
        root.addWidget(status)
        return {
            "widget": widget,
            "status": status,
            "overlay_status": overlay_status,
            "tabs": tabs,
            "create_layout": create_layout,
            "layout_layout": layout_layout,
            "components_layout": components_layout,
            "plugins_layout": plugins_layout,
        }

    def _mount_panels(self) -> None:
        if "create_layout" not in self.form:
            return
        self.form["create_layout"].addWidget(_group_box("Create Controller", self.create_panel.widget))
        self.form["create_layout"].addWidget(_group_box("Controller Setup", self.info_panel.widget))
        self.form["layout_layout"].addWidget(_group_box("Layout", self.layout_panel.widget))
        self.form["layout_layout"].addWidget(_group_box("Constraints", self.constraints_panel.widget))
        self.form["components_layout"].addWidget(_group_box("Components", self.components_panel.widget))
        self.form["plugins_layout"].addWidget(_group_box("Plugins", self.plugin_manager_panel.widget))

    def _handle_created(self, _state: dict[str, Any]) -> None:
        self.refresh_context_panels(refresh_components=True)
        self.refresh_overlay()
        self.focus_panel("create")
        self.set_status("Controller created. Review size and shell settings, then use Components or Auto Place to refine the layout.")

    def _handle_layout_applied(self, _result: dict[str, Any]) -> None:
        self.refresh_context_panels(refresh_components=True)
        report = self.constraints_panel.validate()
        self.refresh_overlay()
        self.focus_panel("constraints")
        message, _level = format_validation_message(report)
        self.set_status(message)

    def _handle_components_changed(self, _state: dict[str, Any]) -> None:
        self.refresh_context_panels(refresh_components=False)
        report = self.constraints_panel.validate()
        self.refresh_overlay()
        self.focus_panel("components")
        message, _level = format_validation_message(report)
        self.set_status(f"Component update applied. {message}")

    def _handle_controller_updated(self, _state: dict[str, Any]) -> None:
        self.refresh_context_panels(refresh_components=True)
        self.refresh_overlay()
        self.focus_panel("create")
        self.set_status("Controller settings updated. Check the model preview and re-run validation if dimensions changed.")

    def _handle_selection_changed(self, _component_id: str | None) -> None:
        self.info_panel.refresh()
        self.refresh_overlay()

    def _handle_validated(self, _report: dict[str, Any]) -> None:
        self.info_panel.refresh()
        self.refresh_overlay()
        message, _level = format_validation_message(_report)
        self.set_status(message)

    def _handle_plugins_changed(self) -> None:
        self.create_panel.refresh()
        self.layout_panel.refresh()
        self.components_panel.refresh()
        self.constraints_panel.refresh()
        self.info_panel.refresh()

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


def ensure_workbench_ui(doc: Any | None = None, focus: str = "create") -> ProductWorkbenchPanel:
    global _ACTIVE_DOCK
    global _ACTIVE_WORKBENCH

    if doc is None and App is not None:
        doc = App.ActiveDocument or App.newDocument("Controller")
    if doc is None:
        raise RuntimeError("No active FreeCAD document")
    _bootstrap_document_if_needed(doc)
    try:
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
        log_exception("Failed to build Open Controller workbench UI", exc)
        _ACTIVE_DOCK = _show_fallback_dock(exc)
        raise RuntimeError(f"Open Controller workbench UI setup failed: {exc}") from exc


def _group_box(title: str, child: Any) -> Any:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return child
    group = qtwidgets.QGroupBox(title)
    if hasattr(group, "setMinimumSize"):
        group.setMinimumSize(0, 0)
    set_size_policy(group, horizontal="preferred", vertical="preferred")
    layout = qtwidgets.QVBoxLayout(group)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.addWidget(child)
    return group


def _show_in_dock(panel: ProductWorkbenchPanel) -> Any | None:
    dock = create_or_reuse_dock("Open Controller", panel.widget)
    if dock is None:
        log_to_console("Qt dock support unavailable; Open Controller dock not created.", level="warning")
    return dock


def _show_existing_dock(dock: Any | None) -> None:
    focus_dock(dock)


def _show_fallback_dock(exc: Exception) -> Any | None:
    _qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        return None
    widget = qtwidgets.QWidget()
    layout = qtwidgets.QVBoxLayout(widget)
    title = qtwidgets.QLabel("Open Controller")
    title.setStyleSheet("font-weight: 600;")
    message = qtwidgets.QLabel("The workbench UI could not be built. Check the FreeCAD report view for details.")
    message.setWordWrap(True)
    details = qtwidgets.QLabel(f"{exc.__class__.__name__}: {exc}")
    details.setWordWrap(True)
    layout.addWidget(title)
    layout.addWidget(message)
    layout.addWidget(details)
    log_to_console("Showing fallback Open Controller dock after UI build failure.", level="warning")
    return create_or_reuse_dock("Open Controller", widget)


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

    _ACTIVE_WORKBENCH = None
    removed = remove_dock()
    _ACTIVE_DOCK = None
    if removed:
        log_to_console("Open Controller dock reset.")
    else:
        log_to_console("Open Controller dock reset requested but no dock was present.", level="warning")
    return removed

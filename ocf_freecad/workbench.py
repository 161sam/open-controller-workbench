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

from ocf_freecad.gui.interaction.move_tool import MoveTool
from ocf_freecad.gui.docking import create_or_reuse_dock, focus_dock, remove_dock
from ocf_freecad.gui.overlay.renderer import OverlayRenderer
from ocf_freecad.gui.panels._common import FallbackLabel, load_qt, log_exception, log_to_console, set_label_text, set_size_policy
from ocf_freecad.gui.panels.components_panel import ComponentsPanel
from ocf_freecad.gui.panels.constraints_panel import ConstraintsPanel
from ocf_freecad.gui.panels.create_panel import CreatePanel
from ocf_freecad.gui.panels.info_panel import InfoPanel
from ocf_freecad.gui.panels.layout_panel import LayoutPanel
from ocf_freecad.gui.panels.plugin_manager_panel import PluginManagerPanel
from ocf_freecad.gui.runtime import icon_path
from ocf_freecad.freecad_api.metadata import get_document_data
from ocf_freecad.freecad_api.state import has_persisted_state
from ocf_freecad.services.controller_service import ControllerService
from ocf_freecad.services.interaction_service import InteractionService
from ocf_freecad.services.overlay_service import OverlayService

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
    MenuText = "Open Controller"
    ToolTip = "Design modular MIDI controllers with templates, layout tools, and validation."
    Icon = icon_path("workbench")

    def GetClassName(self) -> str:
        return "Gui::PythonWorkbench"

    def Initialize(self) -> None:
        if Gui is None:
            return
        from ocf_freecad.commands.add_component import AddComponentCommand
        from ocf_freecad.commands.apply_layout import ApplyLayoutCommand
        from ocf_freecad.commands.create_from_template import CreateFromTemplateCommand
        from ocf_freecad.commands.disable_plugin import DisablePluginCommand
        from ocf_freecad.commands.enable_plugin import EnablePluginCommand
        from ocf_freecad.commands.move_component_interactive import MoveComponentInteractiveCommand
        from ocf_freecad.commands.open_plugin_manager import OpenPluginManagerCommand
        from ocf_freecad.commands.reload_plugins import ReloadPluginsCommand
        from ocf_freecad.commands.select_component import SelectComponentCommand
        from ocf_freecad.commands.show_constraint_overlay import ShowConstraintOverlayCommand
        from ocf_freecad.commands.snap_to_grid import SnapToGridCommand
        from ocf_freecad.commands.toggle_conflict_lines import ToggleConflictLinesCommand
        from ocf_freecad.commands.toggle_constraint_labels import ToggleConstraintLabelsCommand
        from ocf_freecad.commands.toggle_measurements import ToggleMeasurementsCommand
        from ocf_freecad.commands.toggle_overlay import ToggleOverlayCommand
        from ocf_freecad.commands.validate_constraints import ValidateConstraintsCommand

        Gui.addCommand("OCF_CreateController", _LoggedCommand("OCF_CreateController", CreateFromTemplateCommand()))
        Gui.addCommand("OCF_AddComponent", _LoggedCommand("OCF_AddComponent", AddComponentCommand()))
        Gui.addCommand("OCF_ApplyLayout", _LoggedCommand("OCF_ApplyLayout", ApplyLayoutCommand()))
        Gui.addCommand("OCF_SelectComponent", _LoggedCommand("OCF_SelectComponent", SelectComponentCommand()))
        Gui.addCommand("OCF_ValidateConstraints", _LoggedCommand("OCF_ValidateConstraints", ValidateConstraintsCommand()))
        Gui.addCommand("OCF_ToggleOverlay", _LoggedCommand("OCF_ToggleOverlay", ToggleOverlayCommand()))
        Gui.addCommand("OCF_ShowConstraintOverlay", _LoggedCommand("OCF_ShowConstraintOverlay", ShowConstraintOverlayCommand()))
        Gui.addCommand("OCF_MoveComponentInteractive", _LoggedCommand("OCF_MoveComponentInteractive", MoveComponentInteractiveCommand()))
        Gui.addCommand("OCF_SnapToGrid", _LoggedCommand("OCF_SnapToGrid", SnapToGridCommand()))
        Gui.addCommand("OCF_ToggleMeasurements", _LoggedCommand("OCF_ToggleMeasurements", ToggleMeasurementsCommand()))
        Gui.addCommand("OCF_ToggleConflictLines", _LoggedCommand("OCF_ToggleConflictLines", ToggleConflictLinesCommand()))
        Gui.addCommand("OCF_ToggleConstraintLabels", _LoggedCommand("OCF_ToggleConstraintLabels", ToggleConstraintLabelsCommand()))
        Gui.addCommand("OCF_OpenPluginManager", _LoggedCommand("OCF_OpenPluginManager", OpenPluginManagerCommand()))
        Gui.addCommand("OCF_EnablePlugin", _LoggedCommand("OCF_EnablePlugin", EnablePluginCommand()))
        Gui.addCommand("OCF_DisablePlugin", _LoggedCommand("OCF_DisablePlugin", DisablePluginCommand()))
        Gui.addCommand("OCF_ReloadPlugins", _LoggedCommand("OCF_ReloadPlugins", ReloadPluginsCommand()))

        project_commands = ["OCF_CreateController"]
        component_commands = [
            "OCF_AddComponent",
            "OCF_SelectComponent",
        ]
        layout_commands = [
            "OCF_ApplyLayout",
            "OCF_MoveComponentInteractive",
            "OCF_SnapToGrid",
        ]
        validate_commands = [
            "OCF_ValidateConstraints",
            "OCF_ToggleOverlay",
            "OCF_ShowConstraintOverlay",
            "OCF_ToggleMeasurements",
            "OCF_ToggleConflictLines",
            "OCF_ToggleConstraintLabels",
        ]
        plugin_commands = [
            "OCF_OpenPluginManager",
        ]
        plugin_advanced_commands = [
            "OCF_EnablePlugin",
            "OCF_DisablePlugin",
            "OCF_ReloadPlugins",
        ]
        self.appendToolbar("OCF Project", project_commands)
        self.appendToolbar("OCF Components", component_commands)
        self.appendToolbar("OCF Layout", layout_commands)
        self.appendToolbar("OCF Validate", validate_commands[:3])
        self.appendToolbar("OCF Tools", plugin_commands)
        self.appendMenu(
            "OCF",
            project_commands + component_commands + layout_commands + validate_commands[:1] + plugin_commands,
        )
        self.appendMenu("OCF/Create", project_commands)
        self.appendMenu("OCF/Components", component_commands)
        self.appendMenu("OCF/Layout", layout_commands)
        self.appendMenu("OCF/View", validate_commands[1:])
        self.appendMenu("OCF/Validate", validate_commands[:1] + validate_commands[2:])
        self.appendMenu("OCF/Plugins", plugin_commands)
        self.appendMenu("OCF/Plugins/Advanced", plugin_advanced_commands)

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
        set_label_text(self.form["status"], message)
        set_label_text(self.form["overlay_status"], self._overlay_status_text())

    def refresh_overlay(self) -> dict[str, Any]:
        payload = self.overlay_renderer.refresh(self.doc)
        set_label_text(self.form["overlay_status"], self._overlay_status_text(payload))
        return payload

    def toggle_overlay(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_overlay(self.doc)
        self.refresh_all()
        self.set_status(f"Overlay {'enabled' if settings['overlay_enabled'] else 'disabled'}.")
        return settings

    def toggle_constraint_overlay(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_constraint_overlay(self.doc)
        self.refresh_all()
        self.set_status(
            f"Constraint overlay {'enabled' if settings['show_constraints'] else 'disabled'}."
        )
        return settings

    def toggle_measurements(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_measurements(self.doc)
        self.refresh_all()
        self.set_status(f"Measurements {'enabled' if settings['measurements_enabled'] else 'disabled'}.")
        return settings

    def toggle_conflict_lines(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_conflict_lines(self.doc)
        self.refresh_all()
        self.set_status(f"Conflict lines {'enabled' if settings['conflict_lines_enabled'] else 'disabled'}.")
        return settings

    def toggle_constraint_labels(self) -> dict[str, Any]:
        settings = self.interaction_service.toggle_constraint_labels(self.doc)
        self.refresh_all()
        self.set_status(
            f"Constraint labels {'enabled' if settings['constraint_labels_enabled'] else 'disabled'}."
        )
        return settings

    def arm_move_for_selection(self) -> dict[str, Any]:
        settings = self.move_tool.arm(self.doc)
        self.refresh_all()
        self.focus_panel("components")
        self.set_status(f"Move mode armed for '{settings['move_component_id']}'.")
        return settings

    def move_to(self, x: float, y: float) -> dict[str, Any]:
        result = self.move_tool.move_to(self.doc, x, y)
        self.refresh_all()
        self.focus_panel("components")
        self.set_status(f"Moved '{result['component_id']}' to {result['x']:.2f}, {result['y']:.2f} mm.")
        return result

    def snap_selection_to_grid(self) -> dict[str, Any]:
        result = self.interaction_service.snap_selected_component(self.doc)
        self.refresh_all()
        self.focus_panel("components")
        self.set_status(f"Snapped '{result['component_id']}' to grid.")
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
        self.components_panel.refresh()
        self.layout_panel.refresh()
        self.constraints_panel.refresh()
        self.info_panel.refresh()
        self.refresh_overlay()
        self.focus_panel("create")
        self.set_status("Controller created. Review size and shell settings, then add or place components.")

    def _handle_layout_applied(self, _result: dict[str, Any]) -> None:
        self.components_panel.refresh()
        self.constraints_panel.validate()
        self.info_panel.refresh()
        self.refresh_overlay()
        self.focus_panel("constraints")

    def _handle_components_changed(self, _state: dict[str, Any]) -> None:
        self.layout_panel.refresh()
        self.constraints_panel.validate()
        self.info_panel.refresh()
        self.refresh_overlay()
        self.focus_panel("components")

    def _handle_controller_updated(self, _state: dict[str, Any]) -> None:
        self.layout_panel.refresh()
        self.constraints_panel.refresh()
        self.components_panel.refresh()
        self.info_panel.refresh()
        self.refresh_overlay()
        self.focus_panel("create")

    def _handle_selection_changed(self, _component_id: str | None) -> None:
        self.info_panel.refresh()
        self.refresh_overlay()

    def _handle_validated(self, _report: dict[str, Any]) -> None:
        self.info_panel.refresh()
        self.refresh_overlay()

    def _handle_plugins_changed(self) -> None:
        self.create_panel.refresh()
        self.layout_panel.refresh()
        self.components_panel.refresh()
        self.constraints_panel.refresh()
        self.info_panel.refresh()

    def _overlay_status_text(self, payload: dict[str, Any] | None = None) -> str:
        current = payload or get_document_data(self.doc, "OCFOverlayState", {})
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

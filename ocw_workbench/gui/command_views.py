from __future__ import annotations

from typing import Any

from ocw_workbench.gui.panels.components_panel import ComponentsPanel
from ocw_workbench.gui.panels.constraints_panel import ConstraintsPanel
from ocw_workbench.gui.panels.create_panel import CreatePanel
from ocw_workbench.gui.panels.plugin_manager_panel import PluginManagerPanel
from ocw_workbench.gui.runtime import open_dialog
from ocw_workbench.services.controller_service import ControllerService


def show_create_controller_dialog(doc: Any, on_status: Any | None = None) -> Any | None:
    panel = CreatePanel(doc, controller_service=ControllerService(), on_status=on_status)
    return open_dialog("Create Controller", panel, width=760, height=780)


def show_add_component_dialog(doc: Any, on_status: Any | None = None) -> Any | None:
    panel = ComponentsPanel(doc, controller_service=ControllerService(), on_status=on_status)
    return open_dialog("Add Component", panel, width=760, height=760)


def show_plugin_manager_dialog(on_status: Any | None = None) -> Any | None:
    panel = PluginManagerPanel(on_status=on_status)
    return open_dialog("Plugin Manager", panel, width=980, height=760)


def show_constraint_report_dialog(doc: Any, on_status: Any | None = None) -> Any | None:
    panel = ConstraintsPanel(doc, controller_service=ControllerService(), on_status=on_status)
    panel.validate()
    return open_dialog("Constraint Validation", panel, width=760, height=640)

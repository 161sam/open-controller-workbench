from __future__ import annotations

from pathlib import Path
from typing import Any

from ocw_workbench.exporters.assembly_exporter import export_assembly
from ocw_workbench.exporters.bom_exporter import export_bom_csv, export_bom_yaml
from ocw_workbench.exporters.electrical_exporter import export_electrical_mapping
from ocw_workbench.exporters.manufacturing_exporter import export_manufacturing
from ocw_workbench.exporters.schematic_exporter import export_schematic
from ocw_workbench.plugins.context import PluginContext
from ocw_workbench.utils.yaml_io import dump_yaml


def register_exporters(context: PluginContext) -> None:
    context.register_provider("exporters", "kicad_layout", export_kicad_layout)
    context.register_provider("exporters", "electrical_mapping", export_electrical_mapping)
    context.register_provider("exporters", "schematic", export_schematic)
    context.register_provider("exporters", "bom_yaml", export_bom_yaml)
    context.register_provider("exporters", "bom_csv", export_bom_csv)
    context.register_provider("exporters", "manufacturing", export_manufacturing)
    context.register_provider("exporters", "assembly", export_assembly)


def export_kicad_layout(data: dict[str, Any], path: str | Path) -> None:
    dump_yaml(path, data)

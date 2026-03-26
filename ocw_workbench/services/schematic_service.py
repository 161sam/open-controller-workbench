from __future__ import annotations

from pathlib import Path
from typing import Any

from ocw_workbench.exporters.schematic_exporter import export_schematic
from ocw_workbench.generator.electrical_mapper import ElectricalMapper
from ocw_workbench.generator.electrical_resolver import ElectricalResolver
from ocw_workbench.generator.schematic_builder import SchematicBuilder


class SchematicService:
    def __init__(
        self,
        builder: SchematicBuilder | None = None,
        electrical_mapper: ElectricalMapper | None = None,
    ) -> None:
        self.builder = builder or SchematicBuilder()
        self.electrical_mapper = electrical_mapper or ElectricalMapper(ElectricalResolver())

    def build_from_mapping(self, electrical_mapping: dict[str, Any]) -> dict[str, Any]:
        return self.builder.build(electrical_mapping)

    def build_from_controller(
        self,
        controller: dict[str, Any] | Any,
        components: list[dict[str, Any] | Any],
        firmware: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        electrical_mapping = self.electrical_mapper.map_controller(
            controller,
            components,
            firmware=firmware,
            meta=meta,
        )
        return self.build_from_mapping(electrical_mapping)

    def export(self, data: dict[str, Any], path: str | Path) -> None:
        export_schematic(data, path)

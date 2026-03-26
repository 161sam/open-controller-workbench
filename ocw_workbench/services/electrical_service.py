from __future__ import annotations

from pathlib import Path
from typing import Any

from ocw_workbench.exporters.electrical_exporter import export_electrical_mapping
from ocw_workbench.generator.electrical_mapper import ElectricalMapper
from ocw_workbench.generator.electrical_resolver import ElectricalResolver


class ElectricalService:
    def __init__(
        self,
        resolver: ElectricalResolver | None = None,
        mapper: ElectricalMapper | None = None,
    ) -> None:
        self.resolver = resolver or ElectricalResolver()
        self.mapper = mapper or ElectricalMapper(self.resolver)

    def resolve_component(self, component: dict[str, Any] | Any) -> dict[str, Any]:
        return self.resolver.resolve(component)

    def map_controller(
        self,
        controller: dict[str, Any] | Any,
        components: list[dict[str, Any] | Any],
        firmware: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.mapper.map_controller(controller, components, firmware=firmware, meta=meta)

    def export_mapping(self, data: dict[str, Any], path: str | Path) -> None:
        export_electrical_mapping(data, path)

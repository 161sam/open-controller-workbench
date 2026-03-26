from __future__ import annotations

from typing import Any

from ocw_workbench.manufacturing.assembly_builder import AssemblyBuilder
from ocw_workbench.manufacturing.bom_builder import BomBuilder
from ocw_workbench.manufacturing.manufacturing_builder import ManufacturingBuilder


class ManufacturingService:
    def __init__(
        self,
        bom_builder: BomBuilder | None = None,
        manufacturing_builder: ManufacturingBuilder | None = None,
        assembly_builder: AssemblyBuilder | None = None,
    ) -> None:
        self.bom_builder = bom_builder or BomBuilder()
        self.manufacturing_builder = manufacturing_builder or ManufacturingBuilder()
        self.assembly_builder = assembly_builder or AssemblyBuilder()

    def build_bom(
        self,
        controller: dict[str, Any],
        components: list[dict[str, Any]],
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.bom_builder.build(controller, components, profile=profile)

    def build_manufacturing(
        self,
        controller: dict[str, Any],
        components: list[dict[str, Any]],
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.manufacturing_builder.build(controller, components, profile=profile)

    def build_assembly(
        self,
        controller: dict[str, Any],
        components: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self.assembly_builder.build(controller, components)

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BomItem:
    item_id: str
    category: str
    component: str
    manufacturer: str | None
    part_number: str | None
    description: str
    quantity: int
    unit: str = "pcs"
    notes: str | None = None
    material: str | None = None
    thickness_mm: float | None = None
    process: str | None = None
    part_name: str | None = None
    derived_from: str | None = None
    manufacturing_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "item_id": self.item_id,
            "category": self.category,
            "component": self.component,
            "manufacturer": self.manufacturer,
            "part_number": self.part_number,
            "description": self.description,
            "quantity": self.quantity,
            "unit": self.unit,
        }
        if self.notes:
            data["notes"] = self.notes
        if self.material:
            data["material"] = self.material
        if self.thickness_mm is not None:
            data["thickness_mm"] = self.thickness_mm
        if self.process:
            data["process"] = self.process
        if self.part_name:
            data["part_name"] = self.part_name
        if self.derived_from:
            data["derived_from"] = self.derived_from
        if self.manufacturing_type:
            data["manufacturing_type"] = self.manufacturing_type
        return data


@dataclass(frozen=True)
class ManufacturingOperation:
    operation_id: str
    part_id: str
    type: str
    shape: str
    position: dict[str, float]
    dimensions: dict[str, float]
    source_component_id: str | None = None
    tolerance_mm: float | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "operation_id": self.operation_id,
            "part_id": self.part_id,
            "type": self.type,
            "shape": self.shape,
            "position": self.position,
            "dimensions": self.dimensions,
        }
        if self.source_component_id:
            data["source_component_id"] = self.source_component_id
        if self.tolerance_mm is not None:
            data["tolerance_mm"] = self.tolerance_mm
        if self.notes:
            data["notes"] = self.notes
        return data


@dataclass(frozen=True)
class ManufacturingPart:
    part_id: str
    name: str
    type: str
    dimensions_mm: dict[str, float]
    thickness_mm: float
    material: str
    process_recommendation: str
    operation_summary: dict[str, int]
    operations: list[ManufacturingOperation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "part_id": self.part_id,
            "name": self.name,
            "type": self.type,
            "dimensions_mm": self.dimensions_mm,
            "thickness_mm": self.thickness_mm,
            "material": self.material,
            "process_recommendation": self.process_recommendation,
            "operation_summary": self.operation_summary,
            "operations": [item.to_dict() for item in self.operations],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class AssemblyStep:
    step_id: str
    title: str
    description: str
    required_parts: list[str]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "description": self.description,
            "required_parts": list(self.required_parts),
            "notes": list(self.notes),
        }

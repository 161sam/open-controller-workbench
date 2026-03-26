from __future__ import annotations

from collections import Counter
from typing import Any

from ocw_workbench.services.library_service import LibraryService
from ocw_workbench.manufacturing.models import BomItem
from ocw_workbench.manufacturing.normalizer import normalize_profile


class BomBuilder:
    def __init__(self, library_service: LibraryService | None = None) -> None:
        self.library_service = library_service or LibraryService()

    def build(
        self,
        controller: dict[str, Any],
        components: list[dict[str, Any]],
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_profile(profile)
        items: list[BomItem] = []
        warnings: list[str] = []

        counts = Counter(
            component["library_ref"]
            for component in components
            if isinstance(component.get("library_ref"), str) and component.get("library_ref")
        )
        for library_ref, quantity in sorted(counts.items()):
            try:
                library_item = self.library_service.get(library_ref)
            except Exception:
                warnings.append(f"Missing library data for component '{library_ref}'")
                items.append(
                    BomItem(
                        item_id=f"bom:{library_ref}",
                        category="electronics",
                        component=library_ref,
                        manufacturer=None,
                        part_number=None,
                        description=f"Unknown library component {library_ref}",
                        quantity=quantity,
                        notes="library data missing",
                    )
                )
                continue
            items.append(
                BomItem(
                    item_id=f"bom:{library_ref}",
                    category=_bom_category(library_item),
                    component=library_ref,
                    manufacturer=library_item.get("manufacturer"),
                    part_number=library_item.get("part_number"),
                    description=str(library_item.get("description", library_ref)),
                    quantity=quantity,
                    notes=_join_notes(library_item.get("pcb", {}).get("notes")),
                )
            )

        items.extend(_mechanical_bom_items(controller, normalized))
        items.extend(_fastener_bom_items(normalized))
        items.append(
            BomItem(
                item_id="bom:pcb:main",
                category="pcb",
                component="main_pcb",
                manufacturer=None,
                part_number=None,
                description="Main PCB placeholder assembly",
                quantity=1,
                notes="Generated placeholder for manufacturing planning",
                part_name="main_pcb",
                manufacturing_type="pcb",
            )
        )

        return {
            "schema_version": normalized["schema_version"],
            "export_type": "bom",
            "items": [item.to_dict() for item in items],
            "warnings": warnings,
        }


def _bom_category(library_item: dict[str, Any]) -> str:
    category = str(library_item.get("category", "electronics"))
    mapping = {
        "encoder": "controls",
        "button": "controls",
        "fader": "controls",
        "pad": "controls",
        "rgb_button": "controls",
        "display": "display",
    }
    return mapping.get(category, "electronics")


def _mechanical_bom_items(controller: dict[str, Any], profile: dict[str, Any]) -> list[BomItem]:
    surface = controller.get("surface") or {}
    width = float(surface.get("width", controller.get("width", 0.0)))
    height = float(surface.get("height", controller.get("depth", 0.0)))
    top = profile["materials"]["top_plate"]
    bottom = profile["materials"]["bottom_plate"]
    side = profile["materials"]["side_panels"]
    return [
        BomItem(
            item_id="bom:part:top_plate",
            category="enclosure",
            component="top_plate",
            manufacturer=None,
            part_number=None,
            description=f"Top plate {width:.1f} x {height:.1f} mm",
            quantity=1,
            material=top["material"],
            thickness_mm=float(top["thickness_mm"]),
            process="laser_cut",
            part_name="top_plate",
            derived_from="controller.surface",
            manufacturing_type="panel",
        ),
        BomItem(
            item_id="bom:part:bottom_plate",
            category="mechanical",
            component="bottom_plate",
            manufacturer=None,
            part_number=None,
            description=f"Bottom plate {width:.1f} x {height:.1f} mm",
            quantity=1,
            material=bottom["material"],
            thickness_mm=float(bottom["thickness_mm"]),
            process="laser_cut_panel",
            part_name="bottom_plate",
            derived_from="controller.surface",
            manufacturing_type="panel",
        ),
        BomItem(
            item_id="bom:part:side_panels",
            category="mechanical",
            component="side_panel",
            manufacturer=None,
            part_number=None,
            description="Side enclosure panels",
            quantity=4,
            material=side["material"],
            thickness_mm=float(side["thickness_mm"]),
            process="cnc_router",
            part_name="side_panels",
            derived_from="controller.depth/height",
            manufacturing_type="enclosure",
        ),
    ]


def _fastener_bom_items(profile: dict[str, Any]) -> list[BomItem]:
    screw = profile["fasteners"]["panel_mount_screw"]
    standoff = profile["fasteners"]["standoff"]
    return [
        BomItem(
            item_id="bom:fastener:panel_screw",
            category="fasteners",
            component="panel_mount_screw",
            manufacturer=screw["manufacturer"],
            part_number=screw["part_number"],
            description=screw["description"],
            quantity=4,
            notes="Optional enclosure hardware",
        ),
        BomItem(
            item_id="bom:fastener:standoff",
            category="fasteners",
            component="standoff",
            manufacturer=standoff["manufacturer"],
            part_number=standoff["part_number"],
            description=standoff["description"],
            quantity=4,
            notes="Optional PCB mounting hardware",
        ),
    ]


def _join_notes(notes: Any) -> str | None:
    if isinstance(notes, list):
        return "; ".join(str(item) for item in notes)
    return None

from __future__ import annotations

from collections import Counter
from typing import Any

from ocw_workbench.manufacturing.models import AssemblyStep


class AssemblyBuilder:
    def build(self, controller: dict[str, Any], components: list[dict[str, Any]]) -> dict[str, Any]:
        component_counts = Counter(str(component.get("type", "component")) for component in components)
        steps = [
            AssemblyStep(
                step_id="step_1",
                title="Install Panel Controls",
                description="Insert all panel-mounted controls and displays into the top plate cutouts.",
                required_parts=["top_plate"] + sorted(component_counts.keys()),
            ),
            AssemblyStep(
                step_id="step_2",
                title="Secure Hardware",
                description="Tighten encoder nuts, switch retainers and display hardware.",
                required_parts=["panel_mount_screw", "standoff"],
                notes=["Check front-panel alignment before tightening."],
            ),
            AssemblyStep(
                step_id="step_3",
                title="Mount PCB",
                description="Install the main PCB and connect panel components.",
                required_parts=["main_pcb", "standoff"],
            ),
            AssemblyStep(
                step_id="step_4",
                title="Close Enclosure",
                description="Attach side panels and bottom plate, then verify mechanical clearance.",
                required_parts=["bottom_plate", "side_panel"],
            ),
        ]
        return {
            "schema_version": "ocf-assembly/v1",
            "export_type": "assembly",
            "controller": {"id": controller.get("id", "controller")},
            "major_subassemblies": [
                {"id": "panel_controls", "parts": sorted(component_counts.keys())},
                {"id": "enclosure", "parts": ["top_plate", "bottom_plate", "side_panel"]},
                {"id": "electronics", "parts": ["main_pcb"]},
            ],
            "steps": [step.to_dict() for step in steps],
            "warnings": [],
            "notes": [
                "Verify display orientation before final assembly.",
                "Perform constraint validation before manufacturing release.",
            ],
        }

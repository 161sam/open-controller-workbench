from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.schema.validator import validate_schema


class ValidateProjectCommand(BaseCommand):
    ICON_NAME = "validate_constraints"

    def GetResources(self):
        return self.resources(
            "Validate Project",
            "Validate the current project schema.",
        )

    def Activated(self):
        validate_schema({})
        print("Validation complete")

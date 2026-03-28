from __future__ import annotations

from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.schema.loader import load_schema


class CreateFromSchemaCommand(BaseCommand):
    ICON_NAME = "create_controller"

    def GetResources(self):
        return self.resources(
            "Create From Schema",
            "Load a controller schema from disk.",
        )

    def Activated(self):
        data = load_schema("controller.hw.yaml")
        print(data)

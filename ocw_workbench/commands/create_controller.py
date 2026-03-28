from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.services.controller_service import ControllerService


class CreateControllerCommand(BaseCommand):
    ICON_NAME = "create_controller"

    def GetResources(self):
        return self.resources("Create Controller", "Create a new controller document.")

    def Activated(self):
        import FreeCAD as App

        doc = App.newDocument("Controller")
        ControllerService().create_controller(doc, {"id": doc.Name.lower()})
        print("New controller document created:", doc.Name)

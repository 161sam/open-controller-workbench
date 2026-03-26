from ocw_workbench.commands.base import BaseCommand
from ocw_workbench.services.controller_service import ControllerService

class CreateControllerCommand(BaseCommand):
    def GetResources(self):
        return {
            "MenuText": "Create Controller",
            "ToolTip": "Create a new MIDI controller project"
        }

    def Activated(self):
        import FreeCAD as App

        doc = App.newDocument("Controller")
        ControllerService().create_controller(doc, {"id": doc.Name.lower()})
        print("New controller document created:", doc.Name)

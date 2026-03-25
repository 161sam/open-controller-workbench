import FreeCADGui as Gui


class OpenControllerWorkbench(Gui.Workbench):
    MenuText = "Open Controller"
    ToolTip = "Modular MIDI Controller Design"
    Icon = ""

    def Initialize(self):
        from ocf_freecad.commands.add_component import AddComponentCommand
        from ocf_freecad.commands.apply_layout import ApplyLayoutCommand
        from ocf_freecad.commands.create_from_template import CreateFromTemplateCommand
        from ocf_freecad.commands.select_component import SelectComponentCommand
        from ocf_freecad.commands.validate_constraints import ValidateConstraintsCommand

        Gui.addCommand("OCF_CreateController", CreateFromTemplateCommand())
        Gui.addCommand("OCF_AddComponent", AddComponentCommand())
        Gui.addCommand("OCF_ApplyLayout", ApplyLayoutCommand())
        Gui.addCommand("OCF_SelectComponent", SelectComponentCommand())
        Gui.addCommand("OCF_ValidateConstraints", ValidateConstraintsCommand())

        create_commands = ["OCF_CreateController"]
        edit_commands = [
            "OCF_AddComponent",
            "OCF_SelectComponent",
            "OCF_ApplyLayout",
            "OCF_ValidateConstraints",
        ]
        self.appendToolbar("OCF Create", create_commands)
        self.appendToolbar("OCF Edit", edit_commands)
        self.appendMenu("OCF", create_commands + edit_commands)
        self.appendMenu("OCF/Create", create_commands)
        self.appendMenu("OCF/Edit", edit_commands)

    def Activated(self):
        pass

    def Deactivated(self):
        pass

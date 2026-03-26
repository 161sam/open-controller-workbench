from ocw_workbench.freecad_api import shapes

__all__ = ["create_box"]


def create_box(doc, width, depth, height, name="ControllerBody", x=0, y=0, z=0):
    return shapes.create_box(doc, name, width, depth, height, x=x, y=y, z=z)

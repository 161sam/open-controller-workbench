def create_box(doc, name, width, depth, height, x=0, y=0, z=0):
    import FreeCAD as App
    import Part

    shape = Part.makeBox(width, depth, height)
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    obj.Placement.Base = App.Vector(x, y, z)
    return obj


def create_rect_prism(doc, name, width, depth, height, x, y, z=0):
    return create_box(doc, name, width, depth, height, x=x, y=y, z=z)


def create_cylinder(doc, name, radius, height, x, y, z=0):
    import FreeCAD as App
    import Part

    cylinder = Part.makeCylinder(radius, height)
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = cylinder
    obj.Placement.Base = App.Vector(x, y, z)
    return obj


def cut(base_obj, tool_obj, name=None):
    result = base_obj.Shape.cut(tool_obj.Shape)
    obj = base_obj.Document.addObject(
        "Part::Feature",
        name or f"{base_obj.Name}_cut",
    )
    obj.Shape = result
    return obj

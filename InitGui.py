import os
import sys
import traceback

repo_root = None
module_file = globals().get("__file__")
if isinstance(module_file, str) and module_file:
    candidate = os.path.dirname(os.path.realpath(module_file))
    if os.path.exists(os.path.join(candidate, "ocw_workbench", "workbench.py")):
        repo_root = candidate
if repo_root is None:
    module_spec = globals().get("__spec__")
    origin = getattr(module_spec, "origin", None)
    if isinstance(origin, str) and origin:
        candidate = os.path.dirname(os.path.realpath(origin))
        if os.path.exists(os.path.join(candidate, "ocw_workbench", "workbench.py")):
            repo_root = candidate
if repo_root is None:
    candidates = []
    snap_user_common = os.environ.get("SNAP_USER_COMMON")
    snap_user_data = os.environ.get("SNAP_USER_DATA")
    snap_real_home = os.environ.get("SNAP_REAL_HOME")
    home = os.path.expanduser("~")
    if snap_user_common:
        candidates.append(os.path.join(snap_user_common, "Mod", "OpenControllerWorkbench"))
    if snap_user_data:
        candidates.append(os.path.join(snap_user_data, "Mod", "OpenControllerWorkbench"))
    if snap_real_home:
        candidates.append(os.path.join(snap_real_home, ".FreeCAD", "Mod", "OpenControllerWorkbench"))
        candidates.append(os.path.join(snap_real_home, ".local", "share", "FreeCAD", "Mod", "OpenControllerWorkbench"))
    candidates.append(os.path.join(home, ".FreeCAD", "Mod", "OpenControllerWorkbench"))
    candidates.append(os.path.join(home, ".local", "share", "FreeCAD", "Mod", "OpenControllerWorkbench"))
    for candidate in candidates:
        if os.path.exists(os.path.join(candidate, "ocw_workbench", "workbench.py")):
            repo_root = candidate
            break
if repo_root is None:
    raise RuntimeError("Could not resolve OpenControllerWorkbench repository root from InitGui.py")

if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

print("OCW InitGui loaded:", repo_root)

try:
    import FreeCADGui
    from ocw_workbench.gui.panels._common import qt_self_check
    from ocw_workbench.workbench import OpenControllerWorkbench

    qt_self_check()
    FreeCADGui.addWorkbench(OpenControllerWorkbench())
    print("OCW workbench registered")
except Exception as exc:
    print("OCW InitGui error:", exc)
    traceback.print_exc()
    raise

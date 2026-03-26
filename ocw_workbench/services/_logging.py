from __future__ import annotations


def log_to_console(message: str, level: str = "message") -> None:
    text = f"[OCW] {message}"
    if not text.endswith("\n"):
        text += "\n"
    try:
        import FreeCAD as App
    except ImportError:
        App = None
    console = getattr(App, "Console", None) if App is not None else None
    writer_name = {
        "error": "PrintError",
        "warning": "PrintWarning",
        "message": "PrintMessage",
    }.get(level, "PrintMessage")
    writer = getattr(console, writer_name, None) if console is not None else None
    if callable(writer):
        writer(text)
        return
    print(text, end="")

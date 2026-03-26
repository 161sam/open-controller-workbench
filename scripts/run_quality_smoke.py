from __future__ import annotations

from pathlib import Path
import sys
import tempfile

from ocw_workbench.freecad_api.state import read_state, write_state
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.userdata.persistence import UserDataPersistence


class SmokeDocument:
    def __init__(self) -> None:
        self.Name = "SmokeDoc"
        self.Objects = []
        self.recompute_count = 0

    def recompute(self) -> None:
        self.recompute_count += 1


def main() -> int:
    doc = SmokeDocument()
    service = ControllerService()
    state = service.create_controller(doc, {"id": "smoke"})
    write_state(doc, state)
    reloaded = read_state(doc)
    if reloaded is None or reloaded["controller"]["id"] != "smoke":
        raise SystemExit("state persistence smoke failed")

    with tempfile.TemporaryDirectory(prefix="ocw-quality-") as temp_dir:
        persistence = UserDataPersistence(base_dir=temp_dir)
        persistence.save(persistence.load())
        if not Path(temp_dir, "userdata.json").exists():
            raise SystemExit("userdata smoke failed")

    print("Quality smoke OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Desktop Pet Nicole — Frontend entry point.

Config from .env: PET_WIDTH, PET_FPS

Exits: right-click → 退出妮可, or Ctrl+C on start.sh
       Backend is killed automatically on exit.
"""

import atexit
import os
import signal
import subprocess as sp
import sys
from pathlib import Path

from dotenv import load_dotenv
from PyQt6.QtWidgets import QApplication

from pet_window import PetWindow

_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

PET_WIDTH = int(os.getenv("PET_WIDTH", "180"))
PET_FPS = int(os.getenv("PET_FPS", "24"))
PET_SCALE = PET_WIDTH / 640.0


def _kill_backend():
    """Kill backend process on port 8000."""
    try:
        pids = sp.check_output(["lsof", "-ti:8000"]).decode().strip()
        if pids:
            for pid in pids.split("\n"):
                os.kill(int(pid), signal.SIGTERM)
    except Exception:
        pass


def main():
    # Cleanup backend on exit
    atexit.register(_kill_backend)
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    pet = PetWindow(scale=PET_SCALE, fps=PET_FPS)
    screen = app.primaryScreen().geometry()
    pet.move(screen.width() // 4, screen.height() // 3)
    pet.show()
    print(f"[pet] window at {pet.pos().x()},{pet.pos().y()} {pet.width()}x{pet.height()}")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

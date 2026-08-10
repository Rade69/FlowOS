"""FlowOS GUI — PySide6 aplikacija.

Bootstrap fajl. Sva konstrukcija i wiring su u composition_root.py.
"""

import sys

from PySide6.QtWidgets import QApplication

from flowos.gui.composition_root import create_gui
from flowos.gui.views.overview_skeleton import apply_dark_theme


def main():
    live = "--live" in sys.argv
    app = QApplication(sys.argv)
    app.setApplicationName("FlowOS")
    apply_dark_theme(app)

    gui = create_gui(use_live=live)
    gui.show()

    mode = "LIVE (povezano na backend)" if live else "MOCK (bez backend-a)"
    print(f"FlowOS GUI — {mode}")
    if not live:
        print("  Koristi --live za povezivanje sa servisom.")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

"""FlowOS GUI — PySide6 aplikacija.

Pokreće QApplication, konstruiše MainWindow kroz composition root,
i ulazi u Qt event loop. Sav I/O ide preko Controller → Services,
nikad direktno iz View-a.
"""

import sys

# PySide6 importi na vrhu — osiguravaju da je Qt dostupan pre bilo čega drugog
from PySide6.QtWidgets import QApplication  # noqa: E402


def main() -> int:
    """Glavna ulazna tačka za flowos-gui.exe."""
    app = QApplication(sys.argv)
    app.setApplicationName("FlowOS")
    app.setOrganizationName("FlowOS")

    # Skeleton — ne učitavamo MainWindow dok ne postoji
    # window = composition_root.create_main_window()
    # window.show()

    # Placeholder: ako nema GUI-ja, samo ispiši i izađi
    print("FlowOS GUI — skeleton pokrenut (nema još prozora)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

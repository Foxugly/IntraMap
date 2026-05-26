"""Point d'entrée de l'interface graphique IntraMap.

Lancement ::

    intramap-gui                 # ouvre inventory.yaml du dossier courant
    intramap-gui chemin.yaml     # ouvre un inventaire précis
    python -m intramap.gui.app
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from PySide6.QtWidgets import QApplication

    from intramap.gui.main_window import MainWindow

    argv = list(sys.argv if argv is None else argv)
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName("IntraMap")
    app.setApplicationDisplayName("IntraMap")

    positional = [a for a in argv[1:] if not a.startswith("-")]
    inventory_path = positional[0] if positional else None

    window = MainWindow(inventory_path)
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

"""Génère l'icône PNG de la prise murale à partir de son SVG.

Le renderer Graphviz et l'interface utilisent des PNG ; le dépôt fournit
``outlet.svg`` et ce script produit le ``outlet.png`` correspondant. À lancer
une seule fois après récupération du code :

    python tools/make_outlet_png.py

Nécessite PySide6 (déjà installé pour l'interface graphique : ``.[gui]``).
"""
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

_ICONS = (Path(__file__).resolve().parent.parent
          / "intramap" / "renderers" / "icons")
_SVG = _ICONS / "outlet.svg"
_PNG = _ICONS / "outlet.png"
_SIZE = 256


def main() -> int:
    if not _SVG.is_file():
        print(f"Introuvable : {_SVG}", file=sys.stderr)
        return 1

    # Une instance d'application Qt est requise pour le moteur de rendu.
    app = QGuiApplication(sys.argv)
    _ = app

    renderer = QSvgRenderer(str(_SVG))
    image = QImage(_SIZE, _SIZE, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()

    if not image.save(str(_PNG), "PNG"):
        print(f"Échec de l'écriture : {_PNG}", file=sys.stderr)
        return 1
    print(f"Créé : {_PNG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

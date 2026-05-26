"""Génère les PNG manquants des icônes de devices à partir des SVG.

Le renderer Graphviz et l'interface graphique utilisent des PNG. Le dépôt
fournit les fichiers SVG ; ce script crée le PNG correspondant pour chaque
SVG qui n'en a pas encore. À lancer une fois après récupération du code :

    python tools/make_icons.py

Nécessite PySide6 (déjà installé pour l'interface graphique : ``.[gui]``).
"""
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

_ICONS = (Path(__file__).resolve().parent.parent
          / "intramap" / "renderers" / "icons")
_SIZE = 256


def main() -> int:
    if not _ICONS.is_dir():
        print(f"Dossier d'icônes introuvable : {_ICONS}", file=sys.stderr)
        return 1

    # Une instance d'application Qt est requise pour le moteur de rendu.
    app = QGuiApplication(sys.argv)
    _ = app

    created = 0
    for svg in sorted(_ICONS.glob("*.svg")):
        png = svg.with_suffix(".png")
        if png.exists():
            continue
        renderer = QSvgRenderer(str(svg))
        image = QImage(_SIZE, _SIZE, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        if not image.save(str(png), "PNG"):
            print(f"Échec de l'écriture : {png}", file=sys.stderr)
            return 1
        print(f"Créé : {png.name}")
        created += 1

    if created == 0:
        print("Toutes les icônes PNG sont déjà présentes.")
    else:
        print(f"{created} icône(s) PNG générée(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

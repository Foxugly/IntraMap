"""Configuration pytest partagée.

Force la plateforme Qt « offscreen » (avant tout import de PySide6) pour que
les tests d'interface s'exécutent sans serveur d'affichage, en CI comme en
local.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    """QApplication unique pour la session de tests GUI.

    Isole QSettings dans un emplacement de test temporaire (mode test +
    format INI) pour ne jamais écrire dans le registre / la config réelle.
    """
    pyside = pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QSettings, QStandardPaths
    QStandardPaths.setTestModeEnabled(True)
    QSettings.setDefaultFormat(QSettings.IniFormat)
    app = pyside.QApplication.instance() or pyside.QApplication([])
    yield app

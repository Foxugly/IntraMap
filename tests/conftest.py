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
    """QApplication unique pour la session de tests GUI."""
    pyside = pytest.importorskip("PySide6.QtWidgets")
    app = pyside.QApplication.instance() or pyside.QApplication([])
    yield app

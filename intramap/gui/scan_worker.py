"""Scan réseau exécuté dans un thread pour ne pas figer l'interface."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from intramap import scanner
from intramap.cli import _detect_subnets


def detect_subnets() -> list[str]:
    """Sous-réseaux IPv4 locaux candidats (forme CIDR). Cf. CLI ``scan``."""
    return _detect_subnets()


class ScanWorker(QThread):
    """Exécute ``scanner.scan`` en arrière-plan.

    Émet :attr:`succeeded` avec la liste des ``DiscoveredHost`` ou
    :attr:`failed` avec un message d'erreur lisible. Le scan nmap peut durer
    plusieurs secondes : le lancer hors du thread UI évite tout gel.
    """

    succeeded = Signal(list)
    failed = Signal(str)

    def __init__(self, network: str, parent=None):
        super().__init__(parent)
        self._network = network

    def run(self) -> None:
        try:
            discovered = scanner.scan(self._network)
        except RuntimeError as e:
            self.failed.emit(str(e))
            return
        except Exception as e:  # nmap/permissions imprévus
            self.failed.emit(
                f"Échec du scan du réseau {self._network} :\n{e}")
            return
        self.succeeded.emit(discovered)

"""Nœud du canvas : représentation déplaçable d'un :class:`Host`."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject

from intramap.gui.assets import device_color, icon_pixmap
from intramap.models import Host, _resolve_device_type

NODE_W = 172.0
NODE_H = 116.0
_ICON = 44.0
_RADIUS = 10.0


class DeviceNode(QGraphicsObject):
    """Carte d'un device : icône, nom, IP, MAC. Déplaçable et sélectionnable.

    Émet :attr:`moved` à chaque déplacement pour que la fenêtre marque le
    document comme modifié, et :attr:`double_clicked` (avec la MAC) au
    double-clic.
    """

    moved = Signal()
    double_clicked = Signal(str)

    def __init__(self, host: Host):
        super().__init__()
        self.host = host
        self._edges: list = []
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        # Pas de cache : le nœud doit se rendre en vectoriel (et à la bonne
        # échelle de police) lors de l'export PDF.
        self.setZValue(1.0)
        self.setToolTip(self._tooltip())

    # -- géométrie ---------------------------------------------------------
    @property
    def mac(self) -> str:
        return self.host.mac

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, NODE_W, NODE_H)

    def scene_center(self) -> QPointF:
        return self.mapToScene(QPointF(NODE_W / 2, NODE_H / 2))

    def set_dimmed(self, dimmed: bool) -> None:
        """Estompe (recherche) ou ré-affiche le nœud à pleine opacité."""
        self.setOpacity(0.25 if dimmed else 1.0)

    # -- arêtes ------------------------------------------------------------
    def add_edge(self, edge) -> None:
        self._edges.append(edge)

    def edges(self) -> list:
        return list(self._edges)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for edge in self._edges:
                edge.adjust()
            self.moved.emit()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event) -> None:
        self.double_clicked.emit(self.mac)
        event.accept()

    # -- rafraîchissement après édition -----------------------------------
    def refresh(self) -> None:
        """À appeler après modification de ``self.host`` pour redessiner."""
        self.setToolTip(self._tooltip())
        self.update()

    def _tooltip(self) -> str:
        h = self.host
        lines = [
            h.custom_name or h.mac,
            f"MAC : {h.mac}",
            f"IP : {h.ip or '—'}",
            f"Type : {_resolve_device_type(h)}",
            f"Constructeur : {h.vendor or '—'}",
            f"État : {'en ligne' if h.online else 'hors ligne'}",
        ]
        if h.manual:
            lines.append("(device ajouté manuellement)")
        return "\n".join(lines)

    # -- rendu -------------------------------------------------------------
    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing, True)
        h = self.host
        dtype = _resolve_device_type(h)
        accent = device_color(dtype)
        rect = QRectF(1, 1, NODE_W - 2, NODE_H - 2)

        # Corps
        body = QColor("#ffffff") if h.online else QColor("#f0f0f0")
        painter.setBrush(QBrush(body))
        if self.isSelected():
            painter.setPen(QPen(QColor("#1a73e8"), 3))
        elif h.online:
            painter.setPen(QPen(accent, 2))
        else:
            pen = QPen(QColor("#999999"), 2, Qt.DashLine)
            painter.setPen(pen)
        painter.drawRoundedRect(rect, _RADIUS, _RADIUS)

        # Bandeau d'accent
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(accent))
        painter.drawRoundedRect(QRectF(1, 1, NODE_W - 2, 6), 3, 3)

        # Icône
        pm = icon_pixmap(dtype)
        if not pm.isNull():
            scaled = pm.scaled(
                int(_ICON), int(_ICON),
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            painter.setOpacity(1.0 if h.online else 0.45)
            painter.drawPixmap(
                int((NODE_W - scaled.width()) / 2), 14, scaled,
            )
            painter.setOpacity(1.0)

        # Textes
        name = h.custom_name or h.mac
        text_color = QColor("#202020") if h.online else QColor("#888888")

        # Tailles en pixels (unités de scène) : se mettent à l'échelle comme
        # la géométrie, y compris à l'export PDF.
        font = QFont()
        font.setPixelSize(13)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(text_color))
        self._draw_elided(painter, name, 66, font)

        font.setBold(False)
        font.setPixelSize(12)
        painter.setFont(font)
        self._draw_elided(painter, h.ip or "—", 84, font)

        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#999999")))
        self._draw_elided(painter, h.mac, 99, font)

        # Pastille « manuel »
        if h.manual:
            painter.setBrush(QBrush(QColor("#1a73e8")))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(NODE_W - 12, 14), 4, 4)

    def _draw_elided(self, painter: QPainter, text: str, y: float,
                     font: QFont) -> None:
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(font)
        elided = fm.elidedText(text, Qt.ElideRight, int(NODE_W - 16))
        painter.drawText(QRectF(8, y, NODE_W - 16, 16),
                         Qt.AlignHCenter | Qt.AlignTop, elided)

"""Boîtes de regroupement visuel : un cadre par étage, un par pièce.

Un cadre de **pièce** est un simple décor (transparent à la souris). Un cadre
d'**étage** est en plus déplaçable : le saisir par son en-tête déplace tous
les devices de l'étage (les pièces et les nœuds suivent). Le cadre lui-même
n'a pas de position propre — il se recadre autour de ses membres.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem

from intramap.gui.i18n import tr

# Z-order : les cadres passent sous les arêtes (-1) et les nœuds (1).
FLOOR_Z = -20.0
ROOM_Z = -15.0

_LABEL_H = 24.0
_ROOM_PAD = 18.0
_FLOOR_PAD = 16.0

_FLOOR_FILL = QColor(31, 119, 180, 16)
_FLOOR_BORDER = QColor(31, 119, 180, 150)
_ROOM_FILL = QColor(110, 110, 110, 16)
_ROOM_BORDER = QColor(110, 110, 110, 130)


class GroupBox(QGraphicsItem):
    """Cadre étiqueté englobant un étage (``level='floor'``) ou une pièce.

    Les membres sont des :class:`~intramap.gui.node.DeviceNode` ; un cadre
    d'étage référence en plus ses cadres de pièce via :attr:`child_boxes`.
    """

    def __init__(self, label: str, level: str):
        super().__init__()
        self.label = label or "—"
        self.level = level  # "floor" | "room"
        self.member_nodes: list = []
        self.child_boxes: list[GroupBox] = []
        self._rect = QRectF(0, 0, 140, 90)
        self._drag_last: QPointF | None = None
        self.setZValue(FLOOR_Z if level == "floor" else ROOM_Z)

        if level == "floor":
            # Déplaçable : seul l'en-tête capte la souris (cf. shape()).
            self.setAcceptedMouseButtons(Qt.LeftButton)
            self.setCursor(Qt.OpenHandCursor)
            self.setToolTip(tr("Glisser l'en-tête pour déplacer tout l'étage"))
        else:
            self.setAcceptedMouseButtons(Qt.NoButton)  # décor pur

    # -- géométrie ---------------------------------------------------------
    def boundingRect(self) -> QRectF:
        return self._rect.adjusted(-3, -3, 3, 3)

    def _header_rect(self) -> QRectF:
        return QRectF(self._rect.left(), self._rect.top(),
                      self._rect.width(), _LABEL_H)

    def shape(self) -> QPainterPath:
        """Zone interactive : l'en-tête seul pour un étage (pour ne pas gêner
        la sélection au lasso dans le corps du cadre)."""
        path = QPainterPath()
        if self.level == "floor":
            path.addRect(self._header_rect())
        return path

    def all_nodes(self) -> list:
        """Tous les nœuds de l'étage : membres directs + membres des pièces."""
        nodes = list(self.member_nodes)
        for box in self.child_boxes:
            nodes.extend(box.member_nodes)
        return nodes

    def recompute(self) -> None:
        """Recadre la boîte autour de ses membres (nœuds + sous-cadres).

        Pour un étage, appeler *après* avoir recalculé ses pièces.
        """
        rects: list[QRectF] = []
        for node in self.member_nodes:
            if node.scene() is not None:
                rects.append(node.sceneBoundingRect())
        for box in self.child_boxes:
            rects.append(box._rect)
        if not rects:
            return

        united = rects[0]
        for r in rects[1:]:
            united = united.united(r)

        pad = _ROOM_PAD if self.level == "room" else _FLOOR_PAD
        new = QRectF(
            united.left() - pad,
            united.top() - pad - _LABEL_H,
            united.width() + 2 * pad,
            united.height() + 2 * pad + _LABEL_H,
        )
        if new != self._rect:
            self.prepareGeometryChange()
            self._rect = new
        self.update()

    # -- déplacement de l'étage entier ------------------------------------
    def mousePressEvent(self, event) -> None:
        if self.level == "floor" and event.button() == Qt.LeftButton:
            self._drag_last = event.scenePos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def move_by(self, delta: QPointF) -> None:
        """Déplace tous les nœuds de l'étage du vecteur ``delta``.

        Ce sont les nœuds qui bougent ; le cadre se recadre ensuite autour
        d'eux. Chaque déplacement de nœud fait suivre arêtes et sous-cadres.
        """
        for node in self.all_nodes():
            node.setPos(node.pos() + delta)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_last is not None:
            delta = event.scenePos() - self._drag_last
            self._drag_last = event.scenePos()
            self.move_by(delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_last is not None:
            self._drag_last = None
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # -- rendu -------------------------------------------------------------
    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing, True)
        if self.level == "floor":
            fill, border, style = _FLOOR_FILL, _FLOOR_BORDER, Qt.SolidLine
            font_px = 15
        else:
            fill, border, style = _ROOM_FILL, _ROOM_BORDER, Qt.DashLine
            font_px = 12

        pen = QPen(border, 1.6)
        pen.setStyle(style)
        painter.setPen(pen)
        painter.setBrush(QBrush(fill))
        painter.drawRoundedRect(self._rect, 12, 12)

        # En-tête : bandeau légèrement teinté pour signaler la prise de glisser.
        if self.level == "floor":
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(31, 119, 180, 32)))
            hdr = self._header_rect()
            painter.drawRoundedRect(
                QRectF(hdr.left(), hdr.top(), hdr.width(), hdr.height() + 6),
                12, 12)

        # Taille en pixels (unités de scène) : se met à l'échelle comme le
        # cadre, y compris à l'export PDF.
        font = QFont()
        font.setBold(True)
        font.setPixelSize(font_px)
        painter.setFont(font)
        painter.setPen(QPen(border.darker(160)))
        painter.drawText(
            QRectF(self._rect.left() + 14, self._rect.top() + 3,
                   self._rect.width() - 28, _LABEL_H),
            Qt.AlignLeft | Qt.AlignVCenter, self.label)

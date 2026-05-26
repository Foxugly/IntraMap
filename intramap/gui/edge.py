"""Arêtes du canvas : routage orthogonal avec coude déplaçable.

Trois styles de routage globaux :

- ``"straight"``  — ligne directe ;
- ``"ortho_h"``   — angles droits, segment central **vertical** (H-V-H) ;
- ``"ortho_v"``   — angles droits, segment central **horizontal** (V-H-V).

Chaque arête expose une poignée (:class:`BendHandle`) que l'utilisateur fait
glisser pour déplacer le coude. La position du coude (``custom_split``) est
une coordonnée absolue de scène, sauvegardée dans le fichier de layout.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsPathItem

EDGE_Z = -1.0
HANDLE_Z = 2.0

ROUTING_STYLES = ("straight", "ortho_h", "ortho_v")

_COLORS = {
    "wired": QColor("#555555"),
    "poe": QColor("#ff7f0e"),
    "wifi": QColor("#1f77b4"),
}


def edge_key(src_mac: str, dst_mac: str, kind: str) -> str:
    """Identifiant stable d'une arête, pour la persistance des coudes.

    Les deux extrémités sont triées : la clé ne dépend donc pas de l'ordre
    ``mac_a``/``mac_b`` du câble (qui peut changer d'un scan à l'autre), ce
    qui évite de perdre le coude personnalisé au rechargement.
    """
    a, b = sorted((src_mac, dst_mac))
    return f"{a}|{b}|{kind}"


class BendHandle(QGraphicsObject):
    """Petite poignée ronde déplaçable qui contrôle le coude d'une arête."""

    customized = Signal()

    def __init__(self, edge: "Edge"):
        super().__init__()
        self.edge = edge
        self._r = 5.0
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setZValue(HANDLE_Z)
        self.setCursor(Qt.SizeAllCursor)
        self.setToolTip(
            "Glisser pour déplacer le coude — double-clic pour réinitialiser")

    def boundingRect(self) -> QRectF:
        m = self._r + 1.5
        return QRectF(-m, -m, 2 * m, 2 * m)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing, True)
        color = _COLORS.get(self.edge.kind, _COLORS["wired"])
        painter.setBrush(color)
        painter.setPen(QPen(QColor("white"), 1.5))
        painter.drawEllipse(QPointF(0, 0), self._r, self._r)

    def itemChange(self, change, value):
        if (change == QGraphicsItem.ItemPositionHasChanged
                and not self.edge.is_adjusting):
            self.edge.on_handle_moved(self.pos())
            self.customized.emit()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event) -> None:
        self.edge.reset_bend()
        self.customized.emit()
        event.accept()


class Edge(QGraphicsPathItem):
    """Lien filaire / PoE / Wi-Fi routé en angles droits entre deux nœuds."""

    def __init__(self, source, dest, kind: str = "wired",
                 label: str = "", style: str = "ortho_h",
                 doubled: bool = False, heavy: bool = False):
        super().__init__()
        self.source = source
        self.dest = dest
        self.kind = kind
        self.label = label
        self.style = style if style in ROUTING_STYLES else "ortho_h"
        self.custom_split: float | None = None
        self.is_adjusting = False
        # Visibilité globale des poignées (cf. set_handles_visible) : respectée
        # par adjust() pour qu'un déplacement de nœud ne réaffiche pas une
        # poignée volontairement masquée (ex. pendant l'export PDF).
        self._handles_visible = True
        # Câble doublé : tracé en double trait.
        self.doubled = doubled
        # Faisceau (lien vers un patch panel) : tracé en triple trait épais.
        self.heavy = heavy

        self.setZValue(EDGE_Z)
        self.setBrush(Qt.NoBrush)  # un chemin ouvert ne doit jamais être rempli
        color = _COLORS.get(kind, _COLORS["wired"])
        if kind == "poe":
            pen = QPen(color, 3)
        elif kind == "wifi":
            pen = QPen(color, 2, Qt.DashLine)
        else:
            pen = QPen(color, 2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.MiterJoin)
        self.setPen(pen)

        source.add_edge(self)
        dest.add_edge(self)

        self.handle = BendHandle(self)
        self.handle.setParentItem(self)
        self.adjust()

    # -- identité / persistance -------------------------------------------
    def key(self) -> str:
        return edge_key(self.source.mac, self.dest.mac, self.kind)

    # -- style / coude -----------------------------------------------------
    def set_style(self, style: str) -> None:
        """Change le style de routage. Le coude personnalisé est réinitialisé
        car sa signification (axe X ou Y) dépend du style."""
        if style not in ROUTING_STYLES:
            return
        self.style = style
        self.custom_split = None
        self.adjust()

    def set_split(self, value: float | None) -> None:
        self.custom_split = value
        self.adjust()

    def reset_bend(self) -> None:
        self.custom_split = None
        self.adjust()

    def set_handles_visible(self, visible: bool) -> None:
        """Affiche / masque la poignée de coude de façon **persistante** : le
        choix est mémorisé et respecté par adjust() au prochain recalcul."""
        self._handles_visible = visible
        self.handle.setVisible(visible and self.style != "straight")

    def on_handle_moved(self, pos: QPointF) -> None:
        if self.style == "ortho_v":
            self.custom_split = pos.y()
        elif self.style == "ortho_h":
            self.custom_split = pos.x()
        else:
            return
        self.adjust()

    # -- routage -----------------------------------------------------------
    def adjust(self) -> None:
        """Recalcule le tracé entre les centres des deux nœuds."""
        if self.source is None or self.dest is None:
            return
        p1 = self.source.scene_center()
        p2 = self.dest.scene_center()
        path = QPainterPath(p1)

        if self.style == "straight":
            path.lineTo(p2)
            hpos = QPointF((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2)
        elif self.style == "ortho_v":
            sy = (self.custom_split if self.custom_split is not None
                  else (p1.y() + p2.y()) / 2)
            path.lineTo(p1.x(), sy)
            path.lineTo(p2.x(), sy)
            path.lineTo(p2)
            hpos = QPointF((p1.x() + p2.x()) / 2, sy)
        else:  # ortho_h
            sx = (self.custom_split if self.custom_split is not None
                  else (p1.x() + p2.x()) / 2)
            path.lineTo(sx, p1.y())
            path.lineTo(sx, p2.y())
            path.lineTo(p2)
            hpos = QPointF(sx, (p1.y() + p2.y()) / 2)

        self.setPath(path)
        # Repositionne la poignée sans déclencher on_handle_moved.
        self.is_adjusting = True
        self.handle.setPos(hpos)
        self.handle.setVisible(self._handles_visible and self.style != "straight")
        self.is_adjusting = False

    # -- rendu -------------------------------------------------------------
    def boundingRect(self) -> QRectF:
        # Marge pour les tracés épais (liaisons doublées / faisceaux).
        return super().boundingRect().adjusted(-9, -9, 9, 9)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(Qt.NoBrush)
        path = self.path()
        pen = self.pen()
        if self.heavy:
            # Faisceau : trois rails colorés épais (beaucoup de câbles).
            for width, color in ((13.0, pen.color()),
                                 (8.0, QColor("white")),
                                 (3.0, pen.color())):
                layer = QPen(pen)
                layer.setColor(color)
                layer.setWidthF(width)
                painter.setPen(layer)
                painter.drawPath(path)
        elif self.doubled:
            # Double trait : tracé épais coloré, puis tracé blanc plus fin
            # par-dessus — donne deux rails parallèles.
            outer = QPen(pen)
            outer.setWidthF(pen.widthF() + 3.0)
            painter.setPen(outer)
            painter.drawPath(path)
            inner = QPen(pen)
            inner.setColor(QColor("white"))
            inner.setWidthF(max(0.5, pen.widthF()))
            painter.setPen(inner)
            painter.drawPath(path)
        else:
            painter.setPen(pen)
            painter.drawPath(path)

        if not self.label:
            return
        anchor = self.handle.pos()
        painter.setPen(QPen(self.pen().color()))
        font = painter.font()
        # Taille en pixels (unités de scène) : se met à l'échelle comme le
        # tracé, y compris à l'export PDF.
        font.setPixelSize(11)
        painter.setFont(font)
        painter.drawText(anchor + QPointF(9, -5), self.label)

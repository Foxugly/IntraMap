"""Canvas interactif : QGraphicsView + scène (nœuds, arêtes, cadres de groupe)."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from intramap.gui.edge import Edge
from intramap.gui.group import GroupBox
from intramap.gui.layout import DEFAULT_ROUTING_STYLE
from intramap.gui.node import DeviceNode
from intramap.models import Inventory, Link, _resolve_device_type

_MIN_SCALE = 0.15
_MAX_SCALE = 4.0
_UNLOCATED = "Non localisé"


def node_matches(host, query: str) -> bool:
    """True si ``host`` correspond à la requête de recherche libre.

    Requête vide -> True (aucun filtre). Sinon, recherche de sous-chaîne
    (insensible à la casse) dans nom / hostname / IP / MAC / type / étage /
    pièce.
    """
    q = query.strip().lower()
    if not q:
        return True
    fields = [host.custom_name, host.hostname, host.ip, host.mac,
              _resolve_device_type(host),
              host.location.floor, host.location.room]
    return any(q in f.lower() for f in fields if f)


def _link_label(link: Link, this_mac: str | None = None) -> str:
    """Libellé court d'un câble : ``port_a↔port_b PoE``."""
    parts: list[str] = []
    if link.port_a is not None or link.port_b is not None:
        a = str(link.port_a) if link.port_a is not None else "?"
        b = str(link.port_b) if link.port_b is not None else "?"
        parts.append(f"{a}↔{b}")
    if link.poe:
        parts.append("PoE")
    return " ".join(parts)


class MapView(QGraphicsView):
    """Vue graphique de la carte réseau."""

    node_moved = Signal()
    selection_changed = Signal(str)
    node_double_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#fafafa"))

        self.nodes: dict[str, DeviceNode] = {}
        self.edges: list[Edge] = []
        self.floor_boxes: list[GroupBox] = []
        self.room_boxes: list[GroupBox] = []
        self.routing_style = DEFAULT_ROUTING_STYLE

        self._panning = False
        self._pan_start = None

        self._scene.selectionChanged.connect(self._on_selection_changed)

    def load(self, inv: Inventory,
             positions: dict[str, tuple[float, float]],
             edge_bends: dict[str, float] | None = None,
             routing_style: str | None = None) -> None:
        edge_bends = edge_bends or {}
        if routing_style:
            self.routing_style = routing_style

        self._scene.blockSignals(True)
        self._scene.clear()
        self.nodes.clear()
        self.edges.clear()
        self.floor_boxes.clear()
        self.room_boxes.clear()

        for mac, host in inv.hosts.items():
            node = DeviceNode(host)
            x, y = positions.get(mac, (0.0, 0.0))
            node.setPos(x, y)
            node.moved.connect(self._on_node_moved)
            node.double_clicked.connect(self.node_double_clicked.emit)
            self._scene.addItem(node)
            self.nodes[mac] = node

        self._build_groups(inv)
        self._build_edges(inv, edge_bends)
        self._recompute_groups()

        self._scene.blockSignals(False)
        self._update_scene_rect()

    def _build_groups(self, inv: Inventory) -> None:
        tree: dict[str, dict[object, list[str]]] = {}
        for mac, host in inv.hosts.items():
            floor = host.location.floor or _UNLOCATED
            tree.setdefault(floor, {}).setdefault(
                host.location.room, []).append(mac)

        for floor in sorted(tree):
            fbox = GroupBox(floor, "floor")
            self._scene.addItem(fbox)
            self.floor_boxes.append(fbox)
            for room, macs in tree[floor].items():
                members = [self.nodes[m] for m in macs if m in self.nodes]
                if room is None:
                    fbox.member_nodes.extend(members)
                else:
                    rbox = GroupBox(str(room), "room")
                    rbox.member_nodes.extend(members)
                    self._scene.addItem(rbox)
                    self.room_boxes.append(rbox)
                    fbox.child_boxes.append(rbox)

    def _build_edges(self, inv: Inventory,
                     edge_bends: dict[str, float]) -> None:
        """Construit les arêtes : un câble = une liaison entre deux appareils.

        Tous les câbles entre une même paire d'appareils sont regroupés en
        UNE arête : 1 câble → trait simple, 2 → double, 3+ → triple. Orange
        si au moins un câble est en PoE.
        """
        groups: dict[tuple[str, str], dict] = {}
        order: list[tuple[str, str]] = []
        for link in inv.links:
            if link.mac_a not in self.nodes or link.mac_b not in self.nodes:
                continue
            pair = tuple(sorted((link.mac_a, link.mac_b)))
            grp = groups.get(pair)
            if grp is None:
                grp = {"a": link.mac_a, "b": link.mac_b, "links": []}
                groups[pair] = grp
                order.append(pair)
            grp["links"].append(link)

        for mac, host in inv.hosts.items():
            ap = host.wifi_ap_mac
            if ap and ap in self.nodes and mac in self.nodes:
                self._add_edge(self.nodes[mac], self.nodes[ap], "wifi",
                               "Wi-Fi", edge_bends)

        for pair in order:
            grp = groups[pair]
            links = grp["links"]
            src, dst = self.nodes[grp["a"]], self.nodes[grp["b"]]
            kind = "poe" if any(lk.poe for lk in links) else "wired"
            n = len(links)
            if n >= 3:
                doubled, heavy = False, True
            elif n == 2:
                doubled, heavy = True, False
            else:
                doubled, heavy = False, False
            label = _link_label(links[0]) if n == 1 else f"{n} liaisons"
            self._add_edge(src, dst, kind, label, edge_bends,
                           doubled=doubled, heavy=heavy)

    def _add_edge(self, src: DeviceNode, dst: DeviceNode, kind: str,
                  label: str, edge_bends: dict[str, float],
                  doubled: bool = False, heavy: bool = False) -> None:
        edge = Edge(src, dst, kind, label, self.routing_style, doubled, heavy)
        bend = edge_bends.get(edge.key())
        if bend is not None:
            edge.set_split(bend)
        edge.handle.customized.connect(self.node_moved.emit)
        self._scene.addItem(edge)
        self.edges.append(edge)

    def _recompute_groups(self) -> None:
        for box in self.room_boxes:
            box.recompute()
        for box in self.floor_boxes:
            box.recompute()

    def set_routing_style(self, style: str) -> None:
        self.routing_style = style
        for edge in self.edges:
            edge.set_style(style)
        self.node_moved.emit()

    def reset_all_bends(self) -> None:
        for edge in self.edges:
            edge.reset_bend()
        self.node_moved.emit()

    def current_positions(self) -> dict[str, tuple[float, float]]:
        return {
            mac: (node.pos().x(), node.pos().y())
            for mac, node in self.nodes.items()
        }

    def current_edge_bends(self) -> dict[str, float]:
        return {
            edge.key(): edge.custom_split
            for edge in self.edges
            if edge.custom_split is not None
        }

    def selected_mac(self) -> str | None:
        for mac, node in self.nodes.items():
            if node.isSelected():
                return mac
        return None

    def selected_macs(self) -> list[str]:
        return [mac for mac, node in self.nodes.items() if node.isSelected()]

    def select_mac(self, mac: str) -> None:
        self._scene.blockSignals(True)
        for m, node in self.nodes.items():
            node.setSelected(m == mac)
        self._scene.blockSignals(False)
        if mac in self.nodes:
            self.centerOn(self.nodes[mac])

    def set_handles_visible(self, visible: bool) -> None:
        for edge in self.edges:
            edge.set_handles_visible(visible)

    def filter_nodes(self, query: str) -> int:
        """Estompe les nœuds ne correspondant pas à ``query`` ; renvoie le
        nombre de correspondances. Requête vide -> tout ré-affiché."""
        q = query.strip()
        matches = 0
        for node in self.nodes.values():
            ok = node_matches(node.host, q)
            node.set_dimmed(bool(q) and not ok)
            if ok:
                matches += 1
        return matches

    def center_on_first_match(self, query: str) -> None:
        if not query.strip():
            return
        for mac in sorted(self.nodes):
            if node_matches(self.nodes[mac].host, query):
                self.centerOn(self.nodes[mac])
                return

    def _update_scene_rect(self) -> None:
        if not self.nodes:
            self._scene.setSceneRect(QRectF(0, 0, 800, 600))
            return
        rect = self._scene.itemsBoundingRect()
        self._scene.setSceneRect(rect.adjusted(-300, -300, 300, 300))

    def fit_all(self) -> None:
        if self.nodes:
            self.fitInView(self._scene.itemsBoundingRect().adjusted(
                -40, -40, 40, 40), Qt.KeepAspectRatio)

    def _on_node_moved(self) -> None:
        self._recompute_groups()
        self.node_moved.emit()

    def _on_selection_changed(self) -> None:
        self.selection_changed.emit(self.selected_mac() or "")

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        new_scale = self.transform().m11() * factor
        if _MIN_SCALE <= new_scale <= _MAX_SCALE:
            self.scale(factor, factor)

    def zoom_in(self) -> None:
        self.scale(1.2, 1.2)

    def zoom_out(self) -> None:
        self.scale(1 / 1.2, 1 / 1.2)

    def contextMenuEvent(self, event) -> None:
        event.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._panning and self._pan_start is not None:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if (event.button() in (Qt.MiddleButton, Qt.RightButton)
                and self._panning):
            self._panning = False
            self._pan_start = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawBackground(painter, rect)
        step = 50
        pen = QPen(QColor("#e8e8e8"))
        pen.setWidth(0)
        painter.setPen(pen)
        left = int(rect.left()) - (int(rect.left()) % step)
        top = int(rect.top()) - (int(rect.top()) % step)
        x = left
        while x < rect.right():
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += step
        y = top
        while y < rect.bottom():
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += step

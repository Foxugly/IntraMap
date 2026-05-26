"""Renderer HTML interactif autonome (vis-network via CDN).

Produit une page HTML qu'on peut ouvrir dans un navigateur pour explorer la
carte (pan / zoom / déplacement). La topologie est sérialisée en JSON ; le
rendu/layout est assuré par vis-network côté client.
"""
import json

from intramap.models import Host, Inventory, _resolve_device_type
from intramap.renderers._common import edge_label as _edge_label
from intramap.renderers.icons import DEVICE_COLORS

_CDN = ("https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/"
        "vis-network.min.js")

_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>IntraMap</title>
<script src="__CDN__"></script>
<style>html,body{margin:0;height:100%}#net{width:100%;height:100vh}</style>
</head>
<body>
<div id="net"></div>
<script>
const nodes = new vis.DataSet(__NODES__);
const edges = new vis.DataSet(__EDGES__);
new vis.Network(
  document.getElementById("net"),
  {nodes: nodes, edges: edges},
  {physics: {stabilization: true}, interaction: {hover: true},
   nodes: {shape: "box"}});
</script>
</body>
</html>
"""


def _node(host: Host, node_id: str) -> dict:
    dtype = _resolve_device_type(host)
    label = "\n".join(p for p in (host.custom_name or host.mac, host.ip,
                                  host.mac) if p)
    node: dict = {
        "id": node_id,
        "label": label,
        "shape": "box",
        "title": f"{host.vendor or 'unknown'} — {dtype}",
        "color": {"background": DEVICE_COLORS[dtype], "border": "#333333"},
    }
    if not host.online:
        node["color"] = {"background": "#dddddd", "border": "#888888"}
        node["font"] = {"color": "#888888"}
    return node


def render(inv: Inventory) -> str:
    node_ids: dict[str, str] = {
        mac: f"h{i + 1}" for i, mac in enumerate(sorted(inv.hosts.keys()))
    }
    nodes = [_node(inv.hosts[mac], nid) for mac, nid in node_ids.items()]

    edges: list[dict] = []
    for link in inv.links:
        if link.mac_a not in node_ids or link.mac_b not in node_ids:
            continue
        edge: dict = {"from": node_ids[link.mac_a], "to": node_ids[link.mac_b]}
        label = _edge_label(link)
        if label:
            edge["label"] = label
        if link.poe:
            edge["color"] = {"color": "#ff7f0e"}
            edge["width"] = 3
        edges.append(edge)

    for mac in sorted(inv.hosts.keys()):
        ap = inv.hosts[mac].wifi_ap_mac
        if ap and ap in node_ids:
            edges.append({
                "from": node_ids[mac], "to": node_ids[ap],
                "label": "Wi-Fi", "dashes": True,
                "color": {"color": "#1f77b4"},
            })

    return (_TEMPLATE
            .replace("__CDN__", _CDN)
            .replace("__NODES__", json.dumps(nodes, ensure_ascii=False))
            .replace("__EDGES__", json.dumps(edges, ensure_ascii=False)))

import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime


_HEX12 = re.compile(r"^[0-9a-f]{12}$")


def normalize_mac(raw: str) -> str:
    """Return MAC in canonical form: lowercase, ':' separator."""
    if not isinstance(raw, str):
        raise ValueError(f"MAC must be a string, got {type(raw).__name__}")
    compact = raw.strip().lower().replace(":", "").replace("-", "")
    if not _HEX12.match(compact):
        raise ValueError(f"Not a valid MAC address: {raw!r}")
    return ":".join(compact[i:i + 2] for i in range(0, 12, 2))


def _parse_dt(value: str | datetime | date) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return datetime.fromisoformat(value)


@dataclass
class Location:
    floor: str | None = None
    room: str | None = None
    rack: str | None = None
    rack_unit: int | None = None


_LOCATION_FIELDS: frozenset[str] = frozenset(
    {"floor", "room", "rack", "rack_unit"})


@dataclass
class Link:
    """A physical cable between two devices — fully symmetric.

    The cable has two ends. Each end has a MAC (``mac_a``/``mac_b`` — the
    device it plugs into) and a port number (``port_a``/``port_b`` — the port
    on that device). The cable can carry PoE. There is no « source » or
    « destination » : the cable just connects two appareils.

    Stored centrally in :class:`Inventory.links` — not owned by either device.
    """
    mac_a: str
    mac_b: str
    port_a: int | None = None
    port_b: int | None = None
    poe: bool = False

    def __post_init__(self) -> None:
        self.mac_a = normalize_mac(self.mac_a)
        self.mac_b = normalize_mac(self.mac_b)

    def touches(self, mac: str) -> bool:
        m = normalize_mac(mac)
        return self.mac_a == m or self.mac_b == m

    def other_mac(self, mac: str) -> str:
        """The MAC at the other end of the cable from ``mac``."""
        m = normalize_mac(mac)
        if self.mac_a == m:
            return self.mac_b
        if self.mac_b == m:
            return self.mac_a
        raise ValueError(f"MAC {mac!r} is not an endpoint of this link")

    def port_at(self, mac: str) -> int | None:
        """The port number on the side where ``mac`` is plugged in."""
        m = normalize_mac(mac)
        if self.mac_a == m:
            return self.port_a
        if self.mac_b == m:
            return self.port_b
        raise ValueError(f"MAC {mac!r} is not an endpoint of this link")


@dataclass
class DiscoveredHost:
    """A host as seen by the scanner — raw, before inventory integration."""
    mac: str
    ip: str
    hostname: str | None
    vendor: str | None

    def __post_init__(self) -> None:
        self.mac = normalize_mac(self.mac)


@dataclass
class Host:
    mac: str
    ip: str | None
    hostname: str | None
    vendor: str | None
    first_seen: datetime
    last_seen: datetime
    custom_name: str | None = None
    location: Location = field(default_factory=Location)
    device_type: str | None = None
    manual: bool = False
    # Marque l'accès Internet (la box). Sommet du traceroute physique.
    is_gateway: bool = False
    # MAC du switch PoE qui alimente cet appareil. Renseigné = appareil PoE :
    # le traceroute reste en PoE jusqu'à ce switch, puis repasse hors PoE.
    poe_gateway: str | None = None
    wifi_ap_mac: str | None = None
    # Labels libres par port (n° port -> texte) : utile pour les outlets
    # (« jack 1 = câble 21 du patch panel ») et les patch panels.
    port_labels: dict[int, str] = field(default_factory=dict)
    online: bool = True

    def __post_init__(self) -> None:
        self.mac = normalize_mac(self.mac)
        if self.wifi_ap_mac is not None:
            self.wifi_ap_mac = normalize_mac(self.wifi_ap_mac)
        if self.poe_gateway is not None:
            self.poe_gateway = normalize_mac(self.poe_gateway)
        if self.port_labels:
            # Les clés peuvent revenir en str depuis certains parseurs YAML.
            self.port_labels = {int(k): str(v)
                                for k, v in self.port_labels.items()}

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "hostname": self.hostname,
            "vendor": self.vendor,
            "custom_name": self.custom_name,
            "location": asdict(self.location),
            "device_type": self.device_type,
            "manual": self.manual,
            "is_gateway": self.is_gateway,
            "poe_gateway": self.poe_gateway,
            "wifi_ap_mac": self.wifi_ap_mac,
            "port_labels": dict(self.port_labels),
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "online": self.online,
        }

    @classmethod
    def from_dict(cls, mac: str, data: dict) -> "Host":
        loc_data = data.get("location") or {}
        if not isinstance(loc_data, dict):
            raise ValueError(
                f"Host {mac}: 'location' must be a mapping, got "
                f"{type(loc_data).__name__}"
            )
        unknown_loc = sorted(set(loc_data) - _LOCATION_FIELDS)
        if unknown_loc:
            raise ValueError(
                f"Host {mac}: 'location' has unknown field(s) {unknown_loc}; "
                f"allowed fields are {sorted(_LOCATION_FIELDS)}"
            )

        for ts_key in ("first_seen", "last_seen"):
            if ts_key not in data:
                raise ValueError(
                    f"Host {mac}: missing required '{ts_key}' timestamp"
                )

        device_type = data.get("device_type")
        if device_type is not None and not isinstance(device_type, str):
            raise ValueError(
                f"Host {mac}: 'device_type' must be a string or null, got "
                f"{type(device_type).__name__} ({device_type!r})"
            )

        manual = data.get("manual", False)
        if not isinstance(manual, bool):
            raise ValueError(
                f"Host {mac}: 'manual' must be a boolean (true/false), got "
                f"{type(manual).__name__} ({manual!r})"
            )

        is_gateway = data.get("is_gateway", False)
        if not isinstance(is_gateway, bool):
            raise ValueError(
                f"Host {mac}: 'is_gateway' must be a boolean (true/false), "
                f"got {type(is_gateway).__name__} ({is_gateway!r})"
            )

        poe_gateway = data.get("poe_gateway")
        if poe_gateway is not None and not isinstance(poe_gateway, str):
            raise ValueError(
                f"Host {mac}: 'poe_gateway' must be a string (MAC) or null, "
                f"got {type(poe_gateway).__name__} ({poe_gateway!r})"
            )

        wifi_ap_mac = data.get("wifi_ap_mac")
        if wifi_ap_mac is not None and not isinstance(wifi_ap_mac, str):
            raise ValueError(
                f"Host {mac}: 'wifi_ap_mac' must be a string or null, got "
                f"{type(wifi_ap_mac).__name__} ({wifi_ap_mac!r})"
            )

        port_labels_raw = data.get("port_labels") or {}
        if not isinstance(port_labels_raw, dict):
            raise ValueError(
                f"Host {mac}: 'port_labels' must be a mapping of port -> "
                f"label, got {type(port_labels_raw).__name__}"
            )
        port_labels: dict[int, str] = {}
        for k, v in port_labels_raw.items():
            try:
                port_labels[int(k)] = str(v) if v is not None else ""
            except (TypeError, ValueError):
                raise ValueError(
                    f"Host {mac}: 'port_labels' keys must be integer port "
                    f"numbers, got {k!r}"
                )

        return cls(
            mac=mac,
            ip=data.get("ip"),
            hostname=data.get("hostname"),
            vendor=data.get("vendor"),
            custom_name=data.get("custom_name"),
            location=Location(**loc_data),
            device_type=device_type,
            manual=manual,
            is_gateway=is_gateway,
            poe_gateway=poe_gateway,
            wifi_ap_mac=wifi_ap_mac,
            port_labels=port_labels,
            first_seen=_parse_dt(data["first_seen"]),
            last_seen=_parse_dt(data["last_seen"]),
            online=data.get("online", True),
        )


DEVICE_TYPES: frozenset[str] = frozenset({
    "router", "switch", "ap", "controller", "nas",
    "tv", "stb", "phone", "tablet", "laptop",
    "iot", "camera", "printer", "voip", "other",
    "outlet", "patchpanel", "appliance",
})


_VENDOR_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (("sagemcom", "vantiva", "technicolor", "arris"), "router"),
    (("synology", "qnap", "western digital", "seagate"), "nas"),
    (("cisco", "juniper", "aruba", "mikrotik", "netgear"), "switch"),
    (("tp-link", "ubiquiti", "unifi"), "ap"),
    (("lg electronics", "samsung electronics", "sony", "philips"), "tv"),
    (("apple", "google", "xiaomi", "huawei", "oneplus"), "phone"),
    (("hikvision", "dahua", "axis", "bticino"), "camera"),
    (("intel corporate", "dell", "lenovo", "asus", "hp inc",
      "universal global scientific"), "laptop"),
    (("tuya", "tado", "nest", "ring", "philips hue",
      "eedomus", "davicom"), "iot"),
    (("grandstream", "yealink", "polycom", "snom"), "voip"),
    (("canon", "epson", "brother industries"), "printer"),
]


def infer_device_type(vendor: str | None) -> str | None:
    if not vendor:
        return None
    v = vendor.lower()
    for patterns, device_type in _VENDOR_PATTERNS:
        for p in patterns:
            if p in v:
                return device_type
    return None


def _resolve_device_type(host) -> str:
    explicit = getattr(host, "device_type", None)
    if explicit is not None:
        return explicit if explicit in DEVICE_TYPES else "other"
    inferred = infer_device_type(getattr(host, "vendor", None))
    return inferred or "other"


def _legacy_links_from_host(mac: str, data: dict) -> list[Link]:
    """Convert old per-host ``uplinks``/``uplink`` keys into :class:`Link`.

    Old files used to store cables as ``Host.uplinks`` (or the even older
    single ``uplink``) on each host, pointing « up » to its switch. The new
    model stores cables centrally in :class:`Inventory.links`. This helper
    extracts the cables described in legacy data so they can be added to
    that central list.
    """
    out: list[Link] = []
    raw = data.get("uplinks")
    items: list[dict] = []
    if raw is not None:
        if not isinstance(raw, list):
            raise ValueError(
                f"Host {mac}: 'uplinks' must be a list of mappings, got "
                f"{type(raw).__name__} ({raw!r})"
            )
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError(
                    f"Host {mac}: each entry of 'uplinks' must be a "
                    f"mapping with fields switch_mac/switch_port/"
                    f"patch_port/poe, got {type(item).__name__} ({item!r})"
                )
            items.append(item)
    elif "uplink" in data:
        u = data["uplink"]
        if u is None:
            return out
        if not isinstance(u, dict):
            raise ValueError(
                f"Host {mac}: 'uplink' must be null or a mapping with fields "
                f"switch_mac/switch_port/patch_port/poe, got "
                f"{type(u).__name__} ({u!r}). Example:\n"
                f"  uplink:\n"
                f"    switch_mac: aa:bb:cc:dd:ee:ff\n"
                f"    switch_port: 4\n"
                f"    patch_port: 7\n"
                f"    poe: true"
            )
        items = [u]

    for u in items:
        sm = u.get("switch_mac")
        if not sm:
            continue
        poe = bool(u.get("poe", False))
        out.append(Link(
            mac_a=mac, port_a=u.get("patch_port"),
            mac_b=sm, port_b=u.get("switch_port"), poe=poe,
        ))
        # Ancien câble doublé : un second câble sur patch_port_b côté local.
        if u.get("doubled") and u.get("patch_port_b") is not None:
            out.append(Link(
                mac_a=mac, port_a=u.get("patch_port_b"),
                mac_b=sm, port_b=u.get("switch_port"), poe=poe,
            ))
    return out


def _endpoint_sort_key(endpoint: tuple[str, int | None]) -> tuple:
    """Clé d'ordre totale pour une extrémité ``(mac, port)``.

    Évite de comparer ``None`` à un ``int`` (les ports absents trient avant
    les ports numérotés) : indispensable pour les self-loops où les deux
    extrémités partagent le même MAC.
    """
    mac, port = endpoint
    return (mac, port is not None, port if port is not None else 0)


def _link_key(link: Link) -> tuple:
    """Identité canonique d'un câble (ordre des extrémités neutralisé)."""
    a = (link.mac_a, link.port_a)
    b = (link.mac_b, link.port_b)
    if _endpoint_sort_key(b) < _endpoint_sort_key(a):
        a, b = b, a
    return (a, b, link.poe)


_LINK_FIELDS: frozenset[str] = frozenset(
    {"mac_a", "mac_b", "port_a", "port_b", "poe"})


def _link_from_dict(item: dict) -> Link:
    """Construit un :class:`Link` depuis une entrée ``links:`` du YAML.

    Valide les clés et la présence des deux MAC pour produire un message
    clair (plutôt qu'un ``TypeError`` brut de :class:`Link`) quand le fichier
    a été édité à la main ou contient d'anciennes clés (``doubled``…).
    """
    unknown = sorted(set(item) - _LINK_FIELDS)
    if unknown:
        raise ValueError(
            f"Link entry has unknown field(s) {unknown}; allowed fields are "
            f"{sorted(_LINK_FIELDS)}"
        )
    for required in ("mac_a", "mac_b"):
        if not item.get(required):
            raise ValueError(
                f"Link entry missing required '{required}': {item!r}"
            )
    return Link(**item)


@dataclass
class Inventory:
    hosts: dict[str, Host] = field(default_factory=dict)
    links: list[Link] = field(default_factory=list)
    last_scan: datetime | None = None

    def add_link(self, link: Link) -> bool:
        """Ajoute un câble s'il n'existe pas déjà.

        La déduplication se fait sur l'identité canonique (:func:`_link_key`,
        ordre des extrémités neutralisé). Retourne ``True`` si le câble a été
        ajouté, ``False`` si un câble équivalent existait déjà. C'est le point
        d'entrée unique pour créer un câble : il garantit que l'état en mémoire
        ne contient jamais de doublon (ce que ferait sinon diverger l'écran du
        fichier, puisque le chargement dédoublonne).
        """
        key = _link_key(link)
        if any(_link_key(existing) == key for existing in self.links):
            return False
        self.links.append(link)
        return True

    def to_dict(self) -> dict:
        return {
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "links": [asdict(lk) for lk in self.links],
            "hosts": {mac: h.to_dict() for mac, h in sorted(self.hosts.items())},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Inventory":
        last_scan_raw = data.get("last_scan")
        last_scan = _parse_dt(last_scan_raw) if last_scan_raw else None

        links: list[Link] = []
        seen: set[tuple] = set()

        def _add(lk: Link) -> None:
            key = _link_key(lk)
            if key in seen:
                return
            seen.add(key)
            links.append(lk)

        raw_links = data.get("links")
        if raw_links is not None:
            if not isinstance(raw_links, list):
                raise ValueError(
                    f"Inventory 'links' must be a list of mappings, got "
                    f"{type(raw_links).__name__}"
                )
            for item in raw_links:
                if not isinstance(item, dict):
                    raise ValueError(
                        f"Each entry of 'links' must be a mapping with "
                        f"fields mac_a/mac_b/port_a/port_b/poe, got "
                        f"{type(item).__name__} ({item!r})"
                    )
                _add(_link_from_dict(item))

        hosts_data = data.get("hosts") or {}
        hosts: dict[str, Host] = {}
        for mac, hd in hosts_data.items():
            mac_n = normalize_mac(mac)
            hosts[mac_n] = Host.from_dict(mac_n, hd)
            # Compat ascendante : convertir les anciens uplinks par hôte.
            for legacy in _legacy_links_from_host(mac_n, hd):
                _add(legacy)

        return cls(hosts=hosts, links=links, last_scan=last_scan)


def links_touching(inv: Inventory, mac: str) -> list[Link]:
    """Tous les câbles dont l'une des extrémités est ``mac``."""
    target = normalize_mac(mac)
    return [lk for lk in inv.links
            if lk.mac_a == target or lk.mac_b == target]


@dataclass
class Hop:
    """Une étape du traceroute : ``src`` rejoint ``dst`` via le câble ``link``.

    ``wifi=True`` marque un saut sans-fil (association Wi-Fi, pas un vrai
    câble) — utile pour le rapport qui affiche alors « Wi-Fi » au lieu d'un
    numéro de port.
    """
    src: Host
    link: Link
    dst: Host | None
    wifi: bool = False


# ---------------------------------------------------------------------------
# Traceroute non-directionnel, BFS depuis la passerelle Internet
# ---------------------------------------------------------------------------

_INFRA_TRANSIT: frozenset[str] = frozenset({
    "outlet", "switch", "router", "patchpanel", "ap", "controller",
})


def _adjacency(inv: Inventory) -> dict[str, list[tuple[str, Link, bool]]]:
    """Graphe non-orienté des câbles **et** des associations Wi-Fi.

    Renvoie ``{mac: [(voisin, link, wifi), ...]}`` où ``wifi=True`` marque
    un lien virtuel construit à partir de ``host.wifi_ap_mac`` (un appareil
    sans câble mais associé à un AP peut quand même atteindre le réseau).

    Ordre des voisins : câbles non-PoE d'abord, puis câbles PoE, puis liens
    Wi-Fi virtuels. Comme la BFS visite dans l'ordre, ça revient à
    **préférer** les chemins câblés non-PoE quand un choix existe, et à
    n'utiliser le Wi-Fi qu'en dernier recours.
    """
    adj: dict[str, list[tuple[str, Link, bool]]] = {m: [] for m in inv.hosts}
    # 1. Câbles non-PoE (préférés).
    for link in inv.links:
        if link.poe:
            continue
        if link.mac_a in adj and link.mac_b in adj:
            adj[link.mac_a].append((link.mac_b, link, False))
            adj[link.mac_b].append((link.mac_a, link, False))
    # 2. Câbles PoE (utilisables aussi par les non-PoE en transit).
    for link in inv.links:
        if not link.poe:
            continue
        if link.mac_a in adj and link.mac_b in adj:
            adj[link.mac_a].append((link.mac_b, link, False))
            adj[link.mac_b].append((link.mac_a, link, False))
    # 3. Liens virtuels Wi-Fi en dernier.
    for mac, host in inv.hosts.items():
        ap = host.wifi_ap_mac
        if ap and ap in adj:
            v = Link(mac_a=mac, mac_b=ap, poe=False)
            adj[mac].append((ap, v, True))
            adj[ap].append((mac, v, True))
    return adj


def _bfs(inv: Inventory,
         adj: dict[str, list[tuple[str, Link, bool]]],
         source, predicate,
         *, stop_at: str | None = None,
         ) -> tuple[dict, dict[str, object]]:
    """BFS depuis ``source`` dans le graphe non-orienté.

    ``source`` est un MAC unique **ou** un itérable de MAC (BFS multi-sources :
    indispensable quand il existe plusieurs passerelles Internet — chaque
    appareil rejoint alors la plus proche). ``predicate(link, wifi)`` filtre
    les arêtes utilisables.

    Les appareils intermédiaires doivent être des appareils d'infrastructure
    (:data:`_INFRA_TRANSIT`). **Cas particulier du patch panel** : un patch
    panel est un dispositif passif — ce qui rentre par son port N ressort
    aussi par son port N. Pour respecter ça, on visite chaque patch panel
    sous forme de clé enrichie ``(mac, port_d_entrée)`` : un câble n'a le
    droit de transiter par le patch panel que s'il touche aussi ce même
    port (côté patch panel) lors de la sortie.

    Renvoie ``(preds_rich, first_key)`` :
    - ``preds_rich[key] = (prev_key, Link, wifi)`` où une clé est soit
      ``mac`` (str), soit ``(mac, port)`` (tuple, patch panel uniquement).
    - ``first_key[mac]`` est la première clé enrichie atteinte pour ce
      mac — celle qui correspond au chemin le plus court (BFS).
    """
    sources = [source] if isinstance(source, str) else list(source)
    source_set: set[str] = set(sources)
    preds_rich: dict = {}
    visited: set = set(sources)
    queue: list = list(sources)
    first_key: dict[str, object] = {s: s for s in sources}

    # Patch panels modélisés avec un mapping port-à-port explicite : au moins
    # un de leurs ports est touché par 2 câbles ou plus (côté d'entrée et
    # côté de sortie sur le même n°). Pour ceux-là, on impose le pass-through.
    # Les patch panels où chaque port n'apparaît qu'une fois sont traités
    # comme de simples répartiteurs (les ports d'entrée/sortie sont
    # indépendants).
    pp_strict: set[str] = set()
    for _mac, _host in inv.hosts.items():
        if _resolve_device_type(_host) != "patchpanel":
            continue
        port_count: dict[int, int] = {}
        for _lk in inv.links:
            p = None
            if _lk.mac_a == _mac:
                p = _lk.port_a
            elif _lk.mac_b == _mac:
                p = _lk.port_b
            if p is not None:
                port_count[p] = port_count.get(p, 0) + 1
        if any(c >= 2 for c in port_count.values()):
            pp_strict.add(_mac)

    def _rich_key(nbr_mac: str, link: Link):
        """Clé enrichie pour un voisin : (mac, port) si c'est un patch panel
        modélisé port-à-port, sinon le mac brut."""
        if nbr_mac in pp_strict:
            return (nbr_mac, link.port_at(nbr_mac))
        return nbr_mac

    while queue:
        cur_key = queue.pop(0)
        if isinstance(cur_key, tuple):
            cur_mac, entry_port = cur_key
        else:
            cur_mac, entry_port = cur_key, None
        host = inv.hosts.get(cur_mac)
        is_pp = host is not None and _resolve_device_type(host) == "patchpanel"

        is_source = cur_key in source_set
        if not is_source:
            if host is None:
                continue
            if is_pp:
                # Pour un patch panel modélisé port-à-port (strict), on
                # n'autorise le transit que si on connaît le port d'entrée.
                # Sinon (mode splitter), le mac brut suffit.
                if cur_mac in pp_strict and entry_port is None:
                    continue
            elif _resolve_device_type(host) not in _INFRA_TRANSIT:
                continue

        # Pass-through pour les patch panels strict-mode : sortie par le
        # même port que l'entrée.
        strict_pp = (not is_source and is_pp and entry_port is not None
                     and cur_mac in pp_strict)

        for nbr, lk, wifi in adj.get(cur_mac, []):
            if not predicate(lk, wifi):
                continue
            if strict_pp and lk.port_at(cur_mac) != entry_port:
                continue
            nk = _rich_key(nbr, lk)
            if nk in visited:
                continue
            visited.add(nk)
            preds_rich[nk] = (cur_key, lk, wifi)
            if nbr not in first_key:
                first_key[nbr] = nk
            if stop_at is not None and nbr == stop_at:
                return preds_rich, first_key
            queue.append(nk)
    return preds_rich, first_key


def _walk(state: tuple[dict, dict[str, object]],
          src: str, dst, inv: Inventory) -> list[Hop] | None:
    """Remonte le chemin de ``src`` vers ``dst`` à partir de l'état de BFS.

    ``dst`` est un MAC unique **ou** un ensemble de MAC ; la marche s'arrête à
    la première destination atteinte (la plus proche, BFS oblige). ``state``
    est ``(preds_rich, first_key)``. La marche utilise les clés enrichies en
    interne ; le résultat reste une liste de :class:`Hop` indexée par les
    hosts d'origine.
    """
    preds_rich, first_key = state
    dsts = {dst} if isinstance(dst, str) else set(dst)
    if src in dsts:
        return []
    if src not in first_key:
        return None
    out: list[Hop] = []
    cur_key = first_key[src]
    while True:
        cur_mac = cur_key if isinstance(cur_key, str) else cur_key[0]
        if cur_mac in dsts:
            return out
        if cur_key not in preds_rich:
            return None
        prev_key, lk, wifi = preds_rich[cur_key]
        prev_mac = prev_key if isinstance(prev_key, str) else prev_key[0]
        out.append(Hop(src=inv.hosts[cur_mac], link=lk,
                       dst=inv.hosts.get(prev_mac), wifi=wifi))
        cur_key = prev_key


def _gateways(inv: Inventory) -> list[Host]:
    """Toutes les passerelles Internet déclarées (``is_gateway=True``)."""
    return [h for h in inv.hosts.values() if h.is_gateway]


def trace_paths(inv: Inventory, mac: str) -> list[list[Hop]]:
    """Chemin de ``mac`` jusqu'à la passerelle Internet, non-directionnel.

    Un câble est suivi dans les deux sens ; la BFS part de la passerelle
    Internet et ne transite que par les appareils d'infrastructure (outlet,
    switch, router, patchpanel, ap, controller). Un appareil PoE reste en
    PoE jusqu'à son ``poe_gateway`` (le switch PoE), puis le reste du chemin
    se trace hors PoE. Un appareil sans ``poe_gateway`` est tracé hors PoE.

    Renvoie ``[chemin]`` (plus court) ou ``[[]]`` si pas de chemin.
    """
    start = normalize_mac(mac)
    start_host = inv.hosts.get(start)
    if start_host is None or start_host.is_gateway:
        return [[]]
    gateways = _gateways(inv)
    if not gateways:
        return [[]]
    gw_macs = {g.mac for g in gateways}
    adj = _adjacency(inv)
    # Pour un appareil non-PoE : on accepte tout (cables non-PoE, PoE,
    # Wi-Fi). L'ordre de l'adjacence (non-PoE d'abord, Wi-Fi en dernier)
    # garantit qu'on prefere le chemin cable non-PoE quand il existe. La BFS
    # part de toutes les passerelles : chaque appareil rejoint la plus proche.
    non_poe_state = _bfs(inv, adj, gw_macs, lambda lk, wifi: True)
    poe_gw = start_host.poe_gateway
    if poe_gw and poe_gw in inv.hosts:
        # Segment PoE : strict PoE-only, pas de Wi-Fi.
        poe_state = _bfs(inv, adj, poe_gw,
                         lambda lk, wifi: (not wifi) and lk.poe,
                         stop_at=start)
        poe_seg = _walk(poe_state, start, poe_gw, inv)
        if poe_seg is None:
            return [[]]
        non_seg = _walk(non_poe_state, poe_gw, gw_macs, inv) or []
        return [poe_seg + non_seg]
    seg = _walk(non_poe_state, start, gw_macs, inv)
    return [seg] if seg is not None else [[]]


def trace_all_paths(inv: Inventory) -> dict[str, list[Hop]]:
    """Chemins de tous les hotes vers la passerelle, en une passe memoisee."""
    gateways = _gateways(inv)
    if not gateways:
        return {mac: [] for mac, h in inv.hosts.items() if not h.is_gateway}
    gw_macs = {g.mac for g in gateways}
    adj = _adjacency(inv)
    non_poe_state = _bfs(inv, adj, gw_macs, lambda lk, wifi: True)
    poe_cache: dict[str, tuple] = {}
    out: dict[str, list[Hop]] = {}
    for mac, h in inv.hosts.items():
        if h.is_gateway:
            continue
        poe_gw = h.poe_gateway
        if poe_gw and poe_gw in inv.hosts:
            if poe_gw not in poe_cache:
                poe_cache[poe_gw] = _bfs(
                    inv, adj, poe_gw,
                    lambda lk, wifi: (not wifi) and lk.poe)
            seg = _walk(poe_cache[poe_gw], mac, poe_gw, inv)
            if seg is None:
                out[mac] = []
                continue
            tail = _walk(non_poe_state, poe_gw, gw_macs, inv) or []
            out[mac] = seg + tail
        else:
            seg = _walk(non_poe_state, mac, gw_macs, inv)
            out[mac] = seg if seg is not None else []
    return out

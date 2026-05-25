# IntraMap

Scan a local IPv4 network, annotate the inventory with custom names and physical locations (floor / room / rack), then render the result as PlantUML and Graphviz diagrams. Optionally declare uplink wiring (switch / patch panel / PoE) to draw the cabling on the diagram.

## Installation

Requires Python 3.11+ and the `nmap` binary on PATH.

- macOS: `brew install nmap`
- Debian/Ubuntu: `sudo apt install nmap`
- Windows: https://nmap.org/download.html (installer)

Then:

```bash
pip install -e ".[dev]"
```

## Quick start

```bash
# Scan the local subnet (auto-detected) and create / update inventory.yaml
intramap scan

# Or explicitly:
intramap scan --network 192.168.1.0/24

# Edit inventory.yaml by hand to add custom_name and location (floor/room/rack)
# for each host. New hosts appear with custom_name: null.

# Show the inventory
intramap list
intramap list --unnamed   # hosts that still need a custom_name
intramap list --offline   # hosts not seen on the last scan

# Generate diagrams in ./output/
intramap render                       # both PlantUML and Graphviz
intramap render --format plantuml     # just .puml
intramap render --format graphviz     # just .dot
```

## Declaring uplinks (optional)

Edit a host's entry in `inventory.yaml` to add an `uplink` block describing how the device is wired:

```yaml
aa:bb:cc:dd:ee:03:
  ip: 192.168.1.50
  hostname: camera-entree
  vendor: Hikvision
  custom_name: Caméra entrée
  location: {floor: RDC, room: hall, rack: null, rack_unit: null}
  uplink:
    switch_mac: aa:bb:cc:dd:ee:02  # MAC of the upstream switch (must be in the inventory)
    switch_port: 4                  # port number on the switch
    patch_port: 7                   # port on the patch panel of this host's rack
    poe: true                       # device is powered via PoE
  first_seen: ...
  last_seen: ...
  online: true
```

When you run `intramap render`, the diagram will draw an edge from this host to the referenced switch. PoE edges are styled in orange (thick). Edges to unknown MACs are silently skipped.

## Rendering the diagrams to images

The easiest way — `intramap render --image` invokes `dot` automatically with the correct working directory so the bundled icons resolve:

```bash
intramap render --image           # writes network.puml, network.dot, network.svg, network.png + icons/
```

This requires Graphviz (`dot`) in PATH. If it's missing, you get a clear warning and the text files are still produced.

Alternatively, do it by hand. **Important**: `dot` must be run from inside the output directory, otherwise the relative `image="icons/<type>.png"` paths in the .dot file won't resolve:

```bash
# Graphviz — run from inside output/
cd output && dot -Tsvg network.dot -o network.svg && cd ..

# PlantUML (requires plantuml.jar or a local install)
plantuml output/network.puml
```

The PlantUML output is self-contained (sprites resolved by PlantUML's stdlib) and doesn't need a special working directory.

### Diagram layout

The layout is top-to-bottom (`rankdir=TB` in Graphviz, `top to bottom direction` in PlantUML). The hierarchy only becomes visible once you declare `uplink` and/or `wifi_ap_mac` fields on your hosts — with no edges, the layout engine has nothing to rank, and hosts will be packed into clusters by location only.

## How the inventory is organised

`inventory.yaml` is your source of truth — versioned in git, edited by hand. Each scan merges into it:

- New MAC → host added with empty `custom_name`, `location`, `uplink`. Edit them manually.
- Known MAC → IP / hostname / vendor / `last_seen` updated; your annotations preserved.
- Known MAC absent from the latest scan → marked `online: false`, otherwise untouched.

Hosts are identified by MAC address (stable across IP/hostname changes).

## Permissions

`nmap` needs raw-socket access to resolve MAC addresses (ARP). On macOS/Linux run with `sudo`; on Windows launch the shell with administrator privileges. Without that you'll get IPs but not MACs, which breaks identity tracking.

## Out of scope

- IPv6
- VLANs and multi-subnet scans
- Automatic L2 topology discovery via SNMP (uplinks are user-declared only)

## Tests

```bash
pytest
```

## Wi-Fi associations and visual hints

Declare a Wi-Fi association on any host by setting `wifi_ap_mac` to the MAC
of the upstream access point (must be a host in the inventory):

```yaml
aa:bb:cc:dd:ee:03:
  ip: 192.168.1.50
  custom_name: iPhone
  wifi_ap_mac: aa:bb:cc:dd:ee:01   # MAC of the AP
  # ... other fields ...
```

The renderer draws a dashed edge labeled "Wi-Fi" from the host to the AP.
A host can have both a wired `uplink` and a `wifi_ap_mac` — both edges are
drawn.

### Diagram features

- Hierarchical top-to-bottom layout
- Node color by device category (router, switch, NAS, IoT, etc.)
- PoE edges drawn in orange, Wi-Fi edges drawn dashed blue
- Auto-generated legend cluster at the bottom of each diagram
- Cleaner labels with smaller IP/MAC text
- Graphviz SVG output includes `<title>` tooltips with vendor and last-seen info

## Acknowledgements

Icons by [Font Awesome](https://fontawesome.com/), licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The bundled SVGs are unmodified copies of selected Font Awesome Free 6
solid icons (see `intramap/renderers/icons/LICENSE`).

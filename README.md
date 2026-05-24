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

IntraMap only writes the `.puml` and `.dot` files. Convert them to PNG/SVG with:

```bash
# PlantUML (requires plantuml.jar or a local install)
plantuml output/network.puml

# Graphviz
dot -Tsvg output/network.dot -o output/network.svg
```

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

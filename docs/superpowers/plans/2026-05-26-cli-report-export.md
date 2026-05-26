# CLI Report Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the wiring and path reports on the CLI via `intramap report {wiring|paths|all}` (text, plus CSV for wiring), without pulling Qt into the CLI.

**Architecture:** Extract the Qt-free path-report builder out of the GUI dialog into `intramap/path_report.py`; add `build_wiring_csv` to `intramap/wiring_report.py`; add a `report` subcommand to `intramap/cli.py`. The GUI dialog re-imports `build_report` so existing callers/tests stay green.

**Tech Stack:** argparse (existing CLI), stdlib `csv`, existing report builders.

---

### Task 1: Extract path-report builder into a Qt-free module

**Files:**
- Create: `intramap/path_report.py`
- Modify: `intramap/gui/path_report_dialog.py` (drop local builder defs, import from `intramap.path_report`)
- Test: `tests/test_path_report.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_path_report.py`:

```python
"""Tests du builder de rapport de chemins (sans Qt)."""
from datetime import datetime

from intramap.models import Host, Inventory, Link
from intramap.path_report import build_report


def _h(mac, **kw):
    now = datetime(2026, 5, 25)
    d = dict(ip=None, hostname=None, vendor=None, first_seen=now, last_seen=now)
    d.update(kw)
    return Host(mac=mac, **d)


def _inv(*hosts, links=None):
    return Inventory(hosts={h.mac: h for h in hosts}, links=list(links or []))


def test_build_report_traces_device_to_gateway():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router",
            custom_name="Box")
    pc = _h("aa:bb:cc:dd:ee:02", device_type="laptop", custom_name="PC")
    inv = _inv(gw, pc,
               links=[Link(mac_a=pc.mac, port_a=1, mac_b=gw.mac, port_b=2)])
    report = build_report(inv)
    assert "Box" in report and "PC" in report
    assert "Accès Internet" in report


def test_build_report_flags_unreachable_device():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    orphan = _h("aa:bb:cc:dd:ee:02", device_type="laptop", custom_name="Isolé")
    report = build_report(_inv(gw, orphan))
    assert "aucun chemin" in report


def test_build_report_empty_inventory():
    assert "Aucun appareil" in build_report(Inventory())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_path_report.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'intramap.path_report'`.

- [ ] **Step 3: Create `intramap/path_report.py` with the moved code**

```python
"""Rapport texte du traceroute physique (chemin de chaque appareil jusqu'à la
passerelle Internet). Sans dépendance Qt : réutilisable en CLI comme en GUI.
"""
from __future__ import annotations

from intramap.models import Inventory, trace_all_paths


def _device_name(host) -> str:
    return host.custom_name or host.hostname or host.mac


def _hop_detail(hop) -> str:
    """Décrit le saut : ports d'un câble, ou « Wi-Fi » pour une association."""
    if hop.wifi:
        return "Wi-Fi"
    lk = hop.link
    src_p = lk.port_at(hop.src.mac) if hop.src is not None else None
    dst_p = lk.port_at(hop.dst.mac) if hop.dst is not None else None
    parts: list[str] = []
    if src_p is not None:
        parts.append(f"port {src_p}")
    if dst_p is not None:
        parts.append(f"→ port {dst_p}")
    if lk.poe:
        parts.append("PoE")
    return "  ·  ".join(parts)


def build_report(inv: Inventory) -> str:
    """Construit le rapport texte du chemin de chaque appareil vers Internet."""
    if not inv.hosts:
        return "Aucun appareil sur la carte.\n"

    hosts = sorted(inv.hosts.values(), key=lambda h: _device_name(h).lower())
    paths = trace_all_paths(inv)
    lines: list[str] = []
    for h in hosts:
        head = f"■ {_device_name(h)}   [{h.mac}]"
        if h.ip:
            head += f"   {h.ip}"
        if h.poe_gateway:
            head += "   · alimenté en PoE"
        lines.append(head)

        if h.is_gateway:
            lines.append("    ⇒ Passerelle Internet (accès box).")
            lines.append("")
            continue

        path = paths.get(h.mac) or []
        if not path:
            if h.poe_gateway:
                lines.append(
                    "    ⚠ aucun chemin PoE trouvé jusqu'à la passerelle "
                    "Internet (PoE rompu, ou pas de chemin par les "
                    "appareils d'infrastructure)")
            else:
                lines.append(
                    "    ⚠ aucun chemin trouvé jusqu'à la passerelle "
                    "Internet (pas de liaison vers un switch / patch panel "
                    "qui y mène)")
            lines.append("")
            continue

        prev = _device_name(h)
        for hop in path:
            nxt = _device_name(hop.dst)
            detail = _hop_detail(hop)
            suffix = f"   ({detail})" if detail else ""
            lines.append(f"    «{prev}»  →  «{nxt}»{suffix}")
            prev = nxt
        if path[-1].dst.is_gateway:
            lines.append("    ↳ Accès Internet ✓")
        else:
            lines.append(
                f"    ↳ ⚠ chemin partiel — «{prev}» n'atteint pas la "
                f"passerelle Internet")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: Update `intramap/gui/path_report_dialog.py` to import from the new module**

Replace the import block and delete the three moved functions. Change the model import line:

```python
from intramap.models import Inventory
```

(remove `trace_all_paths` from that import — no longer used in the dialog), and add below the PySide6 imports:

```python
from intramap.path_report import build_report
```

Then delete the local definitions of `_device_name`, `_hop_detail`, and `build_report` from the dialog file (lines defining those three functions). The `PathReportDialog` class is unchanged and still calls `build_report(inv)` in `__init__`.

- [ ] **Step 5: Run the path-report and GUI tests**

Run: `python -m pytest tests/test_path_report.py tests/test_gui.py -q`
Expected: PASS (the GUI test importing `intramap.gui.path_report_dialog.build_report` still resolves via the re-import).

- [ ] **Step 6: Verify the CLI path stays Qt-free**

Run: `python -c "import sys, intramap.path_report; assert 'PySide6' not in sys.modules; print('path_report Qt-free OK')"`
Expected: `path_report Qt-free OK`.

- [ ] **Step 7: Commit**

```bash
git add intramap/path_report.py intramap/gui/path_report_dialog.py tests/test_path_report.py
git commit -m "refactor: extract Qt-free path-report builder into intramap.path_report"
```

---

### Task 2: CSV export for the wiring report

**Files:**
- Modify: `intramap/wiring_report.py` (add `build_wiring_csv`)
- Test: `tests/test_wiring_report.py` (append CSV tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_wiring_report.py`:

```python
from intramap.wiring_report import build_wiring_csv

_CSV_HEADER = ("device,mac,floor,room,local_port,local_label,"
               "peer,peer_type,peer_port,peer_label,poe")


def test_csv_emits_exact_header():
    assert build_wiring_csv(Inventory()).splitlines()[0] == _CSV_HEADER


def test_csv_empty_inventory_is_header_only():
    lines = build_wiring_csv(Inventory()).splitlines()
    assert lines == [_CSV_HEADER]


def test_csv_one_row_per_cable_with_peer_info():
    inv = Inventory()
    sw = _h("aa:00:00:00:00:01", "SW", "switch", floor="RDC", room="Salon")
    pc = _h("aa:00:00:00:00:02", "PC", "laptop")
    inv.hosts[sw.mac] = sw
    inv.hosts[pc.mac] = pc
    inv.links = [Link(mac_a=sw.mac, port_a=3, mac_b=pc.mac, port_b=1)]
    rows = build_wiring_csv(inv).splitlines()
    # En-tête + 1 ligne pour le switch (le PC n'est pas un type d'infra).
    assert len(rows) == 2
    assert rows[1] == "SW,aa:00:00:00:00:01,RDC,Salon,3,,PC,laptop,1,,false"


def test_csv_poe_column_true_when_link_is_poe():
    inv = Inventory()
    sw = _h("aa:00:00:00:00:01", "SW", "switch")
    pp = _h("aa:00:00:00:00:02", "PP", "patchpanel")
    inv.hosts[sw.mac] = sw
    inv.hosts[pp.mac] = pp
    inv.links = [Link(mac_a=sw.mac, port_a=1, mac_b=pp.mac, port_b=24,
                      poe=True)]
    rows = build_wiring_csv(inv).splitlines()
    assert all(r.endswith(",true") for r in rows[1:])


def test_csv_includes_port_labels():
    inv = Inventory()
    pp = _h("aa:00:00:00:00:01", "PP", "patchpanel", port_labels={24: "A12"})
    out = _h("aa:00:00:00:00:02", "Outlet", "outlet", port_labels={1: "21"})
    inv.hosts[pp.mac] = pp
    inv.hosts[out.mac] = out
    inv.links = [Link(mac_a=pp.mac, port_a=24, mac_b=out.mac, port_b=1)]
    csv_text = build_wiring_csv(inv)
    # Le label local du PP (A12) et celui de l'outlet vu comme pair (21).
    assert "A12" in csv_text
    assert "21" in csv_text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_wiring_report.py -q -k csv`
Expected: FAIL — `ImportError: cannot import name 'build_wiring_csv'`.

- [ ] **Step 3: Implement `build_wiring_csv`**

In `intramap/wiring_report.py`, add `import csv` and `import io` to the imports, and append this function (it reuses the module's existing `_device_name`, `_peer_info`, `_port_sort_key`, `INFRA_TYPES_ORDER`, `links_touching`, `_resolve_device_type`):

```python
import csv
import io

_CSV_HEADER = [
    "device", "mac", "floor", "room", "local_port", "local_label",
    "peer", "peer_type", "peer_port", "peer_label", "poe",
]


def build_wiring_csv(inv: Inventory) -> str:
    """Export CSV des branchements d'infrastructure : une ligne par couple
    (appareil d'infra, câble qui le touche). En-tête toujours émis."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(_CSV_HEADER)

    by_type: dict[str, list] = {t: [] for t in INFRA_TYPES_ORDER}
    for host in inv.hosts.values():
        t = _resolve_device_type(host)
        if t in by_type:
            by_type[t].append(host)
    for t in INFRA_TYPES_ORDER:
        by_type[t].sort(key=lambda h: _device_name(h).lower())

    for t in INFRA_TYPES_ORDER:
        for host in by_type[t]:
            def own_port(lk: Link) -> int | None:
                return lk.port_a if lk.mac_a == host.mac else lk.port_b
            links = sorted(links_touching(inv, host.mac),
                           key=lambda lk: _port_sort_key(own_port(lk)))
            for lk in links:
                p_here = own_port(lk)
                p_label_here = ""
                if (p_here is not None and host.port_labels
                        and p_here in host.port_labels):
                    p_label_here = host.port_labels[p_here]
                peer_name, peer_port, peer_type, peer_label = _peer_info(
                    inv, lk, host.mac)
                writer.writerow([
                    _device_name(host), host.mac,
                    host.location.floor or "", host.location.room or "",
                    "" if p_here is None else p_here, p_label_here,
                    peer_name, peer_type,
                    "" if peer_port is None else peer_port, peer_label,
                    "true" if lk.poe else "false",
                ])
    return buf.getvalue()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_wiring_report.py -q`
Expected: PASS (existing + new CSV tests).

- [ ] **Step 5: Commit**

```bash
git add intramap/wiring_report.py tests/test_wiring_report.py
git commit -m "feat: CSV export for the infrastructure wiring report"
```

---

### Task 3: `report` CLI subcommand

**Files:**
- Modify: `intramap/cli.py` (imports, `_cmd_report`, `report` subparser)
- Test: `tests/test_cli.py` (append report tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py` (reuses the existing `_seed_inventory`, `main`, `capsys`):

```python
def _seed_wired(path: Path) -> None:
    from intramap.inventory import save
    now = datetime(2026, 5, 24, 14, 0, 0)
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": Host(
            mac="aa:bb:cc:dd:ee:01", ip="192.168.1.1", hostname=None,
            vendor=None, custom_name="Box", device_type="router",
            is_gateway=True, location=Location(floor="RDC", room="Salon"),
            first_seen=now, last_seen=now),
        "aa:bb:cc:dd:ee:02": Host(
            mac="aa:bb:cc:dd:ee:02", ip="192.168.1.2", hostname=None,
            vendor=None, custom_name="SW", device_type="switch",
            location=Location(floor="RDC", room="Salon"),
            first_seen=now, last_seen=now),
    }, links=[Link(mac_a="aa:bb:cc:dd:ee:02", port_a=1,
                   mac_b="aa:bb:cc:dd:ee:01", port_b=8)], last_scan=now)
    save(inv, path)


def test_report_wiring_text_to_stdout(tmp_path, capsys):
    inv_path = tmp_path / "inv.yaml"
    _seed_wired(inv_path)
    rc = main(["--inventory", str(inv_path), "report", "wiring"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Branchements des appareils d'infrastructure" in out


def test_report_paths_text_to_stdout(tmp_path, capsys):
    inv_path = tmp_path / "inv.yaml"
    _seed_wired(inv_path)
    rc = main(["--inventory", str(inv_path), "report", "paths"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Accès Internet" in out


def test_report_all_contains_both(tmp_path, capsys):
    inv_path = tmp_path / "inv.yaml"
    _seed_wired(inv_path)
    rc = main(["--inventory", str(inv_path), "report", "all"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Branchements des appareils" in out
    assert "Accès Internet" in out


def test_report_wiring_csv_header(tmp_path, capsys):
    inv_path = tmp_path / "inv.yaml"
    _seed_wired(inv_path)
    rc = main(["--inventory", str(inv_path), "report", "wiring",
               "--format", "csv"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.splitlines()[0] == (
        "device,mac,floor,room,local_port,local_label,"
        "peer,peer_type,peer_port,peer_label,poe")


def test_report_csv_rejected_for_paths(tmp_path, capsys):
    inv_path = tmp_path / "inv.yaml"
    _seed_wired(inv_path)
    rc = main(["--inventory", str(inv_path), "report", "paths",
               "--format", "csv"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "csv" in (captured.out + captured.err).lower()


def test_report_output_writes_file(tmp_path, capsys):
    inv_path = tmp_path / "inv.yaml"
    _seed_wired(inv_path)
    out_file = tmp_path / "wiring.csv"
    rc = main(["--inventory", str(inv_path), "report", "wiring",
               "--format", "csv", "--output", str(out_file)])
    out = capsys.readouterr().out
    assert rc == 0
    assert out_file.is_file()
    assert "device,mac,floor" in out_file.read_text(encoding="utf-8")
    assert "Wrote" in out


def test_report_missing_inventory_errors(tmp_path, capsys):
    rc = main(["--inventory", str(tmp_path / "absent.yaml"), "report",
               "wiring"])
    captured = capsys.readouterr()
    assert rc != 0
    assert "inventory" in (captured.out + captured.err).lower()
```

Add `Link` to the existing `from intramap.models import ...` line at the top of `tests/test_cli.py` (currently `DiscoveredHost, Host, Inventory, Location`).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -q -k report`
Expected: FAIL — argparse errors ("invalid choice: 'report'") / `_cmd_report` missing.

- [ ] **Step 3: Implement the command**

In `intramap/cli.py`, add near the other report imports at the top:

```python
from intramap.wiring_report import build_wiring_report, build_wiring_csv
from intramap.path_report import build_report as build_path_report
```

Add the command function (next to `_cmd_list` / `_cmd_render`):

```python
def _cmd_report(args: argparse.Namespace) -> int:
    if args.format == "csv" and args.type != "wiring":
        print("--format csv is only supported for the 'wiring' report.",
              file=sys.stderr)
        return 2

    inv, err = _load_or_report(Path(args.inventory))
    if err:
        return err

    if args.format == "csv":
        text = build_wiring_csv(inv)
    elif args.type == "wiring":
        text = build_wiring_report(inv)
    elif args.type == "paths":
        text = build_path_report(inv)
    else:  # all
        text = (build_wiring_report(inv)
                + "\n" + "=" * 60 + "\n\n"
                + build_path_report(inv))

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"Wrote {out_path}")
    else:
        sys.stdout.write(text)
    return 0
```

Register the subparser in `build_parser`, after the `scan` subparser block:

```python
    p_report = subs.add_parser("report",
                               help="Print wiring / network-path reports")
    p_report.add_argument("type", choices=["wiring", "paths", "all"],
                          help="which report to print")
    p_report.add_argument("--format", choices=["text", "csv"], default="text",
                          help="output format; csv is only valid for 'wiring'")
    p_report.add_argument("--output", default=None,
                          help="write to this file instead of stdout")
    p_report.set_defaults(func=_cmd_report)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -q`
Expected: PASS (existing + new report tests).

- [ ] **Step 5: Full suite + Qt-free CLI check**

Run: `python -m pytest -q`
Expected: all pass.
Run: `python -c "import sys, intramap.cli; assert 'PySide6' not in sys.modules; print('cli Qt-free OK')"`
Expected: `cli Qt-free OK`.

- [ ] **Step 6: Commit**

```bash
git add intramap/cli.py tests/test_cli.py
git commit -m "feat: add 'intramap report' command (wiring/paths/all, text + CSV)"
```

---

### Task 4: Push

- [ ] **Step 1: Push to main**

```bash
git push origin main
```

- [ ] **Step 2: (Optional) confirm CI green**

Run: `gh run list --workflow=ci.yml --limit 1`
Expected: a new run for the latest commit; wait for green.

---

## Self-Review

**Spec coverage:**
- Qt-free path-report module + dialog re-import → Task 1. ✓
- `build_wiring_csv` (header, rows, poe, labels, empty) → Task 2. ✓
- `report` command (wiring/paths/all, text/csv, --output, csv-only-wiring guard, missing inventory) → Task 3. ✓
- CLI stays Qt-free → Task 1 Step 6 + Task 3 Step 5. ✓

**Placeholder scan:** No TBD/TODO; full code for the module, the CSV builder, the command, the subparser, and every test is shown. ✓

**Type/name consistency:** `build_report` (path_report) vs `build_path_report` (alias in cli to avoid clashing with the wiring builder); `build_wiring_report` / `build_wiring_csv` names match between Task 2 and Task 3; CSV header string is identical in Task 2 tests, Task 3 test, and the `_CSV_HEADER` list. `_device_name` uses `custom_name or hostname or mac` consistently in path_report (matches the original dialog). ✓

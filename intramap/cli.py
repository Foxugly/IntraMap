import argparse
import ipaddress
import shutil
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import psutil

from intramap import inventory as inventory_mod
from intramap import scanner
from intramap.models import Inventory, _resolve_device_type
from intramap.scan_diff import diff_inventories, format_scan_diff
from intramap.renderers import plantuml as plantuml_renderer
from intramap.renderers import graphviz as graphviz_renderer
from intramap.renderers import mermaid as mermaid_renderer
from intramap.renderers import html as html_renderer
from intramap.wiring_report import build_wiring_report, build_wiring_csv
from intramap.path_report import build_report as build_path_report
from intramap.diagnostics import diagnose


def _load_or_report(inv_path: Path):
    """Return the Inventory, or (None, exit_code) on a user-visible failure."""
    if not inv_path.exists():
        print(f"Inventory file not found: {inv_path}", file=sys.stderr)
        print("Run `intramap scan` first to create one.", file=sys.stderr)
        return None, 2
    try:
        return inventory_mod.load(inv_path), 0
    except Exception as e:
        print(f"Failed to load inventory {inv_path}:\n{e}", file=sys.stderr)
        return None, 4


def _cmd_list(args: argparse.Namespace) -> int:
    inv, err = _load_or_report(Path(args.inventory))
    if err:
        return err

    rows = []
    for mac in sorted(inv.hosts.keys()):
        h = inv.hosts[mac]
        if args.offline and h.online:
            continue
        if args.unnamed and h.custom_name is not None:
            continue
        if args.vendor and (
            h.vendor is None or args.vendor.lower() not in h.vendor.lower()
        ):
            continue
        if args.type_filter is not None:
            if _resolve_device_type(h).lower() != args.type_filter.lower():
                continue
        loc = h.location
        loc_str = "/".join(
            x for x in (loc.floor, loc.room, loc.rack) if x
        ) or "-"
        rows.append((
            mac,
            h.ip or "-",
            h.custom_name or "-",
            _resolve_device_type(h),
            h.vendor or "-",
            h.hostname or "-",
            loc_str,
            "online" if h.online else "OFFLINE",
        ))

    headers = ("MAC", "IP", "Name", "Type", "Vendor", "Hostname", "Location", "Status")
    widths = [max(len(str(r[i])) for r in (rows + [headers])) for i in range(len(headers))]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * w for w in widths)))
    for row in rows:
        print(fmt.format(*row))
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    inv, err = _load_or_report(Path(args.inventory))
    if err:
        return err

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    targets = {
        "plantuml": (out_dir / "network.puml",
                     lambda: plantuml_renderer.render(inv)),
        "graphviz": (out_dir / "network.dot",
                     lambda: graphviz_renderer.render(inv,
                                                      copy_assets_to=out_dir)),
        "mermaid": (out_dir / "network.mmd",
                    lambda: mermaid_renderer.render(inv)),
        "html": (out_dir / "network.html",
                 lambda: html_renderer.render(inv)),
    }
    chosen = list(targets.keys()) if args.format == "all" else [args.format]

    for name in chosen:
        path, render_fn = targets[name]
        path.write_text(render_fn(), encoding="utf-8")
        print(f"Wrote {path}")

    if args.image and "graphviz" in chosen:
        _render_graphviz_image(out_dir)
    return 0


def _render_graphviz_image(out_dir: Path) -> None:
    """Invoke `dot` to produce network.svg and network.png next to network.dot.

    Runs with CWD set to `out_dir` so the relative `image="icons/<type>.png"`
    paths in the .dot file resolve. If `dot` is not in PATH, prints a clear
    warning to stderr and returns (text files were already written).
    """
    dot_exe = shutil.which("dot")
    if dot_exe is None:
        print(
            "Warning: 'dot' (Graphviz) not found in PATH. Skipping image "
            "rendering. Install from https://graphviz.org/download/ or run "
            f"`dot` manually from {out_dir}.",
            file=sys.stderr,
        )
        return

    for fmt in ("svg", "png"):
        result = subprocess.run(
            [dot_exe, f"-T{fmt}", "network.dot", "-o", f"network.{fmt}"],
            cwd=str(out_dir),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"Wrote {out_dir / f'network.{fmt}'}")
        else:
            print(
                f"dot failed for {fmt}: {result.stderr.strip()}",
                file=sys.stderr,
            )


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


_DIAG_LABELS = {"error": "ERREUR", "warning": "ATTENTION", "info": "INFO"}


def _cmd_diagnose(args: argparse.Namespace) -> int:
    inv, err = _load_or_report(Path(args.inventory))
    if err:
        return err

    findings = diagnose(inv)
    if not findings:
        print("Aucune anomalie détectée.")
        return 0

    for f in findings:
        print(f"[{_DIAG_LABELS.get(f.severity, f.severity)}] {f.message}")
    print(f"\n{len(findings)} anomalie(s) détectée(s).")
    return 1 if args.strict else 0


def _detect_subnets() -> list[str]:
    """Return candidate IPv4 subnets from active local interfaces.

    Excludes loopback and link-local (169.254.x.x). Each subnet is returned
    in CIDR form (e.g., '192.168.1.0/24').
    """
    candidates: list[str] = []
    for _ifname, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if getattr(addr, "family", None) != socket.AF_INET:
                continue
            ip = addr.address
            netmask = addr.netmask
            if not ip or not netmask:
                continue
            try:
                iface = ipaddress.ip_interface(f"{ip}/{netmask}")
            except ValueError:
                continue
            if iface.ip.is_loopback or iface.ip.is_link_local:
                continue
            candidates.append(str(iface.network))
    return sorted(set(candidates))


def _cmd_scan(args: argparse.Namespace) -> int:
    network = args.network
    if not network:
        subnets = _detect_subnets()
        if len(subnets) == 0:
            print("No local IPv4 subnet detected. Pass --network explicitly.",
                  file=sys.stderr)
            return 2
        if len(subnets) > 1:
            print("Multiple local subnets detected:", file=sys.stderr)
            for s in subnets:
                print(f"  - {s}", file=sys.stderr)
            print("Pass --network <CIDR> explicitly.", file=sys.stderr)
            return 2
        network = subnets[0]
        print(f"Auto-detected subnet: {network}")

    try:
        discovered = scanner.scan(network)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 3

    inv_path = Path(args.inventory)
    try:
        inv = inventory_mod.load(inv_path)
    except Exception as e:
        print(f"Failed to load existing inventory {inv_path}:\n{e}",
              file=sys.stderr)
        print("Fix the file (or remove it to start fresh) and re-run.",
              file=sys.stderr)
        return 4
    now = datetime.now()
    previous_macs = set(inv.hosts.keys())
    before = Inventory.from_dict(inv.to_dict())  # copie pour le diff
    inventory_mod.merge(inv, discovered, now=now)
    inventory_mod.save(inv, inv_path)

    new = [d.mac for d in discovered if d.mac not in previous_macs]
    offline = [m for m, h in inv.hosts.items() if not h.online]
    unnamed = [m for m, h in inv.hosts.items() if h.custom_name is None]
    print(
        f"Scan complete: {len(discovered)} discovered "
        f"({len(new)} new), {len(offline)} offline, "
        f"{len(unnamed)} without custom_name."
    )
    print(f"Inventory: {inv_path}")
    diff = diff_inventories(before, inv)
    if diff.has_changes:
        print()
        print(format_scan_diff(diff, inv), end="")
    if len(discovered) == 0:
        print(
            "Warning: scan returned zero hosts. On macOS/Linux, MAC discovery "
            "(ARP) requires `sudo`. On Windows, run the shell as administrator.",
            file=sys.stderr,
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="intramap")
    parser.add_argument(
        "--inventory", default="inventory.yaml",
        help="Path to the inventory YAML file (default: inventory.yaml)",
    )
    subs = parser.add_subparsers(dest="command", required=True)

    p_list = subs.add_parser("list", help="List inventory contents")
    p_list.add_argument("--offline", action="store_true",
                        help="Only show hosts currently offline")
    p_list.add_argument("--unnamed", action="store_true",
                        help="Only show hosts with no custom_name")
    p_list.add_argument("--vendor", default=None,
                        help="Only show hosts whose vendor contains the given "
                             "substring (case-insensitive). Hosts without a "
                             "vendor are excluded.")
    p_list.add_argument("--type", default=None, dest="type_filter",
                        help="filter by exact device_type (case-insensitive); "
                             "compares against resolved device_type")
    p_list.set_defaults(func=_cmd_list)

    p_render = subs.add_parser("render", help="Render diagrams from inventory")
    p_render.add_argument(
        "--format",
        choices=["plantuml", "graphviz", "mermaid", "html", "all"],
        default="all")
    p_render.add_argument("--output-dir", default="output")
    p_render.add_argument(
        "--image", action="store_true",
        help="After writing text files, also invoke `dot` to produce "
             "network.svg and network.png (requires Graphviz in PATH). "
             "Runs dot with CWD set to the output dir so icons resolve.",
    )
    p_render.set_defaults(func=_cmd_render)

    p_scan = subs.add_parser("scan", help="Scan the network and merge results")
    p_scan.add_argument("--network",
                        help="CIDR subnet to scan (auto-detected if omitted)")
    p_scan.set_defaults(func=_cmd_scan)

    p_report = subs.add_parser("report",
                               help="Print wiring / network-path reports")
    p_report.add_argument("type", choices=["wiring", "paths", "all"],
                          help="which report to print")
    p_report.add_argument("--format", choices=["text", "csv"], default="text",
                          help="output format; csv is only valid for 'wiring'")
    p_report.add_argument("--output", default=None,
                          help="write to this file instead of stdout")
    p_report.set_defaults(func=_cmd_report)

    p_diag = subs.add_parser(
        "diagnose", help="Check the inventory for cabling anomalies")
    p_diag.add_argument("--strict", action="store_true",
                        help="exit with code 1 if any anomaly is found")
    p_diag.set_defaults(func=_cmd_diagnose)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

import argparse
import sys
from pathlib import Path

from intramap import inventory as inventory_mod


def _cmd_list(args: argparse.Namespace) -> int:
    inv_path = Path(args.inventory)
    if not inv_path.exists():
        print(f"Inventory file not found: {inv_path}", file=sys.stderr)
        print("Run `intramap scan` first to create one.", file=sys.stderr)
        return 2

    inv = inventory_mod.load(inv_path)
    rows = []
    for mac in sorted(inv.hosts.keys()):
        h = inv.hosts[mac]
        if args.offline and h.online:
            continue
        if args.unnamed and h.custom_name is not None:
            continue
        loc = h.location
        loc_str = "/".join(
            x for x in (loc.floor, loc.room, loc.rack) if x
        ) or "-"
        rows.append((
            mac,
            h.ip or "-",
            h.custom_name or "-",
            h.hostname or "-",
            loc_str,
            "online" if h.online else "OFFLINE",
        ))

    headers = ("MAC", "IP", "Name", "Hostname", "Location", "Status")
    widths = [max(len(str(r[i])) for r in (rows + [headers])) for i in range(6)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * w for w in widths)))
    for row in rows:
        print(fmt.format(*row))
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
    p_list.set_defaults(func=_cmd_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

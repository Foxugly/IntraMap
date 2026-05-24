import nmap

from intramap.models import DiscoveredHost


def scan(network: str) -> list[DiscoveredHost]:
    """Scan a CIDR network with nmap host-discovery and return discovered hosts.

    Skips entries that have no MAC address (typically the local machine itself,
    where nmap cannot ARP-resolve its own interface, and IPv6-only entries).
    """
    try:
        scanner = nmap.PortScanner()
    except nmap.PortScannerError as e:
        raise RuntimeError(
            "nmap binary not found in PATH. Install it from "
            "https://nmap.org/download.html"
        ) from e

    scanner.scan(hosts=network, arguments="-sn")

    discovered: list[DiscoveredHost] = []
    for ip in scanner.all_hosts():
        info = scanner[ip]
        addresses = info.get("addresses", {})
        mac = addresses.get("mac")
        if not mac:
            continue  # no MAC means we can't identify it stably

        ipv4 = addresses.get("ipv4", ip)
        hostnames = info.get("hostnames") or []
        hostname = None
        if hostnames:
            raw = (hostnames[0].get("name") or "").strip()
            hostname = raw or None

        vendor_map = info.get("vendor") or {}
        vendor = vendor_map.get(mac) or None

        discovered.append(DiscoveredHost(
            mac=mac, ip=ipv4, hostname=hostname, vendor=vendor,
        ))

    return discovered

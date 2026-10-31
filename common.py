"""Ortak yardımcılar (EXE / kaynak)."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def local_ipv4s() -> list[str]:
    ips = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip not in ips:
            ips.insert(0, ip)
    except Exception:
        pass
    return ips or ["127.0.0.1"]


def default_gateway_guess(ip: str) -> str | None:
    parts = ip.split(".")
    if len(parts) != 4:
        return None
    # VMware NAT host genelde .1
    return ".".join(parts[:3] + ["1"])


def open_firewall_tcp(port: int, name: str = "VM Drop"):
    try:
        subprocess.run(
            [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={name}", "dir=in", "action=allow",
                "protocol=TCP", f"localport={port}",
            ],
            capture_output=True, text=True, timeout=8,
        )
    except Exception:
        pass


def probe_agent(ip: str, port: int, timeout: float = 0.6) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://{ip}:{port}/ping", timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def vmware_arp_ips() -> list[str]:
    """ARP tablosundan VMware (00-0c-29 / 00-50-56) adreslerini topla."""
    ips = []
    try:
        out = subprocess.check_output(["arp", "-a"], text=True, errors="ignore")
    except Exception:
        return ips
    for line in out.splitlines():
        low = line.lower()
        if "00-0c-29" in low or "00-50-56" in low:
            parts = line.split()
            if parts and parts[0].count(".") == 3:
                ip = parts[0].strip()
                if ip not in ips:
                    ips.append(ip)
    return ips

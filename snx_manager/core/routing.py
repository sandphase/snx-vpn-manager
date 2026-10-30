#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snx_manager.core.routing
Kernel routing management, Policy-Based Routing (PBR), prevention of
collisions with Docker bridges, and deterministic cleanup of interfaces and XFRM states.
"""

import subprocess
import ipaddress
import re
from typing import List, Tuple, Optional


def run_cmd(args: List[str], check: bool = False, capture: bool = True) -> subprocess.CompletedProcess:
    """Executes a system command without shell to prevent command injection."""
    try:
        return subprocess.run(args, capture_output=capture, text=True, check=check)
    except Exception as e:
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr=str(e))


def run_root_cmd(args: List[str]) -> subprocess.CompletedProcess:
    """Executes command with elevated privileges using passwordless sudo or pkexec."""
    sudo_check = subprocess.run(["sudo", "-n", "true"], capture_output=True)
    if sudo_check.returncode == 0:
        return run_cmd(["sudo"] + args)
    return run_cmd(["pkexec"] + args)


class RouteManager:
    """Transactional kernel routing manager."""

    def __init__(self, interface: str = "snx-vpn", routing_table: Optional[int] = 18000):
        self.interface = interface
        self.routing_table = routing_table
        self.applied_routes: List[str] = []

    def inject_host_route_32(self, ip_str: str) -> bool:
        """
        Injects a specific /32 host route to prevent traffic hijacking
        by local Docker bridge networks (RFC 1918 172.16.0.0/12).
        """
        clean_ip = ip_str.strip().split("/")[0]
        try:
            ipaddress.ip_address(clean_ip)
        except ValueError:
            return False

        # Inject into main table for highest host-route precedence
        res = run_root_cmd(["ip", "route", "replace", f"{clean_ip}/32", "dev", self.interface])
        if res.returncode == 0:
            self.applied_routes.append(f"{clean_ip}/32")
            return True
        return False

    def remove_host_route_32(self, ip_str: str) -> bool:
        """Removes a /32 host route."""
        clean_ip = ip_str.strip().split("/")[0]
        res = run_root_cmd(["ip", "route", "del", f"{clean_ip}/32", "dev", self.interface])
        return res.returncode == 0

    def setup_pbr_table(self, target_subnets: List[str]) -> bool:
        """
        Configures Policy-Based Routing (PBR) in a dedicated table
        to guarantee strict isolation between VPN traffic and host local network.
        """
        if not self.routing_table:
            return False

        for subnet in target_subnets:
            subnet = subnet.strip()
            if not subnet:
                continue
            # Add routing rule toward dedicated table
            run_root_cmd(["ip", "rule", "add", "to", subnet, "table", str(self.routing_table), "priority", "1000"])
            # Add route in dedicated table
            run_root_cmd(["ip", "route", "replace", subnet, "dev", self.interface, "table", str(self.routing_table)])

        return True

    def cleanup_all(self, extra_ips: Optional[List[str]] = None):
        """
        Comprehensive and safe cleanup of network state:
        1. Removes registered /32 host routes.
        2. Flushes PBR rules from dedicated table.
        3. Flushes lingering IPsec XFRM states/policies to prevent network locks.
        4. Deletes virtual network interface if left open.
        """
        all_targets = list(self.applied_routes)
        if extra_ips:
            all_targets.extend(extra_ips)

        for ip in set(all_targets):
            self.remove_host_route_32(ip)

        # Clean PBR rules
        if self.routing_table:
            run_root_cmd(["ip", "rule", "del", "table", str(self.routing_table)])
            run_root_cmd(["ip", "route", "flush", "table", str(self.routing_table)])

        # Interface cleanup
        run_root_cmd(["ip", "link", "delete", self.interface])

        # Purge lingering IPsec states in kernel
        run_root_cmd(["ip", "xfrm", "state", "flush"])
        run_root_cmd(["ip", "xfrm", "policy", "flush"])


def detect_docker_collisions(vpn_subnets: List[str]) -> List[Tuple[str, str]]:
    """
    Detects if any VPN subnet collides with local Docker or Podman interfaces.
    Returns a list of tuples: (vpn_subnet, docker_interface_name).
    """
    collisions = []
    res = run_cmd(["ip", "-4", "-o", "addr", "show"])
    if res.returncode != 0:
        return collisions

    local_nets = []
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            iface = parts[1]
            cidr = parts[3]
            if "docker" in iface or iface.startswith("br-"):
                try:
                    local_nets.append((ipaddress.ip_network(cidr, strict=False), iface))
                except ValueError:
                    continue

    for v_sub in vpn_subnets:
        try:
            v_net = ipaddress.ip_network(v_sub.strip(), strict=False)
            for l_net, iface in local_nets:
                if v_net.overlaps(l_net):
                    collisions.append((str(v_net), iface))
        except ValueError:
            continue

    return collisions

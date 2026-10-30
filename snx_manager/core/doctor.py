#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snx_manager.core.doctor
Pre-flight diagnostics engine for auditing dependencies,
kernel modules, Docker network bridge collisions, and system permissions.
"""

import os
import shutil
import subprocess
from typing import Dict, Any, List
from snx_manager.core.routing import run_cmd, detect_docker_collisions
from snx_manager.core.dns import DnsManager


def run_diagnostics(vpn_subnets: List[str] = None) -> Dict[str, Any]:
    """Runs a complete test suite of system dependencies and returns the diagnostic report."""
    report = {
        "snx_rs_installed": False,
        "snx_rs_version": "",
        "tun_device_ready": False,
        "iproute2_available": False,
        "dns_manager": "",
        "docker_collisions": [],
        "sudo_passwordless": False,
        "warnings": [],
        "errors": []
    }

    # 1. Check snx-rs binary
    snx_path = shutil.which("snx-rs")
    if snx_path:
        report["snx_rs_installed"] = True
        v_check = run_cmd(["snx-rs", "-V"])
        if v_check.returncode == 0:
            report["snx_rs_version"] = v_check.stdout.strip()
    else:
        report["errors"].append("The 'snx-rs' client is not installed in system ($PATH).")

    # 2. Check kernel TUN device
    if os.path.exists("/dev/net/tun"):
        report["tun_device_ready"] = True
    else:
        run_cmd(["modprobe", "tun"])
        if os.path.exists("/dev/net/tun"):
            report["tun_device_ready"] = True
        else:
            report["errors"].append("Kernel device /dev/net/tun is unavailable.")

    # 3. Check networking utilities
    if shutil.which("ip"):
        report["iproute2_available"] = True
    else:
        report["errors"].append("Essential package 'iproute2' ('ip') is missing.")

    # 4. DNS manager
    dns_mgr = DnsManager()
    report["dns_manager"] = dns_mgr.backend

    # 5. Docker collisions
    if vpn_subnets:
        collisions = detect_docker_collisions(vpn_subnets)
        if collisions:
            for v_sub, iface in collisions:
                report["docker_collisions"].append({"vpn_subnet": v_sub, "docker_interface": iface})
                report["warnings"].append(
                    f"Collision detected: VPN subnet {v_sub} overlaps with local Docker interface '{iface}'."
                )

    # 6. Elevation permissions
    sudo_res = subprocess.run(["sudo", "-n", "true"], capture_output=True)
    report["sudo_passwordless"] = (sudo_res.returncode == 0)
    if not report["sudo_passwordless"]:
        if not shutil.which("pkexec"):
            report["warnings"].append("Neither 'sudo -n' nor 'pkexec' available. Interactive authentication required.")

    return report


def format_doctor_report(report: Dict[str, Any]) -> str:
    """Generates a human-friendly formatted view for the terminal."""
    lines = [
        "============================================================",
        "          🩺 SYSTEM DIAGNOSTICS (snx-manager doctor)        ",
        "============================================================"
    ]

    # snx-rs
    if report["snx_rs_installed"]:
        lines.append(f"  [OK] snx-rs client: Present ({report['snx_rs_version']})")
    else:
        lines.append("  [FAIL] snx-rs client: NOT installed")

    # Kernel TUN
    if report["tun_device_ready"]:
        lines.append("  [OK] Kernel Device: /dev/net/tun available")
    else:
        lines.append("  [FAIL] Kernel Device: /dev/net/tun NOT available")

    # iproute2
    if report["iproute2_available"]:
        lines.append("  [OK] Network Tools: iproute2 present")
    else:
        lines.append("  [FAIL] Network Tools: iproute2 missing")

    # DNS
    lines.append(f"  [INFO] Active DNS Subsystem: {report['dns_manager']}")

    # Elevation
    if report["sudo_passwordless"]:
        lines.append("  [OK] Root Privileges: sudo NOPASSWD configured (Transparent operation)")
    else:
        lines.append("  [INFO] Root Privileges: Interactive elevation via PolicyKit (pkexec) or sudo")

    # Docker collisions
    if report["docker_collisions"]:
        lines.append("\n  [!] WARNING: Docker subnet routing collisions detected:")
        for c in report["docker_collisions"]:
            lines.append(f"      • Subnet {c['vpn_subnet']} competes with local bridge '{c['docker_interface']}'")
        lines.append("      (Manager will inject /32 host routes automatically to mitigate this).")

    lines.append("============================================================")

    if report["errors"]:
        lines.append(f"OVERALL STATUS: ❌ {len(report['errors'])} critical error(s) detected.")
    else:
        lines.append("OVERALL STATUS: ✅ System is ready to operate.")

    return "\n".join(lines)

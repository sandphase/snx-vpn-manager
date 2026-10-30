#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snx_manager.core.backend
VPN tunnel execution engine for snx-rs.
Manages process lifecycle, asynchronous interface polling, integration
with RouteManager and DnsManager, and safe disconnection with state purging.
"""

import os
import sys
import base64
import time
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List

from snx_manager.core.config import load_config, save_config, get_connection_by_id, get_effective_dns
from snx_manager.core.routing import RouteManager, run_cmd, run_root_cmd
from snx_manager.core.dns import DnsManager
from snx_manager.core.secrets import SecretManager

SNX_CONF_PATH = Path("/etc/snx-rs/snx-rs.conf")
SNX_LOG_PATH = Path("/var/log/snx-rs.log")


class VpnBackend:
    """Low-level controller for Check Point tunnels via snx-rs."""

    def __init__(self, interface: str = "snx-vpn"):
        self.interface = interface
        self.route_mgr = RouteManager(interface=interface)
        self.dns_mgr = DnsManager(interface=interface)
        self.secret_mgr = SecretManager()

    def get_status(self) -> Dict[str, Any]:
        """Queries real-time tunnel status."""
        status = {
            "connected": False,
            "interface": self.interface,
            "ip": None,
            "gateway": "",
            "active_id": "",
            "active_name": "",
            "dns_servers": []
        }

        # 1. Check if network interface exists
        res = run_cmd(["ip", "-4", "-br", "addr", "show", "dev", self.interface])
        if res.returncode == 0 and res.stdout.strip():
            parts = res.stdout.split()
            if len(parts) >= 3:
                status["connected"] = True
                status["ip"] = parts[2].split("/")[0]

        # 2. Read active configuration from /etc/snx-rs/snx-rs.conf
        cfg = load_config()
        if SNX_CONF_PATH.exists():
            try:
                with open(SNX_CONF_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("server-name="):
                            status["gateway"] = line.split("=", 1)[1].strip()
                        elif line.startswith("dns-servers="):
                            raw_dns = line.split("=", 1)[1].strip()
                            status["dns_servers"] = [d.strip() for d in raw_dns.split(",") if d.strip()]
            except Exception:
                pass

        # 3. Match with saved profiles
        for conn in cfg.get("connections", []):
            if status["gateway"] and conn.get("gateway") == status["gateway"]:
                status["active_id"] = conn.get("id")
                status["active_name"] = conn.get("name")
                break

        if not status["active_name"] and status["connected"]:
            status["active_name"] = f"Gateway {status['gateway']}" if status["gateway"] else "Active Tunnel"

        return status

    def connect(self, profile_id: str, timeout_seconds: int = 20) -> Tuple[bool, str]:
        """Establishes VPN connection for specified profile."""
        cfg = load_config()
        conn = get_connection_by_id(cfg, profile_id)
        if not conn:
            return False, f"Profile with ID '{profile_id}' not found."

        shared = cfg.get("shared", {})
        gateway = conn.get("gateway", "").strip()
        if not gateway:
            return False, "Profile does not specify a valid Gateway address."

        # Resolve username and password
        user = shared.get("user_name", "")
        pwd = self.secret_mgr.get_password(user, profile_id) or shared.get("password", "")

        # Base64 encoding for snx-rs configuration file
        try:
            b64_pass = base64.b64encode(pwd.encode()).decode()
        except Exception:
            b64_pass = pwd

        effective_dns = get_effective_dns(cfg, conn)
        dns_list = [d.strip() for d in effective_dns.split(",") if d.strip()]
        search_domains = [d.strip() for d in shared.get("search_domains", "").split(",") if d.strip()]
        tunnel_type = shared.get("tunnel_type", "ssl")
        login_type = shared.get("login_type", "vpn")
        ignore_cert = "true" if shared.get("ignore_server_cert", True) else "false"

        # 1. Build configuration file content
        conf_content = (
            f"server-name={gateway}\n"
            f"login-type={login_type}\n"
            f"tunnel-type={tunnel_type}\n"
            f"user-name={user}\n"
            f"password={b64_pass}\n"
            f"log-level=info\n"
            f"ignore-server-cert={ignore_cert}\n"
            f"dns-servers={effective_dns}\n"
        )

        # 2. Disconnect previous tunnel if present
        self.disconnect(notify=False)

        # 3. Securely save configuration to /etc/snx-rs/snx-rs.conf
        tmp_conf = "/tmp/snx-rs.conf.tmp"
        try:
            with open(tmp_conf, "w") as f:
                f.write(conf_content)
            run_root_cmd(["mkdir", "-p", "/etc/snx-rs"])
            run_root_cmd(["cp", "-f", tmp_conf, str(SNX_CONF_PATH)])
            run_root_cmd(["chmod", "600", str(SNX_CONF_PATH)])
            os.remove(tmp_conf)
        except Exception as e:
            return False, f"Error writing {SNX_CONF_PATH}: {e}"

        # 4. Start snx-rs via systemd-run
        snx_bin = shutil.which("snx-rs") or "/usr/bin/snx-rs"
        start_cmd = [
            "systemd-run",
            "--unit=snx-rs-vpn",
            "--description=SNX-RS Check Point Tunnel",
            f"--property=StandardOutput=append:{SNX_LOG_PATH}",
            f"--property=StandardError=append:{SNX_LOG_PATH}",
            snx_bin,
            "-m", "standalone",
            "-c", str(SNX_CONF_PATH),
            "-e", tunnel_type,
            "-f", self.interface,
            "-l", "info"
        ]
        res = run_root_cmd(start_cmd)
        if res.returncode != 0:
            return False, f"Could not start systemd unit for snx-rs: {res.stderr}"

        # 5. Wait for network interface to appear in kernel
        interface_ready = False
        for _ in range(timeout_seconds):
            check = run_cmd(["ip", "link", "show", "dev", self.interface])
            if check.returncode == 0:
                interface_ready = True
                break
            time.sleep(1)

        if not interface_ready:
            self.disconnect(notify=False)
            return False, "Connection timeout: Tunnel interface did not come up (verify credentials or logs)."

        # 6. Inject /32 host routes for DNS (prevents Docker subnet hijacking)
        for dns in dns_list:
            self.route_mgr.inject_host_route_32(dns)

        # 7. Inject custom corporate routes if specified
        custom_routes = conn.get("custom_routes", [])
        if custom_routes:
            self.route_mgr.setup_pbr_table(custom_routes)

        # 8. Apply DNS through active manager (Selective Split-DNS)
        self.dns_mgr.apply_dns(dns_list, search_domains=search_domains, split_dns=True)

        # 9. Update active profile in configuration
        cfg["active_id"] = profile_id
        save_config(cfg)

        # Desktop notification
        self._send_notification(
            "VPN Connected ✅",
            f"Profile: {conn.get('name')}\nGateway: {gateway}",
            icon="network-vpn"
        )

        return True, f"Successfully connected to {conn.get('name')}."

    def disconnect(self, notify: bool = True) -> bool:
        """Stops the tunnel and performs comprehensive network cleanup."""
        # 1. Stop systemd units
        run_root_cmd(["systemctl", "stop", "snx-rs-vpn", "snx-rs"])
        run_root_cmd(["systemctl", "reset-failed", "snx-rs-vpn"])

        # 2. Terminate lingering processes
        run_root_cmd(["pkill", "-15", "-x", "snx-rs"])
        time.sleep(0.5)
        run_root_cmd(["pkill", "-9", "-x", "snx-rs"])

        # 3. Revert DNS
        self.dns_mgr.revert_dns()

        # 4. Clean routes, PBR rules, interfaces, and kernel XFRM states
        self.route_mgr.cleanup_all()

        # 5. Clean sockets and temp files
        run_root_cmd(["rm", "-f", "/var/tmp/*snx*", "/var/run/snx*", "/run/snx*"])

        if notify:
            self._send_notification("VPN Disconnected 🔌", "Secure tunnel closed cleanly.", icon="network-vpn-disconnected")

        return True

    def _send_notification(self, title: str, message: str, icon: str = "network-vpn"):
        """Sends desktop notification safely if notify-send is present."""
        if shutil.which("notify-send"):
            try:
                subprocess.run(["notify-send", "-i", icon, title, message], stderr=subprocess.DEVNULL)
            except Exception:
                pass

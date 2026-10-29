#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snx_manager.core.dns
Gestor dinámico de resolución DNS con soporte para Split-DNS, prevención de fugas
y compatibilidad multiplataforma (systemd-resolved, NetworkManager y resolv.conf clásico).
"""

import os
import shutil
from pathlib import Path
from typing import List, Optional
from snx_manager.core.routing import run_cmd, run_root_cmd

RESOLV_CONF = Path("/etc/resolv.conf")
RESOLV_CONF_BACKUP = Path("/etc/resolv.conf.snx-backup")


class DnsManager:
    """Orquestador de configuración DNS adaptativo."""

    def __init__(self, interface: str = "snx-vpn"):
        self.interface = interface
        self.backend = self._detect_backend()

    def _detect_backend(self) -> str:
        """Determina qué subsistema DNS está activo en la máquina."""
        # Verificar systemd-resolved
        resolved_check = run_cmd(["systemctl", "is-active", "systemd-resolved"])
        if resolved_check.returncode == 0 or shutil.which("resolvectl"):
            return "systemd-resolved"

        # Verificar NetworkManager
        nm_check = run_cmd(["systemctl", "is-active", "NetworkManager"])
        if nm_check.returncode == 0 and shutil.which("nmcli"):
            return "network-manager"

        return "resolv-conf"

    def apply_dns(self, dns_servers: List[str], search_domains: Optional[List[str]] = None, split_dns: bool = True) -> bool:
        """
        Aplica los servidores DNS y dominios de búsqueda según el subsistema detectado.
        Si split_dns=True, asigna routing domains para que solo los dominios internos
        usen la VPN y el resto de internet no se degrade.
        """
        clean_servers = [s.strip() for s in dns_servers if s.strip()]
        if not clean_servers:
            return False

        domains = [d.strip() for d in (search_domains or []) if d.strip()]

        if self.backend == "systemd-resolved":
            # 1. Configurar servidores DNS en la interfaz del túnel
            run_root_cmd(["resolvectl", "dns", self.interface] + clean_servers)

            # 2. Configurar dominios de enrutamiento
            if split_dns and domains:
                # Prefijo '~' indica routing domain selectivo
                routing_domains = [f"~{d}" if not d.startswith("~") else d for d in domains]
                run_root_cmd(["resolvectl", "domain", self.interface] + routing_domains)
                run_root_cmd(["resolvectl", "default-route", self.interface, "false"])
            else:
                # Enrutar toda la resolución por la VPN
                run_root_cmd(["resolvectl", "domain", self.interface, "~."])
                run_root_cmd(["resolvectl", "default-route", self.interface, "true"])
            return True

        elif self.backend == "network-manager":
            servers_str = " ".join(clean_servers)
            res = run_root_cmd(["nmcli", "device", "modify", self.interface, "ipv4.dns", servers_str])
            return res.returncode == 0

        else:
            # Fallback tradicional: Respaldo y escritura en /etc/resolv.conf
            return self._apply_traditional_resolv(clean_servers, domains)

    def _apply_traditional_resolv(self, servers: List[str], domains: List[str]) -> bool:
        try:
            if not RESOLV_CONF_BACKUP.exists() and RESOLV_CONF.exists():
                shutil.copy2(RESOLV_CONF, RESOLV_CONF_BACKUP)

            lines = ["# Generado dinámicamente por SNX VPN Manager\n"]
            if domains:
                lines.append(f"search {' '.join(domains)}\n")
            for s in servers:
                lines.append(f"nameserver {s}\n")

            content = "".join(lines)
            tmp_file = "/tmp/resolv.conf.snxtmp"
            with open(tmp_file, "w") as f:
                f.write(content)

            run_root_cmd(["cp", "-f", tmp_file, str(RESOLV_CONF)])
            run_root_cmd(["chmod", "644", str(RESOLV_CONF)])
            os.remove(tmp_file)
            return True
        except Exception:
            return False

    def revert_dns(self):
        """Restaura la configuración DNS previa al estado original."""
        if self.backend == "systemd-resolved":
            run_root_cmd(["resolvectl", "revert", self.interface])
        elif self.backend == "resolv-conf":
            if RESOLV_CONF_BACKUP.exists():
                run_root_cmd(["cp", "-f", str(RESOLV_CONF_BACKUP), str(RESOLV_CONF)])
                run_root_cmd(["rm", "-f", str(RESOLV_CONF_BACKUP)])

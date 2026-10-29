#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snx_manager.core.routing
Control de enrutamiento del kernel, Policy-Based Routing (PBR), prevención de
colisiones con bridges de Docker y limpieza determinista de interfaces y estados XFRM.
"""

import subprocess
import ipaddress
import re
from typing import List, Tuple, Optional


def run_cmd(args: List[str], check: bool = False, capture: bool = True) -> subprocess.CompletedProcess:
    """Ejecuta un comando de sistema sin shell para prevenir inyecciones."""
    try:
        return subprocess.run(args, capture_output=capture, text=True, check=check)
    except Exception as e:
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr=str(e))


def run_root_cmd(args: List[str]) -> subprocess.CompletedProcess:
    """Ejecuta comando con privilegios elevados utilizando sudo si está disponible sin clave o pkexec."""
    # Verificar si sudo funciona sin pedir contraseña
    sudo_check = subprocess.run(["sudo", "-n", "true"], capture_output=True)
    if sudo_check.returncode == 0:
        return run_cmd(["sudo"] + args)
    return run_cmd(["pkexec"] + args)


class RouteManager:
    """Administrador transaccional de rutas del kernel."""

    def __init__(self, interface: str = "snx-vpn", routing_table: Optional[int] = 18000):
        self.interface = interface
        self.routing_table = routing_table
        self.applied_routes: List[str] = []

    def inject_host_route_32(self, ip_str: str) -> bool:
        """
        Inyecta una ruta de host /32 específica para evitar secuestro de tráfico
        por puentes locales de Docker (RFC 1918 172.16.0.0/12).
        """
        clean_ip = ip_str.strip().split("/")[0]
        try:
            # Validar que sea una IP válida
            ipaddress.ip_address(clean_ip)
        except ValueError:
            return False

        # Inyectar en tabla principal para máxima precedencia de host
        res = run_root_cmd(["ip", "route", "replace", f"{clean_ip}/32", "dev", self.interface])
        if res.returncode == 0:
            self.applied_routes.append(f"{clean_ip}/32")
            return True
        return False

    def remove_host_route_32(self, ip_str: str) -> bool:
        """Elimina una ruta de host /32."""
        clean_ip = ip_str.strip().split("/")[0]
        res = run_root_cmd(["ip", "route", "del", f"{clean_ip}/32", "dev", self.interface])
        return res.returncode == 0

    def setup_pbr_table(self, target_subnets: List[str]) -> bool:
        """
        Configura Policy-Based Routing (PBR) en una tabla dedicada
        para garantizar aislamiento entre la VPN y la red local del host.
        """
        if not self.routing_table:
            return False

        for subnet in target_subnets:
            subnet = subnet.strip()
            if not subnet:
                continue
            # Añadir regla de enrutamiento hacia la tabla dedicada
            run_root_cmd(["ip", "rule", "add", "to", subnet, "table", str(self.routing_table), "priority", "1000"])
            # Añadir ruta en la tabla dedicada
            run_root_cmd(["ip", "route", "replace", subnet, "dev", self.interface, "table", str(self.routing_table)])

        return True

    def cleanup_all(self, extra_ips: Optional[List[str]] = None):
        """
        Limpieza integral y segura del estado de red:
        1. Elimina rutas de host /32 registradas.
        2. Purga reglas PBR de la tabla dedicada.
        3. Purga estados y políticas huérfanas de IPsec XFRM para evitar caídas de red.
        4. Elimina la interfaz virtual si quedó colgada.
        """
        all_targets = list(self.applied_routes)
        if extra_ips:
            all_targets.extend(extra_ips)

        for ip in set(all_targets):
            self.remove_host_route_32(ip)

        # Limpiar reglas PBR si existen
        if self.routing_table:
            run_root_cmd(["ip", "rule", "del", "table", str(self.routing_table)])
            run_root_cmd(["ip", "route", "flush", "table", str(self.routing_table)])

        # Limpieza de interfaz
        run_root_cmd(["ip", "link", "delete", self.interface])

        # Purga de estados residuales de IPsec en el kernel
        run_root_cmd(["ip", "xfrm", "state", "flush"])
        run_root_cmd(["ip", "xfrm", "policy", "flush"])


def detect_docker_collisions(vpn_subnets: List[str]) -> List[Tuple[str, str]]:
    """
    Detecta si alguna subred de la VPN colisiona con interfaces locales de Docker o Podman.
    Retorna una lista de tuplas: (subred_vpn, nombre_interfaz_docker).
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

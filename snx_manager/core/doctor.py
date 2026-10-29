#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snx_manager.core.doctor
Motor de diagnóstico pre-vuelo (Pre-flight Checks) para auditoría de dependencias,
módulos del kernel, colisiones de red con Docker y permisos del sistema.
"""

import os
import shutil
import subprocess
from typing import Dict, Any, List
from snx_manager.core.routing import run_cmd, detect_docker_collisions
from snx_manager.core.dns import DnsManager


def run_diagnostics(vpn_subnets: List[str] = None) -> Dict[str, Any]:
    """Ejecuta una batería completa de pruebas del sistema y retorna el reporte."""
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

    # 1. Comprobar binario snx-rs
    snx_path = shutil.which("snx-rs")
    if snx_path:
        report["snx_rs_installed"] = True
        v_check = run_cmd(["snx-rs", "-V"])
        if v_check.returncode == 0:
            report["snx_rs_version"] = v_check.stdout.strip()
    else:
        report["errors"].append("El cliente 'snx-rs' no está instalado en el sistema ($PATH).")

    # 2. Comprobar dispositivo TUN del kernel
    if os.path.exists("/dev/net/tun"):
        report["tun_device_ready"] = True
    else:
        # Intentar cargar módulo
        run_cmd(["modprobe", "tun"])
        if os.path.exists("/dev/net/tun"):
            report["tun_device_ready"] = True
        else:
            report["errors"].append("El dispositivo del kernel /dev/net/tun no está disponible.")

    # 3. Comprobar utilidades de red
    if shutil.which("ip"):
        report["iproute2_available"] = True
    else:
        report["errors"].append("Falta el paquete esencial 'iproute2' ('ip').")

    # 4. Gestor de DNS
    dns_mgr = DnsManager()
    report["dns_manager"] = dns_mgr.backend

    # 5. Colisiones con Docker
    if vpn_subnets:
        collisions = detect_docker_collisions(vpn_subnets)
        if collisions:
            for v_sub, iface in collisions:
                report["docker_collisions"].append({"vpn_subnet": v_sub, "docker_interface": iface})
                report["warnings"].append(
                    f"Colisión detectada: Subred VPN {v_sub} solapa con la interfaz de Docker '{iface}'."
                )

    # 6. Permisos de elevación
    sudo_res = subprocess.run(["sudo", "-n", "true"], capture_output=True)
    report["sudo_passwordless"] = (sudo_res.returncode == 0)
    if not report["sudo_passwordless"]:
        if not shutil.which("pkexec"):
            report["warnings"].append("Ni 'sudo -n' ni 'pkexec' están disponibles. Se requerirá contraseña interactiva.")

    return report


def format_doctor_report(report: Dict[str, Any]) -> str:
    """Genera una vista amigable y formateada para la terminal."""
    lines = [
        "============================================================",
        "          🩺 DIAGNÓSTICO DEL SISTEMA (snx-manager doctor)    ",
        "============================================================"
    ]

    # snx-rs
    if report["snx_rs_installed"]:
        lines.append(f"  [OK] Cliente snx-rs: Presente ({report['snx_rs_version']})")
    else:
        lines.append("  [FAIL] Cliente snx-rs: NO instalado")

    # Kernel TUN
    if report["tun_device_ready"]:
        lines.append("  [OK] Dispositivo Kernel: /dev/net/tun disponible")
    else:
        lines.append("  [FAIL] Dispositivo Kernel: /dev/net/tun NO disponible")

    # iproute2
    if report["iproute2_available"]:
        lines.append("  [OK] Herramientas de Red: iproute2 presente")
    else:
        lines.append("  [FAIL] Herramientas de Red: iproute2 ausente")

    # DNS
    lines.append(f"  [INFO] Subsistema DNS activo: {report['dns_manager']}")

    # Elevación
    if report["sudo_passwordless"]:
        lines.append("  [OK] Privilegios Root: sudo NOPASSWD configurado (Operación transparente)")
    else:
        lines.append("  [INFO] Privilegios Root: Elevación interactiva mediante PolicyKit (pkexec) o sudo")

    # Colisiones Docker
    if report["docker_collisions"]:
        lines.append("\n  [!] ADVERTENCIA: Se detectaron colisiones de enrutamiento con Docker:")
        for c in report["docker_collisions"]:
            lines.append(f"      • Subred {c['vpn_subnet']} compite con el bridge local '{c['docker_interface']}'")
        lines.append("      (El gestor inyectará rutas de host /32 automáticamente para mitigar esto).")

    lines.append("============================================================")

    if report["errors"]:
        lines.append(f"ESTADO GENERAL: ❌ Se detectaron {len(report['errors'])} error(es) crítico(s).")
    else:
        lines.append("ESTADO GENERAL: ✅ El sistema está listo para operar.")

    return "\n".join(lines)

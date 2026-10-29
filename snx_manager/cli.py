#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snx_manager.cli
Interfaz de línea de comandos dual:
1. Modo Scriptable UNIX (subcomandos connect, disconnect, status, doctor, etc.)
2. Modo TUI Interactivo con colores ANSI para terminales puras / servidores SSH.
Diseñado 100% sobre la biblioteca estándar para máxima compatibilidad y ligereza.
"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import Optional

from snx_manager.core.config import load_config, save_config, export_bundle, import_bundle
from snx_manager.core.backend import VpnBackend
from snx_manager.core.doctor import run_diagnostics, format_doctor_report

# Colores ANSI
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_banner():
    banner = f"""{CYAN}{BOLD}
    ╔══════════════════════════════════════════════════════════╗
    ║             🛡️  SNX CHECK POINT VPN MANAGER             ║
    ╚══════════════════════════════════════════════════════════╝{RESET}"""
    print(banner)


def cmd_status(backend: VpnBackend, json_output: bool = False):
    st = backend.get_status()
    if json_output:
        print(json.dumps(st, indent=2))
        return

    print_banner()
    if st["connected"]:
        print(f"\n  {GREEN}● ESTADO:{RESET} {BOLD}CONECTADO{RESET}")
        print(f"  {CYAN}• Perfil Activo:{RESET}  {st['active_name']} ({st['active_id']})")
        print(f"  {CYAN}• IP Asignada:{RESET}    {st['ip']}")
        print(f"  {CYAN}• Gateway:{RESET}        {st['gateway']}")
        print(f"  {CYAN}• Interfaz:{RESET}       {st['interface']}")
        if st["dns_servers"]:
            print(f"  {CYAN}• Servidores DNS:{RESET} {', '.join(st['dns_servers'])}")
    else:
        print(f"\n  {DIM}○ ESTADO:{RESET} {YELLOW}DESCONECTADO{RESET}")
        print(f"  {DIM}• Ningún túnel VPN está activo en este momento.{RESET}")
    print()


def cmd_list(cfg: dict, json_output: bool = False):
    conns = cfg.get("connections", [])
    if json_output:
        print(json.dumps(conns, indent=2))
        return

    print_banner()
    print(f"\n{BOLD}Perfiles y Sedes Configuradas:{RESET}\n")
    if not conns:
        print(f"  {YELLOW}No hay perfiles configurados.{RESET}")
        print(f"  Usa '{CYAN}snx-manager import <archivo.json>{RESET}' o la interfaz interactiva para añadir uno.\n")
        return

    active_id = cfg.get("active_id", "")
    shared_dns = cfg.get("shared", {}).get("dns_servers", "No definidos")

    for idx, c in enumerate(conns, start=1):
        is_active = (c["id"] == active_id)
        mark = f"{GREEN}● ACTIVO{RESET}" if is_active else f"{DIM}○{RESET}"
        dns = c["custom_dns"] if c.get("use_custom_dns") else f"Compartidos ({shared_dns})"
        print(f"  [{idx}] {BOLD}{c.get('name', c['id'])}{RESET} {mark}")
        print(f"      ID:          {c['id']}")
        print(f"      Gateway:     {c.get('gateway', 'N/A')}")
        print(f"      DNS:         {dns}")
        if c.get("description"):
            print(f"      Descripción: {c['description']}")
        print()


def cmd_connect(backend: VpnBackend, profile_id: str):
    print(f"{CYAN}⏳ Conectando al perfil '{profile_id}'...{RESET}")
    ok, msg = backend.connect(profile_id)
    if ok:
        print(f"{GREEN}✅ {msg}{RESET}")
        sys.exit(0)
    else:
        print(f"{RED}❌ {msg}{RESET}", file=sys.stderr)
        sys.exit(1)


def cmd_disconnect(backend: VpnBackend):
    print(f"{YELLOW}⏳ Desconectando túnel VPN...{RESET}")
    backend.disconnect()
    print(f"{GREEN}✅ VPN desconectada correctamente.{RESET}")


def cmd_doctor(cfg: dict, json_output: bool = False):
    # Recoger subredes conocidas de los perfiles
    subnets = []
    for c in cfg.get("connections", []):
        if c.get("expected_subnet"):
            subnets.append(c["expected_subnet"])
        for r in c.get("custom_routes", []):
            subnets.append(r)

    rep = run_diagnostics(subnets)
    if json_output:
        print(json.dumps(rep, indent=2))
    else:
        print(format_doctor_report(rep))


def interactive_tui(backend: VpnBackend, cfg: dict):
    """Menú TUI para sesiones interactivas de terminal."""
    while True:
        os.system("clear" if os.name == "posix" else "cls")
        st = backend.get_status()
        print_banner()

        if st["connected"]:
            print(f"\n  {GREEN}● ESTADO:{RESET} {BOLD}CONECTADO{RESET} a {st['active_name']} ({st['ip']})")
        else:
            print(f"\n  {DIM}○ ESTADO:{RESET} {YELLOW}DESCONECTADO{RESET}")

        conns = cfg.get("connections", [])
        print(f"\n{BOLD}Sedes Disponibles:{RESET}")
        for idx, c in enumerate(conns, start=1):
            is_active = (st["connected"] and c["gateway"] == st["gateway"])
            badge = f" {GREEN}[CONECTADO]{RESET}" if is_active else ""
            print(f"  [{idx}] {c.get('name', c['id'])}{badge} - {c.get('gateway')}")

        print(f"\n{BOLD}Opciones Generales:{RESET}")
        print("  [D] Desconectar VPN")
        print("  [S] Ver Estado Detallado")
        print("  [T] Diagnóstico del Sistema (Doctor)")
        print("  [Q] Salir")

        try:
            choice = input(f"\n{BOLD}Selecciona una opción:{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSaliendo...")
            break

        if not choice:
            continue

        if choice.lower() == "q":
            break
        elif choice.lower() == "d":
            cmd_disconnect(backend)
            input(f"\n{DIM}Presiona Enter para continuar...{RESET}")
        elif choice.lower() == "s":
            cmd_status(backend)
            input(f"\n{DIM}Presiona Enter para continuar...{RESET}")
        elif choice.lower() == "t":
            cmd_doctor(cfg)
            input(f"\n{DIM}Presiona Enter para continuar...{RESET}")
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(conns):
                cmd_connect(backend, conns[idx]["id"])
                input(f"\n{DIM}Presiona Enter para continuar...{RESET}")
            else:
                print(f"{RED}Número de sede inválido.{RESET}")
                time.sleep(1)


def main():
    parser = argparse.ArgumentParser(
        prog="snx-manager",
        description="Gestor universal de perfiles y conexiones Check Point VPN (snx-rs)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Comandos disponibles")

    # connect
    p_conn = subparsers.add_parser("connect", help="Conectar a una sede por su ID")
    p_conn.add_argument("profile_id", nargs="?", help="ID del perfil/sede (ej. headquarters, bunker)")

    # disconnect
    subparsers.add_parser("disconnect", help="Desconectar la VPN activa")

    # status
    p_st = subparsers.add_parser("status", help="Consultar estado de la conexión")
    p_st.add_argument("--json", action="store_true", help="Salida en formato JSON para scripts")

    # list
    p_list = subparsers.add_parser("list", help="Listar perfiles configurados")
    p_list.add_argument("--json", action="store_true", help="Salida en formato JSON")

    # doctor
    p_doc = subparsers.add_parser("doctor", help="Auditoría de dependencias, kernel y colisiones de red")
    p_doc.add_argument("--json", action="store_true", help="Salida en formato JSON")

    # import / export
    p_imp = subparsers.add_parser("import", help="Importar bundle de perfiles")
    p_imp.add_argument("file", type=Path, help="Ruta al archivo bundle JSON")

    p_exp = subparsers.add_parser("export", help="Exportar perfiles a bundle JSON")
    p_exp.add_argument("file", type=Path, help="Ruta de destino")
    p_exp.add_argument("--include-passwords", action="store_true", help="Incluir contraseñas en el bundle")

    # gui
    subparsers.add_parser("gui", help="Abrir la interfaz gráfica de usuario (PyQt6)")

    # daemon
    p_daemon = subparsers.add_parser("daemon", help="Ejecutar en modo servicio persistente para systemd")
    p_daemon.add_argument("--profile", required=True, help="ID del perfil a mantener conectado")

    args = parser.parse_args()

    cfg = load_config()
    backend = VpnBackend()

    # Si se solicitó GUI explícita
    if args.subcommand == "gui":
        try:
            from snx_manager.gui import launch_gui
            launch_gui()
            sys.exit(0)
        except ImportError as e:
            print(f"{RED}Error: Las dependencias de GUI (PyQt6) no están instaladas en este entorno: {e}{RESET}")
            print(f"Ejecuta en modo consola o instala PyQt6 con: pip install PyQt6")
            sys.exit(1)

    # Subcomandos específicos
    if args.subcommand == "connect":
        if args.profile_id:
            cmd_connect(backend, args.profile_id)
        else:
            conns = cfg.get("connections", [])
            if conns:
                cmd_connect(backend, conns[0]["id"])
            else:
                print(f"{RED}No hay perfiles configurados. Usa 'snx-manager import' o define uno.{RESET}")
                sys.exit(1)

    elif args.subcommand == "disconnect":
        cmd_disconnect(backend)

    elif args.subcommand == "status":
        cmd_status(backend, json_output=args.json)

    elif args.subcommand == "list":
        cmd_list(cfg, json_output=args.json)

    elif args.subcommand == "doctor":
        cmd_doctor(cfg, json_output=args.json)

    elif args.subcommand == "import":
        if import_bundle(cfg, args.file):
            print(f"{GREEN}✅ Perfiles importados exitosamente desde {args.file}{RESET}")
        else:
            print(f"{RED}❌ Falló la importación.{RESET}", file=sys.stderr)
            sys.exit(1)

    elif args.subcommand == "export":
        if export_bundle(cfg, args.file, exclude_passwords=not args.include_passwords):
            print(f"{GREEN}✅ Perfiles exportados exitosamente a {args.file}{RESET}")
        else:
            print(f"{RED}❌ Falló la exportación.{RESET}", file=sys.stderr)
            sys.exit(1)

    elif args.subcommand == "daemon":
        # Modo servicio systemd
        cmd_connect(backend, args.profile)
        # Mantener el proceso vivo para systemd
        import time
        try:
            while True:
                time.sleep(10)
                st = backend.get_status()
                if not st["connected"]:
                    print(f"{YELLOW}[WATCHDOG] Conexión perdida, reintentando...{RESET}")
                    backend.connect(args.profile)
        except KeyboardInterrupt:
            backend.disconnect()

    else:
        # Sin subcomandos:
        # 1. Si hay display gráfico activo, intentar abrir GUI
        if (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")) and not os.environ.get("FORCE_CLI"):
            try:
                from snx_manager.gui import launch_gui
                launch_gui()
                sys.exit(0)
            except Exception:
                pass

        # 2. Si es terminal interactiva, abrir TUI
        if sys.stdin.isatty():
            interactive_tui(backend, cfg)
        else:
            parser.print_help()


if __name__ == "__main__":
    main()

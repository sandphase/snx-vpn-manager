#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snx_manager.cli
Dual command-line interface:
1. Scriptable UNIX mode (subcommands: connect, disconnect, status, doctor, etc.)
2. Interactive ANSI colored TUI mode for pure terminals / headless SSH servers.
Designed 100% on the standard library for maximum portability and speed.
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

# ANSI Colors
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
        print(f"\n  {GREEN}● STATUS:{RESET} {BOLD}CONNECTED{RESET}")
        print(f"  {CYAN}• Active Profile:{RESET}  {st['active_name']} ({st['active_id']})")
        print(f"  {CYAN}• Assigned IP:{RESET}     {st['ip']}")
        print(f"  {CYAN}• Gateway:{RESET}         {st['gateway']}")
        print(f"  {CYAN}• Interface:{RESET}       {st['interface']}")
        if st["dns_servers"]:
            print(f"  {CYAN}• DNS Servers:{RESET}     {', '.join(st['dns_servers'])}")
    else:
        print(f"\n  {DIM}○ STATUS:{RESET} {YELLOW}DISCONNECTED{RESET}")
        print(f"  {DIM}• No VPN tunnel is currently active.{RESET}")
    print()


def cmd_list(cfg: dict, json_output: bool = False):
    conns = cfg.get("connections", [])
    if json_output:
        print(json.dumps(conns, indent=2))
        return

    print_banner()
    print(f"\n{BOLD}Configured Profiles and Sites:{RESET}\n")
    if not conns:
        print(f"  {YELLOW}No profiles configured yet.{RESET}")
        print(f"  Use '{CYAN}snx-manager import <file.json>{RESET}' or interactive mode to add one.\n")
        return

    active_id = cfg.get("active_id", "")
    shared_dns = cfg.get("shared", {}).get("dns_servers", "Not defined")

    for idx, c in enumerate(conns, start=1):
        is_active = (c["id"] == active_id)
        mark = f"{GREEN}● ACTIVE{RESET}" if is_active else f"{DIM}○{RESET}"
        dns = c["custom_dns"] if c.get("use_custom_dns") else f"Shared ({shared_dns})"
        print(f"  [{idx}] {BOLD}{c.get('name', c['id'])}{RESET} {mark}")
        print(f"      ID:          {c['id']}")
        print(f"      Gateway:     {c.get('gateway', 'N/A')}")
        print(f"      DNS:         {dns}")
        if c.get("description"):
            print(f"      Description: {c['description']}")
        print()


def cmd_connect(backend: VpnBackend, profile_id: str):
    print(f"{CYAN}⏳ Connecting to profile '{profile_id}'...{RESET}")
    ok, msg = backend.connect(profile_id)
    if ok:
        print(f"{GREEN}✅ {msg}{RESET}")
        sys.exit(0)
    else:
        print(f"{RED}❌ {msg}{RESET}", file=sys.stderr)
        sys.exit(1)


def cmd_disconnect(backend: VpnBackend):
    print(f"{YELLOW}⏳ Disconnecting VPN tunnel...{RESET}")
    backend.disconnect()
    print(f"{GREEN}✅ VPN disconnected cleanly.{RESET}")


def cmd_doctor(cfg: dict, json_output: bool = False):
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
    """Interactive TUI menu for terminal and SSH sessions."""
    while True:
        os.system("clear" if os.name == "posix" else "cls")
        st = backend.get_status()
        print_banner()

        if st["connected"]:
            print(f"\n  {GREEN}● STATUS:{RESET} {BOLD}CONNECTED{RESET} to {st['active_name']} ({st['ip']})")
        else:
            print(f"\n  {DIM}○ STATUS:{RESET} {YELLOW}DISCONNECTED{RESET}")

        conns = cfg.get("connections", [])
        print(f"\n{BOLD}Available Sites / Profiles:{RESET}")
        for idx, c in enumerate(conns, start=1):
            is_active = (st["connected"] and c["gateway"] == st["gateway"])
            badge = f" {GREEN}[CONNECTED]{RESET}" if is_active else ""
            print(f"  [{idx}] {c.get('name', c['id'])}{badge} - {c.get('gateway')}")

        print(f"\n{BOLD}General Actions:{RESET}")
        print("  [D] Disconnect Active VPN")
        print("  [S] View Detailed Status")
        print("  [T] System Diagnostics (Doctor)")
        print("  [Q] Exit")

        try:
            choice = input(f"\n{BOLD}Select an option:{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if not choice:
            continue

        if choice.lower() == "q":
            break
        elif choice.lower() == "d":
            cmd_disconnect(backend)
            input(f"\n{DIM}Press Enter to continue...{RESET}")
        elif choice.lower() == "s":
            cmd_status(backend)
            input(f"\n{DIM}Press Enter to continue...{RESET}")
        elif choice.lower() == "t":
            cmd_doctor(cfg)
            input(f"\n{DIM}Press Enter to continue...{RESET}")
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(conns):
                cmd_connect(backend, conns[idx]["id"])
                input(f"\n{DIM}Press Enter to continue...{RESET}")
            else:
                print(f"{RED}Invalid site index.{RESET}")
                time.sleep(1)


def main():
    parser = argparse.ArgumentParser(
        prog="snx-manager",
        description="Universal Check Point SNX VPN Profile & Connection Manager (snx-rs)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # connect
    p_conn = subparsers.add_parser("connect", help="Connect to a site by its profile ID")
    p_conn.add_argument("profile_id", nargs="?", help="Profile / site ID (e.g., headquarters, datacenter)")

    # disconnect
    subparsers.add_parser("disconnect", help="Disconnect active VPN tunnel")

    # status
    p_st = subparsers.add_parser("status", help="Query VPN connection status")
    p_st.add_argument("--json", action="store_true", help="Output in JSON format for scripting")

    # list
    p_list = subparsers.add_parser("list", help="List configured connection profiles")
    p_list.add_argument("--json", action="store_true", help="Output in JSON format")

    # doctor
    p_doc = subparsers.add_parser("doctor", help="Audit dependencies, kernel modules, and network collisions")
    p_doc.add_argument("--json", action="store_true", help="Output in JSON format")

    # import / export
    p_imp = subparsers.add_parser("import", help="Import profiles from a bundle JSON")
    p_imp.add_argument("file", type=Path, help="Path to input JSON bundle")

    p_exp = subparsers.add_parser("export", help="Export profiles to a JSON bundle")
    p_exp.add_argument("file", type=Path, help="Target destination path")
    p_exp.add_argument("--include-passwords", action="store_true", help="Include saved passwords in bundle")

    # gui
    subparsers.add_parser("gui", help="Launch the graphical user interface (PyQt6)")

    # daemon
    p_daemon = subparsers.add_parser("daemon", help="Run in persistent service mode for systemd")
    p_daemon.add_argument("--profile", required=True, help="Profile ID to keep connected")

    args = parser.parse_args()

    cfg = load_config()
    backend = VpnBackend()

    # GUI explicit launch
    if args.subcommand == "gui":
        try:
            from snx_manager.gui import launch_gui
            launch_gui()
            sys.exit(0)
        except ImportError as e:
            print(f"{RED}Error: GUI dependencies (PyQt6) are not installed in this environment: {e}{RESET}")
            print(f"Run in console mode or install PyQt6 via: pip install PyQt6")
            sys.exit(1)

    # Specific subcommands
    if args.subcommand == "connect":
        if args.profile_id:
            cmd_connect(backend, args.profile_id)
        else:
            conns = cfg.get("connections", [])
            if conns:
                cmd_connect(backend, conns[0]["id"])
            else:
                print(f"{RED}No profiles configured. Use 'snx-manager import' or add one interactively.{RESET}")
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
            print(f"{GREEN}✅ Profiles imported successfully from {args.file}{RESET}")
        else:
            print(f"{RED}❌ Import failed.{RESET}", file=sys.stderr)
            sys.exit(1)

    elif args.subcommand == "export":
        if export_bundle(cfg, args.file, exclude_passwords=not args.include_passwords):
            print(f"{GREEN}✅ Profiles exported successfully to {args.file}{RESET}")
        else:
            print(f"{RED}❌ Export failed.{RESET}", file=sys.stderr)
            sys.exit(1)

    elif args.subcommand == "daemon":
        # systemd service daemon mode
        cmd_connect(backend, args.profile)
        import time
        try:
            while True:
                time.sleep(10)
                st = backend.get_status()
                if not st["connected"]:
                    print(f"{YELLOW}[WATCHDOG] Connection dropped, reconnecting...{RESET}")
                    backend.connect(args.profile)
        except KeyboardInterrupt:
            backend.disconnect()

    else:
        # Default behavior without subcommands:
        # 1. If graphical display is active, open GUI
        if (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")) and not os.environ.get("FORCE_CLI"):
            try:
                from snx_manager.gui import launch_gui
                launch_gui()
                sys.exit(0)
            except Exception:
                pass

        # 2. If interactive terminal, open TUI
        if sys.stdin.isatty():
            interactive_tui(backend, cfg)
        else:
            parser.print_help()


if __name__ == "__main__":
    main()

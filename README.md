# 🛡️ SNX VPN Manager for Linux

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-brightgreen.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Linux-orange.svg)]()
[![Backend](https://img.shields.io/badge/backend-snx--rs-purple.svg)](https://github.com/ancwrd1/snx-rs)

> **Modern, resilient Check Point SNX VPN client manager for Linux.**  
> Features automated background installation, Policy-Based Routing (PBR), split-DNS, Docker network collision prevention, interactive ANSI TUI, scriptable CLI, and a dark-mode PyQt6 Desktop GUI.

---

## 📌 The Problem It Solves

Connecting to Check Point Firewalls / Security Gateways on modern Linux systems has traditionally been a frustrating ordeal:
- Check Point's legacy Linux client relies on deprecated 32-bit binaries and obsolete browser plugins.
- Modern Linux distributions enforce strict TLS requirements and PEP 668 packaging protections.
- **Docker Network Conflicts:** Docker often assigns RFC 1918 subnets (`172.17.0.0/16` - `172.31.0.0/16`) to local bridge interfaces (`docker0`, `br-*`), silently intercepting corporate DNS traffic and causing corporate hostnames to fail to resolve.
- Switching between different corporate sites (e.g., Datacenter vs. Branch Office) required manual file edits or running separate shell scripts.

**SNX VPN Manager** brings everything together into a clean, unified, enterprise-grade solution built on top of the modern open-source [`snx-rs`](https://github.com/ancwrd1/snx-rs) Rust engine.

---

## ✨ Features

- 🚀 **100% Automated Background Installer (`install.sh`):**
  - Installs `snx-rs` automatically (from official APT repositories or precompiled GitHub binaries).
  - Configures kernel modules (`modprobe tun`), least-privilege `sudoers` rules, systemd template services, and desktop launchers.
  - Automatically detects **Desktop** (GUI + Shortcuts) vs **Server** (Zero-GUI headless mode).

- 🌐 **Shared Fields Architecture:**
  - Common credentials (username, password, global DNS) are configured once in an isolated "Campos Compartidos" section.
  - Individual connections (Datacenter, Branch Office, Cloud Gateway) can inherit shared DNS or define their own dedicated DNS resolvers.

- 🖥️ **Modern Desktop GUI (PyQt6):**
  - Responsive card layout with real-time tunnel status (🟢 Active / ⚪ Disconnected).
  - One-click connect, disconnect, edit, add, and delete.
  - Integrated pre-flight diagnostic tool ("Diagnóstico").
  - Seamless dark theme inspired by modern system tools.

- 🖧 **Server & Headless Friendly (CLI & TUI):**
  - **Zero GUI dependencies on servers:** The CLI and TUI are implemented purely with the Python standard library.
  - Interactive ANSI colored TUI for SSH sessions.
  - Full scriptable CLI (`snx-manager connect <id>`, `snx-manager status --json`, etc.).

- 🔒 **Kernel Route & Collision Management:**
  - Injects atomic `/32` host routes for DNS servers to prevent Docker bridge hijacking.
  - Policy-Based Routing (PBR) table `18000` to prevent traffic leaks.
  - Flushes IPsec XFRM states on disconnect to avoid stuck kernel states.

- 📦 **Corporate Profiles Export/Import:**
  - Export team configurations to sanitized JSON bundles (passwords scrubbed by default) for effortless team onboarding.

---

## 🚀 Quick Start

### 1. Installation

Clone this repository and run the automated installer:

```bash
git clone https://github.com/sandphase/snx-vpn-manager.git
cd snx-vpn-manager
sudo ./install.sh
```

#### Installer Flags:
| Flag | Description |
| :--- | :--- |
| *(Default)* | Interactive prompt: selects Desktop or Server with auto-detection. |
| `--desktop` | Forces Desktop mode (PyQt6 GUI, desktop shortcuts, icons, and CLI). |
| `--server` | Forces Server mode (Zero GUI dependencies, pure CLI + ANSI TUI). |
| `-y, --yes` | Non-interactive mode (assumes defaults). |
| `--dry-run` | Simulates installation steps without modifying system files. |

---

## 💻 Usage

### 1. Interactive Desktop GUI

Launch from your desktop application launcher under **"SNX VPN Manager"**, or execute in terminal:

```bash
snx-manager gui
```

> **Keyboard Shortcut (e.g. `Ctrl+Alt+C`):**  
> The installer installs `/usr/local/bin/snx-vpn-toggle`.  
> Bind your preferred keyboard shortcut in GNOME (`Settings > Keyboard > Shortcuts`), KDE Plasma (`Shortcuts > Custom Shortcuts`), or i3/Sway to `/usr/local/bin/snx-vpn-toggle` to open or toggle the manager instantly.

---

### 2. Interactive Terminal UI (TUI)

If executed inside a terminal without arguments (or on headless servers):

```bash
snx-manager
```

```text
    ╔══════════════════════════════════════════════════════════╗
    ║             🛡️  SNX CHECK POINT VPN MANAGER             ║
    ╚══════════════════════════════════════════════════════════╝

Perfiles y Sedes Configuradas:
  [1] Corporate HQ ● ACTIVO
  [2] Branch Office ○

Opciones disponibles:
  [1] Conectar a un perfil
  [2] Desconectar VPN activa
  [3] Estado detallado de la conexión
  [4] Diagnóstico del sistema (doctor)
  [q] Salir
```

---

### 3. Scriptable UNIX CLI

Perfect for automation, CI/CD, or shell scripts:

```bash
# Check system readiness
snx-manager doctor

# List configured profiles
snx-manager list

# Connect to a profile
snx-manager connect corporate-hq

# Check connection status
snx-manager status
snx-manager status --json

# Disconnect
snx-manager disconnect

# Export team bundle (passwords stripped)
snx-manager export /tmp/team-bundle.json

# Import team bundle
snx-manager import /tmp/team-bundle.json
```

---

### 4. Background Service (systemd)

`snx-manager` includes a template systemd service unit (`snx-vpn@.service`):

```bash
# Start connection to profile 'corporate-hq' as a persistent background daemon:
sudo systemctl start snx-vpn@corporate-hq

# Enable automatic connection at system boot:
sudo systemctl enable snx-vpn@corporate-hq

# View live systemd service logs:
sudo journalctl -u snx-vpn@corporate-hq -f
```

---

## ⚙️ Architecture & Routing Design

```
                     ┌───────────────────────────┐
                     │   GUI / TUI / CLI         │
                     │  (snx-manager frontends)  │
                     └─────────────┬─────────────┘
                                   │
                     ┌─────────────▼─────────────┐
                     │     VpnBackend Core       │
                     │  (State machine & config) │
                     └─────────────┬─────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
   ┌──────────────────────┐                  ┌──────────────────────┐
   │     snx-rs Engine    │                  │  RouteManager & DNS  │
   │  • SSL/TLS Handshake │                  │  • /32 Host Routes   │
   │  • snx-vpn Interface │                  │  • PBR Table 18000   │
   │  • Keepalive Polling │                  │  • systemd-resolved  │
   └──────────────────────┘                  └──────────────────────┘
              │                                         │
              └────────────────────┬────────────────────┘
                                   ▼
                      ┌──────────────────────────┐
                      │    Linux Kernel State    │
                      │  (No Docker Collisions)  │
                      └──────────────────────────┘
```

### Docker RFC 1918 Subnet Collision Safeguard
When Docker runs locally, its virtual bridges often conflict with private internal subnets (e.g. `172.17.0.0/16`, `172.25.0.0/16`). `snx-manager`:
1. Audits existing bridge interfaces using `detect_docker_collisions()`.
2. Explicitly injects high-priority host `/32` routes (`ip route replace <ip>/32 dev snx-vpn`) directly into the main routing table before activating DNS queries.
3. Automatically tears down host routes and flushes kernel IPsec/XFRM states upon disconnect.

---

## 🩺 System Diagnostics (`snx-manager doctor`)

To verify whether your system satisfies all networking, permission, and kernel requirements:

```bash
snx-manager doctor
```

Example output:
```text
============================================================
          🩺 DIAGNÓSTICO DEL SISTEMA (snx-manager doctor)    
============================================================
  [OK] Cliente snx-rs: Presente (snx-rs 6.4.1)
  [OK] Dispositivo Kernel: /dev/net/tun disponible
  [OK] Herramientas de Red: iproute2 presente
  [INFO] Subsistema DNS activo: systemd-resolved
  [OK] Privilegios Root: sudo NOPASSWD configurado (Operación transparente)
============================================================
ESTADO GENERAL: ✅ El sistema está listo para operar.
```

---

## 🧪 Testing

Run the automated test suite without external dependencies:

```bash
make test
```

---

## 🗑️ Uninstallation

To cleanly remove `snx-manager`, systemd units, sudoers rules, and desktop shortcuts:

```bash
sudo ./uninstall.sh
```

To also remove all saved profiles and configurations:

```bash
sudo ./uninstall.sh --purge
```

---

## 📄 License

This project is open-source software licensed under the [MIT License](LICENSE).
The underlying `snx-rs` client is licensed by its respective authors under the GPLv3 / MIT licenses.

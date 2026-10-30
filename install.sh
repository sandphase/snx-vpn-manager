#!/usr/bin/env bash
# ==============================================================================
# SNX Check Point VPN Manager - Universal Automated Installer
# Target OS: Debian, Ubuntu, Fedora, Arch, RHEL, openSUSE
# Architectures: x86_64, aarch64
# ==============================================================================

set -e

# ANSI Color Codes
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

INSTALL_DIR="/opt/snx-manager"
BIN_LINK="/usr/local/bin/snx-manager"
TOGGLE_LINK="/usr/local/bin/snx-vpn-toggle"
SYSTEMD_DIR="/etc/systemd/system"
SUDOERS_FILE="/etc/sudoers.d/snx-manager"
APP_DESKTOP="/usr/share/applications/snx-manager.desktop"
ICON_DIR="/usr/share/icons/hicolor/scalable/apps"

MODE="auto" # "desktop", "server", "auto"
DRY_RUN=false
NON_INTERACTIVE=false

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ==============================================================================
# Helpers
# ==============================================================================

log_info() {
    echo -e "  ${CYAN}•${NC} $1"
}

log_success() {
    echo -e "  ${GREEN}✔${NC} $1"
}

log_warning() {
    echo -e "  ${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "  ${RED}✖${NC} $1" >&2
}

print_banner() {
    echo -e "${CYAN}${BOLD}"
    cat << "EOF"
    ╔══════════════════════════════════════════════════════════╗
    ║       🛡️   SNX VPN MANAGER - UNIVERSAL INSTALLER         ║
    ║        Check Point SNX for Modern Linux Systems          ║
    ╚══════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

usage() {
    cat << EOF
Usage: sudo ./install.sh [OPTIONS]

Options:
  --desktop         Install full Desktop suite (PyQt6 GUI + TUI + CLI + Shortcuts)
  --server          Install Headless Server suite (Zero GUI deps, CLI + ANSI TUI)
  --auto            Automatically detect environment (Desktop if display/X11/Wayland found)
  -y, --yes         Non-interactive mode, accept all default choices
  --dry-run         Simulate installation steps without modifying the system
  -h, --help        Show this help message
EOF
    exit 0
}

# ==============================================================================
# Parse Arguments
# ==============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --desktop)
            MODE="desktop"
            shift
            ;;
        --server)
            MODE="server"
            shift
            ;;
        --auto)
            MODE="auto"
            shift
            ;;
        -y|--yes)
            NON_INTERACTIVE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# ==============================================================================
# Pre-flight Checks
# ==============================================================================

print_banner

if [[ $EUID -ne 0 ]] && [[ "$DRY_RUN" = false ]]; then
    log_error "This installer requires administrative root privileges."
    echo -e "    Please run: ${BOLD}sudo ./install.sh${NC}\n"
    exit 1
fi

REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

echo -e "${BOLD}1. Environment & Architecture Detection${NC}"

ARCH="$(uname -m)"
log_info "Detected architecture: ${BOLD}$ARCH${NC}"
if [[ "$ARCH" != "x86_64" ]] && [[ "$ARCH" != "aarch64" ]]; then
    log_warning "Architecture $ARCH is not officially tested. Proceeding with caution."
fi

# Detect OS
OS_FAMILY="unknown"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    case "$ID" in
        ubuntu|debian|linuxmint|pop)
            OS_FAMILY="debian"
            ;;
        fedora|rhel|centos|rocky|alma)
            OS_FAMILY="fedora"
            ;;
        arch|manjaro|endeavouros)
            OS_FAMILY="arch"
            ;;
        opensuse*|suse)
            OS_FAMILY="suse"
            ;;
        *)
            OS_FAMILY="generic"
            ;;
    esac
    log_info "Operating System: ${BOLD}$PRETTY_NAME${NC} (Family: $OS_FAMILY)"
fi

# Determine Target Profile (Desktop vs Server)
if [[ "$MODE" == "auto" ]]; then
    if [[ -n "${WAYLAND_DISPLAY:-}" ]] || [[ -n "${DISPLAY:-}" ]] || [[ -n "${XDG_CURRENT_DESKTOP:-}" ]]; then
        MODE="desktop"
        log_info "Graphical display detected -> Selected mode: ${BOLD}Desktop (GUI + CLI)${NC}"
    else
        MODE="server"
        log_info "No graphical display detected -> Selected mode: ${BOLD}Server (CLI + pure TUI)${NC}"
    fi
fi

if [[ "$NON_INTERACTIVE" = false ]] && [[ -t 0 ]]; then
    echo -e "\n${BOLD}Select installation profile:${NC}"
    echo -e "  ${BOLD}[1]${NC} 🖥️  Desktop (PyQt6 Graphical GUI + App Launcher + TUI + CLI)"
    echo -e "  ${BOLD}[2]${NC} 🖧  Headless Server (Zero GUI dependencies, pure ANSI TUI + CLI)"
    
    DEFAULT_CHOICE="1"
    [[ "$MODE" == "server" ]] && DEFAULT_CHOICE="2"
    
    read -r -p "  Select [1 or 2] (Default: $DEFAULT_CHOICE): " USER_SELECTION
    USER_SELECTION="${USER_SELECTION:-$DEFAULT_CHOICE}"
    
    if [[ "$USER_SELECTION" == "2" ]]; then
        MODE="server"
    else
        MODE="desktop"
    fi
fi

echo -e "\n${GREEN}✔ Configuration chosen: ${BOLD}${MODE^^} Mode${NC}\n"

# ==============================================================================
# Step 2: System Dependencies
# ==============================================================================

echo -e "${BOLD}2. Installing System Dependencies${NC}"

if [[ "$DRY_RUN" = true ]]; then
    log_info "[DRY-RUN] Skipping package download and installation."
else
    case "$OS_FAMILY" in
        debian)
            log_info "Updating package lists and installing core dependencies..."
            apt-get update -qq || true
            DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
                python3 \
                python3-pip \
                iproute2 \
                kmod \
                curl \
                ca-certificates \
                iptables > /dev/null

            if [[ "$MODE" == "desktop" ]]; then
                log_info "Installing graphical packages (PyQt6) from system repositories..."
                DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
                    python3-pyqt6 \
                    libgl1 \
                    libegl1 > /dev/null || {
                    log_warning "Could not install python3-pyqt6 via apt. Will verify at runtime."
                }
            fi
            ;;
        fedora)
            log_info "Installing packages on Fedora / RHEL..."
            dnf install -y -q python3 iproute kmod curl ca-certificates iptables
            if [[ "$MODE" == "desktop" ]]; then
                dnf install -y -q python3-qt6 || dnf install -y -q python3-PyQt6 || true
            fi
            ;;
        arch)
            log_info "Installing packages on Arch Linux..."
            pacman -Sy --noconfirm --needed python iproute2 kmod curl ca-certificates iptables
            if [[ "$MODE" == "desktop" ]]; then
                pacman -S --noconfirm --needed python-pyqt6 || true
            fi
            ;;
        *)
            log_warning "Generic distribution: ensuring python3 and networking tools..."
            ;;
    esac
fi

# Ensure kernel module tun
if [[ "$DRY_RUN" = false ]]; then
    modprobe tun 2>/dev/null || true
    if [ ! -c /dev/net/tun ]; then
        log_warning "/dev/net/tun not found, creating device node..."
        mkdir -p /dev/net
        mknod /dev/net/tun c 10 200 || true
        chmod 666 /dev/net/tun || true
    fi
    log_success "Kernel module TUN/TAP active."
fi

# ==============================================================================
# Step 3: Install snx-rs Engine
# ==============================================================================

echo -e "\n${BOLD}3. Checking and Installing snx-rs Engine${NC}"

SNX_BIN="$(command -v snx-rs || true)"
if [[ -n "$SNX_BIN" ]]; then
    SNX_VER="$("$SNX_BIN" -v 2>/dev/null || echo 'unknown')"
    log_success "snx-rs is already installed at: $SNX_BIN ($SNX_VER)"
else
    log_info "snx-rs not found. Proceeding with transparent background installation..."
    
    INSTALLED_SNX=false
    
    # Attempt 1: Official APT repository if Debian/Ubuntu
    if [[ "$OS_FAMILY" == "debian" ]] && [[ "$DRY_RUN" = false ]]; then
        log_info "Configuring official ancwrd1/snx-rs package repository..."
        curl -fsSL https://ancwrd1.github.io/snx-rs/deb/snx-rs.gpg -o /etc/apt/trusted.gpg.d/snx-rs.gpg 2>/dev/null || true
        echo "deb https://ancwrd1.github.io/snx-rs/deb ./" > /etc/apt/sources.list.d/snx-rs.list
        apt-get update -qq >/dev/null 2>&1 || true
        if DEBIAN_FRONTEND=noninteractive apt-get install -y -qq snx-rs >/dev/null 2>&1; then
            INSTALLED_SNX=true
            log_success "snx-rs installed successfully via APT."
        fi
    fi

    # Attempt 2: Precompiled binary from GitHub Releases
    if [[ "$INSTALLED_SNX" = false ]] && [[ "$DRY_RUN" = false ]]; then
        log_info "Downloading official precompiled binary from GitHub Releases..."
        TMP_DIR="$(mktemp -d)"
        BIN_URL="https://github.com/ancwrd1/snx-rs/releases/latest/download/snx-rs-linux-x86_64.tar.gz"
        if [[ "$ARCH" == "aarch64" ]]; then
            BIN_URL="https://github.com/ancwrd1/snx-rs/releases/latest/download/snx-rs-linux-aarch64.tar.gz"
        fi

        if curl -fsSL "$BIN_URL" -o "$TMP_DIR/snx-rs.tar.gz" 2>/dev/null; then
            tar -xzf "$TMP_DIR/snx-rs.tar.gz" -C "$TMP_DIR"
            if [ -f "$TMP_DIR/snx-rs" ]; then
                install -m 755 "$TMP_DIR/snx-rs" /usr/local/bin/snx-rs
                INSTALLED_SNX=true
                log_success "snx-rs installed successfully to /usr/local/bin/snx-rs"
            fi
        fi
        rm -rf "$TMP_DIR"
    fi

    # Attempt 3: Cargo fallback
    if [[ "$INSTALLED_SNX" = false ]] && command -v cargo &>/dev/null && [[ "$DRY_RUN" = false ]]; then
        log_info "Compiling snx-rs via cargo in background..."
        cargo install snx-rs --root /usr/local >/dev/null 2>&1 && INSTALLED_SNX=true
    fi

    if [[ "$INSTALLED_SNX" = false ]] && [[ "$DRY_RUN" = false ]]; then
        log_warning "Could not auto-install snx-rs. You can install it manually: cargo install snx-rs"
    fi
fi

# Set network capabilities if setcap is available
if command -v setcap &>/dev/null && [ -f /usr/local/bin/snx-rs ] && [[ "$DRY_RUN" = false ]]; then
    setcap cap_net_admin,cap_net_raw+ep /usr/local/bin/snx-rs 2>/dev/null || true
fi

# ==============================================================================
# Step 4: Install snx-manager Application Files
# ==============================================================================

echo -e "\n${BOLD}4. Deploying snx-manager Application Files${NC}"

if [[ "$DRY_RUN" = true ]]; then
    log_info "[DRY-RUN] Files would be copied to $INSTALL_DIR with symlink at $BIN_LINK"
else
    mkdir -p "$INSTALL_DIR"
    cp -r "$SCRIPT_DIR/snx_manager" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/pyproject.toml" "$INSTALL_DIR/" 2>/dev/null || true
    
    # Create executable wrapper
    cat > "$BIN_LINK" << 'EOF'
#!/usr/bin/env bash
export PYTHONPATH="/opt/snx-manager:$PYTHONPATH"
exec python3 -m snx_manager "$@"
EOF
    chmod +x "$BIN_LINK"
    log_success "Master binary installed at: ${BOLD}$BIN_LINK${NC}"
fi

# ==============================================================================
# Step 5: Systemd Service Unit
# ==============================================================================

echo -e "\n${BOLD}5. Systemd Service Unit Configuration${NC}"

if [[ "$DRY_RUN" = false ]]; then
    mkdir -p "$SYSTEMD_DIR"
    if [ -f "$SCRIPT_DIR/systemd/snx-vpn@.service" ]; then
        cp "$SCRIPT_DIR/systemd/snx-vpn@.service" "$SYSTEMD_DIR/"
    else
        cat > "$SYSTEMD_DIR/snx-vpn@.service" << 'EOF'
[Unit]
Description=Check Point SNX VPN Connection (%i)
After=network-online.target systemd-resolved.service
Wants=network-online.target
Documentation=https://github.com/sandphase/snx-vpn-manager

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/snx-manager daemon %i
Restart=on-failure
RestartSec=5s
KillMode=mixed
TimeoutStopSec=10s

[Install]
WantedBy=multi-user.target
EOF
    fi
    systemctl daemon-reload 2>/dev/null || true
    log_success "Service unit template installed: ${BOLD}$SYSTEMD_DIR/snx-vpn@.service${NC}"
fi

# ==============================================================================
# Step 6: Sudoers Configuration for Transparent Non-Root Execution
# ==============================================================================

echo -e "\n${BOLD}6. Sudoers Security Rules (Transparent Operation)${NC}"

if [[ "$DRY_RUN" = false ]]; then
    mkdir -p /etc/sudoers.d
    cat > "$SUDOERS_FILE" << 'EOF'
# SNX Manager - Minimal rules for PBR routing and interface management without password prompts
%sudo ALL=(ALL) NOPASSWD: /usr/local/bin/snx-manager daemon *, /usr/bin/ip route *, /usr/bin/ip rule *, /usr/bin/ip link delete snx-vpn, /usr/bin/ip xfrm *, /bin/ip route *, /bin/ip rule *, /bin/ip link delete snx-vpn, /bin/ip xfrm *, /usr/bin/systemctl start snx-vpn@*, /usr/bin/systemctl stop snx-vpn@*, /usr/bin/systemctl restart snx-vpn@*, /usr/bin/systemctl status snx-vpn@*
%wheel ALL=(ALL) NOPASSWD: /usr/local/bin/snx-manager daemon *, /usr/bin/ip route *, /usr/bin/ip rule *, /usr/bin/ip link delete snx-vpn, /usr/bin/ip xfrm *, /bin/ip route *, /bin/ip rule *, /bin/ip link delete snx-vpn, /bin/ip xfrm *, /usr/bin/systemctl start snx-vpn@*, /usr/bin/systemctl stop snx-vpn@*, /usr/bin/systemctl restart snx-vpn@*, /usr/bin/systemctl status snx-vpn@*
EOF
    chmod 0440 "$SUDOERS_FILE"
    if visudo -c -f "$SUDOERS_FILE" &>/dev/null; then
        log_success "Sudoers rules validated and installed at $SUDOERS_FILE"
    else
        log_error "Failed to validate sudoers syntax. Removing file for security."
        rm -f "$SUDOERS_FILE"
    fi
fi

# ==============================================================================
# Step 7: Desktop Integration (Icons, Shortcuts, .desktop)
# ==============================================================================

if [[ "$MODE" == "desktop" ]]; then
    echo -e "\n${BOLD}7. Desktop Integration (App Launcher & Icons)${NC}"
    if [[ "$DRY_RUN" = false ]]; then
        # Copy vector icons
        mkdir -p "$ICON_DIR"
        cp "$SCRIPT_DIR/assets/snx-icon.svg" "$ICON_DIR/snx-manager.svg" 2>/dev/null || true
        cp "$SCRIPT_DIR/assets/snx-icon-connected.svg" "$ICON_DIR/snx-manager-connected.svg" 2>/dev/null || true
        gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
        
        # Copy .desktop launcher
        mkdir -p /usr/share/applications
        if [ -f "$SCRIPT_DIR/desktop/snx-manager.desktop" ]; then
            cp "$SCRIPT_DIR/desktop/snx-manager.desktop" "$APP_DESKTOP"
        fi
        update-desktop-database 2>/dev/null || true
        
        # Copy quick toggle script for Ctrl+Alt+C shortcut
        if [ -f "$SCRIPT_DIR/desktop/snx-vpn-toggle.sh" ]; then
            install -m 755 "$SCRIPT_DIR/desktop/snx-vpn-toggle.sh" "$TOGGLE_LINK"
            log_success "Quick toggle shortcut script installed at: $TOGGLE_LINK"
        fi

        log_success "Desktop application launcher installed: $APP_DESKTOP"
    fi
fi

# ==============================================================================
# Step 8: Initial User Profile Setup
# ==============================================================================

echo -e "\n${BOLD}8. User Profile Initialization${NC}"

USER_CONFIG_DIR="$REAL_HOME/.config/snx-manager"
USER_CONFIG_FILE="$USER_CONFIG_DIR/profiles.json"

if [[ "$DRY_RUN" = false ]] && [ ! -f "$USER_CONFIG_FILE" ]; then
    mkdir -p "$USER_CONFIG_DIR"
    cp "$SCRIPT_DIR/examples/profiles.example.json" "$USER_CONFIG_FILE"
    chown -R "$REAL_USER:$REAL_USER" "$USER_CONFIG_DIR" 2>/dev/null || true
    log_success "Initial profile template created at: $USER_CONFIG_FILE"
else
    log_info "Existing user profiles preserved at: $USER_CONFIG_FILE"
fi

# ==============================================================================
# Diagnostics & Summary
# ==============================================================================

echo -e "\n${BOLD}9. Running System Pre-Flight Diagnostics (doctor)${NC}"
if [[ "$DRY_RUN" = false ]]; then
    su - "$REAL_USER" -c "$BIN_LINK doctor" || true
fi

echo -e "\n${GREEN}${BOLD}============================================================${NC}"
echo -e "${GREEN}${BOLD}   🎉 INSTALLATION COMPLETED SUCCESSFULLY! (${MODE^^})   ${NC}"
echo -e "${GREEN}${BOLD}============================================================${NC}"
echo -e "\nUsage options:"
if [[ "$MODE" == "desktop" ]]; then
    echo -e "  • ${BOLD}Graphical GUI:${NC}   Open 'SNX VPN Manager' from your app launcher or run: ${CYAN}snx-manager gui${NC}"
    echo -e "  • ${BOLD}Keyboard Shortcut:${NC} Bind ${CYAN}Ctrl+Alt+C${NC} to command: ${BOLD}$TOGGLE_LINK${NC}"
fi
echo -e "  • ${BOLD}Interactive TUI:${NC}  Run directly: ${CYAN}snx-manager${NC}"
echo -e "  • ${BOLD}CLI Connect:${NC}      ${CYAN}snx-manager connect <id>${NC}"
echo -e "  • ${BOLD}CLI Disconnect:${NC}   ${CYAN}snx-manager disconnect${NC}"
echo -e "  • ${BOLD}Daemon Service:${NC}   ${CYAN}sudo systemctl start snx-vpn@<id>${NC}"
echo -e "  • ${BOLD}Uninstall:${NC}        ${CYAN}sudo ./uninstall.sh${NC}\n"

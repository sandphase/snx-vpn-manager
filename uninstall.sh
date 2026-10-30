#!/usr/bin/env bash
# ==============================================================================
# SNX Check Point VPN Manager - Universal Uninstaller
# ==============================================================================

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

PURGE_CONFIG=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --purge)
            PURGE_CONFIG=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}✖ This uninstaller requires administrative root privileges.${NC}"
    echo -e "  Please run: ${BOLD}sudo ./uninstall.sh${NC}\n"
    exit 1
fi

REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

echo -e "\n${YELLOW}${BOLD}Uninstalling SNX VPN Manager...${NC}\n"

# 1. Stop active services
echo -e "  ${CYAN}•${NC} Stopping active tunnels and services..."
systemctl stop 'snx-vpn@*' 2>/dev/null || true

# 2. Cleanup interface and routes
ip link delete snx-vpn 2>/dev/null || true
ip rule del table 18000 2>/dev/null || true
ip route flush table 18000 2>/dev/null || true
ip xfrm state flush 2>/dev/null || true
ip xfrm policy flush 2>/dev/null || true

# 3. Remove binaries and symlinks
echo -e "  ${CYAN}•${NC} Removing executables..."
rm -f /usr/local/bin/snx-manager
rm -f /usr/local/bin/snx-vpn-toggle

# 4. Remove /opt/snx-manager
rm -rf /opt/snx-manager

# 5. Remove systemd service unit
echo -e "  ${CYAN}•${NC} Removing systemd service unit..."
rm -f /etc/systemd/system/snx-vpn@.service
systemctl daemon-reload 2>/dev/null || true

# 6. Remove sudoers
echo -e "  ${CYAN}•${NC} Removing sudoers configuration..."
rm -f /etc/sudoers.d/snx-manager

# 7. Remove desktop entries and icons
echo -e "  ${CYAN}•${NC} Removing desktop integration..."
rm -f /usr/share/applications/snx-manager.desktop
update-desktop-database 2>/dev/null || true

rm -f /usr/share/icons/hicolor/scalable/apps/snx-manager.svg
rm -f /usr/share/icons/hicolor/scalable/apps/snx-manager-connected.svg
gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true

# 8. Clean up user profiles if purged
if [[ "$PURGE_CONFIG" = true ]]; then
    echo -e "  ${YELLOW}•${NC} Purging user configuration directory..."
    rm -rf "$REAL_HOME/.config/snx-manager"
else
    echo -e "  ${GREEN}•${NC} Your profile configurations were preserved in: ${BOLD}$REAL_HOME/.config/snx-manager/${NC}"
    echo -e "    (To remove all user data completely, run: sudo ./uninstall.sh --purge)"
fi

echo -e "\n${GREEN}✔ SNX VPN Manager has been cleanly uninstalled from your system.${NC}\n"

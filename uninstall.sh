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
    echo -e "${RED}✖ Este script requiere privilegios de administrador.${NC}"
    echo -e "  Por favor ejecuta: ${BOLD}sudo ./uninstall.sh${NC}\n"
    exit 1
fi

REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

echo -e "\n${YELLOW}${BOLD}Desinstalando SNX VPN Manager...${NC}\n"

# 1. Detener servicios activos
echo -e "  ${CYAN}•${NC} Deteniendo servicios y túneles activos..."
systemctl stop 'snx-vpn@*' 2>/dev/null || true

# 2. Limpieza de interfaz y rutas
ip link delete snx-vpn 2>/dev/null || true
ip rule del table 18000 2>/dev/null || true
ip route flush table 18000 2>/dev/null || true
ip xfrm state flush 2>/dev/null || true
ip xfrm policy flush 2>/dev/null || true

# 3. Remover enlaces y binarios
echo -e "  ${CYAN}•${NC} Removiendo ejecutables..."
rm -f /usr/local/bin/snx-manager
rm -f /usr/local/bin/snx-vpn-toggle

# 4. Remover /opt/snx-manager
rm -rf /opt/snx-manager

# 5. Remover servicio systemd
echo -e "  ${CYAN}•${NC} Removiendo unidad de systemd..."
rm -f /etc/systemd/system/snx-vpn@.service
systemctl daemon-reload 2>/dev/null || true

# 6. Remover sudoers
echo -e "  ${CYAN}•${NC} Removiendo reglas de sudoers..."
rm -f /etc/sudoers.d/snx-manager

# 7. Remover desktop entries e iconos
echo -e "  ${CYAN}•${NC} Removiendo integración de escritorio..."
rm -f /usr/share/applications/snx-manager.desktop
update-desktop-database 2>/dev/null || true

rm -f /usr/share/icons/hicolor/scalable/apps/snx-manager.svg
rm -f /usr/share/icons/hicolor/scalable/apps/snx-manager-connected.svg
gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true

# 8. Limpiar perfiles si se solicitó
if [[ "$PURGE_CONFIG" = true ]]; then
    echo -e "  ${YELLOW}•${NC} Purgando directorios de configuración de usuario..."
    rm -rf "$REAL_HOME/.config/snx-manager"
else
    echo -e "  ${GREEN}•${NC} Tu archivo de perfiles se mantuvo intacto en: ${BOLD}$REAL_HOME/.config/snx-manager/${NC}"
    echo -e "    (Para eliminarlo por completo, ejecuta: sudo ./uninstall.sh --purge)"
fi

echo -e "\n${GREEN}✔ SNX VPN Manager ha sido completamente desinstalado del sistema.${NC}\n"

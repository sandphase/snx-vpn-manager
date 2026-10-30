#!/usr/bin/env bash
# snx-vpn-toggle.sh — Helper for global keyboard shortcuts (e.g., Ctrl+Alt+C / Ctrl+Alt+D)
set -euo pipefail

ACTION="${1:-gui}"

case "$ACTION" in
  gui)
    exec snx-manager
    ;;
  connect)
    PROFILE="${2:-}"
    if [ -n "$PROFILE" ]; then
      exec snx-manager connect "$PROFILE"
    else
      exec snx-manager
    fi
    ;;
  disconnect)
    exec snx-manager disconnect
    ;;
  toggle)
    # If connected, disconnect. If disconnected, open GUI manager.
    if snx-manager status --json 2>/dev/null | grep -q '"connected": true'; then
      exec snx-manager disconnect
    else
      exec snx-manager
    fi
    ;;
  *)
    echo "Usage: $0 [gui|connect <id>|disconnect|toggle]"
    exit 1
    ;;
esac

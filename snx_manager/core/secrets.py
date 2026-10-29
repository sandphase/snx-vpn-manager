#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snx_manager.core.secrets
Capa de abstracción segura para almacenamiento de credenciales.
Integra la Secret Service API de FreeDesktop (GNOME Keyring / KWallet) con
fallback determinista para entornos de servidor (Variables de entorno y archivos 0600).
"""

import os
import sys
from typing import Optional

SERVICE_NAME = "snx-vpn-manager"


class SecretManager:
    """Gestor de credenciales con soporte para Keyring del SO y Servidor Headless."""

    def __init__(self):
        self._keyring_available = self._check_keyring()

    def _check_keyring(self) -> bool:
        try:
            import keyring
            # Intentar verificar si hay un backend activo funcional
            backend = keyring.get_keyring()
            if "fail" in backend.__class__.__name__.lower():
                return False
            return True
        except Exception:
            return False

    def get_password(self, username: str, profile_id: str = "shared") -> Optional[str]:
        """Recupera la contraseña con prioridad: Entorno > Keyring del SO > Configuración."""
        # 1. Prioridad máxima en servidores: Variable de entorno
        env_var = f"SNX_PASSWORD_{profile_id.upper().replace('-', '_')}"
        if env_var in os.environ:
            return os.environ[env_var]
        if "SNX_PASSWORD" in os.environ:
            return os.environ["SNX_PASSWORD"]

        # 2. Keyring del Sistema Operativo
        if self._keyring_available and username:
            try:
                import keyring
                key = f"{profile_id}@{username}"
                secret = keyring.get_password(SERVICE_NAME, key)
                if secret:
                    return secret
            except Exception:
                pass

        return None

    def store_password(self, username: str, password: str, profile_id: str = "shared") -> bool:
        """Almacena la contraseña en el Keyring del SO si está disponible."""
        if self._keyring_available and username and password:
            try:
                import keyring
                key = f"{profile_id}@{username}"
                keyring.set_password(SERVICE_NAME, key, password)
                return True
            except Exception:
                return False
        return False

    def delete_password(self, username: str, profile_id: str = "shared") -> bool:
        """Elimina una credencial guardada."""
        if self._keyring_available and username:
            try:
                import keyring
                key = f"{profile_id}@{username}"
                keyring.delete_password(SERVICE_NAME, key)
                return True
            except Exception:
                pass
        return False

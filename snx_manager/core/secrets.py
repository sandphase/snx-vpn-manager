#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snx_manager.core.secrets
Secure credential storage abstraction layer.
Integrates FreeDesktop Secret Service API (GNOME Keyring / KWallet) with
deterministic fallbacks for headless servers (Environment variables and 0600 files).
"""

import os
import sys
from typing import Optional

SERVICE_NAME = "snx-vpn-manager"


class SecretManager:
    """Credential manager supporting OS Keyring and Headless Server environments."""

    def __init__(self):
        self._keyring_available = self._check_keyring()

    def _check_keyring(self) -> bool:
        try:
            import keyring
            backend = keyring.get_keyring()
            if "fail" in backend.__class__.__name__.lower():
                return False
            return True
        except Exception:
            return False

    def get_password(self, username: str, profile_id: str = "shared") -> Optional[str]:
        """Retrieves password with priority: Environment > OS Keyring > Configuration."""
        # 1. Maximum priority on servers: Environment variable
        env_var = f"SNX_PASSWORD_{profile_id.upper().replace('-', '_')}"
        if env_var in os.environ:
            return os.environ[env_var]
        if "SNX_PASSWORD" in os.environ:
            return os.environ["SNX_PASSWORD"]

        # 2. Operating System Keyring
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
        """Stores password in OS Keyring if available."""
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
        """Deletes a saved credential."""
        if self._keyring_available and username:
            try:
                import keyring
                key = f"{profile_id}@{username}"
                keyring.delete_password(SERVICE_NAME, key)
                return True
            except Exception:
                pass
        return False

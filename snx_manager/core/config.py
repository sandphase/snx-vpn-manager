#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snx_manager.core.config
Declarative profile and configuration management module with atomic persistence.
Designed 100% on the standard library for universal Linux portability.
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

CURRENT_SCHEMA_VERSION = "1.0.0"

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "snx-manager"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


def get_default_config() -> Dict[str, Any]:
    """Returns the base initial structure when no prior configuration exists."""
    return {
        "version": CURRENT_SCHEMA_VERSION,
        "active_id": "",
        "shared": {
            "user_name": "",
            "password": "",
            "dns_servers": "",
            "search_domains": "",
            "tunnel_type": "ssl",
            "login_type": "vpn",
            "ignore_server_cert": True
        },
        "connections": []
    }


def migrate_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migration pipeline for future schema versions."""
    version = data.get("version", "0.9.0")
    if version == CURRENT_SCHEMA_VERSION:
        return data

    # Incremental migrations
    data["version"] = CURRENT_SCHEMA_VERSION
    if "shared" not in data:
        data["shared"] = get_default_config()["shared"]
    if "connections" not in data:
        data["connections"] = []
    return data


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Loads and validates configuration file with automatic migration."""
    path = config_path or DEFAULT_CONFIG_FILE
    if not path.exists():
        cfg = get_default_config()
        save_config(cfg, path)
        return cfg

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            return migrate_config(raw_data)
    except Exception as e:
        sys.stderr.write(f"[WARN] Error reading {path}: {e}. Returning default configuration.\n")
        return get_default_config()


def save_config(data: Dict[str, Any], config_path: Optional[Path] = None) -> bool:
    """
    Atomic persistence (Zero-Corruption Pattern):
    Writes to temporary file on the same filesystem and renames atomically with os.replace.
    """
    path = config_path or DEFAULT_CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    data["version"] = CURRENT_SCHEMA_VERSION

    try:
        with tempfile.NamedTemporaryFile("w", dir=str(path.parent), delete=False, encoding="utf-8") as tf:
            json.dump(data, tf, indent=2, ensure_ascii=False)
            temp_name = tf.name

        # Restrict permissions to 0600 (owner read/write only)
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
        return True
    except Exception as e:
        sys.stderr.write(f"[ERROR] Atomic persistence failed at {path}: {e}\n")
        return False


def get_connection_by_id(config: Dict[str, Any], conn_id: str) -> Optional[Dict[str, Any]]:
    """Finds a connection by its unique ID."""
    for c in config.get("connections", []):
        if c.get("id") == conn_id:
            return c
    return None


def get_effective_dns(config: Dict[str, Any], conn: Dict[str, Any]) -> str:
    """Resolves effective DNS applying precedence (Specific > Shared)."""
    if conn.get("use_custom_dns") and conn.get("custom_dns", "").strip():
        return conn["custom_dns"].strip()
    return config.get("shared", {}).get("dns_servers", "").strip()


def export_bundle(config: Dict[str, Any], output_path: Path, exclude_passwords: bool = True) -> bool:
    """Exports profiles into a shareable bundle for teams or automated deployments."""
    bundle = {
        "bundle_version": CURRENT_SCHEMA_VERSION,
        "shared": dict(config.get("shared", {})),
        "connections": [dict(c) for c in config.get("connections", [])]
    }
    if exclude_passwords:
        bundle["shared"]["password"] = ""

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        sys.stderr.write(f"[ERROR] Failed to export bundle: {e}\n")
        return False


def import_bundle(config: Dict[str, Any], bundle_path: Path, merge: bool = True, config_path: Optional[Path] = None) -> bool:
    """Imports connections and shared settings from an exported bundle."""
    if not bundle_path.exists():
        return False
    try:
        with open(bundle_path, "r", encoding="utf-8") as f:
            bundle_data = json.load(f)

        if not merge:
            config["connections"] = []

        existing_ids = {c.get("id") for c in config.get("connections", [])}
        for new_conn in bundle_data.get("connections", []):
            cid = new_conn.get("id")
            if cid in existing_ids:
                # Update existing profile
                for idx, c in enumerate(config["connections"]):
                    if c.get("id") == cid:
                        config["connections"][idx] = new_conn
                        break
            else:
                config.setdefault("connections", []).append(new_conn)
                existing_ids.add(cid)

        # Update shared fields if empty in current config
        bundle_shared = bundle_data.get("shared", {})
        config_shared = config.setdefault("shared", {})
        for k, v in bundle_shared.items():
            if v and not config_shared.get(k):
                config_shared[k] = v

        return save_config(config, config_path)
    except Exception as e:
        sys.stderr.write(f"[ERROR] Failed to import bundle: {e}\n")
        return False

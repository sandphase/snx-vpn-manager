"""
snx_manager.core
Core VPN engine modules agnostic of the user interface.
"""

from snx_manager.core.config import load_config, save_config, get_connection_by_id, export_bundle, import_bundle
from snx_manager.core.backend import VpnBackend
from snx_manager.core.routing import RouteManager, detect_docker_collisions
from snx_manager.core.dns import DnsManager
from snx_manager.core.secrets import SecretManager
from snx_manager.core.doctor import run_diagnostics

__all__ = [
    "load_config",
    "save_config",
    "get_connection_by_id",
    "export_bundle",
    "import_bundle",
    "VpnBackend",
    "RouteManager",
    "detect_docker_collisions",
    "DnsManager",
    "SecretManager",
    "run_diagnostics"
]

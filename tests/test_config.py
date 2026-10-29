"""Unit tests for snx_manager.core.config using standard library unittest."""

import json
import tempfile
import unittest
from pathlib import Path

from snx_manager.core.config import (
    get_default_config,
    load_config,
    save_config,
    export_bundle,
    import_bundle,
    migrate_config,
    CURRENT_SCHEMA_VERSION,
)


class TestConfig(unittest.TestCase):

    def test_default_config_structure(self):
        cfg = get_default_config()
        self.assertEqual(cfg["version"], CURRENT_SCHEMA_VERSION)
        self.assertIn("shared", cfg)
        self.assertIn("connections", cfg)
        self.assertIsInstance(cfg["connections"], list)
        self.assertEqual(cfg["shared"]["tunnel_type"], "ssl")

    def test_atomic_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_profiles.json"
            cfg = get_default_config()
            cfg["shared"]["user_name"] = "test_user"
            cfg["connections"].append({
                "id": "site_a",
                "name": "Site Alpha",
                "server": "192.0.2.1",
                "dns_mode": "shared",
                "custom_dns": "",
                "search_domains": "corp.local",
            })

            self.assertTrue(save_config(cfg, test_file))
            self.assertTrue(test_file.exists())

            loaded = load_config(test_file)
            self.assertEqual(loaded["shared"]["user_name"], "test_user")
            self.assertEqual(len(loaded["connections"]), 1)
            self.assertEqual(loaded["connections"][0]["id"], "site_a")

    def test_migration_legacy_format(self):
        legacy = {
            "connections": [{"id": "old_site", "server": "1.2.3.4"}]
        }
        migrated = migrate_config(legacy)
        self.assertEqual(migrated["version"], CURRENT_SCHEMA_VERSION)
        self.assertIn("shared", migrated)
        self.assertEqual(migrated["shared"]["tunnel_type"], "ssl")
        self.assertEqual(len(migrated["connections"]), 1)

    def test_export_import_bundle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "source.json"
            bundle_file = Path(tmpdir) / "bundle.json"
            dst_file = Path(tmpdir) / "dest.json"

            cfg = get_default_config()
            cfg["shared"]["user_name"] = "alice"
            cfg["shared"]["password"] = "secret123"
            cfg["shared"]["dns_servers"] = "192.0.2.53"
            cfg["connections"].append({
                "id": "datacenter",
                "name": "Datacenter",
                "server": "198.51.100.1",
                "dns_mode": "shared",
            })
            save_config(cfg, src_file)

            # Export bundle (exclude password by default)
            self.assertTrue(export_bundle(cfg, bundle_file, exclude_passwords=True))
            with open(bundle_file, "r") as f:
                exported = json.load(f)
            self.assertEqual(exported["shared"]["password"], "")
            self.assertEqual(exported["shared"]["user_name"], "alice")

            # Import into new config
            new_cfg = get_default_config()
            save_config(new_cfg, dst_file)
            self.assertTrue(import_bundle(new_cfg, bundle_file, config_path=dst_file))

            loaded_dest = load_config(dst_file)
            self.assertEqual(loaded_dest["shared"]["user_name"], "alice")
            self.assertEqual(len(loaded_dest["connections"]), 1)
            self.assertEqual(loaded_dest["connections"][0]["id"], "datacenter")


if __name__ == "__main__":
    unittest.main()

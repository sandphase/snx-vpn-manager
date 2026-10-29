"""Unit tests for snx_manager.cli using standard library unittest."""

import io
import sys
import unittest
from unittest.mock import patch, MagicMock
from snx_manager.cli import main


class TestCli(unittest.TestCase):

    def test_cli_help(self):
        with patch("sys.argv", ["snx-manager", "--help"]):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                with self.assertRaises(SystemExit) as exc:
                    main()
                self.assertEqual(exc.exception.code, 0)

            out = captured.getvalue()
            self.assertIn("snx-manager", out)
            self.assertIn("connect", out)
            self.assertIn("doctor", out)

    @patch("snx_manager.cli.run_diagnostics")
    def test_cli_doctor_json(self, mock_diag):
        mock_diag.return_value = {
            "snx_installed": True,
            "snx_version": "6.4.1",
            "tun_available": True,
            "iproute2_available": True,
            "dns_manager": "systemd-resolved",
            "docker_collisions": [],
            "sudo_nopasswd": True,
            "all_healthy": True,
        }

        with patch("sys.argv", ["snx-manager", "doctor", "--json"]):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                main()

            out = captured.getvalue()
            self.assertIn('"snx_installed": true', out)
            self.assertIn('"all_healthy": true', out)


if __name__ == "__main__":
    unittest.main()

"""Unit tests for snx_manager.core.routing using standard library unittest."""

import ipaddress
import unittest
from unittest.mock import patch, MagicMock
from snx_manager.core.routing import RouteManager, detect_docker_collisions


class TestRouting(unittest.TestCase):

    def test_route_manager_init(self):
        rm = RouteManager(interface="test-tun0", routing_table=12345)
        self.assertEqual(rm.interface, "test-tun0")
        self.assertEqual(rm.routing_table, 12345)
        self.assertEqual(rm.applied_routes, [])

    @patch("snx_manager.core.routing.run_root_cmd")
    def test_inject_host_route_32_valid(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        rm = RouteManager(interface="test-tun0")
        success = rm.inject_host_route_32("192.0.2.10")

        self.assertTrue(success)
        self.assertIn("192.0.2.10/32", rm.applied_routes)
        mock_run.assert_called_once_with(["ip", "route", "replace", "192.0.2.10/32", "dev", "test-tun0"])

    def test_inject_host_route_32_invalid_ip(self):
        rm = RouteManager(interface="test-tun0")
        success = rm.inject_host_route_32("not-an-ip")
        self.assertFalse(success)
        self.assertEqual(len(rm.applied_routes), 0)

    @patch("snx_manager.core.routing.run_cmd")
    def test_detect_docker_collisions(self, mock_run):
        mock_output = (
            "1: lo    inet 127.0.0.1/8 scope host lo\\       valid_lft forever preferred_lft forever\n"
            "2: eth0  inet 192.168.1.100/24 brd 192.168.1.255 scope global eth0\n"
            "3: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0\n"
            "4: br-abc1234 inet 172.18.0.1/16 scope global br-abc1234\n"
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)

        collisions = detect_docker_collisions(["172.17.10.5/32", "10.0.0.1/32"])
        self.assertEqual(len(collisions), 1)
        self.assertEqual(collisions[0][1], "docker0")


if __name__ == "__main__":
    unittest.main()

"""Hardware-independent checks. No GPIO modules required."""
import io
import os
import unittest
from unittest.mock import patch

import pi_server
from remote_backend import RemoteBackend

class BindingTests(unittest.TestCase):
    def test_loopback_does_not_require_token(self):
        pi_server.require_secure_bind("127.0.0.1", "")
    def test_remote_bind_requires_strong_token(self):
        with self.assertRaises(RuntimeError):
            pi_server.require_secure_bind("0.0.0.0", "")
        with self.assertRaises(RuntimeError):
            pi_server.require_secure_bind("192.168.0.12", "short")
        pi_server.require_secure_bind("0.0.0.0", "x"*32)

class ServerAuthorizationTests(unittest.TestCase):
    def test_missing_token_is_rejected_when_configured(self):
        with patch.object(pi_server, "TOKEN", "A"*32):
            request=type("FakeRequest", (), {"headers": {}})()
            self.assertFalse(pi_server.Handler._authorized(request))

    def test_matching_token_is_accepted(self):
        with patch.object(pi_server, "TOKEN", "A"*32):
            request=type("FakeRequest", (), {"headers": {"Authorization": "Bearer " + "A"*32}})()
            self.assertTrue(pi_server.Handler._authorized(request))

    def test_wrong_token_is_rejected(self):
        with patch.object(pi_server, "TOKEN", "A"*32):
            request=type("FakeRequest", (), {"headers": {"Authorization": "Bearer " + "B"*32}})()
            self.assertFalse(pi_server.Handler._authorized(request))

class ClientTests(unittest.TestCase):
    def test_client_defaults_are_local(self):
        with patch.dict(os.environ, {}, clear=True):
            b=RemoteBackend()
            self.assertEqual(b.base_url, "http://127.0.0.1:8765")
            self.assertEqual(b._auth_headers(), {})
            self.assertFalse(b.hardware)
    def test_client_uses_configured_host_and_token(self):
        with patch.dict(os.environ,{"PICONTROL_HOST":"192.168.0.55","PICONTROL_PORT":"1234","PICONTROL_TOKEN":"testing-123"}):
            b=RemoteBackend()
            self.assertEqual(b.base_url,"http://192.168.0.55:1234")
            self.assertEqual(b._auth_headers(),{"Authorization":"Bearer testing-123"})
    def test_client_can_stay_in_simulation(self):
        with patch.dict(os.environ, {}, clear=True):
            b=RemoteBackend()
            b.set_simulation(True)
            self.assertFalse(b.hardware)

if __name__=="__main__": unittest.main()

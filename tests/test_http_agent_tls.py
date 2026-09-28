import json
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import requests

from src.client.agents.http_agent import HTTPAgent


@unittest.skipUnless(shutil.which("openssl"), "openssl is required for the local TLS fixture")
class HTTPAgentTLS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.certificate = str(Path(cls.directory.name) / "certificate.pem")
        key = str(Path(cls.directory.name) / "key.pem")
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-keyout", key, "-out", cls.certificate, "-days", "1",
             "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
            check=True, capture_output=True,
        )

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                cls.bodies.append(body)
                payload = json.dumps({"reply": "fixture reply"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        cls.bodies = []
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cls.certificate, key)
        cls.server.socket = context.wrap_socket(cls.server.socket, server_side=True)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.url = "https://127.0.0.1:%s/chat" % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()
        cls.directory.cleanup()

    def test_untrusted_certificate_is_rejected_by_default(self):
        before = len(self.bodies)
        agent = HTTPAgent(url=self.url, return_format="{response[reply]}")
        with patch("src.client.agents.http_agent.time.sleep"):
            with self.assertRaisesRegex(Exception, "Failed"):
                agent.inference([{"role": "user", "content": "Hello"}])
        self.assertEqual(len(self.bodies), before)

    def test_custom_ca_is_scoped_to_this_request(self):
        original = requests.Session.merge_environment_settings
        agent = HTTPAgent(
            url=self.url, verify=self.certificate, return_format="{response[reply]}",
            prompter={"name": "role_content_dict", "args": {"agent_role": "assistant"}},
        )
        self.assertEqual(agent.inference([
            {"role": "user", "content": "Hello"},
            {"role": "agent", "content": "Previous answer"},
        ]), "fixture reply")
        self.assertEqual(self.bodies[-1]["messages"][-1]["role"], "assistant")
        self.assertIs(requests.Session.merge_environment_settings, original)
        with self.assertRaises(requests.exceptions.SSLError):
            requests.post(self.url, json={}, timeout=5)

    def test_explicit_opt_out_does_not_disable_other_sessions(self):
        agent = HTTPAgent(url=self.url, verify=False, return_format="{response[reply]}")
        with self.assertWarns(requests.packages.urllib3.exceptions.InsecureRequestWarning):
            self.assertEqual(agent.inference([{"role": "user", "content": "Hello"}]), "fixture reply")
        with self.assertRaises(requests.exceptions.SSLError):
            requests.post(self.url, json={}, timeout=5)


if __name__ == "__main__":
    unittest.main()

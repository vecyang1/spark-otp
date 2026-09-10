"""
Contract and Schema Conformance Tests for Spark OTP.
Ensures every model, schema endpoint, and API payload adheres to the contract.
"""
import unittest
import json
import urllib.request
import threading
import time
from spark_otp.contracts import OPENAPI_SPEC, SCHEMAS
from spark_otp.models import OTPResult, EmailSummary
from spark_otp.server import create_server

class MockClient:
    def is_available(self):
        return True

    def get_accounts(self):
        return ["dev.team@acme-cloud.net", "alex.turner@gmail.com"]

    def get_latest_otp(self, domain=None, max_age_seconds=None, account=None):
        return OTPResult(
            code="181174",
            service="bandwagon_auth",
            domain=domain or "bandwagonhost.com",
            callback_url=None,
            message_id="721250",
            subject="Device verification",
            sender="Bandwagon Host <noreply@64clouds.com>",
            received_at="2026-09-08T20:34:00",
            expires_at="2026-09-08T21:34:00",
            is_expired=False,
            time_remaining_seconds=1778
        )

class TestContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = MockClient()
        cls.server = create_server(host="127.0.0.1", port=0, client=cls.client)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_openapi_spec_structure(self):
        """OpenAPI document must have required version, paths, and components."""
        self.assertEqual(OPENAPI_SPEC["openapi"], "3.0.3")
        self.assertIn("/api/health", OPENAPI_SPEC["paths"])
        self.assertIn("/api/accounts", OPENAPI_SPEC["paths"])
        self.assertIn("/api/otp", OPENAPI_SPEC["paths"])
        self.assertIn("/api/stream", OPENAPI_SPEC["paths"])
        self.assertIn("/api/telemetry", OPENAPI_SPEC["paths"])
        self.assertIn("/api/schema", OPENAPI_SPEC["paths"])
        self.assertIn("/api/openapi.json", OPENAPI_SPEC["paths"])

    def test_schema_endpoint(self):
        """GET /api/schema returns all component schemas."""
        url = f"http://127.0.0.1:{self.port}/api/schema"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.getcode(), 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertIn("OTPResult", data)
        self.assertIn("HealthResponse", data)
        self.assertIn("AccountListResponse", data)
        self.assertIn("TelemetryResponse", data)

    def test_openapi_endpoint(self):
        """GET /api/openapi.json returns complete specification."""
        url = f"http://127.0.0.1:{self.port}/api/openapi.json"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.getcode(), 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertEqual(data["info"]["title"], "Spark OTP Bridge API")

    def test_otp_response_schema_conformance(self):
        """GET /api/otp payload matches the OTPResult and OTPResponse contracts."""
        url = f"http://127.0.0.1:{self.port}/api/otp?domain=bawagon"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.getcode(), 200)
        data = json.loads(req.read().decode("utf-8"))

        # Verify top-level OTPResponse
        self.assertTrue(data["success"])
        self.assertIn("metrics", data)
        self.assertIn("duration_ms", data["metrics"])

        # Verify nested OTPResult
        otp = data["otp"]
        required_fields = SCHEMAS["OTPResult"]["required"]
        for field in required_fields:
            self.assertIn(field, otp, f"Missing required contract field '{field}' in OTP payload")
        self.assertEqual(otp["code"], "181174")
        self.assertEqual(otp["service"], "bandwagon_auth")
        self.assertIsInstance(otp["time_remaining_seconds"], int)
        self.assertIsInstance(otp["is_expired"], bool)

    def test_accounts_response_schema_conformance(self):
        """GET /api/accounts payload matches AccountListResponse schema."""
        url = f"http://127.0.0.1:{self.port}/api/accounts"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.getcode(), 200)
        data = json.loads(req.read().decode("utf-8"))

        required_fields = SCHEMAS["AccountListResponse"]["required"]
        for field in required_fields:
            self.assertIn(field, data, f"Missing required field '{field}' in Accounts payload")
        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["accounts"]), 2)

    def test_health_response_schema_conformance(self):
        """GET /api/health payload matches HealthResponse schema."""
        url = f"http://127.0.0.1:{self.port}/api/health"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.getcode(), 200)
        data = json.loads(req.read().decode("utf-8"))

        required_fields = SCHEMAS["HealthResponse"]["required"]
        for field in required_fields:
            self.assertIn(field, data, f"Missing required field '{field}' in Health payload")
        self.assertTrue(data["spark_available"])

if __name__ == "__main__":
    unittest.main()

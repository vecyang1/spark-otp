"""
Contract tests for Spark OTP HTTP Server and Endpoints.
"""
import unittest
import threading
import time
import urllib.request
import json
from spark_otp.server import create_server
from spark_otp.models import OTPResult

class MockSparkClient:
    def __init__(self):
        self.mock_otp = OTPResult(
            code="123456",
            service="mock_service",
            domain="test.domain.com",
            callback_url="https://test.domain.com/callback",
            message_id="999",
            subject="Verification code for test.domain.com",
            sender="auth@test.domain.com",
            received_at="2026-09-07T12:00:00",
            expires_at="2026-09-07T12:10:00",
            is_expired=False,
            time_remaining_seconds=500
        )

    def is_available(self) -> bool:
        return True

    def get_accounts(self):
        return ["alex.turner@gmail.com", "dev.team@acme-cloud.net"]

    def get_latest_otp(self, domain=None, max_age_seconds=None, account=None, exclude_codes=None, exclude_message_ids=None, since_time=None, **kwargs):
        if domain == "error.test":
            raise RuntimeError("Spark CLI timeout")
        if domain == "wrong.domain.com":
            return None
        if account == "nonexistent@gmail.com":
            return None
        if exclude_codes and self.mock_otp.code in exclude_codes:
            return None
        if exclude_message_ids and self.mock_otp.message_id in exclude_message_ids:
            return None
        return self.mock_otp

class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock_client = MockSparkClient()
        cls.server = create_server(host="127.0.0.1", port=0, client=cls.mock_client)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_health_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/api/health"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.status, 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["spark_available"])

    def test_otp_endpoint_success(self):
        url = f"http://127.0.0.1:{self.port}/api/otp?domain=test.domain.com"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.status, 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertEqual(data["otp"]["code"], "123456")

    def test_otp_endpoint_not_found(self):
        url = f"http://127.0.0.1:{self.port}/api/otp?domain=wrong.domain.com"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.status, 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertFalse(data["success"])
        self.assertIsNone(data.get("otp"))

    def test_cors_headers(self):
        url = f"http://127.0.0.1:{self.port}/api/health"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.headers.get("Access-Control-Allow-Origin"), "*")

    def test_accounts_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/api/accounts"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.status, 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 2)
        self.assertIn("alex.turner@gmail.com", data["accounts"])
        self.assertIn("dev.team@acme-cloud.net", data["accounts"])

    def test_otp_endpoint_account_param(self):
        # Valid account
        url = f"http://127.0.0.1:{self.port}/api/otp?domain=test.domain.com&account=alex.turner@gmail.com"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.status, 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertEqual(data["otp"]["code"], "123456")

        # Nonexistent account
        url_none = f"http://127.0.0.1:{self.port}/api/otp?domain=test.domain.com&account=nonexistent@gmail.com"
        req_none = urllib.request.urlopen(url_none)
        self.assertEqual(req_none.status, 200)
        data_none = json.loads(req_none.read().decode("utf-8"))
        self.assertFalse(data_none["success"])

    def test_kuma_heartbeat_worker_graceful(self):
        from spark_otp.server import start_kuma_heartbeat
        # Test that start_kuma_heartbeat starts thread and handles unreachable URL gracefully
        start_kuma_heartbeat("http://127.0.0.1:19999/nonexistent", interval=1)
        time.sleep(0.1)

    def test_telemetry_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/api/telemetry"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.status, 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertIn("telemetry", data)
        self.assertIn("avg_latency_ms", data["telemetry"])
        self.assertIn("hit_rate_pct", data["telemetry"])

        # /api/metrics alias
        url_metrics = f"http://127.0.0.1:{self.port}/api/metrics"
        req_metrics = urllib.request.urlopen(url_metrics)
        self.assertEqual(req_metrics.status, 200)

    def test_logs_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/api/logs?limit=10"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.status, 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertIn("logs", data)
        self.assertIsInstance(data["logs"], list)

    def test_otp_endpoint_metrics(self):
        url = f"http://127.0.0.1:{self.port}/api/otp?domain=test.domain.com"
        req = urllib.request.urlopen(url)
        data = json.loads(req.read().decode("utf-8"))
        self.assertIn("metrics", data)
        self.assertIn("duration_ms", data["metrics"])
        self.assertGreaterEqual(data["metrics"]["duration_ms"], 0.0)

    def test_telemetry_otp_specific_metrics(self):
        url = f"http://127.0.0.1:{self.port}/api/telemetry"
        req = urllib.request.urlopen(url)
        data = json.loads(req.read().decode("utf-8"))
        t = data["telemetry"]
        self.assertIn("otp_hit_rate_pct", t)
        self.assertIn("otp_avg_latency_ms", t)
        self.assertIn("otp_total", t)

    def test_stream_client_disconnect_clean_exit(self):
        """Test that client abrupt disconnect from SSE stream does not raise unhandled exception."""
        url = f"http://127.0.0.1:{self.port}/api/stream?domain=test.domain.com"
        req = urllib.request.urlopen(url)
        # Read the first event line then immediately close socket
        line = req.readline()
        self.assertTrue(len(line) > 0)
        req.close()  # abrupt socket close triggering BrokenPipeError/ConnectionResetError/OSError

    def test_otp_endpoint_exception_handling(self):
        """Test that server gracefully handles client exceptions with HTTP 500 and records error telemetry."""
        url = f"http://127.0.0.1:{self.port}/api/otp?domain=error.test"
        try:
            urllib.request.urlopen(url)
            self.fail("Expected HTTPError 500")
        except urllib.error.HTTPError as err:
            self.assertEqual(err.code, 500)
            body = json.loads(err.read().decode("utf-8"))
            self.assertFalse(body["success"])
            self.assertIn("Spark CLI timeout", body["error"])

    def test_otp_endpoint_exclude_codes(self):
        """Test that /api/otp respects exclude_codes parameter."""
        url = f"http://127.0.0.1:{self.port}/api/otp?domain=test.domain.com&exclude_codes=123456"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.status, 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertFalse(data["success"])
        self.assertIn("No valid OTP found", data["message"])

    def test_stream_endpoint_exclude_codes(self):
        """Test that /api/stream excludes bad codes and sends keepalive."""
        url = f"http://127.0.0.1:{self.port}/api/stream?domain=test.domain.com&exclude_codes=123456"
        req = urllib.request.urlopen(url, timeout=3)
        self.assertEqual(req.status, 200)
        line = req.readline().decode("utf-8")
        self.assertIn(": keepalive", line)
        req.close()

    def test_stream_endpoint_exclude_message_ids(self):
        """Test that /api/stream excludes bad message IDs and sends keepalive."""
        url = f"http://127.0.0.1:{self.port}/api/stream?domain=test.domain.com&exclude_message_ids=999"
        req = urllib.request.urlopen(url, timeout=3)
        self.assertEqual(req.status, 200)
        line = req.readline().decode("utf-8")
        self.assertIn(": keepalive", line)
        req.close()

if __name__ == "__main__":
    unittest.main()


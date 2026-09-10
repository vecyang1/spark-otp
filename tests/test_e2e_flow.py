"""
Comprehensive End-to-End Simulation Tests for Spark OTP Autofill.
Tests the full lifecycle: Mock Spark -> Extraction -> Daemon API -> SSE Event Delivery.
"""
import unittest
import threading
import time
import json
import urllib.request
from datetime import datetime
from spark_otp.server import create_server
from spark_otp.models import OTPResult
from spark_otp.extractor import extract_otp_from_thread
from tests.fixtures import REAL_CLOUDFLARE_FINANCE_EMAIL

class MockStreamingSparkClient:
    def __init__(self):
        self.code_to_emit = "987654"
        self.is_ready = True
        self.accounts = ["alex.turner@example.com", "alex.turner@acme-cloud.net"]

    def is_available(self) -> bool:
        return self.is_ready

    def get_accounts(self):
        return self.accounts

    def get_latest_otp(self, domain=None, max_age_seconds=None, account=None):
        if not self.is_ready or domain == "unrelated.domain.com":
            return None
        if account and account not in self.accounts:
            return None
        return OTPResult(
            code=self.code_to_emit,
            service="universal_otp" if "myapp" in (domain or "") else "cloudflare_access",
            domain=domain or "finance.acme-cloud.net",
            callback_url=f"https://acme-corp.cloudflareaccess.com/callback?code={self.code_to_emit}",
            message_id="888001",
            subject=f"Login code for {domain or 'finance.acme-cloud.net'}",
            sender=f"Auth <auth@{domain or 'cloudflare.com'}>",
            received_at=datetime.now().isoformat(),
            expires_at=datetime.now().isoformat(),
            is_expired=False,
            time_remaining_seconds=590
        )

class TestE2EFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock_client = MockStreamingSparkClient()
        cls.server = create_server(host="127.0.0.1", port=0, client=cls.mock_client)
        cls.port = cls.server.server_address[1]
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_full_e2e_otp_fetch(self):
        url = f"http://127.0.0.1:{self.port}/api/otp?domain=finance.acme-cloud.net"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.status, 200)
        data = json.loads(req.read().decode("utf-8"))
        
        self.assertTrue(data["success"])
        self.assertEqual(data["otp"]["code"], "987654")
        self.assertEqual(data["otp"]["domain"], "finance.acme-cloud.net")
        self.assertIn("callback?code=987654", data["otp"]["callback_url"])

    def test_sse_streaming_delivery(self):
        """Verify that SSE stream emits event: otp with JSON data."""
        url = f"http://127.0.0.1:{self.port}/api/stream?domain=finance.acme-cloud.net"
        req = urllib.request.urlopen(url, timeout=5)
        self.assertEqual(req.status, 200)
        self.assertIn("text/event-stream", req.headers.get("Content-Type"))

        # Read first event block
        lines = []
        for _ in range(5):
            line = req.readline().decode("utf-8")
            lines.append(line)
            if "event: otp" in line:
                data_line = req.readline().decode("utf-8")
                self.assertTrue(data_line.startswith("data: "))
                payload = json.loads(data_line[6:].strip())
                self.assertEqual(payload["code"], "987654")
                break
        req.close()

    def test_adversarial_offline_spark_client(self):
        """Verify behavior when Spark Desktop is not running."""
        self.mock_client.is_ready = False
        url = f"http://127.0.0.1:{self.port}/api/health"
        req = urllib.request.urlopen(url)
        data = json.loads(req.read().decode("utf-8"))
        self.assertFalse(data["spark_available"])

        otp_url = f"http://127.0.0.1:{self.port}/api/otp?domain=finance.acme-cloud.net"
        otp_req = urllib.request.urlopen(otp_url)
        otp_data = json.loads(otp_req.read().decode("utf-8"))
        self.assertFalse(otp_data["success"])
        self.mock_client.is_ready = True

    def test_e2e_multi_account_targeting(self):
        """Test account parameter filtering in E2E API call."""
        # Account exists
        url = f"http://127.0.0.1:{self.port}/api/otp?domain=finance.acme-cloud.net&account=alex.turner@acme-cloud.net"
        req = urllib.request.urlopen(url)
        data = json.loads(req.read().decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertEqual(data["otp"]["code"], "987654")

        # Account does not exist
        bad_url = f"http://127.0.0.1:{self.port}/api/otp?domain=finance.acme-cloud.net&account=nobody@nowhere.com"
        bad_req = urllib.request.urlopen(bad_url)
        bad_data = json.loads(bad_req.read().decode("utf-8"))
        self.assertFalse(bad_data["success"])

    def test_e2e_universal_saas_flow(self):
        """Test universal SaaS domain resolution in E2E API call."""
        url = f"http://127.0.0.1:{self.port}/api/otp?domain=myapp.cloud"
        req = urllib.request.urlopen(url)
        data = json.loads(req.read().decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertEqual(data["otp"]["service"], "universal_otp")
        self.assertEqual(data["otp"]["domain"], "myapp.cloud")

    def test_e2e_bandwagon_sqlite_flow(self):
        """Test end-to-end Bandwagon Host verification code delivery using direct SQLite backend."""
        import tempfile
        import os
        from spark_otp.spark_client import SparkClient
        from tests.test_sqlite_backend import create_mock_spark_sqlite, insert_mock_message

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "messages.sqlite")
            create_mock_spark_sqlite(db_path)
            now = datetime.now()
            ts_now = int(now.timestamp())
            insert_mock_message(
                db_path,
                pk=721280,
                sender="Bandwagon Host <noreply@64clouds.com>",
                recipient="alex.turner@example.com",
                subject="Device verification",
                short_body="Your device verification code: 273529. It is valid for 1 hour. Do NOT share this code with anyone.",
                received_ts=ts_now - 15
            )

            sqlite_client = SparkClient(sqlite_path=db_path, spark_bin="/usr/bin/false")
            custom_server = create_server(host="127.0.0.1", port=0, client=sqlite_client)
            custom_port = custom_server.server_address[1]
            t = threading.Thread(target=custom_server.serve_forever, daemon=True)
            t.start()
            try:
                # Test API GET /api/otp
                url = f"http://127.0.0.1:{custom_port}/api/otp?domain=bandwagonhost.com&account=alex.turner@example.com"
                req = urllib.request.urlopen(url)
                self.assertEqual(req.status, 200)
                data = json.loads(req.read().decode("utf-8"))
                self.assertTrue(data["success"])
                self.assertEqual(data["otp"]["code"], "273529")
                self.assertEqual(data["otp"]["service"], "bandwagon_auth")
                self.assertEqual(data["otp"]["domain"], "bandwagonhost.com")

                # Test SSE GET /api/stream
                stream_url = f"http://127.0.0.1:{custom_port}/api/stream?domain=bandwagonhost.com&account=alex.turner@example.com"
                stream_req = urllib.request.urlopen(stream_url, timeout=5)
                self.assertEqual(stream_req.status, 200)
                for _ in range(10):
                    line = stream_req.readline().decode("utf-8")
                    if "event: otp" in line:
                        data_line = stream_req.readline().decode("utf-8")
                        payload = json.loads(data_line[6:].strip())
                        self.assertEqual(payload["code"], "273529")
                        break
                stream_req.close()
            finally:
                custom_server.shutdown()
                custom_server.server_close()

    def test_e2e_failed_code_anti_loop_and_recovery(self):
        """
        Full End-to-End verification of the anti-loop fix:
        1. Code 913626 exists in SQLite and is returned on first call.
        2. Client submits, Bandwagon reloads with ?incorrect=true.
        3. Client queries /api/otp with exclude_codes=913626 -> Daemon returns success=False.
        4. Fresh code 855329 arrives in mailbox -> Daemon returns success=True with 855329.
        5. SSE stream with exclude_codes=913626 delivers 855329 without looping on 913626.
        """
        import tempfile
        import os
        from spark_otp.spark_client import SparkClient
        from tests.test_sqlite_backend import create_mock_spark_sqlite, insert_mock_message

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "messages.sqlite")
            create_mock_spark_sqlite(db_path)
            now = datetime.now()
            ts_now = int(now.timestamp())

            # 1. Old code that failed on Bandwagon
            insert_mock_message(
                db_path,
                pk=721537,
                sender="Bandwagon Host <noreply@64clouds.com>",
                recipient="dev.team@acme-cloud.net",
                subject="Device verification",
                short_body="Your device verification code: 913626. It is valid for 1 hour.",
                received_ts=ts_now - 60
            )

            sqlite_client = SparkClient(sqlite_path=db_path, spark_bin="/usr/bin/false")
            server = create_server(host="127.0.0.1", port=0, client=sqlite_client)
            port = server.server_address[1]
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            try:
                # 1. Initial query: returns 913626
                url_initial = f"http://127.0.0.1:{port}/api/otp?domain=bandwagonhost.com&account=dev.team@acme-cloud.net"
                req1 = urllib.request.urlopen(url_initial)
                data1 = json.loads(req1.read().decode("utf-8"))
                self.assertTrue(data1["success"])
                self.assertEqual(data1["otp"]["code"], "913626")

                # 2. Client rejected 913626 after page reloaded with ?incorrect=true.
                # Query with exclude_codes and exclude_message_ids:
                url_excluded = (
                    f"http://127.0.0.1:{port}/api/otp?"
                    f"domain=bandwagonhost.com&account=dev.team@acme-cloud.net&"
                    f"exclude_codes=913626&exclude_message_ids=721537&since_time={ts_now - 30}"
                )
                req2 = urllib.request.urlopen(url_excluded)
                data2 = json.loads(req2.read().decode("utf-8"))
                # Anti-loop check: Must NOT return the rejected code!
                self.assertFalse(data2["success"], "Daemon must not return excluded failed code")

                # 3. New email arrives with fresh code 855329
                insert_mock_message(
                    db_path,
                    pk=721538,
                    sender="Bandwagon Host <noreply@64clouds.com>",
                    recipient="dev.team@acme-cloud.net",
                    subject="Device verification",
                    short_body="Your device verification code: 855329. It is valid for 1 hour.",
                    received_ts=ts_now - 5
                )

                # Query again with exclude_codes: must recover and return 855329
                req3 = urllib.request.urlopen(url_excluded)
                data3 = json.loads(req3.read().decode("utf-8"))
                self.assertTrue(data3["success"], "Daemon must return new fresh code")
                self.assertEqual(data3["otp"]["code"], "855329")
                self.assertEqual(data3["otp"]["message_id"], "721538")

                # 4. Test SSE stream with exclude_codes: delivers 855329
                stream_url = (
                    f"http://127.0.0.1:{port}/api/stream?"
                    f"domain=bandwagonhost.com&account=dev.team@acme-cloud.net&"
                    f"exclude_codes=913626&exclude_message_ids=721537"
                )
                stream_req = urllib.request.urlopen(stream_url, timeout=5)
                self.assertEqual(stream_req.status, 200)
                received_code = None
                for _ in range(10):
                    line = stream_req.readline().decode("utf-8")
                    if "event: otp" in line:
                        data_line = stream_req.readline().decode("utf-8")
                        payload = json.loads(data_line[6:].strip())
                        received_code = payload["code"]
                        break
                stream_req.close()
                self.assertEqual(received_code, "855329", "SSE must stream the fresh code, skipping excluded code")

            finally:
                server.shutdown()
                server.server_close()

if __name__ == "__main__":
    unittest.main()

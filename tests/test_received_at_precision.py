"""
F-OTP-2 regression: the daemon/client must return second-precision `received_at`.

Root cause: the `fetch_thread()` full-thread fallback text carries a minute-granular
`Date:` line; an OTPResult built from that text reported `received_at` truncated to
`:00`. The race guard compares `received_at` against the login-request lower bound, so a
fresh code received later in the same minute (e.g. bound 21:12:21, code 21:12:50 ->
21:12:00) would be misclassified as stale and never submitted.

The database row is the timing SSOT: every OTPResult produced from a SQLite / Apple Mail
row must be stamped with `datetime.fromtimestamp(row_received_ts)`.
"""
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request
from datetime import datetime

from spark_otp.server import create_server
from spark_otp.spark_client import SparkClient
from tests.test_sqlite_backend import create_mock_spark_sqlite, insert_mock_message

NOW = datetime(2026, 11, 13, 21, 12, 21)          # login-request lower bound instant
RECEIVED_TS = int(datetime(2026, 11, 13, 21, 11, 56).timestamp())  # :56 seconds


class TestReceivedAtPrecision(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "messages.sqlite")
        create_mock_spark_sqlite(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _client(self):
        return SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")

    def _insert_full_body_message(self):
        insert_mock_message(
            self.db_path,
            pk=740001,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="dev.team@example.com",
            subject="Device verification",
            short_body="Your device verification code: 334455. It is valid for 1 hour.",
            received_ts=RECEIVED_TS,
        )

    def _insert_truncated_body_message(self):
        # shortBody is truncated before the code -> forces the fetch_thread() fallback,
        # whose thread text Date line is minute-granular (":00").
        insert_mock_message(
            self.db_path,
            pk=740002,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="dev.team@example.com",
            subject="Device verification",
            short_body="Your device verification code:",
            received_ts=RECEIVED_TS,
        )

    def test_short_body_hit_keeps_second_precision(self):
        """Direct shortBody hit must return the DB row's :56 seconds."""
        self._insert_full_body_message()
        client = self._client()
        otp = client.get_latest_otp(domain="bandwagonhost.com", allow_expired=True, now=NOW, max_age_seconds=600)
        self.assertIsNotNone(otp)
        self.assertIn("21:11:56", otp.received_at, f"received_at lost DB precision: {otp.received_at}")
        self.assertEqual(otp.message_id, "740001")
        # expires_at must be re-derived from received_at + TTL, keeping second precision
        exp = datetime.fromisoformat(otp.expires_at)
        rec = datetime.fromisoformat(otp.received_at)
        self.assertEqual((exp - rec).total_seconds(), 3600.0)

    def test_full_thread_fallback_uses_db_timestamp_not_minute_parse(self):
        """fetch_thread fallback (minute-granular Date line) must still return :56 from the DB row."""
        self._insert_truncated_body_message()
        client = self._client()
        client.fetch_thread = lambda message_id: (
            f"ID: {message_id}\nSubject: Device verification\n"
            "From: Bandwagon Host <noreply@64clouds.com>\n"
            "To: dev.team@example.com\n"
            "Date: 2026-11-13 21:11\n\n"
            "Your device verification code: 445566. It is valid for 1 hour.\n"
        )
        otp = client.get_latest_otp(domain="bandwagonhost.com", allow_expired=True, now=NOW, max_age_seconds=600)
        self.assertIsNotNone(otp)
        self.assertEqual(otp.code, "445566")
        self.assertIn("21:11:56", otp.received_at, f"fetch_thread fallback kept minute-truncated date: {otp.received_at}")
        self.assertNotIn("21:11:00", otp.received_at)
        self.assertEqual(otp.message_id, "740002")

    def test_api_otp_endpoint_keeps_second_precision(self):
        """GET /api/otp must expose the DB-authoritative :56 seconds (the GO-3 real-machine check)."""
        self._insert_truncated_body_message()
        client = self._client()
        client.fetch_thread = lambda message_id: (
            f"ID: {message_id}\nSubject: Device verification\n"
            "From: Bandwagon Host <noreply@64clouds.com>\n"
            "To: dev.team@example.com\n"
            "Date: 2026-11-13 21:11\n\n"
            "Your device verification code: 445566. It is valid for 1 hour.\n"
        )
        server = create_server(host="127.0.0.1", port=0, client=client)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            time.sleep(0.1)
            url = f"http://127.0.0.1:{port}/api/otp?domain=bandwagonhost.com&allow_expired=1&max_age=600"
            with urllib.request.urlopen(url) as r:
                self.assertEqual(r.getcode(), 200)
                data = json.loads(r.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            received = data["otp"]["received_at"]
            self.assertIn("21:11:56", received, f"/api/otp lost DB precision: {received}")
            self.assertEqual(data["otp"]["message_id"], "740002")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

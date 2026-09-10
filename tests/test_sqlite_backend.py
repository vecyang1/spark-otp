"""
Tests for Spark Desktop SQLite Direct Fast-Path Backend.
Verifies sub-millisecond retrieval, account prioritization, and multi-code handling.
"""
import unittest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from spark_otp.spark_client import SparkClient
from spark_otp.config import config

def create_mock_spark_sqlite(db_path: str):
    """Create a minimal SQLite schema mimicking Spark Desktop's messages table."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE messages (
            pk INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            accountPk INTEGER NOT NULL,
            userPk INTEGER NOT NULL DEFAULT 0,
            messageType INTEGER NOT NULL DEFAULT 0,
            creationDate INTEGER NOT NULL DEFAULT 0,
            receivedDate INTEGER NOT NULL,
            messageFrom TEXT,
            messageTo TEXT,
            subject TEXT,
            shortBody TEXT,
            unseen INTEGER NOT NULL DEFAULT 1,
            inInbox INTEGER NOT NULL DEFAULT 1,
            flags INTEGER NOT NULL DEFAULT 0,
            category INTEGER NOT NULL DEFAULT 2
        )
    """)
    conn.commit()
    conn.close()

def insert_mock_message(db_path: str, pk: int, sender: str, recipient: str, subject: str, short_body: str, received_ts: int):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        INSERT INTO messages (pk, accountPk, receivedDate, messageFrom, messageTo, subject, shortBody)
        VALUES (?, 1, ?, ?, ?, ?, ?)
    """, (pk, received_ts, sender, recipient, subject, short_body))
    conn.commit()
    conn.close()

class TestSparkSqliteBackend(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "messages.sqlite")
        create_mock_spark_sqlite(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sqlite_fastpath_extraction_bandwagon(self):
        """Verify that SparkClient reads directly from SQLite and extracts 273529."""
        now = datetime.now()
        ts_now = int(now.timestamp())
        insert_mock_message(
            self.db_path,
            pk=721280,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="alex.turner@example.com",
            subject="Device verification",
            short_body="Your device verification code: 273529. It is valid for 1 hour. Do NOT share this code with anyone.",
            received_ts=ts_now - 120  # 2 minutes ago
        )

        client = SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")
        otp = client.get_latest_otp(domain="bandwagonhost.com", now=now)
        self.assertIsNotNone(otp, "Must extract OTP from SQLite")
        self.assertEqual(otp.code, "273529")
        self.assertEqual(otp.service, "bandwagon_auth")
        self.assertEqual(otp.message_id, "721280")

    def test_sqlite_account_prioritization(self):
        """Verify that when account=alex.turner@example.com is requested, that account's message is prioritized."""
        now = datetime.now()
        ts_now = int(now.timestamp())

        # Email for dev.team received 30 seconds ago (newer)
        insert_mock_message(
            self.db_path,
            pk=721275,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="dev.team@acme-cloud.net",
            subject="Device verification",
            short_body="Your device verification code: 111222. It is valid for 1 hour.",
            received_ts=ts_now - 30
        )

        # Email for alex.turner received 60 seconds ago
        insert_mock_message(
            self.db_path,
            pk=721280,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="alex.turner@example.com",
            subject="Device verification",
            short_body="Your device verification code: 273529. It is valid for 1 hour.",
            received_ts=ts_now - 60
        )

        client = SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")

        # Query specifying alex.turner@example.com
        otp_yang = client.get_latest_otp(domain="bandwagonhost.com", account="alex.turner@example.com", now=now)
        self.assertIsNotNone(otp_yang)
        self.assertEqual(otp_yang.code, "273529", "Must prioritize alex.turner message")

        # Query specifying dev.team@acme-cloud.net
        otp_fly = client.get_latest_otp(domain="bandwagonhost.com", account="dev.team@acme-cloud.net", now=now)
        self.assertIsNotNone(otp_fly)
        self.assertEqual(otp_fly.code, "111222", "Must prioritize dev.team message")

    def test_sqlite_account_fallback_when_not_in_requested_account(self):
        """Verify that if account=dev.team@acme-cloud.net is requested but OTP only arrived in alex.turner, it gracefully returns alex.turner's OTP."""
        now = datetime.now()
        ts_now = int(now.timestamp())

        insert_mock_message(
            self.db_path,
            pk=721280,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="alex.turner@example.com",
            subject="Device verification",
            short_body="Your device verification code: 875358. It is valid for 1 hour.",
            received_ts=ts_now - 60
        )

        client = SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")
        otp = client.get_latest_otp(domain="bandwagonhost.com", account="dev.team@acme-cloud.net", now=now)
        self.assertIsNotNone(otp, "Should fallback to check all accounts if requested account has no match")
        self.assertEqual(otp.code, "875358")

    def test_sqlite_expired_otp_rejection(self):
        """Verify that OTP older than TTL is rejected."""
        now = datetime.now()
        ts_now = int(now.timestamp())

        # Bandwagon OTP received 75 minutes ago (TTL is 3600s = 60 minutes)
        insert_mock_message(
            self.db_path,
            pk=721200,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="alex.turner@example.com",
            subject="Device verification",
            short_body="Your device verification code: 999888. It is valid for 1 hour.",
            received_ts=ts_now - 4500
        )

        client = SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")
        otp = client.get_latest_otp(domain="bandwagonhost.com", now=now)
        self.assertIsNone(otp, "Expired OTP (75 min > 60 min TTL) must be rejected")

    def test_sqlite_upper_bound_future_rejection(self):
        """Verify that emails received in the future (>30s) relative to 'now' are rejected."""
        now = datetime(2026, 9, 8, 21, 38, 0)
        ts_now = int(now.timestamp())

        # Email arrives 10 minutes in the future relative to 'now'
        insert_mock_message(
            self.db_path,
            pk=721303,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="alex.turner@example.com",
            subject="Device verification",
            short_body="Your device verification code: 856968. It is valid for 1 hour.",
            received_ts=ts_now + 600
        )

        client = SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")
        otp = client.get_latest_otp(domain="bandwagonhost.com", now=now)
        self.assertIsNone(otp, "Future email must not be returned when evaluating at past time")

    def test_sqlite_recency_aware_fallback(self):
        """Verify that a fresh OTP in alex.turner takes precedence over a 40-minute-old OTP in dev.team."""
        now = datetime.now()
        ts_now = int(now.timestamp())

        # Stale email for dev.team received 40 minutes ago (still within 60 min TTL)
        insert_mock_message(
            self.db_path,
            pk=721200,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="dev.team@acme-cloud.net",
            subject="Device verification",
            short_body="Your device verification code: 111222. It is valid for 1 hour.",
            received_ts=ts_now - 2400
        )

        # Fresh email for alex.turner received 15 seconds ago
        insert_mock_message(
            self.db_path,
            pk=721280,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="alex.turner@example.com",
            subject="Device verification",
            short_body="Your device verification code: 273529. It is valid for 1 hour.",
            received_ts=ts_now - 15
        )

        client = SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")
        otp = client.get_latest_otp(domain="bandwagonhost.com", account="dev.team@acme-cloud.net", now=now)
        self.assertIsNotNone(otp)
        self.assertEqual(otp.code, "273529", "Fresh OTP from alex.turner must override stale 40-minute-old OTP from dev.team")

    def test_sqlite_real_host_historical_screenshot_codes(self):
        """Verify that Spark SQLite backend extracts historical codes (875358 and 273529)."""
        t_937 = datetime(2026, 9, 8, 21, 37, 30)
        insert_mock_message(
            self.db_path,
            pk=721270,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="alex.turner@example.com",
            subject="Device verification",
            short_body="Your device verification code: 875358. It is valid for 1 hour.",
            received_ts=int(t_937.timestamp()) - 25
        )
        t_938 = datetime(2026, 9, 8, 21, 39, 0)
        insert_mock_message(
            self.db_path,
            pk=721280,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="alex.turner@example.com",
            subject="Device verification",
            short_body="Your device verification code: 273529. It is valid for 1 hour.",
            received_ts=int(t_938.timestamp()) - 36
        )
        client = SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")

        otp_937 = client.get_latest_otp(domain="bandwagonhost.com", account="alex.turner@example.com", now=t_937)
        self.assertIsNotNone(otp_937)
        self.assertEqual(otp_937.code, "875358")

        otp_938 = client.get_latest_otp(domain="bandwagonhost.com", account="alex.turner@example.com", now=t_938)
        self.assertIsNotNone(otp_938)
        self.assertEqual(otp_938.code, "273529")

    def test_sqlite_exclude_codes_and_message_ids(self):
        """Verify that exclude_codes and exclude_message_ids bypass rejected codes."""
        now = datetime.now()
        ts_now = int(now.timestamp())

        # Bad code (913626) from 30s ago
        insert_mock_message(
            self.db_path,
            pk=721537,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="dev.team@acme-cloud.net",
            subject="Device verification",
            short_body="Your device verification code: 913626. It is valid for 1 hour.",
            received_ts=ts_now - 30
        )

        # Older good code (855329) from 90s ago
        insert_mock_message(
            self.db_path,
            pk=721530,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="dev.team@acme-cloud.net",
            subject="Device verification",
            short_body="Your device verification code: 855329. It is valid for 1 hour.",
            received_ts=ts_now - 90
        )

        client = SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")

        # Without exclusion, newest code 913626 is returned
        otp_default = client.get_latest_otp(domain="bandwagonhost.com", now=now)
        self.assertIsNotNone(otp_default)
        self.assertEqual(otp_default.code, "913626")

        # With exclude_codes=["913626"], 913626 is bypassed and older 855329 is returned
        otp_excluded = client.get_latest_otp(domain="bandwagonhost.com", exclude_codes=["913626"], now=now)
        self.assertIsNotNone(otp_excluded)
        self.assertEqual(otp_excluded.code, "855329")

        # With exclude_message_ids=["721537"], same bypass occurs
        otp_msg_excluded = client.get_latest_otp(domain="bandwagonhost.com", exclude_message_ids=["721537"], now=now)
        self.assertIsNotNone(otp_msg_excluded)
        self.assertEqual(otp_msg_excluded.code, "855329")

        # When all codes are excluded, None is returned
        otp_none = client.get_latest_otp(domain="bandwagonhost.com", exclude_codes=["913626", "855329"], now=now)
        self.assertIsNone(otp_none)

    def test_sqlite_since_time_filter(self):
        """Verify that since_time only returns messages newer than the given timestamp."""
        now = datetime.now()
        ts_now = int(now.timestamp())

        insert_mock_message(
            self.db_path,
            pk=721540,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="dev.team@acme-cloud.net",
            subject="Device verification",
            short_body="Your device verification code: 334455. It is valid for 1 hour.",
            received_ts=ts_now - 100
        )

        client = SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")

        # since_time is after the message arrival -> returns None
        otp = client.get_latest_otp(domain="bandwagonhost.com", since_time=ts_now - 50, now=now)
        self.assertIsNone(otp)

        # since_time is before the message arrival -> returns 334455
        otp2 = client.get_latest_otp(domain="bandwagonhost.com", since_time=ts_now - 150, now=now)
        self.assertIsNotNone(otp2)
        self.assertEqual(otp2.code, "334455")

if __name__ == "__main__":
    unittest.main()

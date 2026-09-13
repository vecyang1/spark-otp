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
from tests.fixtures import REAL_SAKURA_INTERNET_EMAIL

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
            recipient="dev.team@example.com",
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

        # Query specifying dev.team@example.com
        otp_fly = client.get_latest_otp(domain="bandwagonhost.com", account="dev.team@example.com", now=now)
        self.assertIsNotNone(otp_fly)
        self.assertEqual(otp_fly.code, "111222", "Must prioritize dev.team message")

    def test_sqlite_account_fallback_when_not_in_requested_account(self):
        """Verify that if account=dev.team@example.com is requested but OTP only arrived in alex.turner, it gracefully returns alex.turner's OTP."""
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
        otp = client.get_latest_otp(domain="bandwagonhost.com", account="dev.team@example.com", now=now)
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
        self.assertIsNone(otp, "Expired OTP (75 min > 60 min TTL) must be rejected by default")

        # When fallback_expired=True, it gracefully returns the expired code flagged as expired
        otp_fallback = client.get_latest_otp(domain="bandwagonhost.com", now=now, fallback_expired=True)
        self.assertIsNotNone(otp_fallback)
        self.assertEqual(otp_fallback.code, "999888")
        self.assertTrue(otp_fallback.is_expired)
        self.assertEqual(otp_fallback.time_remaining_seconds, 0)

        # When allow_expired=True, it also returns the expired code
        otp_allowed = client.get_latest_otp(domain="bandwagonhost.com", now=now, allow_expired=True)
        self.assertIsNotNone(otp_allowed)
        self.assertEqual(otp_allowed.code, "999888")
        self.assertTrue(otp_allowed.is_expired)

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
            recipient="dev.team@example.com",
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
        otp = client.get_latest_otp(domain="bandwagonhost.com", account="dev.team@example.com", now=now)
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
            recipient="dev.team@example.com",
            subject="Device verification",
            short_body="Your device verification code: 913626. It is valid for 1 hour.",
            received_ts=ts_now - 30
        )

        # Older good code (855329) from 90s ago
        insert_mock_message(
            self.db_path,
            pk=721530,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="dev.team@example.com",
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
            recipient="dev.team@example.com",
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

    def test_sqlite_truncated_short_body_triggers_fetch_thread(self):
        """Verify that when shortBody is truncated before the OTP (like Sakura CoreData),
        domain_matches triggers fetch_thread and successfully extracts the OTP."""
        now = datetime.now()
        ts_now = int(now.timestamp())

        # Exact truncated shortBody from Sakura Internet CoreData SQLite
        truncated_body = (
            "-------------------------------------------------------- "
            "本メールにお心あたりのない場合は、他の方が誤ってメールアドレスを "
            "入力した可能性がございますので、お見捨ておきください。 "
            "-------------------------------------------------------- "
            "さくらインターネットの会員登録をお申込みいただき、誠にありがとうございます。 "
            "メールアドレスの確認ページで、以下6桁の認証コードを入力してください。 "
        )

        insert_mock_message(
            self.db_path,
            pk=722910,
            sender='さくらインターネット <support@sakura.ad.jp>',
            recipient='user@example.com',
            subject='[さくらインターネット]認証コード入力と会員情報登録のお願い',
            short_body=truncated_body,
            received_ts=ts_now - 60
        )

        client = SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")

        # Mock fetch_thread to return the full thread text containing the code
        full_email_text = REAL_SAKURA_INTERNET_EMAIL.format(
            date_str=now.strftime("%Y-%m-%d %H:%M:%S")
        )
        fetch_thread_called = []

        def mock_fetch_thread(msg_id):
            fetch_thread_called.append(msg_id)
            return full_email_text if msg_id == "722910" else ""

        client.fetch_thread = mock_fetch_thread

        otp = client.get_latest_otp(domain="secure.sakura.ad.jp", account="user@example.com", now=now)
        self.assertIsNotNone(otp, "Must extract OTP by falling back to fetch_thread when shortBody is truncated")
        self.assertEqual(otp.code, "945521")
        self.assertEqual(otp.service, "sakura_internet")
        self.assertEqual(otp.message_id, "722910")
        self.assertIn("722910", fetch_thread_called, "fetch_thread must be invoked when shortBody is truncated")

    def test_sqlite_sakura_with_full_short_body(self):
        """Verify that when shortBody contains the full text including OTP, it extracts without fetch_thread."""
        now = datetime.now()
        ts_now = int(now.timestamp())

        body_with_code = (
            "さくらインターネットの会員登録をお申込みいただき、誠にありがとうございます。\n"
            "※このコードの有効期限は、本メールが送信されてから30分間です。\n"
            "認証コード：945521\n"
        )
        insert_mock_message(
            self.db_path,
            pk=722911,
            sender='さくらインターネット <support@sakura.ad.jp>',
            recipient='user@example.com',
            subject='[さくらインターネット]認証コード入力と会員情報登録のお願い',
            short_body=body_with_code,
            received_ts=ts_now - 60
        )

        client = SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")
        fetch_thread_called = []
        client.fetch_thread = lambda msg_id: fetch_thread_called.append(msg_id) or ""

        otp = client.get_latest_otp(domain="secure.sakura.ad.jp", account="user@example.com", now=now)
        self.assertIsNotNone(otp)
        self.assertEqual(otp.code, "945521")
        self.assertEqual(otp.service, "sakura_internet")
        self.assertEqual(len(fetch_thread_called), 0, "fetch_thread should not be called if shortBody has code")

    def test_sqlite_unrelated_domain_truncated_short_body_does_not_fetch_thread(self):
        """Adversarial check: Unrelated domain must not trigger fetch_thread for Sakura email."""
        now = datetime.now()
        ts_now = int(now.timestamp())

        truncated_body = "メールアドレスの確認ページで、以下6桁の認証コードを入力してください。"
        insert_mock_message(
            self.db_path,
            pk=722912,
            sender='さくらインターネット <support@sakura.ad.jp>',
            recipient='user@example.com',
            subject='[さくらインターネット]認証コード入力と会員情報登録のお願い',
            short_body=truncated_body,
            received_ts=ts_now - 60
        )

        client = SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")
        fetch_thread_called = []
        client.fetch_thread = lambda msg_id: fetch_thread_called.append(msg_id) or ""

        # Query for an unrelated domain
        otp = client.get_latest_otp(domain="evil-phishing.com", now=now)
        self.assertIsNone(otp)
        self.assertEqual(len(fetch_thread_called), 0, "fetch_thread must NOT be invoked for mismatched domain")

    def test_sqlite_sakura_truncated_short_body_fetches_thread_when_domain_is_none(self):
        """When domain is None, truncated short body with OTP intent must trigger fetch_thread."""
        now = datetime.now()
        ts_now = int(now.timestamp())
        dt_str = now.strftime("%Y-%m-%d %H:%M:%S")

        truncated_body = "メールアドレスの確認ページで、以下6桁の認証コードを入力してください。"
        insert_mock_message(
            self.db_path,
            pk=722913,
            sender='さくらインターネット <support@sakura.ad.jp>',
            recipient='user@example.com',
            subject='[さくらインターネット]認証コード入力と会員情報登録のお願い',
            short_body=truncated_body,
            received_ts=ts_now - 60
        )

        full_thread_content = f"""
ID: 722913
Subject: [さくらインターネット]認証コード入力と会員情報登録のお願い
From: さくらインターネット <support@sakura.ad.jp>
To: user@example.com
Date: {dt_str}

メールアドレスの確認ページで、以下6桁の認証コードを入力してください。

認証コード：945521
有効期限は、本メールが送信されてから30分間です。
"""
        client = SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")
        fetch_thread_called = []
        client.fetch_thread = lambda msg_id: fetch_thread_called.append(msg_id) or full_thread_content

        otp = client.get_latest_otp(domain=None, now=now)
        self.assertIsNotNone(otp)
        self.assertEqual(otp.code, "945521")
        self.assertEqual(fetch_thread_called, ["722913"], "fetch_thread must be invoked when domain is None and OTP intent matches")

    def test_sqlite_non_otp_email_does_not_fetch_thread(self):
        """Adversarial check: Non-OTP emails (e.g. registration complete) must NOT trigger fetch_thread."""
        now = datetime.now()
        ts_now = int(now.timestamp())

        insert_mock_message(
            self.db_path,
            pk=722914,
            sender='さくらインターネット <support@sakura.ad.jp>',
            recipient='user@example.com',
            subject='会員登録完了のお知らせ [icc75482]',
            short_body='この度は、さくらインターネットの会員にご登録をいただき、誠にありがとうございます。',
            received_ts=ts_now - 30
        )

        client = SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")
        fetch_thread_called = []
        client.fetch_thread = lambda msg_id: fetch_thread_called.append(msg_id) or ""

        otp = client.get_latest_otp(domain="secure.sakura.ad.jp", now=now)
        self.assertIsNone(otp)
        self.assertEqual(len(fetch_thread_called), 0, "fetch_thread must NOT be invoked for non-OTP messages")

if __name__ == "__main__":
    unittest.main()

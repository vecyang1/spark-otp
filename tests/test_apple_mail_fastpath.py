"""
Unit and integration tests for Apple Mail Envelope Index SQLite Fast-Path in Spark OTP.
"""
import os
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from spark_otp.spark_client import SparkClient
from spark_otp.config import Config, RuleDefinition


class TestAppleMailFastPath(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.mock_db_path = self.tmp_path / "Envelope Index"
        self._init_mock_envelope_index(self.mock_db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _init_mock_envelope_index(self, db_path: Path):
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE mailboxes (
                    ROWID INTEGER PRIMARY KEY,
                    url TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE addresses (
                    ROWID INTEGER PRIMARY KEY,
                    address TEXT,
                    comment TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE subjects (
                    ROWID INTEGER PRIMARY KEY,
                    subject TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE summaries (
                    ROWID INTEGER PRIMARY KEY,
                    summary TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE recipients (
                    ROWID INTEGER PRIMARY KEY,
                    message INTEGER,
                    address INTEGER,
                    type INTEGER
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE messages (
                    ROWID INTEGER PRIMARY KEY,
                    mailbox INTEGER,
                    sender INTEGER,
                    subject INTEGER,
                    summary INTEGER,
                    date_received REAL,
                    read INTEGER
                )
                """
            )
            conn.commit()

    def test_find_apple_mail_db(self):
        client = SparkClient(apple_mail_path=str(self.mock_db_path))
        found = client._find_apple_mail_sqlite_db()
        self.assertEqual(found, self.mock_db_path)

    def test_extract_otp_from_apple_mail_mock(self):
        now_ts = time.time()
        with sqlite3.connect(self.mock_db_path) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO mailboxes VALUES (1, 'imap://UUID-EXAMPLE/INBOX')")
            cur.execute("INSERT INTO addresses VALUES (1, 'noreply@accounts.google.com', 'Google')")
            cur.execute("INSERT INTO addresses VALUES (2, 'marketing@example.com', 'Marketing')")
            cur.execute("INSERT INTO subjects VALUES (1, 'Verify your email address')")
            cur.execute("INSERT INTO summaries VALUES (1, 'Use this code to verify your email address: 928371.')")
            cur.execute("INSERT INTO messages VALUES (101, 1, 1, 1, 1, ?, 0)", (now_ts,))
            cur.execute("INSERT INTO recipients VALUES (1, 101, 2, 0)")
            conn.commit()

        client = SparkClient(spark_bin="disabled", sqlite_path="disabled", apple_mail_path=str(self.mock_db_path))
        res = client.get_latest_otp(domain="google.com")
        self.assertIsNotNone(res)
        self.assertEqual(res.code, "928371")
        self.assertEqual(res.message_id, "101")
        self.assertEqual(res.service, "google_auth")

    def test_cascade_spark_to_apple_mail(self):
        """When Spark SQLite has no matching message, it cascades to Apple Mail SQLite."""
        mock_spark_db = self.tmp_path / "messages.sqlite"
        with sqlite3.connect(mock_spark_db) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE messages (
                    pk INTEGER PRIMARY KEY,
                    messageFrom TEXT,
                    messageTo TEXT,
                    subject TEXT,
                    shortBody TEXT,
                    receivedDate REAL,
                    unseen INTEGER
                )
                """
            )
            # Empty Spark DB (or unrelated messages)
            conn.commit()

        # Seed Apple Mail with fresh AWS code
        now_ts = time.time()
        with sqlite3.connect(self.mock_db_path) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO mailboxes VALUES (1, 'imap://UUID-EXAMPLE-2/INBOX')")
            cur.execute("INSERT INTO addresses VALUES (1, 'no-reply-aws@amazon.com', 'AWS')")
            cur.execute("INSERT INTO addresses VALUES (2, 'user@example.com', 'User')")
            cur.execute("INSERT INTO subjects VALUES (1, 'Amazon Web Services Verification Code')")
            cur.execute("INSERT INTO summaries VALUES (1, 'Your verification code is 654321.')")
            cur.execute("INSERT INTO messages VALUES (202, 1, 1, 1, 1, ?, 0)", (now_ts,))
            cur.execute("INSERT INTO recipients VALUES (1, 202, 2, 0)")
            conn.commit()

        client = SparkClient(sqlite_path=str(mock_spark_db), apple_mail_path=str(self.mock_db_path))
        res = client.get_latest_otp(domain="aws.amazon.com")
        self.assertIsNotNone(res)
        self.assertEqual(res.code, "654321")
        self.assertEqual(res.message_id, "202")

    def test_exclude_codes_and_since_time(self):
        now_ts = time.time()
        with sqlite3.connect(self.mock_db_path) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO mailboxes VALUES (1, 'imap://UUID-1/INBOX')")
            cur.execute("INSERT INTO addresses VALUES (1, 'noreply@github.com', 'GitHub')")
            cur.execute("INSERT INTO addresses VALUES (2, 'user@example.com', 'User')")
            cur.execute("INSERT INTO subjects VALUES (1, 'GitHub verification code')")
            cur.execute("INSERT INTO summaries VALUES (1, 'Your verification code is 112233.')")
            cur.execute("INSERT INTO messages VALUES (301, 1, 1, 1, 1, ?, 0)", (now_ts - 50,))
            cur.execute("INSERT INTO recipients VALUES (1, 301, 2, 0)")
            conn.commit()

        client = SparkClient(spark_bin="disabled", sqlite_path="disabled", apple_mail_path=str(self.mock_db_path))

        # Excluded code test
        res_excluded = client.get_latest_otp(domain="github.com", exclude_codes=["112233"])
        self.assertIsNone(res_excluded)

        # Excluded message id test
        res_id_excluded = client.get_latest_otp(domain="github.com", exclude_message_ids=["301"])
        self.assertIsNone(res_id_excluded)

        # since_time test (message older than since_time)
        res_stale = client.get_latest_otp(domain="github.com", since_time=now_ts - 10)
        self.assertIsNone(res_stale)


if __name__ == "__main__":
    unittest.main()

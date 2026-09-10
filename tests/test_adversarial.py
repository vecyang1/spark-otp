"""
Two-Sided Adversarial Verification Test Suite for Spark OTP.
"测遍了不会说谎的那一半，也要测遍会说谎的那一半"
Tests both legitimate paths and adversarial challenges, edge cases,
malformed inputs, false-friend form fields, expired tokens, and stress scenarios.
"""
import unittest
import json
import subprocess
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from spark_otp.extractor import (
    extract_otp_from_thread,
    extract_universal_otp,
    domain_matches
)
from spark_otp.spark_client import SparkClient
from spark_otp.server import create_server
from spark_otp.models import OTPResult

# Adversarial mock threads
SHIPMENT_TRACKING_EMAIL = """
ID: 881021
Subject: Your package is on the way!
From: FedEx Express <tracking@fedex.com>
To: dev.team@acme-cloud.net
Date: {date_str}
Type: Email

Hello, your package with tracking number 849201 has been dispatched.
Delivery is scheduled by end of day tomorrow.
"""

INVOICE_RECEIPT_EMAIL = """
ID: 881022
Subject: Your invoice for Cloud Services
From: Billing Dept <billing@cloudservice.com>
To: dev.team@acme-cloud.net
Date: {date_str}
Type: Email

Thank you for your business. Invoice # 918234 has been processed.
Total amount charged: $49.00 USD.
"""

EXPIRED_BANDWAGON_EMAIL = """
ID: 720000
Subject: Device verification
From: Bandwagon Host <noreply@64clouds.com>
To: dev.team@acme-cloud.net
Date: {date_str}
Type: Email

Your device verification code: 382910. It is valid for 1 hour. Do NOT share this code with anyone.
"""

EXPIRED_STANDARD_EMAIL = """
ID: 720001
Subject: Your GitHub verification code
From: GitHub <support@github.com>
To: dev.team@acme-cloud.net
Date: {date_str}
Type: Email

Verification code: 519283. This code expires in 10 minutes.
"""

class TestAdversarialEmails(unittest.TestCase):
    """Verify that false-friend emails (tracking numbers, invoices) and expired codes are strictly rejected."""

    def test_reject_shipment_tracking_number(self):
        """A tracking number in a delivery email must NEVER be extracted as an OTP."""
        now = datetime(2026, 9, 8, 20, 0)
        date_str = (now - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M")
        raw = SHIPMENT_TRACKING_EMAIL.format(date_str=date_str)
        result = extract_otp_from_thread(raw, domain_filter="fedex.com", now=now)
        self.assertIsNone(result, "Tracking number must not be recognized as OTP")

    def test_reject_invoice_receipt_number(self):
        """An invoice number in a billing email must NEVER be extracted as an OTP."""
        now = datetime(2026, 9, 8, 20, 0)
        date_str = (now - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M")
        raw = INVOICE_RECEIPT_EMAIL.format(date_str=date_str)
        result = extract_otp_from_thread(raw, domain_filter="cloudservice.com", now=now)
        self.assertIsNone(result, "Invoice number must not be recognized as OTP")

    def test_reject_expired_standard_otp(self):
        """A standard 10-minute OTP received 15 minutes ago must be rejected as expired."""
        now = datetime(2026, 9, 8, 20, 0)
        date_str = (now - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M")
        raw = EXPIRED_STANDARD_EMAIL.format(date_str=date_str)
        result = extract_otp_from_thread(raw, domain_filter="github.com", max_age_seconds=600, now=now)
        self.assertIsNone(result, "Standard OTP older than 10 minutes must be rejected")

    def test_reject_expired_bandwagon_otp(self):
        """A Bandwagon Host 1-hour OTP received 75 minutes ago must be rejected as expired."""
        now = datetime(2026, 9, 8, 21, 45)
        date_str = (now - timedelta(minutes=75)).strftime("%Y-%m-%d %H:%M")
        raw = EXPIRED_BANDWAGON_EMAIL.format(date_str=date_str)
        result = extract_otp_from_thread(raw, domain_filter="bawagon", max_age_seconds=600, now=now)
        self.assertIsNone(result, "Bandwagon OTP older than 1 hour (3600s) must be rejected")

    def test_accept_still_valid_bandwagon_otp_at_50_minutes(self):
        """A Bandwagon Host OTP received 50 minutes ago must STILL be accepted (under 3600s TTL)."""
        now = datetime(2026, 9, 8, 21, 24)
        date_str = (now - timedelta(minutes=50)).strftime("%Y-%m-%d %H:%M")
        raw = EXPIRED_BANDWAGON_EMAIL.format(date_str=date_str)
        result = extract_otp_from_thread(raw, domain_filter="bawagon", max_age_seconds=600, now=now)
        self.assertIsNotNone(result, "Bandwagon OTP received 50 min ago must remain valid")
        self.assertEqual(result.code, "382910")
        self.assertEqual(result.time_remaining_seconds, 10 * 60)


class TestAdversarialDomInputs(unittest.TestCase):
    """Verify that false-friend inputs (promo, captcha, password, search, zip) are disqualified."""

    def _eval_elements(self, elements_data):
        raw_template = r"""
        const fs = require('fs');
        const contentJs = fs.readFileSync('extension/content.js', 'utf8');
        const funcMatch = contentJs.match(/function isDisqualifiedInput\(el\) \{[\s\S]*?\n  \}/);
        if (!funcMatch) {
            console.error("isDisqualifiedInput not found");
            process.exit(1);
        }
        eval(funcMatch[0]);

        const elements = __ELEMENTS_JSON__;
        const results = elements.map(el => ({
            id: el.id || el.name,
            disqualified: isDisqualifiedInput({
                type: el.type || "text",
                name: el.name || "",
                id: el.id || "",
                placeholder: el.placeholder || "",
                getAttribute: (k) => el.attributes ? el.attributes[k] || null : null
            })
        }));
        console.log(JSON.stringify(results));
        """
        js_code = raw_template.replace("__ELEMENTS_JSON__", json.dumps(elements_data))
        proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, check=True)
        return json.loads(proc.stdout)

    def test_disqualify_promo_and_coupon_fields(self):
        """Promo, coupon, discount fields must be disqualified even if they contain the word 'code'."""
        elements = [
            {"id": "coupon", "name": "coupon_code", "placeholder": "Enter promo code"},
            {"id": "discount", "name": "discount", "placeholder": "Discount code"},
            {"id": "ref", "name": "referral_code", "placeholder": "Referral code"}
        ]
        res = self._eval_elements(elements)
        for item in res:
            self.assertTrue(item["disqualified"], f"{item['id']} must be disqualified")

    def test_disqualify_zip_and_postal_codes(self):
        """Zip code and postal code fields must be disqualified."""
        elements = [
            {"id": "zip", "name": "zip_code", "placeholder": "Postal / Zip Code"},
            {"id": "postal", "name": "postalCode", "placeholder": ""}
        ]
        res = self._eval_elements(elements)
        for item in res:
            self.assertTrue(item["disqualified"], f"{item['id']} must be disqualified")

    def test_disqualify_search_inputs(self):
        """Search boxes with 'code' in placeholder must be disqualified."""
        elements = [
            {"id": "search", "name": "q", "placeholder": "Search by product code or name..."}
        ]
        res = self._eval_elements(elements)
        self.assertTrue(res[0]["disqualified"], "Search box must be disqualified")

    def test_disqualify_captcha_inputs(self):
        """Captcha input boxes must be disqualified."""
        elements = [
            {"id": "captcha", "name": "captcha_code", "placeholder": "Enter captcha"}
        ]
        res = self._eval_elements(elements)
        self.assertTrue(res[0]["disqualified"], "Captcha box must be disqualified")

    def test_disqualify_password_change_inputs(self):
        """Password fields without OTP labels must be disqualified."""
        elements = [
            {"id": "old_pass", "type": "password", "name": "old_password", "placeholder": ""},
            {"id": "new_pass", "type": "password", "name": "new_password", "placeholder": ""}
        ]
        res = self._eval_elements(elements)
        for item in res:
            self.assertTrue(item["disqualified"], f"{item['id']} must be disqualified")


class TestAdversarialSparkClient(unittest.TestCase):
    """Verify that SparkClient handles corrupted output, timeouts, and edge cases gracefully."""

    @patch("subprocess.run")
    def test_spark_cli_locked_or_failing(self, mock_run):
        """When Spark CLI fails with non-zero exit code, SparkClient handles it gracefully without crashing."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error: Spark IPC locked")
        client = SparkClient(spark_bin="/usr/local/bin/spark", sqlite_path="disabled")
        otp = client.get_latest_otp(domain="bandwagonhost.com")
        self.assertIsNone(otp, "Should return None when Spark CLI command fails")

    @patch("subprocess.run")
    def test_spark_cli_garbled_output(self, mock_run):
        """When Spark CLI returns corrupt headers or binary noise, parser does not throw uncaught exceptions."""
        mock_run.return_value = MagicMock(returncode=0, stdout="\x00\x01\x02\nRandom text that has no table format")
        client = SparkClient(spark_bin="/usr/local/bin/spark", sqlite_path="disabled")
        accounts = client.get_accounts()
        self.assertEqual(accounts, [], "Should safely return empty list on malformed output")


class TestAdversarialServerAndConcurrency(unittest.TestCase):
    """Verify server resiliency under concurrent hammer requests and malformed parameters."""

    @classmethod
    def setUpClass(cls):
        class FastMockClient:
            def is_available(self):
                return True
            def get_accounts(self):
                return ["test@example.com"]
            def get_latest_otp(self, domain=None, max_age_seconds=None, account=None):
                return OTPResult(
                    code="998877",
                    service="mock_service",
                    domain=domain,
                    callback_url=None,
                    message_id="999",
                    subject="Test code",
                    sender="Auth <auth@example.com>",
                    received_at="2026-09-08T20:00:00",
                    expires_at="2026-09-08T20:10:00",
                    is_expired=False,
                    time_remaining_seconds=300
                )

        cls.client = FastMockClient()
        cls.server = create_server(host="127.0.0.1", port=0, client=cls.client)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_concurrent_api_requests(self):
        """Fire 30 concurrent requests to /api/otp; all 30 must return 200 OK with correct JSON."""
        errors = []
        results = []

        def worker():
            try:
                url = f"http://127.0.0.1:{self.port}/api/otp?domain=example.com"
                req = urllib.request.urlopen(url, timeout=3)
                data = json.loads(req.read().decode("utf-8"))
                if data.get("success") and data.get("otp", {}).get("code") == "998877":
                    results.append(True)
                else:
                    errors.append(f"Unexpected data: {data}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors occurred during concurrent load: {errors}")
        self.assertEqual(len(results), 30, "All 30 concurrent requests must succeed")

    def test_malformed_max_age_query_param(self):
        """Passing non-numeric max_age like 'abc' must not crash the server and must gracefully fall back."""
        url = f"http://127.0.0.1:{self.port}/api/otp?domain=example.com&max_age=abc"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.getcode(), 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertTrue(data["success"])

if __name__ == "__main__":
    unittest.main()

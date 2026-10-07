"""
CLI integration and conformance tests for Spark OTP CLI commands.
"""
import unittest
import subprocess
import sys
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

class TestCLI(unittest.TestCase):
    def test_cli_help(self):
        """Test spark-otp --help outputs available subcommands."""
        res = subprocess.run(
            [sys.executable, "-m", "spark_otp.cli", "--help"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT)
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("diagnose", res.stdout)
        self.assertIn("sync", res.stdout)
        self.assertIn("accounts", res.stdout)
        self.assertIn("health", res.stdout)

    def test_cli_diagnose_help(self):
        """Test spark-otp diagnose --help outputs target and flag definitions."""
        res = subprocess.run(
            [sys.executable, "-m", "spark_otp.cli", "diagnose", "--help"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT)
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--account", res.stdout)
        self.assertIn("--allow-expired", res.stdout)
        self.assertIn("--json", res.stdout)

    def test_cli_diagnose_json_output(self):
        """Test spark-otp diagnose with --json produces valid JSON matching schema."""
        res = subprocess.run(
            [sys.executable, "-m", "spark_otp.cli", "diagnose", "app.example.com", "--json"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT)
        )
        self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
        data = json.loads(res.stdout)
        self.assertIn("query", data)
        self.assertEqual(data["query"]["target"], "app.example.com")
        self.assertEqual(data["query"]["domain"], "app.example.com")
        self.assertIn("environment", data)
        self.assertIn("candidates_count", data)
        self.assertIn("verdict", data)
        self.assertIn("recommendation", data)

    def test_cli_diagnose_human_output(self):
        """Test spark-otp diagnose human-readable audit printout."""
        res = subprocess.run(
            [sys.executable, "-m", "spark_otp.cli", "diagnose", "app.example.com"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT)
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Spark OTP Reconciliation & Diagnostics", res.stdout)
        self.assertIn("Target:", res.stdout)
        self.assertIn("Verdict:", res.stdout)
        self.assertIn("Recommendation:", res.stdout)

    def test_cli_sync_check(self):
        """Test spark-otp sync --check verifies 100% parity between extension and userscript."""
        res = subprocess.run(
            [sys.executable, "-m", "spark_otp.cli", "sync", "--check"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT)
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("SSOT Check Passed", res.stdout)

if __name__ == "__main__":
    unittest.main()

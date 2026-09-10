"""
Unit and integration tests for Spark OTP Telemetry and Observability system.
"""
import time
from spark_otp.telemetry import TelemetryManager, mask_secret_code, TelemetryEvent

class TestTelemetry:
    def test_mask_secret_code(self):
        assert mask_secret_code(None) is None
        assert mask_secret_code("") is None
        assert mask_secret_code("12") == "***"
        assert mask_secret_code("123") == "***"
        assert mask_secret_code("1234") == "1***4"
        assert mask_secret_code("8862") == "8***2"
        assert mask_secret_code("871330") == "87***0"
        assert mask_secret_code("UZW-XAD") == "UZ***D"
        assert mask_secret_code("34P514") == "34***4"

    def test_telemetry_recording_and_metrics(self, tmp_path):
        log_file = tmp_path / "telemetry_test.jsonl"
        mgr = TelemetryManager(
            max_in_memory=10,
            log_file_path=str(log_file),
            enabled=True
        )

        # Record a hit
        mgr.record(
            endpoint="/api/otp",
            duration_ms=45.2,
            status="hit",
            domain="cloudflare.com",
            service="cloudflare_access",
            code="123456"
        )

        # Record a miss
        mgr.record(
            endpoint="/api/otp",
            duration_ms=112.5,
            status="miss",
            domain="unknown.org"
        )

        # Record an error
        mgr.record(
            endpoint="/api/otp",
            duration_ms=5.0,
            status="error",
            error="Spark client offline"
        )

        metrics = mgr.get_metrics()
        assert metrics["total_requests"] == 3
        assert metrics["hits"] == 1
        assert metrics["misses"] == 1
        assert metrics["errors"] == 1
        assert metrics["hit_rate_pct"] == 33.3
        assert metrics["avg_latency_ms"] > 0
        assert len(metrics["recent_events"]) == 3

        # Verify masked code in events
        hit_event = metrics["recent_events"][0]
        assert hit_event["code_masked"] == "12***6"
        assert "123456" not in str(hit_event)

        # Verify get_recent_logs
        logs = mgr.get_recent_logs(limit=2)
        assert len(logs) == 2

    def test_kuma_push_graceful_on_invalid_url(self):
        mgr = TelemetryManager(
            uptime_kuma_push_url="http://127.0.0.1:1/nonexistent",
            enabled=True
        )
        # Should not raise exception
        mgr.record(
            endpoint="/api/otp",
            duration_ms=20.0,
            status="hit",
            code="654321"
        )

    def test_sentry_graceful_without_sentry_sdk(self):
        mgr = TelemetryManager(
            sentry_dsn="https://fake@sentry.io/12345",
            enabled=True
        )
        # If sentry_sdk is not installed, it safely handles it without crashing
        assert isinstance(mgr.sentry_initialized, bool)

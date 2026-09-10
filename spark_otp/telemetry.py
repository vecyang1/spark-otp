"""
In-app Telemetry and Observability System for Spark OTP.
Measures execution speed, query latency, recognition accuracy, and maintains structured audit logs.
Privacy-guaranteed: OTP codes are strictly masked in logs and metrics.
Supports local metrics, Uptime Kuma push, and optional Sentry error tracking.
"""
import os
import json
import time
import threading
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

def mask_secret_code(code: Optional[str]) -> Optional[str]:
    """Mask sensitive OTP code for privacy in logs and telemetry (e.g. '871330' -> '87***0')."""
    if not code:
        return None
    s = str(code).strip()
    if len(s) <= 3:
        return "***"
    if len(s) <= 5:
        return f"{s[0]}***{s[-1]}"
    return f"{s[:2]}***{s[-1]}"

@dataclass
class TelemetryEvent:
    timestamp: str
    endpoint: str
    duration_ms: float
    status: str  # "hit", "miss", "error"
    domain: Optional[str] = None
    account: Optional[str] = None
    service: Optional[str] = None
    code_masked: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class TelemetryManager:
    def __init__(
        self,
        max_in_memory: int = 200,
        log_file_path: Optional[str] = None,
        uptime_kuma_push_url: Optional[str] = None,
        sentry_dsn: Optional[str] = None,
        enabled: bool = True
    ):
        self.enabled = enabled
        self.max_in_memory = max_in_memory
        self.start_time = time.time()
        self._lock = threading.Lock()
        self._events: deque = deque(maxlen=max_in_memory)
        self.uptime_kuma_push_url = uptime_kuma_push_url
        self.sentry_dsn = sentry_dsn

        # Resolve log file path
        if log_file_path:
            self.log_file_path = Path(os.path.expanduser(log_file_path))
        else:
            self.log_file_path = Path.home() / ".spark_otp" / "telemetry.jsonl"

        if self.enabled:
            try:
                self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        # Optional Sentry initialization
        self.sentry_initialized = False
        if self.sentry_dsn:
            self._init_sentry()

    def _init_sentry(self):
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=self.sentry_dsn,
                traces_sample_rate=1.0,
                send_default_pii=False  # Keep PII / secrets strictly off
            )
            self.sentry_initialized = True
        except ImportError:
            # sentry_sdk not installed; gracefully operate without external Sentry
            self.sentry_initialized = False
        except Exception:
            self.sentry_initialized = False

    def record(
        self,
        endpoint: str,
        duration_ms: float,
        status: str,
        domain: Optional[str] = None,
        account: Optional[str] = None,
        service: Optional[str] = None,
        code: Optional[str] = None,
        error: Optional[str] = None,
    ) -> TelemetryEvent:
        """Record an execution event with timing, status, and masked secret."""
        event = TelemetryEvent(
            timestamp=datetime.now().isoformat(),
            endpoint=endpoint,
            duration_ms=round(duration_ms, 2),
            status=status,
            domain=domain,
            account=account,
            service=service,
            code_masked=mask_secret_code(code),
            error=error
        )

        if not self.enabled:
            return event

        with self._lock:
            self._events.append(event)

        # Asynchronously append to disk
        self._append_to_disk(event)

        # Notify Uptime Kuma if configured
        if self.uptime_kuma_push_url and endpoint == "/api/otp":
            self._ping_kuma(duration_ms, status)

        return event

    def _append_to_disk(self, event: TelemetryEvent):
        def _write():
            try:
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event.to_dict()) + "\n")
            except Exception:
                pass
        t = threading.Thread(target=_write, daemon=True)
        t.start()

    def _ping_kuma(self, duration_ms: float, status: str):
        import urllib.request
        def _worker():
            try:
                kuma_status = "up" if status != "error" else "down"
                msg = f"status={status}&ping={int(duration_ms)}"
                sep = "&" if "?" in self.uptime_kuma_push_url else "?"
                url = f"{self.uptime_kuma_push_url}{sep}status={kuma_status}&msg={msg}&ping={int(duration_ms)}"
                req = urllib.request.Request(url, headers={"User-Agent": "Spark-OTP-Telemetry/1.0"})
                urllib.request.urlopen(req, timeout=3)
            except Exception:
                pass
        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def get_metrics(self) -> Dict[str, Any]:
        """Compute aggregated latency, hit rate, and throughput stats."""
        with self._lock:
            events = list(self._events)

        total = len(events)
        hits = sum(1 for e in events if e.status == "hit")
        misses = sum(1 for e in events if e.status == "miss")
        errors = sum(1 for e in events if e.status == "error")

        latencies = [e.duration_ms for e in events if e.duration_ms is not None]
        avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        
        sorted_lat = sorted(latencies)
        p95_latency = 0.0
        if sorted_lat:
            idx = int(len(sorted_lat) * 0.95)
            p95_latency = sorted_lat[min(idx, len(sorted_lat) - 1)]

        hit_rate_pct = round((hits / total) * 100, 1) if total > 0 else 0.0
        uptime_seconds = round(time.time() - self.start_time, 1)

        # Dedicated OTP accuracy metrics
        otp_events = [e for e in events if e.endpoint in ("/api/otp", "/api/stream")]
        otp_total = len(otp_events)
        otp_hits = sum(1 for e in otp_events if e.status == "hit")
        otp_hit_rate_pct = round((otp_hits / otp_total) * 100, 1) if otp_total > 0 else 0.0
        otp_latencies = [e.duration_ms for e in otp_events if e.duration_ms is not None]
        otp_avg_latency_ms = round(sum(otp_latencies) / len(otp_latencies), 2) if otp_latencies else 0.0

        return {
            "uptime_seconds": uptime_seconds,
            "total_requests": total,
            "hits": hits,
            "misses": misses,
            "errors": errors,
            "hit_rate_pct": hit_rate_pct,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "otp_total": otp_total,
            "otp_hits": otp_hits,
            "otp_hit_rate_pct": otp_hit_rate_pct,
            "otp_avg_latency_ms": otp_avg_latency_ms,
            "kuma_configured": bool(self.uptime_kuma_push_url),
            "sentry_configured": self.sentry_initialized,
            "log_file": str(self.log_file_path),
            "recent_events": [e.to_dict() for e in events[-10:]]
        }

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve most recent audit log entries."""
        with self._lock:
            events = list(self._events)
        return [e.to_dict() for e in events[-limit:]]

# Global singleton
telemetry = TelemetryManager()

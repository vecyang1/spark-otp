"""
Lightweight HTTP & SSE Bridge Server for Spark OTP.
"""
import os
import json
import time
import urllib.parse
from pathlib import Path
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional
from .spark_client import SparkClient
from .config import config
from .telemetry import telemetry
from .contracts import OPENAPI_SPEC, SCHEMAS

class OTPRequestHandler(BaseHTTPRequestHandler):
    client: SparkClient = None

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Cache-Control")

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/api/health":
            self.handle_health()
        elif path == "/api/accounts":
            self.handle_accounts()
        elif path == "/api/otp":
            self.handle_otp(params)
        elif path == "/api/stream":
            self.handle_stream(params)
        elif path in ("/api/telemetry", "/api/metrics"):
            self.handle_telemetry()
        elif path == "/api/logs":
            self.handle_logs(params)
        elif path == "/api/openapi.json":
            self.handle_openapi()
        elif path == "/api/schema":
            self.handle_schema()
        else:
            self.send_response(404)
            self._set_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not Found"}).encode("utf-8"))

    def handle_openapi(self):
        self.send_response(200)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(OPENAPI_SPEC, indent=2).encode("utf-8"))

    def handle_schema(self):
        self.send_response(200)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(SCHEMAS, indent=2).encode("utf-8"))

    def handle_health(self):
        self.send_response(200)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        metrics = telemetry.get_metrics()
        apple_mail_avail = False
        if self.client and hasattr(self.client, "_find_apple_mail_sqlite_db"):
            try:
                apple_mail_avail = bool(self.client._find_apple_mail_sqlite_db())
            except Exception:
                pass

        data = {
            "status": "ok",
            "spark_available": self.client.is_available() if self.client else False,
            "apple_mail_available": apple_mail_avail,
            "timestamp": time.time(),
            "port": self.server.server_port,
            "metrics": metrics
        }
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def handle_accounts(self):
        t0 = time.perf_counter()
        self.send_response(200)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        accounts = []
        if self.client:
            try:
                accounts = self.client.get_accounts(include_apple_mail=True)
            except TypeError:
                accounts = self.client.get_accounts()
        duration_ms = (time.perf_counter() - t0) * 1000
        telemetry.record(
            endpoint="/api/accounts",
            duration_ms=duration_ms,
            status="hit" if accounts else "miss",
        )
        data = {
            "success": True,
            "accounts": accounts,
            "count": len(accounts),
            "metrics": {"duration_ms": round(duration_ms, 2)}
        }
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def handle_telemetry(self):
        self.send_response(200)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        metrics = telemetry.get_metrics()
        self.wfile.write(json.dumps({"success": True, "telemetry": metrics}).encode("utf-8"))

    def handle_logs(self, params):
        limit_param = params.get("limit", [50])[0]
        try:
            limit = int(limit_param)
        except (ValueError, TypeError):
            limit = 50
        self.send_response(200)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        logs = telemetry.get_recent_logs(limit=limit)
        self.wfile.write(json.dumps({"success": True, "count": len(logs), "logs": logs}).encode("utf-8"))

    def _safe_get_otp(self, domain, max_age, account, exclude_codes=None, exclude_message_ids=None, since_time=None):
        if not self.client:
            return None
        kwargs = {}
        if exclude_codes is not None:
            kwargs["exclude_codes"] = exclude_codes
        if exclude_message_ids is not None:
            kwargs["exclude_message_ids"] = exclude_message_ids
        if since_time is not None:
            kwargs["since_time"] = since_time
        try:
            return self.client.get_latest_otp(domain=domain, max_age_seconds=max_age, account=account, **kwargs)
        except TypeError:
            try:
                return self.client.get_latest_otp(domain=domain, max_age_seconds=max_age, account=account)
            except TypeError:
                return self.client.get_latest_otp(domain=domain, max_age_seconds=max_age)

    def handle_otp(self, params):
        t0 = time.perf_counter()
        domain = params.get("domain", [None])[0]
        account = params.get("account", [None])[0]
        max_age_param = params.get("max_age", [None])[0]
        max_age = int(max_age_param) if max_age_param and max_age_param.isdigit() else None

        exclude_codes_raw = params.get("exclude_codes", [None])[0]
        exclude_codes = [c.strip() for c in exclude_codes_raw.split(",") if c.strip()] if exclude_codes_raw else None

        exclude_msg_ids_raw = params.get("exclude_message_ids", params.get("exclude_message_id", [None]))[0]
        exclude_message_ids = [m.strip() for m in exclude_msg_ids_raw.split(",") if m.strip()] if exclude_msg_ids_raw else None

        since_time_raw = params.get("since_time", [None])[0]
        since_time = None
        if since_time_raw:
            try:
                since_time = float(since_time_raw)
            except ValueError:
                pass

        error_msg = None
        otp = None
        status = "miss"
        try:
            otp = self._safe_get_otp(
                domain=domain,
                max_age=max_age,
                account=account,
                exclude_codes=exclude_codes,
                exclude_message_ids=exclude_message_ids,
                since_time=since_time
            )
            status = "hit" if otp else "miss"
        except Exception as e:
            status = "error"
            error_msg = str(e)
            if telemetry.sentry_initialized:
                try:
                    import sentry_sdk
                    sentry_sdk.capture_exception(e)
                except Exception:
                    pass

        duration_ms = (time.perf_counter() - t0) * 1000

        telemetry.record(
            endpoint="/api/otp",
            duration_ms=duration_ms,
            status=status,
            domain=domain,
            account=account,
            service=otp.service if otp else None,
            code=otp.code if otp else None,
            error=error_msg
        )
        
        status_code = 500 if status == "error" else 200
        self.send_response(status_code)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        if status == "error":
            resp = {
                "success": False,
                "error": error_msg,
                "metrics": {
                    "duration_ms": round(duration_ms, 2),
                    "timestamp": time.time()
                }
            }
        elif otp:
            resp = {
                "success": True,
                "otp": otp.to_dict(),
                "metrics": {
                    "duration_ms": round(duration_ms, 2),
                    "timestamp": time.time()
                }
            }
        else:
            resp = {
                "success": False,
                "message": f"No valid OTP found for domain '{domain or 'any'}'",
                "metrics": {
                    "duration_ms": round(duration_ms, 2),
                    "timestamp": time.time()
                }
            }
        self.wfile.write(json.dumps(resp).encode("utf-8"))

    def handle_stream(self, params):
        """Server-Sent Events (SSE) stream."""
        domain = params.get("domain", [None])[0]
        account = params.get("account", [None])[0]
        max_age_param = params.get("max_age", [None])[0]
        max_age = int(max_age_param) if max_age_param and max_age_param.isdigit() else None

        exclude_codes_raw = params.get("exclude_codes", [None])[0]
        exclude_codes = [c.strip() for c in exclude_codes_raw.split(",") if c.strip()] if exclude_codes_raw else None

        exclude_msg_ids_raw = params.get("exclude_message_ids", params.get("exclude_message_id", [None]))[0]
        exclude_message_ids = [m.strip() for m in exclude_msg_ids_raw.split(",") if m.strip()] if exclude_msg_ids_raw else None

        since_time_raw = params.get("since_time", [None])[0]
        since_time = None
        if since_time_raw:
            try:
                since_time = float(since_time_raw)
            except ValueError:
                pass

        self.send_response(200)
        self._set_cors_headers()
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        last_code = None
        last_msg_id = None
        timeout_seconds = 180  # 3 minute max stream lifetime
        start_time = time.time()

        try:
            while time.time() - start_time < timeout_seconds:
                t0 = time.perf_counter()
                try:
                    otp = self._safe_get_otp(
                        domain=domain,
                        max_age=max_age,
                        account=account,
                        exclude_codes=exclude_codes,
                        exclude_message_ids=exclude_message_ids,
                        since_time=since_time
                    )
                except Exception as e:
                    telemetry.record(
                        endpoint="/api/stream",
                        duration_ms=0.0,
                        status="error",
                        domain=domain,
                        account=account,
                        error=str(e)
                    )
                    break
                duration_ms = (time.perf_counter() - t0) * 1000

                if otp and (otp.code != last_code or otp.message_id != last_msg_id):
                    is_excluded = False
                    if exclude_codes and any(str(c).strip().upper() == otp.code.strip().upper() for c in exclude_codes):
                        is_excluded = True
                    if exclude_message_ids and str(otp.message_id).strip() in (str(m).strip() for m in exclude_message_ids):
                        is_excluded = True

                    if not is_excluded:
                        last_code = otp.code
                        last_msg_id = otp.message_id
                        telemetry.record(
                            endpoint="/api/stream",
                            duration_ms=duration_ms,
                            status="hit",
                            domain=domain,
                            account=account,
                            service=otp.service,
                            code=otp.code
                        )
                        payload = json.dumps(otp.to_dict())
                        self.wfile.write(f"event: otp\ndata: {payload}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    else:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                else:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                # Back off polling if code is already found to save Spark CLI IPC load
                time.sleep(5 if last_code else 2)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass

    def log_message(self, format, *args):
        # Suppress noisy standard request logging in production
        return

def start_kuma_heartbeat(url: str, interval: int = 60):
    """Optional background thread to send heartbeat ping to Uptime Kuma push URL."""
    import urllib.request
    import threading

    def _worker():
        while True:
            try:
                urllib.request.urlopen(url, timeout=5)
            except Exception:
                pass
            time.sleep(interval)

    t = threading.Thread(target=_worker, daemon=True, name="KumaHeartbeatWorker")
    t.start()

def create_server(host: str = "127.0.0.1", port: int = 9428, client: Optional[SparkClient] = None) -> ThreadingHTTPServer:
    if client is None:
        client = SparkClient()

    # Re-sync telemetry config
    telemetry.uptime_kuma_push_url = config.uptime_kuma_push_url
    telemetry.sentry_dsn = config.sentry_dsn
    telemetry.enabled = config.telemetry_enabled
    if config.log_path:
        telemetry.log_file_path = Path(os.path.expanduser(config.log_path))

    if config.uptime_kuma_push_url:
        start_kuma_heartbeat(config.uptime_kuma_push_url)

    class BoundHandler(OTPRequestHandler):
        pass
    BoundHandler.client = client

    server = ThreadingHTTPServer((host, port), BoundHandler)
    server.daemon_threads = True
    return server

# Spark OTP Verification Map

Scope: project-local

## Launch
- **Local Daemon**: `./scripts/manage_daemon.sh start` (or `./scripts/manage_daemon.sh restart`; runs `python3 -B -u cli.py serve --port 9428` on loopback `127.0.0.1:9428` via LaunchAgent `com.spark_otp.daemon.plist`).
- **Browser Extension**: Load unpacked repository root (`manifest.json`) or `extension/` in Chrome/Chromium (`chrome://extensions`), or install `userscript/spark-otp.user.js`.
- **Deployment Lane**: `local-desktop-extension` (zero cloud/VPS/public web deployment; packaged releases publish via `./scripts/release.sh <tag>`).

## Doctor
- **Daemon Health**: `curl -sf http://127.0.0.1:9428/api/health` (verifies `"status": "ok"`, `spark_sqlite_available`, `port: 9428`, and local telemetry metrics).
- **SSOT & Packaging Preflight**: `PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/sync_engine.py --check` and `PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest tests/test_extension_packaging.py -q` (enforces zero top-level `_`-prefixed entries such as `__pycache__` that trigger Chromium `DISABLE_RELOAD`).
- **Diagnostic-First Inspection**: `spark-otp diagnose --target <domain> --allow-expired --json` or `GET http://127.0.0.1:9428/api/diagnose?target=<domain>&allow_expired=true`.

## Drive
- **Two-Sided Unit & Adversarial Suite**: `PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest tests/ -q` (covers extractor, SQLite fast-path, `cache.sqlite` HTML fallback, SendGrid URL isolation, race-guard `since_time`, DOM detection, and extension/userscript parity).
- **Real-Browser Extension Smoke E2E**: `PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/e2e_extension_smoke.py` (launches Chrome for Testing with `--load-extension=.`, clicks login trigger, verifies first `/api/stream` request carries `since_time == floor(loginRequestAt/1000)` and `race_guarded` pill state).
- **Live Domain Resolution Check**: `curl -sf "http://127.0.0.1:9428/api/otp?domain=spaceship.com&allow_expired=1"` and `spark-otp get --domain <domain> --json`.

## Evidence
- `scripts/sync_engine.py --check` exit `0` (`100% parity`).
- `PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest tests/ -q` exit `0` (`241 passed` as of `v1.7.4`).
- `PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/e2e_extension_smoke.py` exit `0` (`PASS`, real extension service worker registered).
- `curl -sf http://127.0.0.1:9428/api/health` returning HTTP `200` with `"status": "ok"`.
- Real-browser autofill screenshot verifying input population, submit trigger, and non-flashing green `Auto-filled & submitted` pill.

## Cleanup
- `scripts/e2e_extension_smoke.py` automatically terminates its temporary Chromium process and removes its `mkdtemp` profile directory in `finally`.
- Always invoke Python with `-B` / `PYTHONDONTWRITEBYTECODE=1`; if any top-level `__pycache__` appears at repo root, remove it immediately before reloading the unpacked extension.
- Run `./scripts/manage_daemon.sh stop` only when intentionally shutting down the local bridge.

## What Usually Lies
- **Mock-DOM unit tests without real page copy**: Static resend helper prompts on real OTP pages (e.g. `"您的验证码已过期或您没有收到？ 重新发送验证码"` or `"Code expired or didn't receive it? Resend"`) can falsely trip `detectPageError()` even when isolated unit mocks pass.
- **`--load-extension` vs `chrome://extensions` Reload**: Chromium's `--load-extension` skips `CheckForIllegalFilenames`, so a top-level `__pycache__` directory can pass CLI smoke tests while breaking interactive Reload (`DISABLE_RELOAD`); rely on `tests/test_extension_packaging.py` and the explicit preflight in `scripts/e2e_extension_smoke.py`.
- **ESP preheader padding in `shortBody`**: SendGrid/ESP `U+034F` invisible spacers push OTP bodies out of SQLite `shortBody` and hide OTP keywords; never assume `shortBody` alone proves `NON_AUTH_EMAIL`.
- **Concurrent `EventSource` + `pollOnce` race**: An in-flight `/api/otp` response arriving milliseconds after SSE filled the code can re-enter `isCodeRejected()` and overwrite a green success pill with a red `rejected` state unless same-`activeCode` non-error responses are ignored.

## Observability

| Pillar | Status | Details / Justification |
|---|---|---|
| Uptime Kuma | `skipped` | Loopback-only local macOS LaunchAgent (`127.0.0.1:9428`) with zero public ingress; optional push-heartbeat support exists via `SPARK_OTP_KUMA_URL` (`spark_otp/server.py`) for opt-in deployments, while local liveness is verified via `scripts/manage_daemon.sh status` and `GET /api/health`. |
| Sentry | `skipped` | Local single-machine CLI/daemon reading local mailbox databases; optional opt-in SDK support exists via `SPARK_OTP_SENTRY_DSN` (`spark_otp/telemetry.py`), intentionally disabled by default so local email metadata never leaves the host. |
| HyperDX | `skipped` | Loopback-only local daemon with built-in rotating JSONL audit telemetry (`spark_otp/telemetry.py`, 5 MB rotation cap) exposed locally at `/api/telemetry` and `/api/logs`; remote OTLP ingestion is unnecessary and excluded by design for local privacy. |

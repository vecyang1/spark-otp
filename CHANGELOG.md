# Changelog - Spark OTP Autofill

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.3] - 2026-09-08

### Added
- **Anti-Loop Protection on Rejected / Failed Verification Pages**:
  - Automatically detects page error states via URL query params (`?incorrect=true`, `?error=...`, `?failed=...`, `?invalid=...`) and DOM alert elements (`role="alert"`, `.alert-danger`, "Incorrect code, please try again", "验证码错误", etc.).
  - Preserves submitted code state, failed codes, and failure timestamps across page reloads via `sessionStorage` (`spark_otp_auth_{domain}`).
  - When an error is detected upon reload after submitting a code, that code and its message ID are immediately registered into `failedCodes` and `failedMessageIds`.
  - Floating pill enters `code_failed` state with warning badge and context: `"验证码 {code} 校验失败，等待新邮件..."` with manual override ("强制填充") and refresh ("刷新") buttons.
- **Backend Rejection & Exclude Query Filtering (`/api/otp` and `/api/stream`)**:
  - Added `exclude_codes`, `exclude_message_ids`, and `since_time` query parameters to `/api/otp` and `/api/stream`.
  - Added SQL filtering in `_get_otp_from_sqlite` and CLI filtering in `_search_emails_for_otp` to prevent the daemon from returning previously rejected codes.
  - OpenAPI 3.0.3 contract updated in `spark_otp/contracts.py` documenting the new query parameters.
- **Auto-Submit Guardrails**:
  - Max 1 auto-submission per unique OTP code (`submissionCounts[code] >= 1`).
  - Pre-flight rejection gate (`isCodeRejected`): blocks autofill and submission of failed codes, stale emails received before error detection, or previously submitted codes on error pages.
  - Fresh OTP recovery: seamlessly auto-fills and submits new codes (`code !== failedCode`, `received_at > lastFailedAt`) arriving via SSE or polling.
- **End-to-End & Cross-Script Verification Suite**:
  - Added `test_bandwagon_incorrect_loop_rejection_and_recovery` in `tests/test_dom_detection.py` simulating the exact BandwagonHost `browser_auth.php?incorrect=true` loop rejection and recovery with 100% parity across `extension/content.js` and `userscript/spark-otp.user.js`.
  - Added `test_sqlite_exclude_codes_and_message_ids` and `test_sqlite_since_time_filter` in `tests/test_sqlite_backend.py`.
  - Added `test_otp_endpoint_exclude_codes`, `test_stream_endpoint_exclude_codes`, and `test_stream_endpoint_exclude_message_ids` in `tests/test_server.py`.
  - Added `test_e2e_failed_code_anti_loop_and_recovery` in `tests/test_e2e_flow.py`.
  - Added `test_error_page_input_sniffing_and_storage_order_resilience` in `tests/test_dom_detection.py`.
  - Total automated test suite expanded to 132 passing tests.

### Fixed
- **Polymorphic Storage Argument Ordering**: Made `saveAuthState` polymorphic (`(state, domain)` or `(domain, state)`), eliminating key pollution (`spark_otp_auth_[object Object]`) and ensuring failure state persists properly across reloads.
- **Userscript State Staleness & Failed State Rendering**: Fixed `start()` in `spark-otp.user.js` referencing stale `authState` after calling `recordCodeFailed`, guaranteeing `renderFailedState` is rendered immediately upon error reload.
- **Error Page Input Sniffing**: If `sessionStorage` has no recorded submitted code on reload (e.g., fresh tab, cleared session), automatically sniff the failed code from existing `#verification_code` input when an error banner is present, registering it as rejected and preventing loop.
- **Non-Creeping Timestamp Invariant**: Prevented repeated background checks and DOM mutations from bumping `lastFailedAt` forward in time, ensuring newly arrived emails are not falsely rejected as stale.
- **SSE Keepalive for Excluded Codes & Exclude Message IDs**: `/api/stream` now emits continuous `: keepalive\n\n` when an excluded code or excluded message ID matches, preventing socket starvation or client hang.
- **Timestamp Propagation in `fillAndSubmit`**: Passed `receivedMs` through `fillAndSubmit` so `receivedAtMs <= lastFailedAt` rejection rule is strictly enforced on submission.
- **Empty Code Display Fallback**: `renderPill("code_failed")` and `renderFailedState()` cleanly display `"验证码校验失败，等待新邮件..."` without `"undefined"` text or non-functional force-fill buttons when no code is available.

## [1.3.2] - 2026-09-08

### Added
- **Complete End-to-End DOM Lifecycle Test (`test_e2e_bandwagon_browser_auth_dom_flow`)**:
  - Full simulation of `bandwagonhost.com/browser_auth.php` DOM tree.
  - Verifies DOM input resolution (`#verification_code`), email extraction (`alex.turner@gmail.com`), value setting, and submission targeting `"Verify and remember this device"`.
  - Enforces identical parity across both Chrome Extension (`content.js`) and Tampermonkey Userscript (`spark-otp.user.js`).
- **Live Historical Verification Test (`test_sqlite_real_host_historical_screenshot_codes`)**:
  - Directly tests live host Spark Desktop SQLite DB against historical codes from user screenshots:
    - Code `875358` at 21:37:30 (9:37 PM)
    - Code `273529` at 21:39:00 (9:38 PM)
- **Recency-Aware Account Fallback**:
  - In `_get_otp_from_sqlite`, when an explicit `account` is requested (or defaulted, e.g. `dev.team@acme-cloud.net`), if another linked account (`alex.turner@gmail.com`) receives a fresh OTP that is >180s newer than the target account's latest message, the fresh OTP takes precedence. Prevents stale OTPs from trapping users.

### Fixed
- **Future Email Rejection & Upper-Bound Query**:
  - Added `receivedDate <= ?` (now + 30s clock skew tolerance) in `_get_otp_from_sqlite` and strict negative `age_seconds < -30` check in `extractor.py`, eliminating time-travel match errors during past-time simulation and historical replay.
- **Userscript / Extension Full Feature Parity**:
  - Added steps 3 (account info blocks), 4 (emphasis regex extraction), and 5 (global single user email scan) to `findEmailOnPage()` in `spark-otp.user.js`.
  - Added dynamic re-sniffing of page email on every polling tick and "刷新" click, dynamically attaching `&account=` and updating pill subtitle text.
  - Fixed submit button targeting in `triggerSubmit()`: prioritizes submit buttons matching `isVerifyButton` over generic buttons, and includes `input[type="submit"]` in container searches.

## [1.3.1] - 2026-09-08

### Added
- **Direct SQLite Fast-Path (Tier 0 Backend)**:
  - Added sub-millisecond direct query (`mode=ro`) to Spark Desktop's CoreData database (`~/Library/Application Support/Spark Mail/core-data/messages.sqlite`).
  - Response time dropped from ~7,500ms to <5ms (sub-10ms end-to-end HTTP response).
  - Bypasses Spark CLI thread-collapsing bug where multiple emails with identical subject (`Device verification`) only return the root message ID, hiding fresh incoming verification codes.
  - Account prioritization: honors `account` query parameter to inspect the target inbox first, with seamless fallback across all accounts.
  - Full test isolation: configurable via `SPARK_OTP_SQLITE_PATH` (`auto` in production, `disabled` in pytest via `tests/conftest.py`).
- **Universal Page Email Sniffing (`findEmailOnPage`)**:
  - Implemented high-fidelity sentence matching for auth pages (e.g. `"To protect your account, we have sent a 6-digit verification code to alex.turner@gmail.com"` and Chinese equivalents).
  - Added candidate email sanitization stripping surrounding punctuation, quotes, brackets, and colons.
  - Strict system/support email disqualification (`support@`, `help@`, `billing@`, etc.) ensuring only user recipient addresses are selected.
  - Wired into extension and userscript, automatically passing `&account=` to `/api/otp` and `/api/stream`, and displaying account badge in pill UI.
- **WHMCS & Custom Submit Button Detection**:
  - Added support for `browser_auth.php` input fields (`input[name="verification_code"]`, `input[name="code"]`).
  - Added support for submit buttons like `"Verify and remember this device"` across `<button>` and `<input type="submit">`.
- **Comprehensive E2E Simulation**:
  - Added `tests/test_sqlite_backend.py` (4 unit tests).
  - Added `test_e2e_bandwagon_sqlite_flow` in `tests/test_e2e_flow.py` testing the full pipeline from SQLite to daemon HTTP and SSE stream.
  - Expanded automated test suite to 120 passing tests.

### Fixed
- **CLI Thread Root Date Filtering**:
  - Prevented false-positive pre-filtering of thread root timestamps when a specific domain is queried, avoiding drops of newly received verification codes within existing threads.
- **Punctuation Stripping in Page Sniffer**:
  - Resolved trailing punctuation (`.`, `,`, `:`) attaching to extracted email strings before regex validation.

## [1.3.0] - 2026-09-08

### Added
- **Contract-First Architecture & OpenAPI 3.0.3**:
  - Added `spark_otp/contracts.py` defining authoritative JSON schemas and OpenAPI 3.0.3 documentation.
  - Implemented `/api/openapi.json` and `/api/schema` endpoints in `spark_otp/server.py`.
  - Added TypeScript contract interfaces `extension/types/contracts.d.ts` for compile-time safety across extension and userscript.
  - Added `tests/test_contracts.py` verifying schema conformance across all endpoints (6/6 passing).
- **Single Source of Truth & Unidirectional Reactive Flow**:
  - Added `chrome.storage.onChanged` listener in `extension/content.js` allowing instant propagation of settings (port, account, auto-submit) across all active tabs without page reload.
  - Dynamic expiration rendering: pill UI derives time remaining from authoritative `expires_at` / `time_remaining_seconds` rather than drifting local stopwatches.
- **Push-based Realtime Streaming in Userscript**:
  - Upgraded `userscript/spark-otp.user.js` to full `EventSource` SSE streaming (`/api/stream`) with automatic polling fallback.
- **Two-Sided Adversarial Verification ("测遍了不会说谎的那一半，也要测遍会说谎的那一半")**:
  - Added `tests/test_adversarial.py` (14/14 tests passing) verifying:
    - Rejection of false-friend DOM fields: promo/coupon codes, zip/postal codes, search inputs, captcha boxes, password change inputs.
    - Rejection of false-friend emails: shipment tracking numbers, invoice billing receipts.
    - Strict expiration boundary enforcement (rejecting expired standard & Bandwagon tokens, accepting active tokens within 1-hour window).
    - Spark CLI crash/corruption tolerance.
    - 30-client concurrent load test.
  - Total automated test count expanded from 89 to 109 tests (100% pass rate).
- **Service & CLI Enhancements**:
  - Added `daemon` subcommand to `cli.py` (`start`, `stop`, `restart`, `status`, `logs`, `enable-autostart`, `disable-autostart`).
  - Added `schema` and `openapi` subcommands to `cli.py`.
  - Added `logs` command to `operations/manage_daemon.sh`.
- **Version Parity**:
  - Bumped `extension/manifest.json` and root `manifest.json` to version `1.3.0`.

## [1.2.2] - 2026-09-08

### Fixed
- **Flaky Test Port Allocation (Errno 48 Address Already in Use)**:
  - Replaced hardcoded ports (`19430`, `19428`) in `test_server.py` and `test_e2e_flow.py` with dynamic kernel port allocation (`port=0`), retrieving `server.server_address[1]` dynamically.
  - Enabled `daemon_threads = True` on `ThreadingHTTPServer` to prevent dangling client handler threads from blocking process shutdown.
- **Multi-Sender Filter Query for Bandwagon Host**:
  - Expanded `bandwagon_auth` `filter_query` from `from:64clouds.com` to `from:64clouds.com OR from:bandwagonhost.com OR from:it7.net`. Verified against actual user inbox containing official emails from `Bandwagon Host <support@bandwagonhost.com>`.
- **Background Polling & SSE Stream Resource Leak**:
  - In `extension/content.js`, automatically invoke `stopListening()` when an OTP code is detected and filled in both `EventSource` stream and fallback polling modes, preventing unbounded CPU and Spark CLI IPC usage.
  - In `spark_otp/server.py`, added backoff sleep (5s instead of 2s) in `/api/stream` after a code has already been dispatched.
  - Added "重新获取" (Retry) action button to the found state pill so users can easily re-listen if a code expires.
  - In `userscript/spark-otp.user.js`, added `isPollingInflight` lock to prevent parallel fetch storms.
- **WHMCS & Bootstrap Control-Group DOM Heuristics**:
  - In `extension/content.js` and `userscript/spark-otp.user.js`, expanded Priority 5 label matcher to inspect enclosing `.control-group`, `.form-group`, `.field`, and sibling inputs when `<label>` lacks a `for="id"` attribute.
  - In `isDisqualifiedInput`, inspected associated `<label>` text so that password-masked OTP inputs with valid labels are not prematurely disqualified.
- **Extension Manifest Sync**:
  - Bumped `extension/manifest.json` version to `1.2.2`.

## [1.2.1] - 2026-09-08

### Fixed
- **Bawagon Alias & Shorthand Matching**:
  - Added support for `bawagon`, `bawagon.com`, and non-.net mirror domains (`bwh81.com`, `bwh88.org`) across `config.py`, `domain_matches`, and `spark_client.py`.
- **Targeted Filter Query & Ultra-Low Latency (<200ms)**:
  - Added `filter_query` capability to `RuleDefinition` (`from:64clouds.com` for Bandwagon Host).
  - Multi-tier search hierarchy: targeted rule query first (~150-200ms, completely immune to inbox alert spam eviction), followed by single Unified Inbox listing with preferred account prioritization, reducing Spark IPC calls by 50-70%.
- **DOM Detection & WHMCS 2FA Coverage**:
  - Expanded `isOtpLike` in `content.js` and `spark-otp.user.js` to include `device`, `twofactor`, `twofa`, `secondfactor`, and `twofactorauthcode`.
  - Added label-based input detection (`label[for]` and enclosing `<label>`) to correctly identify OTP inputs where name/ID is generic.
  - Added inflight lock (`isPollingInflight`) in `content.js` to prevent overlapping requests during fallback polling.
- **Extractor TTL Calculation**:
  - Corrected `effective_max_age = max(max_age_seconds, rule_max_ttl)` in `extractor.py` so passing custom `max_age_seconds` cannot prematurely evict 1-hour valid tokens.

## [1.2.0] - 2026-09-08

### Added
- **Bandwagon Host & KiwiVM Support (`bandwagon_auth`)**:
  - First-class deterministic extraction rule for Bandwagon Host (`noreply@64clouds.com`, `Bandwagon Host`, `KiwiVM`, `IT7`).
  - Supported domains: `bandwagonhost.com`, `bwh81.net`, `bwh88.net`, `bwh89.net`, `bwh1.net`, `bwh8.net`, `bwh9.net`, `64clouds.com`, `kiwivm.it7.net`, `it7.net`.
  - Added support for 1-hour expiration TTL (`It is valid for 1 hour.`, `小时`, `小時`, `時間`) scaling to 3600 seconds.
- **Resilient Account Fallback (`spark_otp/spark_client.py`)**:
  - When querying a specific mailbox account (e.g. `dev.team@acme-cloud.net`), if no matching OTP is found, gracefully falls back to Unified Inbox (`all accounts`) so cross-account verification codes (e.g. arriving in `alex.turner@gmail.com`) are never missed.
- **Enhanced DOM Input Detection**:
  - Added `device` and `2fa` field selectors (`input[name*="device"]`, `input[id*="device"]`, `input[placeholder*="device"]`, `input[name*="2fa"]`) to `findOtpInputs` in both Chrome extension and Userscript.
- **Comprehensive Verification**:
  - Added 6 new automated tests covering official domain, mirror domains (`bwh81.net`, `bwh88.net`), 1-hour TTL expiration boundary, and account fallback mechanism (89/89 tests passing).

### Changed
- **Brand Space & Mirror Normalization**:
  - Added space-collapsed brand matching (`bandwagon host` matches `bandwagonhost`).
  - Added `bwh\d*` mirror domain regex resolution across `domain_matches` and `spark_client.py`.
- **Extension Defaults**:
  - Updated default preferred email in `content.js`, `popup.html`, and `popup.js` to `alex.turner@gmail.com`.

## [1.1.0] - 2026-09-07

### Added
- **Privacy-First Telemetry Engine (`spark_otp/telemetry.py`)**:
  - In-memory rolling metrics tracking requests, hits, misses, hit rate %, average latency, and p95 latency.
  - Append-only local JSONL audit logging (`~/.spark_otp/telemetry.jsonl`) with masked OTPs (`52***6`).
  - Uptime Kuma push heartbeat integration via `SPARK_OTP_KUMA_URL`.
  - Optional Sentry exception monitoring via `SPARK_OTP_SENTRY_DSN`.
  - Daemon API endpoints: `/api/telemetry`, `/api/metrics`, and `/api/logs` with microsecond `duration_ms` tracking.
- **Immediate Visual Detection & Ticking Feedback**:
  - Floating pill UI badge appearing instantly on verification field detection: `"已检测到验证码输入框，后台正在静默查询/等待验证码..."`.
  - Real-time ticking elapsed timer badge (`00:01`, `00:02`) and manual refresh button.
  - Live system performance and telemetry card inside the Chrome extension popup.
- **Multilingual Expiration Parsing**:
  - Deterministic TTL extractor for expiration phrases across Chinese (`10分钟内有效`), Japanese (`有効期限10分`), and English (`valid for 5 minutes`).
- **Comprehensive Verification**:
  - Expanded test suite from 15 to 83 automated unit, contract, and adversarial tests (100% passing).

### Changed
- **Performance Optimization**: Added domain-aware pre-filtering in `spark_client.py` to prevent fetching unrelated threads for other services, reducing non-matching domain latency from 6,142ms to <200ms.
- **Spark CLI Flag Parser**: Added support for `attachment` and compound flags (e.g., `unread attachment`), preventing subject text corruption.
- **Userscript Parity**: Added manual refresh button, dismiss button, and 3-minute watching timeout to `spark-otp.user.js`.

### Fixed
- Fixed TTL override bug where explicit short lifespans were overridden by default `max_age_seconds`.
- Hardened server exception capture to return structured HTTP 500 JSON without crashing daemon.

## [1.0.0] - 2026-09-07

### Added
- **Deterministic Zero-LLM OTP Extraction Engine (`spark_otp/extractor.py`)**:
  - Pre-configured regex and proximity extraction for 25+ major services (Cloudflare, GitHub, Google, AWS, Stripe, Supabase, Vercel, Slack, Steam Guard, etc.).
  - Disqualification safeguards against transaction amounts, reference codes, phone numbers, and dictionary words.
- **Spark CLI Integration (`spark_otp/spark_client.py`)**:
  - Robust table parser interfacing with local macOS `spark` command across 7 user mailboxes.
- **Local HTTP Daemon (`spark_otp/server.py`)**:
  - REST endpoint (`/api/otp`) and SSE stream (`/api/stream`) on non-conflicting port `9428`.
- **Browser Automation Artifacts**:
  - Chrome Extension Manifest V3 with auto-fill, auto-submit, floating pill, and magic link jump.
  - Standalone Tampermonkey Userscript (`userscript/spark-otp.user.js`).
  - Chrome Native Messaging host (`spark_otp/native_messaging.py`).
- **Project Scaffolding**:
  - CLI entrypoint (`cli.py`), launchd service descriptor, and documentation suite.

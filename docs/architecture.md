# Spark OTP Architecture

Scope: project-local

## App Summary
`spark-otp` extracts and autofills email verification codes and Cloudflare Access / 2FA one-time passcodes from macOS Spark Desktop into web browsers via a local Python CLI/daemon and Chrome Extension / Tampermonkey Userscript.

## System Diagram
```
              [Spark Desktop CoreData Mailbox]
                              │
              ┌───────────────┴───────────────┐
              ▼ (Tier 0: <3ms, mode=ro)       ▼ (Tier 1: ~7s fallback)
    [messages.sqlite Direct Read]       [spark CLI IPC Subprocess]
              │                               │
              └───────────────┬───────────────┘
                              ▼
                   [spark_otp Core Engine]
               (Extractor, Contracts, Telemetry)
                              │
                              ▼
                [spark-otp Daemon (Port 9428)]
               (REST, SSE Stream with Keepalive,
                 OpenAPI 3.0.3, JSON Schema)
                              │
                              ▼
              [Chrome Extension / Userscript]
               ┌──────────────┴──────────────┐
               ▼                             ▼
   [5-Tier Page Email Sniffer]    [Anti-Loop Protection]
  (Target Form, Sentence Context, (Page Error Detection,
   Info Cards, Emphasis Tags,     sessionStorage Blacklist,
   Single User Email Fallback)    Input Residue Sniffing,
                                  Timestamp Anti-Creeping)
                              │
                              ▼
                  [DOM Event Injection]
            (Single, Segmented, React Setter,
             Shadow DOM / ContentEditable)
                              │
                              ▼
              [Target Web Authentication Form]
```

## First Principles & Architectural Invariants

### 1. Single Source of Truth (SSOT)
- The user's Spark Desktop SQLite database (`~/Library/Application Support/Spark Mail/core-data/messages.sqlite`) is the sole authoritative state of truth.
- The HTTP daemon (`/api/otp`, `/api/stream`) is the read portal.
- The Chrome Extension / Userscript floating pill and autofill form are projections of that truth.

### 2. Unidirectional Data Flow
- **Read Path**: Spark SQLite DB -> Daemon API -> Extension/Userscript UI.
- **Write Path**: Submission action -> Target web auth endpoint -> Error/Success response -> If rejected, extension writes to `sessionStorage` blacklist and requests `/api/otp` with `exclude_codes` and `since_time` -> Autoritative API re-evaluates -> UI renders new state. Never trust optimistic local state after failure.

### 3. Derived State ("能派生的不要存")
- Do not store redundant or duplicate states. Expiration, time remaining, masking, and domain resolution are derived on-the-fly from timestamps and raw message content.

### 4. Contract-First & End-to-End Type Safety
- The SQLite table schema and `contracts.py` define the authoritative contracts.
- OpenAPI 3.0.3 specification (`/api/openapi.json`) and JSON Schema (`/api/schema`) provide machine-readable contracts consumed by clients and automated test suites.

### 5. Push-Based Realtime Sync
- Primary ingestion uses Server-Sent Events (`GET /api/stream?domain=...`) with periodic `: keepalive\n\n` packets to maintain persistent connectivity without reconnect storms.
- Resilient polling fallback (1s interval) engages automatically if SSE connection drops.

### 6. Two-Sided Verification Protocol
- "测遍了不会说谎的那一半，也要测遍会说谎的那一半":
  - **Positive Path**: Valid OTP extraction across 25+ services, sub-3ms latency, correct input selection and submit triggering.
  - **Adversarial Path**: Negative TTL rejection, future timestamp (clock skew) blocking, malformed CLI noise handling, rejected code blacklist filtering, and preventing infinite submission loops on `?incorrect=true`.

### 7. Evidence Rule
- "没人跑的检查不算证据": Every architectural invariant and code path is protected by automated tests (132/132 passing) with verifiable stdout/stderr receipts.

## Module Map
- `spark_otp/extractor.py`: Zero-LLM deterministic regex parsing engine with TTL validation and future timestamp rejection.
- `spark_otp/spark_client.py`: Dual-engine client combining Tier 0 SQLite direct read with Tier 1 CLI fallback, recency-aware account sorting, and query exclusion.
- `spark_otp/server.py`: Standard library HTTP & SSE bridge daemon on port 9428 exposing REST, SSE stream, OpenAPI, and JSON Schema.
- `spark_otp/contracts.py`: OpenAPI 3.0.3 and JSON Schema contract definitions.
- `spark_otp/telemetry.py`: Privacy-masked latency percentiles, hit rates, and rotating audit logging.
- `spark_otp/config.py`: Service detection rules, regex patterns, and environment configuration (`SPARK_OTP_SQLITE_PATH`, `SPARK_OTP_PORT`).
- `spark_otp/cli.py`: Unified CLI (`get`, `serve`, `watch`, `accounts`, `health`).
- `extension/`: Chrome Extension (Manifest V3) content script, floating pill UI, and popup with reactive storage sync.
- `userscript/`: Standalone Violentmonkey / Tampermonkey userscript maintaining 100% feature parity with the extension.

## Data And Storage
- **Source of Truth**: macOS Spark Desktop local mailbox CoreData cache (`messages.sqlite`).
- **Local Bridge**: In-memory ephemeral evaluation, zero disk persistence of credentials.
- **Session Blacklist**: Domain-scoped `sessionStorage` tracking `failedCodes`, `failedMessageIds`, and `lastFailedAt` to prevent submission loops.
- **Chrome Storage**: Port and auto-submit preferences in `chrome.storage.sync`.

## Runtime And Deployment
- Python 3.10+ standard library (zero external pip dependencies for daemon core).
- Managed via `./operations/manage_daemon.sh {start|stop|restart|status}`.
- Default port 9428 (localhost only).

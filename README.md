# Spark OTP Autofill

<div align="center">

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Chrome Extension](https://img.shields.io/badge/Chrome_Extension-MV3-brightgreen.svg)](extension/)
[![Userscript](https://img.shields.io/badge/Userscript-Tampermonkey-orange.svg)](userscript/)
[![Tests](https://img.shields.io/badge/Tests-132%20passed-success.svg)](tests/)

**Universal zero-LLM email verification code (OTP / 2FA) auto-detection, extraction, and autofill engine powered by local macOS Spark Desktop.**

[Features](#key-capabilities) • [Quick Start](#quick-start) • [Repository Structure](#repository-structure) • [API Contracts](#api-reference) • [Verification](#testing--verification) • [License](#license)

</div>

---

> [!IMPORTANT]
> **Privacy & AI-Native Architecture / 隐私保护与本地架构说明**
> - **English:** Spark OTP Autofill operates **100% locally** on your macOS machine. All OTP parsing is deterministic regex and proximity matching (zero LLM inference, zero cloud dependencies, zero external transmission of credentials). Verification codes are processed in memory and masked in telemetry logs (`52***6`).
> - **中文：** Spark OTP Autofill **完全在本地 macOS 机器**上运行。所有验证码提取均为本地确定性正则与规则解析（零 LLM 调用、零外部云服务依赖、零凭证外发）。敏感验证码仅驻留于本地内存，并在所有审计日志中强制脱敏（如 `52***6`）。

---

## Key Capabilities

1. **Deterministic Zero-LLM Extraction Engine**:
   - Out-of-the-box rule profiles for **25+ major services**: Cloudflare Access, GitHub, Google, AWS / Amazon, Microsoft / Azure / Live, Stripe, Supabase, Vercel, Notion, Discord, Steam Guard (alphanumeric), Twitter / X, Shopify, Apple ID, Slack (hyphenated `UZW-XAD` normalized), Adobe (markdown bold wrapping), SOLIDWORKS / 3DS (`34P514`), TidyCal, Dia Browser, Marqeta 3DS Banking PINs, Bandwagon Host / KiwiVM, and more.
   - **Intelligent Multilingual Fallback**: Contextual proximity keyword scoring extracts codes from arbitrary enterprise SaaS platforms across English, 简体中文, 日本語, ภาษาไทย, and Tiếng Việt.
   - **Disqualification Safeguards**: Prevents false positive extraction of shipment tracking numbers, invoice amounts, reference codes, phone numbers, and dictionary words.

2. **Sub-Millisecond Direct SQLite Fast-Path (Tier 0)**:
   - Direct read-only URI connection (`mode=ro`) to Spark Desktop's CoreData database (`~/Library/Application Support/Spark Mail/core-data/messages.sqlite`).
   - Retrieval latency drops from ~7,500ms (CLI IPC) to **sub-3ms**.
   - Solves the Spark CLI thread-collapsing bug on identical subjects (e.g. `Device verification`), ensuring newly arrived OTPs are never masked.
   - Recency-aware account fallback: automatically promotes fresher OTPs from linked accounts if stale by >180s.

3. **5-Tier Universal Page Email Sniffing**:
   - Automatically sniffs the recipient email address from auth pages (e.g. `"To protect your account, we have sent a 6-digit code to alex.turner@gmail.com"`).
   - Dynamically binds `&account=` into API queries and displays the account badge in the floating pill UI.
   - 5-tier fallback cascade: form context, sentence regex matching, user profile cards, emphasis tags, and single valid user email scan.

4. **Anti-Loop Submission Guardrails & Failed Code Memory**:
   - Active error detection: senses URL error parameters (`?incorrect=true`, `?error=...`) and DOM alert banners.
   - Session-persistent blacklist (`sessionStorage`): records failed codes and message IDs across page reloads.
   - Input residue sniffing: automatically detects previously entered failed codes on error pages even if session storage is clear.
   - Daemon query filtering: `/api/otp` and `/api/stream` accept `exclude_codes`, `exclude_message_ids`, and `since_time`.
   - Never loops or re-submits a rejected code; waits strictly for newly received incoming emails.

5. **Universal DOM Input Detection & Immediate UI Feedback**:
   - Instant visual feedback upon input detection: displays floating pill with live ticking query timer (`00:01`, `00:02`) and manual refresh button.
   - Supports single input boxes, 4/6/8-digit segmented multi-box inputs (auto-advancing focus).
   - React 16+ controlled components via native property descriptor setters and `_valueTracker` bypass.
   - Modern component libraries (`input-otp`, `shadcn/ui`, `contenteditable` PIN fields).
   - Synthetic event dispatch (`input`, `change`, `keydown`, `keyup`, `keypress`, `paste`).
   - Internationalization (i18n): English and 简体中文 with automatic locale detection and popup switcher.

6. **Contract-First OpenAPI 3.0.3 & JSON Schema**:
   - Authoritative schemas exposed via `/api/openapi.json` and `/api/schema`.
   - Type contracts mirrored in TypeScript (`extension/types/contracts.d.ts`).

---

## Repository Structure

```
.
├── .gitignore
├── AGENTS.md
├── CHANGELOG.md
├── CLAUDE.md
├── DESIGN.md
├── GEMINI.md
├── LICENSE
├── README.md
├── cli.py
├── docs
│   ├── README.md
│   └── architecture.md
├── extension
│   ├── content.js
│   ├── icons
│   │   ├── icon.svg
│   │   ├── icon128.png
│   │   ├── icon16.png
│   │   └── icon48.png
│   ├── manifest.json
│   ├── popup
│   │   ├── popup.css
│   │   ├── popup.html
│   │   └── popup.js
│   ├── styles.css
│   └── types
│       └── contracts.d.ts
├── manifest.json
├── package.json
├── pyproject.toml
├── resources
│   └── README.md
├── spark_otp
│   ├── cli.py
│   ├── config.py
│   ├── contracts.py
│   ├── extractor.py
│   ├── models.py
│   ├── native_messaging.py
│   ├── server.py
│   ├── spark_client.py
│   └── telemetry.py
├── tests
│   ├── conftest.py
│   ├── fixtures.py
│   ├── test_adversarial.py
│   ├── test_contracts.py
│   ├── test_dom_detection.py
│   ├── test_e2e_flow.py
│   ├── test_extractor.py
│   ├── test_server.py
│   ├── test_spark_client.py
│   ├── test_sqlite_backend.py
│   └── test_telemetry.py
└── userscript
    └── spark-otp.user.js
```

---

## Quick Start

### Prerequisites
- macOS 12+
- [Spark Mail Desktop](https://sparkmailapp.com/) (with mail accounts logged in)
- Python 3.10 or later

### 1. Install & Start Daemon
```bash
# Clone the repository
git clone https://github.com/vecyang1/spark-otp.git
cd spark-otp

# Install python package (editable mode)
pip install -e .

# Start the local daemon on port 9428 (http://127.0.0.1:9428):
spark-otp serve --port 9428
# Or: python3 cli.py serve --port 9428
```

### 2. CLI Usage
```bash
# List all configured Spark email accounts:
spark-otp accounts

# Get latest OTP for current domain:
spark-otp get --domain github.com

# Target a specific email account:
spark-otp get --domain dashboard.stripe.com --account alex.turner@gmail.com

# Output structured JSON:
spark-otp get --domain finance.acme-cloud.net --json

# Watch for incoming codes in real-time in your terminal:
spark-otp watch --domain vercel.com
```

### 3. Chrome Extension (Manifest V3)
1. Open Google Chrome and navigate to `chrome://extensions`.
2. Enable **Developer mode** (toggle in the top-right corner).
3. Click **Load unpacked**.
4. Select the `extension/` directory inside this repository.
5. Click the extension icon in Chrome toolbar to configure preferred server port (default: `9428`), default email account, auto-submit toggle, and UI language.

### 4. Tampermonkey Userscript
If you prefer not using an unpacked extension:
1. Install [Tampermonkey](https://www.tampermonkey.net/) or Violentmonkey.
2. Install the userscript from `userscript/spark-otp.user.js`.
3. The userscript automatically detects 2FA input boxes on any website and connects to your local daemon at `http://127.0.0.1:9428`.

---

## API Reference

The local daemon exposes a high-performance REST and SSE API on port `9428`:

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Readiness check and live telemetry summary (`{"status": "ok", "spark_available": true}`). |
| `/api/accounts` | GET | List all mailbox accounts detected from Spark Desktop. |
| `/api/otp` | GET | Query latest matching OTP. Accepts `domain`, `account`, `max_age`, `exclude_codes`, `exclude_message_ids`, `since_time`. |
| `/api/stream` | GET | Server-Sent Events (SSE) real-time stream with automatic keepalive packets. |
| `/api/telemetry` | GET | Rolling metrics (hit rate %, average latency, p95 latency, masked event counts). |
| `/api/metrics` | GET | Alias for `/api/telemetry`. |
| `/api/logs` | GET | Recent privacy-masked audit logs (`limit` parameter supported). |
| `/api/openapi.json` | GET | Machine-readable OpenAPI 3.0.3 specification. |
| `/api/schema` | GET | Authoritative JSON Schema definitions for all request and response contracts. |

---

## Testing & Verification

Spark OTP includes a rigorous two-sided test suite covering positive paths, edge cases, adversarial challenges, and multi-threaded concurrency:

```bash
# Run the full automated test suite (132 tests):
python3 -m unittest discover -s tests -p "test_*.py" -v

# Or using pytest:
python3 -m pytest tests/ -v
```

### Verification Coverage
- `tests/test_extractor.py`: 54 tests validating deterministic parsing across 25+ services and multilingual patterns.
- `tests/test_dom_detection.py`: 8 tests validating WHMCS, segmented inputs, and anti-loop error recovery.
- `tests/test_adversarial.py`: 14 tests validating rejection of shipping tracking numbers, invoice numbers, expired tokens, and 30-client concurrency.
- `tests/test_sqlite_backend.py`: 9 tests validating sub-millisecond SQLite fast-path, account prioritization, and since-time filtering.
- `tests/test_spark_client.py`: 14 tests validating table parsing, account extraction, and rule queries.
- `tests/test_server.py`: 16 tests validating all HTTP/SSE endpoints, error handling, CORS, and keepalive.
- `tests/test_e2e_flow.py`: 7 tests validating full end-to-end integration and streaming delivery.
- `tests/test_contracts.py`: 6 tests validating OpenAPI 3.0.3 and JSON Schema compliance.
- `tests/test_telemetry.py`: 4 tests validating masked metrics and JSONL persistence.

---

## License

This project is licensed under the **Apache License, Version 2.0**. See the [LICENSE](LICENSE) file for details.


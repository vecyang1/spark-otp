#!/usr/bin/env python3
"""
Controlled Chrome extension smoke test for the Spark OTP race guard (v1.7.0+).

One command proves, in a real browser with the real unpacked extension:

  1. the extension loads from the repository root (same manifest Chrome uses in
     production) and its service worker registers;
  2. a Cloudflare-Access-style login page is detected (email step -> OTP step);
  3. clicking "Send login code" records `loginRequestAt` in the per-domain
     sessionStorage auth state;
  4. the FIRST /api/stream query already carries `since_time` and it equals
     floor(loginRequestAt / 1000) — i.e. stale codes requested before this login
     attempt can never be resolved by the first query;
  5. the floating pill shows the `race_guarded` state.

Design notes (wheel-check): no new framework, no pip dependency. The CDP client
is a short Node script embedded as a string, mirroring the existing
`tests/test_dom_detection.py` pattern of driving Node from Python. Branded
Google Chrome >= 137 refuses `--load-extension`, so Chrome-for-Testing /
Chromium binaries are preferred; a missing browser is reported as SKIP (exit 0)
rather than FAIL.

Usage:
    python3 scripts/e2e_extension_smoke.py
    python3 scripts/e2e_extension_smoke.py --chrome-bin "/path/to/Chrome for Testing" --keep
"""

import argparse
import glob
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MOCK_LOGIN_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Sign in</title></head>
<body>
  <h1>Sign in to app.example.com</h1>
  <div id="step-email">
    <input id="email" type="email" name="email" autocomplete="email" placeholder="Enter your email">
    <button id="send-btn" type="button">Send login code</button>
  </div>
  <script>
    document.getElementById("send-btn").addEventListener("click", function () {
      document.getElementById("step-email").remove();
      const wrap = document.createElement("div");
      wrap.innerHTML = '<p>We sent a login code to your email</p>' +
        '<input id="code" name="code" type="text" maxlength="6" autocomplete="one-time-code" placeholder="Enter the 6-digit code">' +
        '<button id="verify" type="button">Sign in</button>';
      document.body.appendChild(wrap);
      window.__loginRequestedAt = Date.now();
    });
  </script>
</body></html>
"""

# Embedded CDP client. Receives: process.argv[1]=CDP port, argv[2]=mock page port.
CDP_NODE_SCRIPT = r"""
(async () => {
  const CDP = 'http://127.0.0.1:' + process.argv[1];
  const PAGE = 'http://127.0.0.1:' + process.argv[2] + '/cloudflare-mock.html';
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const jget = async (url) => (await fetch(url)).json();

  let version = null;
  for (let i = 0; i < 150; i++) {
    try { version = await jget(CDP + '/json/version'); break; } catch (e) { await sleep(200); }
  }
  if (!version) throw new Error('CDP endpoint not reachable');

  // Prove the real unpacked extension registered its service worker.
  const targets = await jget(CDP + '/json/list');
  const extWorkers = targets.filter((t) =>
    (t.type === 'service_worker' || t.type === 'background_page') &&
    (t.url || '').indexOf('chrome-extension://') === 0
  ).map((t) => ({ type: t.type, url: t.url }));
  const pageTarget = targets.find((t) => t.type === 'page');
  if (!pageTarget) throw new Error('no page target');

  const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  const results = new Map();
  const requests = [];
  ws.addEventListener('message', (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id !== undefined) results.set(m.id, m);
    if (m.method === 'Network.requestWillBeSent') requests.push(m.params.request.url);
  });
  let nextId = 1;
  const raw = (method, params = {}) => {
    const id = nextId++;
    ws.send(JSON.stringify({ id, method, params }));
    return id;
  };
  async function wait(id, ms = 12000) {
    const t = Date.now();
    while (Date.now() - t < ms) {
      if (results.has(id)) return results.get(id);
      await sleep(50);
    }
    throw new Error('CDP timeout for command id ' + id);
  }
  async function run(expression) {
    const r = await wait(raw('Runtime.evaluate', { expression, returnByValue: true }));
    if (r.result && r.result.exceptionDetails) {
      throw new Error('eval exception: ' + JSON.stringify(r.result.exceptionDetails).slice(0, 300));
    }
    const v = r.result && r.result.result ? r.result.result.value : undefined;
    return v;
  }

  await wait(raw('Network.enable'), 6000);
  await wait(raw('Runtime.enable'), 12000);

  await run(`location.href = ${JSON.stringify(PAGE)}`);
  let loaded = false;
  for (let i = 0; i < 60; i++) {
    await sleep(250);
    try {
      const st = JSON.parse(await run(`JSON.stringify({ready: document.readyState, btn: !!document.getElementById('send-btn')})`));
      if (st.btn && st.ready !== 'loading') { loaded = true; break; }
    } catch (e) {}
  }
  if (!loaded) throw new Error('mock login page did not load');

  const before = JSON.parse(await run(`JSON.stringify({
    href: location.href,
    hasEmail: !!document.getElementById('email'),
    pill: (document.getElementById('spark-otp-pill-container') || {}).innerText || ''
  })`));

  await run(`document.getElementById('send-btn').click()`);
  await sleep(4000);

  const after = JSON.parse(await run(`JSON.stringify({
    hasOtp: !!document.getElementById('code'),
    pill: (document.getElementById('spark-otp-pill-container') || {}).innerText || '',
    authStates: Object.keys(sessionStorage)
      .filter((k) => k.indexOf('spark_otp_auth_') === 0)
      .map((k) => { try { return { key: k, value: JSON.parse(sessionStorage.getItem(k)) }; } catch (e) { return { key: k, value: null }; } })
  })`));

  const apiRequests = requests.filter((u) => u.indexOf('/api/') !== -1 && u.indexOf('domain=') !== -1);
  const streamReq = apiRequests.find((u) => u.indexOf('/api/stream') !== -1) || '';
  const m = streamReq.match(/since_time=(\d+)/);

  console.log(JSON.stringify({
    browser: version.Browser,
    extensionServiceWorkers: extWorkers,
    before, after,
    apiRequests: apiRequests.slice(-6),
    streamSinceTime: m ? Number(m[1]) : null
  }));
  ws.close();
  process.exit(0);
})().catch((e) => { console.error('CDP_ERROR: ' + ((e && e.stack) || e)); process.exit(1); });
"""


def find_chrome_binary(explicit=None):
    """Locate a Chromium build that still supports --load-extension."""
    if explicit:
        return explicit, "explicit --chrome-bin"
    env_bin = os.environ.get("SPARK_OTP_CHROME_BIN")
    if env_bin:
        return env_bin, "SPARK_OTP_CHROME_BIN"
    home = Path.home()
    patterns = [
        str(home / "Library/Caches/ms-playwright/chromium-*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"),
        str(home / "Library/Caches/ms-playwright/chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium"),
        str(home / ".cache/ms-playwright/chromium-*/chrome-*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"),
        "/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        # Branded Chrome >= 137 ignores --load-extension; kept as a last resort only.
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for pat in patterns:
        for candidate in sorted(glob.glob(pat), reverse=True):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate, pat
    return None, None


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_mock_server():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (stdlib naming)
            body = MOCK_LOGIN_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # silence
            return

    port = free_port()
    httpd = http.server.HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, port


def wait_for_cdp(port, timeout_seconds=30):
    import urllib.request
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as r:
                if r.getcode() == 200:
                    return json.loads(r.read().decode("utf-8"))
        except Exception:
            time.sleep(0.25)
    return None


def fail(message):
    print(f"FAIL: {message}")
    return 1


def main():
    parser = argparse.ArgumentParser(description="Controlled Chrome extension smoke test for the Spark OTP race guard")
    parser.add_argument("--chrome-bin", default=None, help="Path to a Chrome-for-Testing/Chromium binary (default: auto-detect)")
    parser.add_argument("--keep", action="store_true", help="Keep the temporary Chrome profile for inspection")
    parser.add_argument("--timeout", type=int, default=90, help="Overall smoke test timeout in seconds")
    args = parser.parse_args()

    if shutil.which("node") is None:
        print("SKIP: node is required to drive the CDP client (not found in PATH)")
        return 0

    chrome_bin, chrome_source = find_chrome_binary(args.chrome_bin)
    if not chrome_bin:
        print("SKIP: no Chrome-for-Testing / Chromium binary found.")
        print("      Install one or pass --chrome-bin <path> (branded Chrome >= 137 ignores --load-extension).")
        return 0
    try:
        chrome_version = subprocess.run([chrome_bin, "--version"], capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception as exc:
        print(f"SKIP: chrome binary could not be executed: {exc}")
        return 0
    print(f"[smoke] chrome: {chrome_bin} ({chrome_version or 'unknown version'}) via {chrome_source}")

    tmpdir = tempfile.mkdtemp(prefix="spark-otp-e2e-")
    profile_dir = os.path.join(tmpdir, "profile")
    httpd, page_port = start_mock_server()
    cdp_port = free_port()
    chrome_proc = None
    started = time.time()
    try:
        chrome_proc = subprocess.Popen(
            [
                chrome_bin,
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={profile_dir}",
                f"--load-extension={REPO_ROOT}",
                f"--disable-extensions-except={REPO_ROOT}",
                f"--remote-debugging-port={cdp_port}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        version = wait_for_cdp(cdp_port, timeout_seconds=30)
        if not version:
            return fail("Chrome started but its DevTools endpoint never became reachable")
        print(f"[smoke] CDP: {version.get('Browser', 'unknown')} port={cdp_port}")

        node_script = CDP_NODE_SCRIPT
        proc = subprocess.run(
            ["node", "-e", node_script, str(cdp_port), str(page_port)],
            capture_output=True,
            text=True,
            timeout=args.timeout,
        )
        if proc.returncode != 0:
            return fail(f"CDP client failed:\n{proc.stderr.strip()[-2000:]}")

        try:
            data = json.loads(proc.stdout.strip().splitlines()[-1])
        except Exception as exc:
            return fail(f"could not parse CDP client output ({exc}):\n{proc.stdout.strip()[-2000:]}")

        errors = []
        if not data.get("extensionServiceWorkers"):
            errors.append("extension service worker not registered (is --load-extension supported by this Chrome build?)")
        stream_since = data.get("streamSinceTime")
        auth_states = data.get("after", {}).get("authStates") or []
        state = None
        for item in auth_states:
            value = item.get("value") or {}
            if isinstance(value, dict) and value.get("loginRequestAt"):
                state = value
                break
        if state is None:
            errors.append("per-domain auth state with loginRequestAt was not written after clicking Send login code")
        if stream_since is None:
            errors.append("no /api/stream request with since_time captured (first query missing the time lower bound)")
        elif state is not None:
            expected = int(state["loginRequestAt"] // 1000)
            if stream_since != expected:
                errors.append(f"since_time mismatch: stream={stream_since} expected=floor(loginRequestAt/1000)={expected}")
        pill = data.get("after", {}).get("pill") or ""
        if "race guard" not in pill.lower() and "竞态守卫" not in pill:
            errors.append(f"pill did not render the race_guarded state (got: {pill!r})")
        if not data.get("after", {}).get("hasOtp"):
            errors.append("mock page never switched to the OTP step")

        print(f"[smoke] extension service workers: {json.dumps(data.get('extensionServiceWorkers'), ensure_ascii=False)}")
        print(f"[smoke] loginRequestAt={None if state is None else state.get('loginRequestAt')} source={None if state is None else state.get('loginRequestSource')}")
        print(f"[smoke] first-query since_time={stream_since} expected={None if state is None else int(state['loginRequestAt'] // 1000)}")
        print(f"[smoke] pill: {pill.strip().splitlines()[0] if pill.strip() else '(empty)'}")
        print(f"[smoke] api requests: {json.dumps(data.get('apiRequests'), ensure_ascii=False)}")

        if errors:
            for err in errors:
                print(f"[smoke] ERROR: {err}")
            return fail(f"{len(errors)} assertion(s) failed")
        print(f"[smoke] PASS in {time.time() - started:.1f}s")
        return 0
    finally:
        if chrome_proc is not None and chrome_proc.poll() is None:
            chrome_proc.terminate()
            try:
                chrome_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                chrome_proc.kill()
        httpd.shutdown()
        if args.keep:
            print(f"[smoke] kept profile: {profile_dir}")
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

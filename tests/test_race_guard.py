"""
Race Guard conformance tests (A/B/C): first-query time lower bound, bounded
auto-resend after a rejection, and UI/diagnostic observability.

Uses the same Node.js vm harness pattern as tests/test_dom_detection.py: the
SSOT engine block is extracted from extension/content.js and evaluated in a
sandbox, then the identical scenario matrix is run against the userscript copy
to guarantee 100% behavioral parity.
"""
import json
import os
import subprocess
import unittest
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
T0 = 1700000000000  # must match T0 inside the Node scenario script

START_MARKER = "// === BEGIN CORE DOM DETECTION ENGINE (SSOT) ==="
END_MARKER = "// === END CORE DOM DETECTION ENGINE (SSOT) ==="

_RACE_SCENARIO_JS = r"""
const vm = require('vm');
const contentJs = __CONTENT_JS__;
const userJs = __USER_JS__;

function extractSsot(src) {
  const s = '// === BEGIN CORE DOM DETECTION ENGINE (SSOT) ===';
  const e = '// === END CORE DOM DETECTION ENGINE (SSOT) ===';
  const start = src.indexOf(s);
  const end = src.indexOf(e, start);
  if (start === -1 || end === -1) throw new Error('SSOT markers missing');
  return src.slice(start + s.length, end);
}

const T0 = 1700000000000; // deterministic fake clock base

function makeSandbox(buttons) {
  const storage = {};
  let clock = T0;
  const RealDate = Date;
  function FakeDate(...args) {
    if (!(this instanceof FakeDate)) return new RealDate(...args);
    if (args.length === 0) return new RealDate(clock);
    return new RealDate(...args);
  }
  FakeDate.now = () => clock;
  FakeDate.prototype = RealDate.prototype;

  const alertEl = { textContent: '', children: [] };
  const el = (spec) => ({
    tagName: spec.tagName || 'BUTTON',
    textContent: spec.text || '',
    value: spec.value || '',
    disabled: Boolean(spec.disabled),
    _clicked: 0,
    click() { this._clicked += 1; },
    getAttribute(k) {
      if (k === 'aria-label' || k === 'title') return spec.aria || null;
      return null;
    },
    closest(sel) {
      if (spec.inPill && String(sel).indexOf('spark-otp-pill-container') !== -1) return { id: 'spark-otp-pill-container' };
      return null;
    }
  });
  const nodes = (buttons || []).map(el);

  const sandbox = {
    window: {
      location: {
        hostname: 'app.example.com',
        pathname: '/cdn-cgi/access/login',
        search: '',
        hash: '',
        href: 'https://app.example.com/cdn-cgi/access/login'
      },
      sessionStorage: {
        getItem(k) { return Object.prototype.hasOwnProperty.call(storage, k) ? storage[k] : null; },
        setItem(k, v) { storage[k] = String(v); },
        removeItem(k) { delete storage[k]; }
      },
      getComputedStyle: () => ({ display: 'block', visibility: 'visible', opacity: '1' })
    },
    document: {
      title: 'Sign in',
      body: { innerText: 'Enter the code' },
      readyState: 'complete',
      addEventListener() {},
      querySelector: () => null,
      querySelectorAll(sel) {
        if (sel === 'button, a[href], [role="button"], input[type="button"], input[type="submit"]') return nodes;
        return [];
      }
    },
    URL,
    console,
    CSS: { escape: (x) => x },
    NodeFilter: { SHOW_ELEMENT: 1 },
    Date: FakeDate
  };
  sandbox.window.top = sandbox.window;
  sandbox.window.self = sandbox.window;
  sandbox.__advance = (ms) => { clock += ms; };
  sandbox.__clock = () => clock;
  sandbox.__buttons = nodes;
  return sandbox;
}

function parseQuery(q) {
  const out = {};
  q.split('&').forEach((pair) => {
    const i = pair.indexOf('=');
    const k = decodeURIComponent(pair.slice(0, i));
    out[k] = decodeURIComponent(pair.slice(i + 1));
  });
  return out;
}

function runCase(src) {
  const D = 'app.example.com';
  const sandbox = makeSandbox([
    { text: 'Cancel' },
    { text: 'Sign out' },
    { text: 'Send Code', inPill: true },
    { text: 'Resend code' },
    { text: 'Delete account' }
  ]);
  const ctx = vm.createContext(sandbox);
  vm.runInContext(extractSsot(src), ctx);

  const out = {};

  // --- A1: first query (before any login request) already has a bound ---
  const freshReport = ctx.getRaceGuardReport('fresh.example.com');
  const freshQuery = parseQuery(ctx.buildApiQuery('fresh.example.com', 'me@example.com', {}));
  out.freshSinceTime = Number(freshQuery.since_time);
  out.freshFallbackSec = Math.floor(freshReport.page_fallback_ms / 1000);
  out.freshSource = freshReport.since_source;
  out.hasAllowExpired = freshQuery.allow_expired === '0';

  // --- A2: login request captured -> first query bound == loginRequestAt ---
  ctx.recordLoginRequest(D, 'button_click', T0);
  const q1 = parseQuery(ctx.buildApiQuery(D, 'me@example.com', { strictAccount: true }));
  out.loginSinceTime = Number(q1.since_time);
  out.loginSinceSource = ctx.getRaceGuardReport(D).since_source;
  out.strictAccount = q1.strict_account;

  // --- A3: stale code is excluded, fresh code is accepted ---
  out.staleRejected = ctx.isCodeRejected('262007', 'm-old', T0 - 60 * 1000, D);
  out.freshAccepted = ctx.isCodeRejected('121586', 'm-new', T0 + 5 * 1000, D);
  const staleReport = ctx.recordRaceCandidate(D, { code: '262007', message_id: 'm-old', received_at_ms: T0 - 60 * 1000 });
  out.staleVerdict = staleReport.verdict;
  const acceptedReport = ctx.recordRaceCandidate(D, { code: '121586', message_id: 'm-new', received_at_ms: T0 + 5 * 1000 });
  out.acceptedVerdict = acceptedReport.verdict;
  const rep = ctx.getRaceGuardReport(D);
  out.reportSinceTime = rep.since_time;
  out.reportLoginAt = rep.login_request_at;
  out.reportCandidateCount = rep.candidates.length;
  out.reportCandidateVerdicts = rep.candidates.map((c) => c.verdict);
  out.diagnoseRaceGuard = Boolean(ctx.diagnosePageDom && ctx.diagnosePageDom().race_guard);

  // --- A4: resend moves the bound forward (max(loginRequestAt, lastResendAt, fallback)) ---
  sandbox.__advance(20 * 60 * 1000);
  ctx.recordResend(D, 'auto', T0 + 1200000);
  const afterResend = parseQuery(ctx.buildApiQuery(D, 'me@example.com', {}));
  out.resendSinceTime = Number(afterResend.since_time);
  out.resendSource = ctx.getRaceGuardReport(D).since_source;
  out.oldCodeNowStale = ctx.isCodeRejected('121586', 'm-new', T0 + 5 * 1000, D);

  // --- B: bounded auto-resend plan ---
  const pageErr = { hasError: true, reason: 'dom_text', text: 'That account does not have access.' };
  // Reset budget for a clean rejection event.
  ctx.recordLoginRequest(D, 'button_click', sandbox.__clock());
  const st = ctx.getAuthState(D);
  st.lastFailedAt = sandbox.__clock();
  ctx.saveAuthState(st, D);

  const plan1 = ctx.planAutoResend(D, pageErr, sandbox.__clock() + 500);
  out.plan1 = { action: plan1.action, count: plan1.resend_count, hasControl: Boolean(plan1.control) };
  ctx.recordResend(D, 'auto', sandbox.__clock() + 500);

  const plan2 = ctx.planAutoResend(D, pageErr, sandbox.__clock() + 1500);
  out.plan2 = { action: plan2.action, reason: plan2.reason };

  // New rejection event, but cooldown has not elapsed yet.
  const st2 = ctx.getAuthState(D);
  st2.lastFailedAt = sandbox.__clock() + 5000;
  ctx.saveAuthState(st2, D);
  const plan3 = ctx.planAutoResend(D, pageErr, sandbox.__clock() + 6000);
  out.plan3 = { action: plan3.action, reason: plan3.reason };

  // After the 20s cooldown a second (and final) resend is allowed.
  const plan4 = ctx.planAutoResend(D, pageErr, sandbox.__clock() + 25000);
  out.plan4 = { action: plan4.action, count: plan4.resend_count };
  ctx.recordResend(D, 'auto', sandbox.__clock() + 25000);

  // Third rejection exceeds the hard cap of 2 auto-resends.
  const st3 = ctx.getAuthState(D);
  st3.lastFailedAt = sandbox.__clock() + 30000;
  ctx.saveAuthState(st3, D);
  const plan5 = ctx.planAutoResend(D, pageErr, sandbox.__clock() + 60000);
  out.plan5 = { action: plan5.action, reason: plan5.reason, count: plan5.resend_count, limit: plan5.resend_limit };

  // Non-auth page error must never trigger a resend.
  const nonAuth = ctx.planAutoResend(D, { hasError: true, reason: 'url_param' }, sandbox.__clock() + 90000);
  out.nonAuthPlan = nonAuth.action;

  // --- B2: no resend control -> manual_required, nothing clicked ---
  const sb2 = makeSandbox([{ text: 'Cancel' }, { text: 'Sign out' }]);
  const ctx2 = vm.createContext(sb2);
  vm.runInContext(extractSsot(src), ctx2);
  ctx2.recordLoginRequest(D, 'button_click', T0);
  const st4 = ctx2.getAuthState(D);
  st4.lastFailedAt = T0 + 1000;
  ctx2.saveAuthState(st4, D);
  const planNoControl = ctx2.planAutoResend(D, pageErr, T0 + 2000);
  out.noControlPlan = { action: planNoControl.action, reason: planNoControl.reason };
  out.noControlClicks = sb2.__buttons.reduce((n, b) => n + b._clicked, 0);

  // --- B3: dangerous buttons are never chosen; pill buttons excluded ---
  out.controlLabel = (function () {
    const ctrl = ctx.findResendControl();
    return ctrl ? ctrl.textContent : null;
  })();
  out.pillSkipped = ctx.findResendControl() !== null && ctx.findResendControl().textContent !== 'Send Code';
  out.controlClicksBeforeClick = sandbox.__buttons.find(b => b.textContent === 'Resend code')._clicked;

  return out;
}

console.log(JSON.stringify({ ext: runCase(contentJs), user: runCase(userJs) }));
"""


def _run_race_scenario():
    content_js = (REPO_ROOT / "extension" / "content.js").read_text(encoding="utf-8")
    user_js = (REPO_ROOT / "userscript" / "spark-otp.user.js").read_text(encoding="utf-8")
    js_code = _RACE_SCENARIO_JS.replace("__CONTENT_JS__", json.dumps(content_js)).replace("__USER_JS__", json.dumps(user_js))
    proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, cwd=str(REPO_ROOT))
    if proc.returncode != 0:
        raise AssertionError(f"Node race scenario failed: {proc.stderr}")
    return json.loads(proc.stdout)


class TestRaceGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = _run_race_scenario()

    def _get(self, key):
        return self.data["ext"][key]

    def test_a1_first_query_always_has_lower_bound(self):
        """The very first query must carry since_time (page fallback = pageLoadAt - 300s), not only after a failure."""
        self.assertTrue(self._get("hasAllowExpired"))
        self.assertEqual(self._get("freshSinceTime"), self._get("freshFallbackSec"))
        self.assertEqual(self._get("freshSource"), "page_fallback")
        for target in ("ext", "user"):
            self.assertEqual(self.data[target]["freshSinceTime"], self.data[target]["freshFallbackSec"], target)

    def test_a2_login_request_bound_and_strict_account(self):
        """since_time == floor(loginRequestAt/1000) and the strict/allow-expired hardening survives."""
        self.assertEqual(self._get("loginSinceTime"), int(T0 // 1000))
        self.assertEqual(self._get("loginSinceSource"), "login_request")
        self.assertEqual(self._get("strictAccount"), "1")

    def test_a3_stale_candidate_excluded_and_fresh_accepted(self):
        self.assertTrue(self._get("staleRejected"), "code received before the login request must be rejected")
        self.assertFalse(self._get("freshAccepted"), "code received after the login request must be accepted")
        self.assertEqual(self._get("staleVerdict"), "excluded_stale")
        self.assertEqual(self._get("acceptedVerdict"), "accepted")
        self.assertEqual(self._get("reportCandidateVerdicts"), ["accepted", "excluded_stale"])
        self.assertTrue(self._get("diagnoseRaceGuard"), "diagnosePageDom() must expose a race_guard block")

    def test_a4_resend_moves_lower_bound_forward(self):
        self.assertEqual(self._get("resendSinceTime"), int((T0 + 1200000) // 1000))
        self.assertEqual(self._get("resendSource"), "resend")
        self.assertTrue(self._get("oldCodeNowStale"), "code from the previous attempt must be stale after a resend")

    def test_b_auto_resend_is_bounded_and_never_loops(self):
        self.assertEqual(self._get("plan1")["action"], "resend")
        self.assertTrue(self._get("plan1")["hasControl"])
        self.assertEqual(self._get("plan1")["count"], 1)
        # Same failure event must never be resent twice (no duplicate submission).
        self.assertEqual(self._get("plan2")["action"], "wait")
        self.assertEqual(self._get("plan2")["reason"], "already_resent_for_this_failure")
        # Cooldown gate.
        self.assertEqual(self._get("plan3")["action"], "wait")
        self.assertEqual(self._get("plan3")["reason"], "cooldown")
        # Second resend after cooldown, then the hard cap.
        self.assertEqual(self._get("plan4")["action"], "resend")
        self.assertEqual(self._get("plan4")["count"], 2)
        self.assertEqual(self._get("plan5")["action"], "manual_required")
        self.assertEqual(self._get("plan5")["reason"], "resend_limit")
        self.assertEqual(self._get("plan5")["limit"], 2)
        self.assertEqual(self._get("nonAuthPlan"), "none")

    def test_b2_no_resend_control_means_manual_required_and_no_click(self):
        self.assertEqual(self._get("noControlPlan")["action"], "manual_required")
        self.assertEqual(self._get("noControlPlan")["reason"], "no_resend_control")
        self.assertEqual(self._get("noControlClicks"), 0, "must never click a dangerous/absent control")

    def test_b3_resend_control_matching_excludes_dangerous_and_pill_buttons(self):
        self.assertEqual(self._get("controlLabel"), "Resend code")
        self.assertTrue(self._get("pillSkipped"))
        self.assertEqual(self._get("controlClicksBeforeClick"), 0, "planning must not click; only the orchestrator clicks")

    def test_zz_userscript_parity(self):
        """The SSOT engine must behave identically in the userscript build."""
        self.assertEqual(self.data["ext"], self.data["user"], "userscript SSOT drifted from extension behavior")



_PROGRAMMATIC_CLICK_SCENARIO_JS = r"""
const vm = require('vm');
const contentJs = __CONTENT_JS__;
const userJs = __USER_JS__;

function extractSsot(src) {
  const s = '// === BEGIN CORE DOM DETECTION ENGINE (SSOT) ===';
  const e = '// === END CORE DOM DETECTION ENGINE (SSOT) ===';
  const start = src.indexOf(s);
  const end = src.indexOf(e, start);
  if (start === -1 || end === -1) throw new Error('SSOT markers missing');
  return src.slice(start + s.length, end);
}

const T0 = 1700000000000;

function makeSandbox(buttons) {
  const storage = {};
  let clock = T0;
  const RealDate = Date;
  function FakeDate(...args) {
    if (!(this instanceof FakeDate)) return new RealDate(...args);
    if (args.length === 0) return new RealDate(clock);
    return new RealDate(...args);
  }
  FakeDate.now = () => clock;
  FakeDate.prototype = RealDate.prototype;

  const listeners = { click: [], submit: [], keydown: [] };
  // Real browser semantics: a button .click() synchronously dispatches a capture-phase
  // click event to the document listeners, whether the click was user- or code-driven.
  const nodes = (buttons || []).map((spec) => ({
    tagName: spec.tagName || 'BUTTON',
    textContent: spec.text || '',
    value: spec.value || '',
    disabled: Boolean(spec.disabled),
    _clicked: 0,
    click() {
      this._clicked += 1;
      (listeners.click || []).forEach((fn) => fn({ target: this, type: 'click' }));
    },
    getAttribute() { return null; },
    closest() { return null; }
  }));

  const sandbox = {
    window: {
      location: { hostname: 'app.example.com', pathname: '/cdn-cgi/access/login', search: '', hash: '', href: 'https://app.example.com/cdn-cgi/access/login' },
      sessionStorage: {
        getItem(k) { return Object.prototype.hasOwnProperty.call(storage, k) ? storage[k] : null; },
        setItem(k, v) { storage[k] = String(v); },
        removeItem(k) { delete storage[k]; }
      },
      getComputedStyle: () => ({ display: 'block', visibility: 'visible', opacity: '1' })
    },
    document: {
      title: 'Sign in',
      body: { innerText: 'Enter the code' },
      readyState: 'complete',
      addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
      querySelector: () => null,
      querySelectorAll(sel) {
        if (sel === 'button, a[href], [role="button"], input[type="button"], input[type="submit"]') return nodes;
        return [];
      }
    },
    URL,
    console,
    CSS: { escape: (x) => x },
    NodeFilter: { SHOW_ELEMENT: 1 },
    Date: FakeDate
  };
  sandbox.window.top = sandbox.window;
  sandbox.window.self = sandbox.window;
  sandbox.__advance = (ms) => { clock += ms; };
  sandbox.__clock = () => clock;
  sandbox.__listeners = listeners;
  return sandbox;
}

function runCase(src) {
  const D = 'app.example.com';
  const sandbox = makeSandbox([
    { text: 'Cancel' },
    { text: 'Resend code' },
    { text: 'Sign out' }
  ]);
  const ctx = vm.createContext(sandbox);
  vm.runInContext(extractSsot(src), ctx);

  // Real capture listener registration (SSOT): click/submit are now instrumented.
  ctx.installLoginRequestCapture(D);

  const out = {};
  const t0 = sandbox.__clock();
  ctx.recordLoginRequest(D, 'button_click', t0);
  const st = ctx.getAuthState(D);
  st.lastFailedAt = t0 + 1000;
  ctx.saveAuthState(st, D);
  const pageErr = { hasError: true, reason: 'dom_text', text: 'That account does not have access.' };

  // --- auto resend #1: plan -> recordResend -> programmatic click (orchestration order) ---
  const plan1 = ctx.planAutoResend(D, pageErr, t0 + 2000);
  ctx.recordResend(D, 'auto', t0 + 2000);
  const clickResult = ctx.runProgrammaticClick(plan1.control);
  const st1 = ctx.getAuthState(D);
  out.autoResend1 = {
    planAction: plan1.action,
    clickResult,
    resendCount: st1.resendCount,
    resendForFailedAt: st1.resendForFailedAt,
    lastFailedAt: st1.lastFailedAt,
    loginRequestAt: st1.loginRequestAt,
    budgetPreserved: st1.resendCount === 1 && st1.resendForFailedAt === st1.lastFailedAt,
    loginRequestNotReset: st1.loginRequestAt === t0
  };

  // --- same failure must be "wait / already_resent" (no second click) ---
  const plan2 = ctx.planAutoResend(D, pageErr, t0 + 3000);
  out.sameFailurePlan = { action: plan2.action, reason: plan2.reason };

  // --- second distinct failure after cooldown -> second resend, then hard cap ---
  sandbox.__advance(25000); // clock now T0+25000
  const st2 = ctx.getAuthState(D);
  st2.lastFailedAt = sandbox.__clock();
  ctx.saveAuthState(st2, D);
  const plan3 = ctx.planAutoResend(D, pageErr, sandbox.__clock() + 1000);
  ctx.recordResend(D, 'auto', sandbox.__clock() + 1000);
  ctx.runProgrammaticClick(plan3.control);
  const st3 = ctx.getAuthState(D);
  out.autoResend2 = { action: plan3.action, resendCount: st3.resendCount, budgetPreserved: st3.resendForFailedAt === st3.lastFailedAt };

  // Third rejection -> manual_required and NO click (control.click not invoked again).
  sandbox.__advance(25000);
  const st4 = ctx.getAuthState(D);
  st4.lastFailedAt = sandbox.__clock();
  ctx.saveAuthState(st4, D);
  const plan4 = ctx.planAutoResend(D, pageErr, sandbox.__clock() + 1000);
  out.thirdRejection = { action: plan4.action, reason: plan4.reason, controlPresent: Boolean(plan4.control) };

  // --- real user click on a login-request control must STILL be captured ---
  // After runProgrammaticClick() returns, the guard flag must be false again.
  sandbox.__advance(5000);
  const userNow = sandbox.__clock();
  const userTrigger = { textContent: 'Send login code', value: '', disabled: false, getAttribute: () => null, closest: () => null };
  (sandbox.__listeners.click || []).forEach((fn) => fn({ target: userTrigger, type: 'click' }));
  const st5 = ctx.getAuthState(D);
  out.userClickAfter = {
    loginRequestAtUpdated: st5.loginRequestAt === userNow,
    resendBudgetReset: st5.resendCount === 0 && st5.lastResendAt === 0
  };

  return out;
}

console.log(JSON.stringify({ ext: runCase(contentJs), user: runCase(userJs) }));
"""


def _run_programmatic_click_scenario():
    content_js = (REPO_ROOT / "extension" / "content.js").read_text(encoding="utf-8")
    user_js = (REPO_ROOT / "userscript" / "spark-otp.user.js").read_text(encoding="utf-8")
    js_code = _PROGRAMMATIC_CLICK_SCENARIO_JS.replace("__CONTENT_JS__", json.dumps(content_js)).replace("__USER_JS__", json.dumps(user_js))
    proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, cwd=str(REPO_ROOT))
    if proc.returncode != 0:
        raise AssertionError(f"Node programmatic-click scenario failed: {proc.stderr}")
    return json.loads(proc.stdout)


class TestProgrammaticResendClickGuard(unittest.TestCase):
    """Regression: a programmatic .click() on the resend control must not be mistaken for
    a user login request (which would reset the auto-resend budget and re-open the loop)."""

    @classmethod
    def setUpClass(cls):
        cls.data = _run_programmatic_click_scenario()

    def _check_target(self, target):
        r = self.data[target]
        self.assertEqual(r["autoResend1"]["planAction"], "resend", target)
        self.assertTrue(r["autoResend1"]["clickResult"], target)
        self.assertTrue(r["autoResend1"]["budgetPreserved"], f"{target}: resend budget was reset by the programmatic click")
        self.assertEqual(r["autoResend1"]["resendCount"], 1, target)
        self.assertEqual(r["autoResend1"]["resendForFailedAt"], r["autoResend1"]["lastFailedAt"], target)
        self.assertTrue(r["autoResend1"]["loginRequestNotReset"], f"{target}: programmatic click must not fabricate a new loginRequestAt")
        self.assertEqual(r["sameFailurePlan"]["action"], "wait", target)
        self.assertEqual(r["sameFailurePlan"]["reason"], "already_resent_for_this_failure", target)
        self.assertEqual(r["autoResend2"]["action"], "resend", target)
        self.assertEqual(r["autoResend2"]["resendCount"], 2, target)
        self.assertTrue(r["autoResend2"]["budgetPreserved"], target)
        self.assertEqual(r["thirdRejection"]["action"], "manual_required", target)
        self.assertEqual(r["thirdRejection"]["reason"], "resend_limit", target)
        self.assertFalse(r["thirdRejection"]["controlPresent"], f"{target}: hard-capped plan must not offer a control to click")
        self.assertTrue(r["userClickAfter"]["loginRequestAtUpdated"], f"{target}: guard must not swallow a real user click")
        self.assertTrue(r["userClickAfter"]["resendBudgetReset"], f"{target}: a genuine new login request must reset the resend budget")

    def test_programmatic_click_does_not_reset_resend_budget(self):
        self._check_target("ext")

    def test_userscript_programmatic_click_parity(self):
        self._check_target("user")
        self.assertEqual(self.data["ext"], self.data["user"], "userscript SSOT drifted from extension behavior")


class TestRaceGuardUiAndContract(unittest.TestCase):
    def test_pill_states_and_i18n_exist_in_both_targets(self):
        for rel in ("extension/content.js", "userscript/spark-otp.user.js"):
            src = (REPO_ROOT / rel).read_text(encoding="utf-8")
            for state in ("race_guarded", "resend_sent", "waiting_new_code", "manual_required"):
                self.assertIn(state, src, f"{rel} missing pill state {state}")
            for key in (
                "raceGuardedTitle", "raceGuardedSubtitle",
                "resendSentTitle", "resendSentSubtitle",
                "waitingNewCodeTitle", "waitingNewCodeSubtitle",
                "manualRequiredTitle", "manualRequiredSubtitle",
            ):
                self.assertIn(key, src, f"{rel} missing i18n key {key}")
            # Both en and zh blocks must carry the new keys.
            self.assertEqual(src.count("raceGuardedTitle:"), 2, f"{rel}: raceGuardedTitle must exist in en+zh")

    def test_popup_race_guard_contract(self):
        popup_js = (REPO_ROOT / "extension" / "popup" / "popup.js").read_text(encoding="utf-8")
        popup_html = (REPO_ROOT / "extension" / "popup" / "popup.html").read_text(encoding="utf-8")
        types = (REPO_ROOT / "extension" / "types" / "contracts.d.ts").read_text(encoding="utf-8")
        self.assertIn("inspector-race-guard", popup_html)
        self.assertIn("renderRaceGuard", popup_js)
        self.assertIn("race_guard", popup_js)
        for field in ("since_time", "login_request_at", "resend_count", "last_failed_reason"):
            self.assertIn(field, popup_js, f"popup must render race_guard.{field}")
        self.assertIn("RaceGuardReport", types)
        self.assertIn("race_guard: RaceGuardReport", types)
        self.assertIn("since_source", types)


class TestDiagnoseSinceTimeEngine(unittest.TestCase):
    """Daemon-side diagnose engine: candidates older than the login-request bound are
    counted and explained, and resolution never returns the stale code."""

    def setUp(self):
        import tempfile
        from tests.test_sqlite_backend import create_mock_spark_sqlite, insert_mock_message
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "messages.sqlite")
        create_mock_spark_sqlite(self.db_path)
        now = datetime.now()
        ts = int(now.timestamp())
        # 19:48 stale code (invalidated by the later login request)
        insert_mock_message(
            self.db_path, pk=900001,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="dev.team@example.com",
            subject="Device verification",
            short_body="Your device verification code: 262007. It is valid for 1 hour.",
            received_ts=ts - 600,
        )
        # 19:59 fresh code (arrived after the login request at ts-100)
        insert_mock_message(
            self.db_path, pk=900002,
            sender="Bandwagon Host <noreply@64clouds.com>",
            recipient="dev.team@example.com",
            subject="Device verification",
            short_body="Your device verification code: 121586. It is valid for 1 hour.",
            received_ts=ts - 10,
        )
        self.now = now
        self.ts = ts
        from spark_otp.spark_client import SparkClient
        self.client = SparkClient(sqlite_path=self.db_path, spark_bin="/usr/bin/false")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_diagnose_marks_stale_candidate_excluded_and_waits_for_new_code(self):
        diag = self.client.diagnose(
            target="bandwagonhost.com",
            account="dev.team@example.com",
            since_time=self.ts - 100,
            now=self.now,
        )
        self.assertEqual(diag["since_time"], self.ts - 100)
        self.assertGreaterEqual(diag["excluded_by_since_time_count"], 1)
        self.assertIn("since_time", diag["excluded_by_since_time_reason"])
        stale = [c for c in diag["candidates"] if c["message_id"] == "900001"]
        fresh = [c for c in diag["candidates"] if c["message_id"] == "900002"]
        self.assertTrue(stale and stale[0]["excluded_by_since_time"], "old code must be flagged excluded_stale")
        self.assertEqual(stale[0]["since_time_verdict"], "excluded_stale")
        self.assertTrue(fresh and not fresh[0]["excluded_by_since_time"])
        self.assertIsNotNone(diag["resolved_otp"])
        self.assertEqual(diag["resolved_otp"]["code"], "121586", "resolution must prefer the fresh code")
        self.assertEqual(diag["query"]["since_time"], self.ts - 100)

    def test_diagnose_without_since_time_keeps_legacy_shape(self):
        diag = self.client.diagnose(target="bandwagonhost.com", now=self.now)
        self.assertIsNone(diag["since_time"])
        self.assertEqual(diag["excluded_by_since_time_count"], 0)
        self.assertIsNone(diag["excluded_by_since_time_reason"])
        self.assertTrue(all(not c["excluded_by_since_time"] for c in diag["candidates"]))


if __name__ == "__main__":
    unittest.main()

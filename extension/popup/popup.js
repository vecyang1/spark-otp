document.addEventListener("DOMContentLoaded", async () => {
  const statusBadge = document.getElementById("status-badge");
  const latestCode = document.getElementById("latest-code");
  const latestDomain = document.getElementById("latest-domain");
  const btnCopy = document.getElementById("btn-copy-latest");
  const toggleAutoSubmit = document.getElementById("toggle-auto-submit");
  const toggleAutoEmail = document.getElementById("toggle-auto-email");
  const toggleAutoJump = document.getElementById("toggle-auto-jump");
  const selectAccount = document.getElementById("select-account");
  const selectLang = document.getElementById("select-lang");
  const inputEmail = document.getElementById("input-email");
  const inputPort = document.getElementById("input-port");
  const btnSave = document.getElementById("btn-save");
  const btnRefresh = document.getElementById("btn-refresh");
  const saveMsg = document.getElementById("save-msg");

  let savedAccount = "";

  // Load saved settings
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.sync) {
    chrome.storage.sync.get(["serverPort", "autoSubmit", "autoEmail", "defaultEmail", "selectedAccount", "autoDirectJump", "language"], (res) => {
      if (res.serverPort) inputPort.value = res.serverPort;
      if (typeof res.autoSubmit !== "undefined") toggleAutoSubmit.checked = res.autoSubmit;
      if (typeof res.autoEmail !== "undefined") toggleAutoEmail.checked = res.autoEmail;
      if (res.defaultEmail) inputEmail.value = res.defaultEmail;
      if (res.selectedAccount) savedAccount = res.selectedAccount;
      if (typeof res.autoDirectJump !== "undefined") toggleAutoJump.checked = res.autoDirectJump;
      if (res.language && selectLang) selectLang.value = res.language;
      checkDaemon();
    });
  } else {
    checkDaemon();
  }

  async function checkDaemon() {
    const port = inputPort.value || 9428;
    statusBadge.className = "badge checking";
    statusBadge.textContent = "Checking...";

    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/health`, { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        if (data.spark_available) {
          statusBadge.className = "badge online";
          statusBadge.textContent = "Connected";
          fetchAccounts(port);
          fetchLatestOtp(port);
          fetchTelemetry(port);
        } else {
          statusBadge.className = "badge offline";
          statusBadge.textContent = "Spark Offline";
        }
      } else {
        throw new Error("Bad status");
      }
    } catch (e) {
      statusBadge.className = "badge offline";
      statusBadge.textContent = "Daemon Offline";
      latestCode.textContent = "------";
      btnCopy.disabled = true;
      latestDomain.textContent = "Run: python3 cli.py start";
      document.getElementById("metric-latency").textContent = "-- ms";
      document.getElementById("metric-hitrate").textContent = "-- %";
      document.getElementById("metric-requests").textContent = "0";
    }
  }

  async function fetchTelemetry(port) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/telemetry`, { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.telemetry) {
          const t = data.telemetry;
          const latEl = document.getElementById("metric-latency");
          const hitEl = document.getElementById("metric-hitrate");
          const reqEl = document.getElementById("metric-requests");
          const lat = typeof t.otp_avg_latency_ms !== "undefined" && t.otp_total > 0 ? t.otp_avg_latency_ms : (t.avg_latency_ms || 0);
          const hit = typeof t.otp_hit_rate_pct !== "undefined" && t.otp_total > 0 ? t.otp_hit_rate_pct : (t.hit_rate_pct || 0);
          const total = typeof t.otp_total !== "undefined" && t.otp_total > 0 ? t.otp_total : (t.total_requests || 0);
          if (latEl) latEl.textContent = `${lat} ms`;
          if (hitEl) hitEl.textContent = `${hit}%`;
          if (reqEl) reqEl.textContent = String(total);
        }
      }
    } catch (e) {}
  }

  async function fetchAccounts(port) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/accounts`, { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        if (data.success && Array.isArray(data.accounts)) {
          selectAccount.innerHTML = '<option value="">Unified Inbox (All Accounts)</option>';
          for (const acc of data.accounts) {
            const opt = document.createElement("option");
            opt.value = acc;
            opt.textContent = acc;
            if (acc === savedAccount) opt.selected = true;
            selectAccount.appendChild(opt);
          }
        }
      }
    } catch (e) {}
  }

  async function fetchLatestOtp(port) {
    try {
      let url = `http://127.0.0.1:${port}/api/otp`;
      if (savedAccount) url += `?account=${encodeURIComponent(savedAccount)}`;
      const res = await fetch(url, { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.otp) {
          latestCode.textContent = data.otp.code;
          btnCopy.disabled = false;
          latestDomain.textContent = `${data.otp.domain || data.otp.service} (${data.otp.time_remaining_seconds}s left)`;
        } else {
          latestCode.textContent = "------";
          btnCopy.disabled = true;
          latestDomain.textContent = "No active OTP found";
        }
      }
    } catch (e) {
      // ignore
    }
  }

  btnCopy.addEventListener("click", () => {
    const code = latestCode.textContent;
    if (code && code !== "------") {
      navigator.clipboard.writeText(code);
      btnCopy.textContent = "Copied!";
      setTimeout(() => { btnCopy.textContent = "Copy"; }, 1500);
    }
  });

  btnSave.addEventListener("click", () => {
    const port = parseInt(inputPort.value, 10) || 9428;
    const autoSubmit = toggleAutoSubmit.checked;
    const autoEmail = toggleAutoEmail.checked;
    const defaultEmail = inputEmail.value.trim() || "alex.turner@gmail.com";
    const selectedAccountVal = selectAccount.value || "";
    savedAccount = selectedAccountVal;
    const autoDirectJump = toggleAutoJump.checked;
    const languageVal = selectLang ? selectLang.value : "auto";

    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.sync) {
      chrome.storage.sync.set({
        serverPort: port,
        autoSubmit: autoSubmit,
        autoEmail: autoEmail,
        defaultEmail: defaultEmail,
        selectedAccount: selectedAccountVal,
        autoDirectJump: autoDirectJump,
        language: languageVal
      }, () => {
        saveMsg.textContent = "Settings saved!";
        setTimeout(() => { saveMsg.textContent = ""; }, 2000);
        checkDaemon();
      });
    }
  });

  btnRefresh.addEventListener("click", checkDaemon);
});

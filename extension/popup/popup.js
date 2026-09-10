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
  let currentLang = "auto";
  let lastDaemonStatus = "checking"; // checking, online, spark_offline, daemon_offline

  const POPUP_I18N = {
    en: {
      connecting: "Connecting...",
      checking: "Checking...",
      connected: "Connected",
      spark_offline: "Spark Offline",
      daemon_offline: "Daemon Offline",
      latest_detected_code: "Latest Detected Code",
      copy: "Copy",
      copied: "Copied!",
      no_recent_code: "No recent code",
      no_active_otp: "No active OTP found",
      run_cli: "Run: python3 cli.py daemon start",
      system_performance: "System Performance & Latency",
      avg_latency: "Avg Latency",
      hit_rate: "Hit Rate",
      queries: "Queries",
      automation_settings: "Automation Settings",
      auto_submit: "Auto-submit verification code",
      auto_email: "Auto-fill email & send code",
      auto_jump: "Auto-jump via Cloudflare magic link",
      spark_mailbox_account: "Spark Mailbox Account",
      unified_inbox: "Unified Inbox (All Accounts)",
      language_label: "Language / 语言",
      lang_auto: "Auto (Browser)",
      preferred_email: "Preferred Email",
      daemon_port: "Daemon Port",
      check_daemon: "Check Daemon",
      save_settings: "Save Settings",
      saved_msg: "Settings saved!",
      left_sec: "s left"
    },
    zh: {
      connecting: "正在连接...",
      checking: "正在检查...",
      connected: "已连接",
      spark_offline: "Spark 离线",
      daemon_offline: "后台服务离线",
      latest_detected_code: "最新捕获验证码",
      copy: "复制",
      copied: "已复制!",
      no_recent_code: "暂无最新验证码",
      no_active_otp: "未找到有效验证码",
      run_cli: "请在终端运行: python3 cli.py daemon start",
      system_performance: "系统性能与耗时指标",
      avg_latency: "平均延迟",
      hit_rate: "命中率",
      queries: "查询次数",
      automation_settings: "自动化与策略设置",
      auto_submit: "自动填充并提交验证码",
      auto_email: "自动填充首选邮箱并发送验证码",
      auto_jump: "自动跳转 Cloudflare 直达登录链接",
      spark_mailbox_account: "Spark 邮箱账户过滤",
      unified_inbox: "全域统一收件箱 (所有账户)",
      language_label: "界面语言 / Language",
      lang_auto: "跟随浏览器 (Auto)",
      preferred_email: "默认首选邮箱",
      daemon_port: "本地服务端口",
      check_daemon: "检查服务状态",
      save_settings: "保存配置",
      saved_msg: "配置已保存并同步!",
      left_sec: "秒有效"
    }
  };

  function resolveLang(pref) {
    if (pref && pref !== "auto") return pref;
    const navLang = (typeof navigator !== "undefined" && (navigator.language || navigator.userLanguage) || "").toLowerCase();
    return navLang.startsWith("zh") ? "zh" : "en";
  }

  function t(key, lang = currentLang) {
    const active = resolveLang(lang);
    const dict = POPUP_I18N[active] || POPUP_I18N.en;
    return dict[key] || POPUP_I18N.en[key] || key;
  }

  function applyLanguage(lang) {
    currentLang = lang;
    const active = resolveLang(lang);
    const dict = POPUP_I18N[active] || POPUP_I18N.en;
    document.querySelectorAll("[data-i18n]").forEach(el => {
      const key = el.getAttribute("data-i18n");
      if (dict[key]) {
        el.textContent = dict[key];
      }
    });

    // Refresh dynamic status badge
    if (lastDaemonStatus === "online") {
      statusBadge.textContent = t("connected");
    } else if (lastDaemonStatus === "spark_offline") {
      statusBadge.textContent = t("spark_offline");
    } else if (lastDaemonStatus === "daemon_offline") {
      statusBadge.textContent = t("daemon_offline");
      if (latestDomain.textContent.includes("python3") || latestDomain.textContent.includes("cli.py")) {
        latestDomain.textContent = t("run_cli");
      }
    } else {
      statusBadge.textContent = t("checking");
    }

    // Refresh unified inbox default option
    const firstOpt = selectAccount.querySelector("option[value='']");
    if (firstOpt) {
      firstOpt.textContent = t("unified_inbox");
    }
  }

  if (selectLang) {
    selectLang.addEventListener("change", () => {
      applyLanguage(selectLang.value);
    });
  }

  // Load saved settings
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.sync) {
    chrome.storage.sync.get(["serverPort", "autoSubmit", "autoEmail", "defaultEmail", "selectedAccount", "autoDirectJump", "language"], (res) => {
      if (res.serverPort) inputPort.value = res.serverPort;
      if (typeof res.autoSubmit !== "undefined") toggleAutoSubmit.checked = res.autoSubmit;
      if (typeof res.autoEmail !== "undefined") toggleAutoEmail.checked = res.autoEmail;
      if (res.defaultEmail) inputEmail.value = res.defaultEmail;
      if (res.selectedAccount) savedAccount = res.selectedAccount;
      if (typeof res.autoDirectJump !== "undefined") toggleAutoJump.checked = res.autoDirectJump;
      if (res.language && selectLang) {
        selectLang.value = res.language;
        currentLang = res.language;
      }
      applyLanguage(currentLang);
      checkDaemon();
    });
  } else {
    applyLanguage("auto");
    checkDaemon();
  }

  async function checkDaemon() {
    const port = inputPort.value || 9428;
    lastDaemonStatus = "checking";
    statusBadge.className = "badge checking";
    statusBadge.textContent = t("checking");

    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/health`, { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        if (data.spark_available) {
          lastDaemonStatus = "online";
          statusBadge.className = "badge online";
          statusBadge.textContent = t("connected");
          fetchAccounts(port);
          fetchLatestOtp(port);
          fetchTelemetry(port);
        } else {
          lastDaemonStatus = "spark_offline";
          statusBadge.className = "badge offline";
          statusBadge.textContent = t("spark_offline");
        }
      } else {
        throw new Error("Bad status");
      }
    } catch (e) {
      lastDaemonStatus = "daemon_offline";
      statusBadge.className = "badge offline";
      statusBadge.textContent = t("daemon_offline");
      latestCode.textContent = "------";
      btnCopy.disabled = true;
      latestDomain.textContent = t("run_cli");
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
          const telem = data.telemetry;
          const latEl = document.getElementById("metric-latency");
          const hitEl = document.getElementById("metric-hitrate");
          const reqEl = document.getElementById("metric-requests");
          const lat = typeof telem.otp_avg_latency_ms !== "undefined" && telem.otp_total > 0 ? telem.otp_avg_latency_ms : (telem.avg_latency_ms || 0);
          const hit = typeof telem.otp_hit_rate_pct !== "undefined" && telem.otp_total > 0 ? telem.otp_hit_rate_pct : (telem.hit_rate_pct || 0);
          const total = typeof telem.otp_total !== "undefined" && telem.otp_total > 0 ? telem.otp_total : (telem.total_requests || 0);
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
          selectAccount.innerHTML = `<option value="" data-i18n="unified_inbox">${t("unified_inbox")}</option>`;
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
          latestDomain.textContent = `${data.otp.domain || data.otp.service} (${data.otp.time_remaining_seconds}${t("left_sec")})`;
        } else {
          latestCode.textContent = "------";
          btnCopy.disabled = true;
          latestDomain.textContent = t("no_active_otp");
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
      btnCopy.textContent = t("copied");
      setTimeout(() => { btnCopy.textContent = t("copy"); }, 1500);
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
        saveMsg.textContent = t("saved_msg");
        setTimeout(() => { saveMsg.textContent = ""; }, 2000);
        checkDaemon();
      });
    }
  });

  btnRefresh.addEventListener("click", checkDaemon);
});

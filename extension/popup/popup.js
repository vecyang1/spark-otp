document.addEventListener("DOMContentLoaded", async () => {
  const statusBadge = document.getElementById("status-badge");
  const latestCard = document.getElementById("latest-card");
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
  const inputNewDisabledDomain = document.getElementById("input-new-disabled-domain");
  const btnAddDisabledDomain = document.getElementById("btn-add-disabled-domain");
  const disabledDomainsList = document.getElementById("disabled-domains-list");
  const toggleEmailOnly = document.getElementById("toggle-email-only");
  const inputNewBlockedTerm = document.getElementById("input-new-blocked-term");
  const btnAddBlockedTerm = document.getElementById("btn-add-blocked-term");
  const blockedTermsList = document.getElementById("blocked-terms-list");
  const btnInspectPage = document.getElementById("btn-inspect-page");
  const inspectorDomain = document.getElementById("inspector-domain");
  const inspectorChannelBadge = document.getElementById("inspector-channel-badge");
  const inspectorVerdict = document.getElementById("inspector-verdict");
  const btnBlockCurrentSite = document.getElementById("btn-block-current-site");
  const btnPresetCard = document.getElementById("btn-preset-card");
  const btnPresetTotp = document.getElementById("btn-preset-totp");
  const btnPresetSms = document.getElementById("btn-preset-sms");
  const btnPresetEmail = document.getElementById("btn-preset-email");
  const sandboxSampleLabel = document.getElementById("sandbox-sample-label");
  const sandboxSampleContext = document.getElementById("sandbox-sample-context");
  const btnRunSandbox = document.getElementById("btn-run-sandbox");
  const sandboxResultBox = document.getElementById("sandbox-result-box");

  let savedAccount = "";
  let currentLang = "auto";
  let lastDaemonStatus = "checking"; // checking, online, spark_offline, daemon_offline
  let disabledDomains = [];
  let emailOnlyMode = true;
  let customBlockedTerms = [];
  let activeInspectedDomain = "";
  let lastInspectorReport = null;

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
      page_inspector_title: "Page Detection Inspector",
      inspect_page: "Inspect",
      channel_none: "No OTP Field",
      channel_email_otp: "Email OTP Active",
      channel_card_blocked: "Card/Payment Blocked",
      channel_auth_blocked: "Authenticator Blocked",
      channel_sms_blocked: "SMS Blocked (Email-Only)",
      channel_site_disabled: "Site Disabled",
      inspector_waiting: "Inspecting active tab DOM...",
      inspector_no_tab: "No inspectable web tab active",
      block_current_site: "Block Current Site",
      unblock_current_site: "Unblock Current Site",
      rule_sandbox_title: "Rule & Input Diagnostic Tester",
      preset_card_cvv: "Card CVV",
      preset_auth_app: "Authenticator App",
      preset_sms: "SMS Code",
      preset_email_otp: "Email OTP",
      test_sample_btn: "Test",
      sandbox_hint: "Click a preset or enter a field sample to verify rule behavior.",
      strict_email_only: "Strict Email-Only Mode (Block Card, TOTP & SMS)",
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
      left_sec: "s left",
      disabled_sites_label: "Disabled Sites (Blacklist)",
      add_domain: "Add",
      no_disabled_sites: "No disabled sites",
      custom_blocked_terms_label: "Custom Blocked Field Keywords",
      add_blocked_term: "Add",
      no_blocked_terms: "No custom blocked keywords"
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
      page_inspector_title: "当前页面识别诊断器",
      inspect_page: "重新检测",
      channel_none: "无验证码框",
      channel_email_otp: "邮箱验证码已激活",
      channel_card_blocked: "已拦截银行卡/支付框",
      channel_auth_blocked: "已拦截验证器/TOTP",
      channel_sms_blocked: "已拦截短信验证码",
      channel_site_disabled: "当前站点已禁用",
      inspector_waiting: "正在扫描当前标签页 DOM...",
      inspector_no_tab: "当前标签页无可用网页上下文",
      block_current_site: "一键禁用当前网站",
      unblock_current_site: "解除当前网站禁用",
      rule_sandbox_title: "规则对账与输入样本测试器",
      preset_card_cvv: "银行卡安全码 CVV",
      preset_auth_app: "验证器 App (TOTP)",
      preset_sms: "手机短信码",
      preset_email_otp: "邮箱验证码",
      test_sample_btn: "测试",
      sandbox_hint: "点击预设样本或输入字段名称/上下文，即时验算拦截与放行规则。",
      strict_email_only: "严格仅限邮箱模式 (拦截银行卡 CVV、验证器 App 与短信)",
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
      left_sec: "秒有效",
      disabled_sites_label: "已禁用网站名单 (黑名单)",
      add_domain: "添加",
      no_disabled_sites: "暂无禁用网站",
      custom_blocked_terms_label: "自定义拦截字段关键词",
      add_blocked_term: "添加",
      no_blocked_terms: "暂无自定义拦截关键词"
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
    if (selectAccount) {
      const firstOpt = selectAccount.querySelector("option[value='']");
      if (firstOpt) {
        firstOpt.textContent = t("unified_inbox");
      }
    }

    if (lastInspectorReport) {
      renderInspectorReport(lastInspectorReport);
    }
    renderDisabledDomains();
    renderBlockedTerms();
  }

  if (selectLang) {
    selectLang.addEventListener("change", () => {
      applyLanguage(selectLang.value);
    });
  }

  function renderDisabledDomains() {
    if (!disabledDomainsList) return;
    disabledDomainsList.innerHTML = "";
    if (!disabledDomains || disabledDomains.length === 0) {
      disabledDomainsList.innerHTML = `<span style="font-size:11px;color:#64748b;">${t("no_disabled_sites")}</span>`;
      return;
    }
    disabledDomains.forEach(domain => {
      const pill = document.createElement("span");
      pill.className = "tag-pill";
      pill.innerHTML = `<span>${domain}</span><button class="tag-remove" title="Remove" data-domain="${domain}">×</button>`;
      disabledDomainsList.appendChild(pill);
    });

    disabledDomainsList.querySelectorAll(".tag-remove").forEach(btn => {
      btn.addEventListener("click", () => {
        const d = btn.getAttribute("data-domain");
        disabledDomains = disabledDomains.filter(x => x !== d);
        saveDisabledDomains();
        renderDisabledDomains();
        updateBlockSiteButtonState();
      });
    });
  }

  function saveDisabledDomains() {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.sync) {
      chrome.storage.sync.set({ disabledDomains });
    }
  }

  if (btnAddDisabledDomain && inputNewDisabledDomain) {
    btnAddDisabledDomain.addEventListener("click", () => {
      const val = (inputNewDisabledDomain.value || "").trim().toLowerCase();
      if (val && !disabledDomains.includes(val)) {
        disabledDomains.push(val);
        inputNewDisabledDomain.value = "";
        saveDisabledDomains();
        renderDisabledDomains();
        updateBlockSiteButtonState();
      }
    });
    inputNewDisabledDomain.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        btnAddDisabledDomain.click();
      }
    });
  }

  function renderBlockedTerms() {
    if (!blockedTermsList) return;
    blockedTermsList.innerHTML = "";
    if (!customBlockedTerms || customBlockedTerms.length === 0) {
      blockedTermsList.innerHTML = `<span style="font-size:11px;color:#64748b;">${t("no_blocked_terms")}</span>`;
      return;
    }
    customBlockedTerms.forEach(term => {
      const pill = document.createElement("span");
      pill.className = "tag-pill";
      pill.innerHTML = `<span>${term}</span><button class="tag-remove" title="Remove" data-term="${term}">×</button>`;
      blockedTermsList.appendChild(pill);
    });

    blockedTermsList.querySelectorAll(".tag-remove").forEach(btn => {
      btn.addEventListener("click", () => {
        const val = btn.getAttribute("data-term");
        customBlockedTerms = customBlockedTerms.filter(x => x !== val);
        saveBlockedTerms();
        renderBlockedTerms();
      });
    });
  }

  function saveBlockedTerms() {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.sync) {
      chrome.storage.sync.set({ customBlockedTerms });
    }
  }

  if (btnAddBlockedTerm && inputNewBlockedTerm) {
    btnAddBlockedTerm.addEventListener("click", () => {
      const val = (inputNewBlockedTerm.value || "").trim().toLowerCase();
      if (val && !customBlockedTerms.includes(val)) {
        customBlockedTerms.push(val);
        inputNewBlockedTerm.value = "";
        saveBlockedTerms();
        renderBlockedTerms();
      }
    });
    inputNewBlockedTerm.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        btnAddBlockedTerm.click();
      }
    });
  }

  if (toggleEmailOnly) {
    toggleEmailOnly.addEventListener("change", () => {
      emailOnlyMode = Boolean(toggleEmailOnly.checked);
      if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.sync) {
        chrome.storage.sync.set({ emailOnlyMode });
      }
      setTimeout(inspectActiveTab, 120);
    });
  }

  function isHostBlocked(host) {
    if (!host) return false;
    const h = host.toLowerCase();
    return (disabledDomains || []).some(d => {
      const rule = (d || "").trim().toLowerCase();
      return rule && (h === rule || h.endsWith("." + rule));
    });
  }

  function updateBlockSiteButtonState() {
    if (!btnBlockCurrentSite) return;
    if (!activeInspectedDomain || activeInspectedDomain === "chrome://" || activeInspectedDomain.includes(" ")) {
      btnBlockCurrentSite.style.display = "none";
      return;
    }
    btnBlockCurrentSite.style.display = "inline-block";
    if (isHostBlocked(activeInspectedDomain)) {
      btnBlockCurrentSite.textContent = t("unblock_current_site");
    } else {
      btnBlockCurrentSite.textContent = t("block_current_site");
    }
  }

  if (btnBlockCurrentSite) {
    btnBlockCurrentSite.addEventListener("click", () => {
      if (!activeInspectedDomain) return;
      const host = activeInspectedDomain.toLowerCase();
      if (isHostBlocked(host)) {
        disabledDomains = disabledDomains.filter(d => {
          const rule = (d || "").trim().toLowerCase();
          return !(host === rule || host.endsWith("." + rule));
        });
      } else if (!disabledDomains.includes(host)) {
        disabledDomains.push(host);
      }
      saveDisabledDomains();
      renderDisabledDomains();
      updateBlockSiteButtonState();
      setTimeout(inspectActiveTab, 150);
    });
  }

  function renderInspectorReport(report) {
    lastInspectorReport = report;
    if (!inspectorDomain || !inspectorChannelBadge || !inspectorVerdict) return;
    if (!report) {
      inspectorDomain.textContent = t("inspector_no_tab");
      inspectorChannelBadge.className = "badge neutral";
      inspectorChannelBadge.textContent = t("channel_none");
      inspectorVerdict.textContent = t("inspector_no_tab");
      return;
    }

    activeInspectedDomain = report.domain || "";
    inspectorDomain.textContent = report.domain || "(unknown)";
    updateBlockSiteButtonState();

    const channel = isHostBlocked(activeInspectedDomain) ? "site_disabled" : (report.detected_channel || "none");
    if (channel === "email_otp") {
      inspectorChannelBadge.className = "badge online";
      inspectorChannelBadge.textContent = t("channel_email_otp");
    } else if (channel === "card_payment_blocked") {
      inspectorChannelBadge.className = "badge blocked";
      inspectorChannelBadge.textContent = t("channel_card_blocked");
    } else if (channel === "authenticator_app_blocked") {
      inspectorChannelBadge.className = "badge blocked";
      inspectorChannelBadge.textContent = t("channel_auth_blocked");
    } else if (channel === "sms_only_blocked") {
      inspectorChannelBadge.className = "badge blocked";
      inspectorChannelBadge.textContent = t("channel_sms_blocked");
    } else if (channel === "site_disabled") {
      inspectorChannelBadge.className = "badge blocked";
      inspectorChannelBadge.textContent = t("channel_site_disabled");
    } else {
      inspectorChannelBadge.className = "badge neutral";
      inspectorChannelBadge.textContent = t("channel_none");
    }

    const candidates = Array.isArray(report.candidates) ? report.candidates : [];
    const topMatch = candidates.find(c => c.qualified) || candidates.find(c => c.disqualified && c.rule_id !== "no_otp_signal") || candidates[0];
    let html = `<div>${report.verdict || ""}</div>`;
    if (topMatch && topMatch.rule_id) {
      html += `<div style="margin-top:4px;"><span class="rule-code-pill">${topMatch.rule_id}</span><span>${topMatch.reason || ""}</span></div>`;
    }
    inspectorVerdict.innerHTML = html;
  }

  function inspectActiveTab() {
    if (!inspectorDomain) return;
    if (typeof chrome === "undefined" || !chrome.tabs || !chrome.tabs.query) {
      activeInspectedDomain = "";
      updateBlockSiteButtonState();
      renderInspectorReport(null);
      return;
    }
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs && tabs[0];
      if (!tab || !tab.id) {
        renderInspectorReport(null);
        return;
      }
      let fallbackHost = "";
      try {
        if (tab.url && /^https?:/i.test(tab.url)) {
          fallbackHost = new URL(tab.url).hostname;
        }
      } catch (e) {}

      if (!fallbackHost) {
        activeInspectedDomain = "";
        updateBlockSiteButtonState();
        renderInspectorReport(null);
        return;
      }

      try {
        chrome.tabs.sendMessage(tab.id, { type: "SPARK_OTP_DIAGNOSE_PAGE" }, (res) => {
          if (chrome.runtime && chrome.runtime.lastError) {
            renderInspectorReport({
              domain: fallbackHost,
              detected_channel: isHostBlocked(fallbackHost) ? "site_disabled" : "none",
              verdict: isHostBlocked(fallbackHost)
                ? `Site '${fallbackHost}' is disabled in blacklist.`
                : `Active on ${fallbackHost} (reload tab if extension was just updated).`,
              candidates: []
            });
            return;
          }
          if (res && res.success && res.diagnosis) {
            renderInspectorReport(res.diagnosis);
          } else {
            renderInspectorReport({
              domain: fallbackHost,
              detected_channel: isHostBlocked(fallbackHost) ? "site_disabled" : "none",
              verdict: `No active OTP inputs reported on ${fallbackHost}.`,
              candidates: []
            });
          }
        });
      } catch (e) {
        renderInspectorReport({
          domain: fallbackHost,
          detected_channel: "none",
          verdict: `Active on ${fallbackHost}.`,
          candidates: []
        });
      }
    });
  }

  if (btnInspectPage) {
    btnInspectPage.addEventListener("click", inspectActiveTab);
  }

  async function evaluateSampleDiagnostic(sample) {
    // 1. Try active tab content script (uses live in-page diagnoseSyntheticSample SSOT)
    if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.query) {
      const tabRes = await new Promise((resolve) => {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
          const tab = tabs && tabs[0];
          if (!tab || !tab.id || !tab.url || !/^https?:/i.test(tab.url)) {
            resolve(null);
            return;
          }
          try {
            chrome.tabs.sendMessage(tab.id, { type: "SPARK_OTP_TEST_SAMPLE", sample }, (resp) => {
              if (chrome.runtime && chrome.runtime.lastError) {
                resolve(null);
                return;
              }
              resolve(resp && resp.diagnosis ? resp.diagnosis : null);
            });
          } catch (e) {
            resolve(null);
          }
        });
      });
      if (tabRes) return tabRes;
    }

    // 2. Fallback to local HTTP daemon /api/diagnose?dom_sample=... (uses Node + content.js SSOT)
    const port = (inputPort && inputPort.value) ? inputPort.value : 9428;
    try {
      const q = encodeURIComponent(JSON.stringify(sample));
      const res = await fetch(`http://127.0.0.1:${port}/api/diagnose?dom_sample=${q}`, { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        if (data && data.dom_sample_diagnosis) {
          return data.dom_sample_diagnosis;
        }
      }
    } catch (e) {}

    // 3. Deterministic offline fallback if neither tab nor daemon is reachable
    const combined = `${sample.name || ""} ${sample.id || ""} ${sample.placeholder || ""} ${sample.ariaLabel || ""} ${sample.labelText || ""} ${sample.autocomplete || ""}`.toLowerCase();
    const ctx = `${combined} ${sample.formText || ""} ${sample.headingText || ""} ${sample.url || ""}`.toLowerCase();
    if (/cvv|cvc|csc|cc-csc|card.?number|expiration.?date|credit.?card|debit.?card|payment.?method|self-serve-checkout/i.test(ctx)) {
      return {
        disqualified: true,
        qualified: false,
        channel: "card_payment_blocked",
        rule_id: "card_payment_context",
        reason: "Blocked credit/debit card or payment checkout security code (CVV/CVC)."
      };
    }
    if (/authenticator\s*app|google\s*authenticator|totp|two[-_\s]?factor\s*app|1password|authy|passkey/i.test(ctx)) {
      return {
        disqualified: true,
        qualified: false,
        channel: "authenticator_app_blocked",
        rule_id: "authenticator_app_context",
        reason: "Blocked Authenticator App (TOTP / 2FA App) prompt."
      };
    }
    if (emailOnlyMode && (/sms|text\s*message|短信|手机验证码/i.test(ctx)) && !(/email|e-mail|邮箱|邮件/i.test(ctx))) {
      return {
        disqualified: true,
        qualified: false,
        channel: "sms_only_blocked",
        rule_id: "sms_only_context",
        reason: "Blocked SMS/Phone verification field (Strict Email-Only Mode enabled)."
      };
    }
    if (/otp|verification\s*code|security\s*code|验证码|one-time-code/i.test(ctx)) {
      return {
        disqualified: false,
        qualified: true,
        channel: "email_otp",
        rule_id: "explicit_otp_marker",
        reason: "Qualified as Email OTP input."
      };
    }
    return {
      disqualified: false,
      qualified: false,
      channel: "none",
      rule_id: "no_otp_signal",
      reason: "No email OTP signal detected."
    };
  }

  async function runRuleSandbox(overrideSample) {
    if (!sandboxResultBox) return;
    const labelVal = overrideSample ? (overrideSample.labelText || overrideSample.placeholder || "") : ((sandboxSampleLabel && sandboxSampleLabel.value) || "");
    const ctxVal = overrideSample ? (overrideSample.formText || "") : ((sandboxSampleContext && sandboxSampleContext.value) || "");
    if (overrideSample && sandboxSampleLabel && sandboxSampleContext) {
      sandboxSampleLabel.value = labelVal;
      sandboxSampleContext.value = ctxVal;
    }

    const sample = Object.assign({
      labelText: labelVal,
      placeholder: labelVal,
      formText: ctxVal,
      headingText: ctxVal,
      emailOnlyMode: emailOnlyMode,
      customBlockedTerms: customBlockedTerms
    }, overrideSample || {});

    const diag = await evaluateSampleDiagnostic(sample);
    const statusText = diag.qualified
      ? `<strong style="color:#4ade80;">ALLOW (Email OTP)</strong>`
      : (diag.disqualified
        ? `<strong style="color:#f87171;">BLOCKED (${diag.channel})</strong>`
        : `<strong style="color:#94a3b8;">IGNORED (${diag.channel})</strong>`);
    sandboxResultBox.innerHTML = `<div>${statusText} <span class="rule-code-pill">${diag.rule_id || "rule"}</span></div><div style="margin-top:3px;">${diag.reason || ""}</div>`;
  }

  if (btnRunSandbox) {
    btnRunSandbox.addEventListener("click", () => runRuleSandbox(null));
  }
  if (btnPresetCard) {
    btnPresetCard.addEventListener("click", () => runRuleSandbox({
      labelText: "Security code*",
      placeholder: "CVV",
      maxLength: 4,
      formText: "Credit/Debit card First name* Last name* Card number* Expiration date* Security code* Postal code*",
      url: "https://payment.www.linkedin.com/self-serve-checkout/"
    }));
  }
  if (btnPresetTotp) {
    btnPresetTotp.addEventListener("click", () => runRuleSandbox({
      labelText: "6-digit code",
      placeholder: "000000",
      autocomplete: "one-time-code",
      maxLength: 6,
      formText: "Two-factor authentication: Enter the 6-digit verification code generated by your authenticator app (Google Authenticator or 1Password)."
    }));
  }
  if (btnPresetSms) {
    btnPresetSms.addEventListener("click", () => runRuleSandbox({
      labelText: "SMS verification code",
      placeholder: "Enter 6-digit SMS code",
      maxLength: 6,
      formText: "We sent a text message to +1 ***-***-4829. Enter the SMS code below."
    }));
  }
  if (btnPresetEmail) {
    btnPresetEmail.addEventListener("click", () => runRuleSandbox({
      labelText: "Email verification code",
      placeholder: "Enter 6-digit code",
      autocomplete: "one-time-code",
      maxLength: 6,
      formText: "Check your email inbox. We sent a 6-digit verification code to alex.turner@example.com."
    }));
  }

  // Load saved settings
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.sync) {
    chrome.storage.sync.get(["serverPort", "autoSubmit", "autoEmail", "defaultEmail", "selectedAccount", "autoDirectJump", "language", "disabledDomains", "emailOnlyMode", "customBlockedTerms"], (res) => {
      if (res.serverPort) inputPort.value = res.serverPort;
      if (typeof res.autoSubmit !== "undefined") toggleAutoSubmit.checked = res.autoSubmit;
      if (typeof res.autoEmail !== "undefined") toggleAutoEmail.checked = res.autoEmail;
      if (res.defaultEmail) inputEmail.value = res.defaultEmail;
      if (res.selectedAccount) savedAccount = res.selectedAccount;
      if (typeof res.autoDirectJump !== "undefined") toggleAutoJump.checked = res.autoDirectJump;
      if (typeof res.emailOnlyMode !== "undefined") {
        emailOnlyMode = Boolean(res.emailOnlyMode);
        if (toggleEmailOnly) toggleEmailOnly.checked = emailOnlyMode;
      }
      if (res.language && selectLang) {
        selectLang.value = res.language;
        currentLang = res.language;
      }
      if (res.disabledDomains && Array.isArray(res.disabledDomains)) {
        disabledDomains = res.disabledDomains;
      }
      if (res.customBlockedTerms && Array.isArray(res.customBlockedTerms)) {
        customBlockedTerms = res.customBlockedTerms;
      }
      applyLanguage(currentLang);
      renderDisabledDomains();
      renderBlockedTerms();
      checkDaemon();
      inspectActiveTab();
    });
  } else {
    applyLanguage("auto");
    renderDisabledDomains();
    renderBlockedTerms();
    checkDaemon();
    inspectActiveTab();
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
        if (data.spark_available || data.spark_sqlite_available) {
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

  let pollTimer = null;
  let pollAttempts = 0;
  const MAX_POLL_ATTEMPTS = 5;

  async function fetchLatestOtp(port, isRetry = false) {
    if (!isRetry) {
      pollAttempts = 0;
      if (pollTimer) {
        clearTimeout(pollTimer);
        pollTimer = null;
      }
    }
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
          if (pollTimer) {
            clearTimeout(pollTimer);
            pollTimer = null;
          }
          return;
        } else {
          latestCode.textContent = "------";
          btnCopy.disabled = true;
          latestDomain.textContent = t("no_active_otp");
        }
      }
    } catch (e) {
      latestCode.textContent = "------";
      btnCopy.disabled = true;
      latestDomain.textContent = t("no_active_otp");
    }

    // Self-healing short polling: retry up to MAX_POLL_ATTEMPTS if no active OTP was found yet
    if (pollAttempts < MAX_POLL_ATTEMPTS) {
      pollAttempts++;
      pollTimer = setTimeout(() => {
        fetchLatestOtp(port, true);
      }, 1500);
    }
  }

  if (latestCard) {
    if (latestCard.style) latestCard.style.cursor = "pointer";
    latestCard.title = "Click to refresh code";
    latestCard.addEventListener("click", (e) => {
      if (e.target !== btnCopy) {
        const port = inputPort.value || 9428;
        fetchLatestOtp(port, false);
      }
    });
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
    const defaultEmail = inputEmail.value.trim();
    const selectedAccountVal = selectAccount.value || "";
    savedAccount = selectedAccountVal;
    const autoDirectJump = toggleAutoJump.checked;
    const emailOnlyVal = toggleEmailOnly ? toggleEmailOnly.checked : emailOnlyMode;
    emailOnlyMode = emailOnlyVal;
    const languageVal = selectLang ? selectLang.value : "auto";

    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.sync) {
      chrome.storage.sync.set({
        serverPort: port,
        autoSubmit: autoSubmit,
        autoEmail: autoEmail,
        defaultEmail: defaultEmail,
        selectedAccount: selectedAccountVal,
        autoDirectJump: autoDirectJump,
        emailOnlyMode: emailOnlyVal,
        language: languageVal,
        disabledDomains: disabledDomains,
        customBlockedTerms: customBlockedTerms
      }, () => {
        saveMsg.textContent = t("saved_msg");
        setTimeout(() => { saveMsg.textContent = ""; }, 2000);
        checkDaemon();
        inspectActiveTab();
      });
    }
  });

  btnRefresh.addEventListener("click", checkDaemon);
});

/**
 * Spark OTP Autofill - Universal Content Script
 * Automatically connects to local spark-otp daemon (http://127.0.0.1:9428)
 * and detects/autofills verification codes across any website, service, or auth provider.
 */

(function () {
  const DEFAULT_PORT = 9428;
  const DEFAULT_EMAIL = "alex.turner@example.com";

  let serverPort = DEFAULT_PORT;
  let autoSubmit = true;
  let autoEmail = false;
  let defaultEmail = DEFAULT_EMAIL;
  let selectedAccount = ""; // Empty = Unified Inbox
  let autoDirectJump = false;
  let currentLang = "auto";
  let disabledDomains = [];

  function isDomainDisabled(domain) {
    if (!domain) return false;
    const d = domain.toLowerCase();
    const href = (typeof window !== "undefined" && window.location && window.location.href ? window.location.href : "").toLowerCase();
    if (disabledDomains && Array.isArray(disabledDomains)) {
      return disabledDomains.some(disabled => {
        if (!disabled) return false;
        const norm = disabled.trim().toLowerCase();
        return norm && (d === norm || d.endsWith("." + norm) || href.includes(norm));
      });
    }
    return false;
  }

  const I18N = {
    en: {
      watchingTitle: "Verification field detected",
      watchingSubtitle: "Searching for verification code in background...",
      allMailboxes: "All Mailboxes",
      refresh: "Refresh",
      codeFound: "Code retrieved: ",
      autoFilled: "Auto-filled & submitted",
      readyToFill: "Ready, click to fill",
      remainingMin: " · {n}m left",
      fill: "Fill",
      copy: "Copy",
      copied: "Copied!",
      refreshNew: "Fetch New",
      directJump: "Direct Link",
      codeFailedTitle: "Verification code <span class=\"spark-otp-code-highlight\">{code}</span> rejected, waiting for new email...",
      codeFailedTitleGeneric: "Verification code rejected, waiting for new email...",
      codeFailedSubtitle: "Prevented duplicate submit · Listening for fresh code",
      failedBadge: "Rejected",
      excludedOldCode: "Excluded old code",
      notFound: "Not found",
      offline: "Offline",
      readyToSend: "Ready to send code to {email}",
      sendCode: "Send Code",
      sparkLogin: "Spark Login",
      forceFill: "Force Fill",
    },
    zh: {
      watchingTitle: "已检测到验证码输入框",
      watchingSubtitle: "后台正在静默查询/等待验证码...",
      allMailboxes: "全域邮箱",
      refresh: "刷新",
      codeFound: "验证码获取成功: ",
      autoFilled: "已自动填充并提交",
      readyToFill: "已就绪，点击填充",
      remainingMin: " · 剩余 {n} 分钟",
      fill: "填充",
      copy: "复制",
      copied: "已复制!",
      refreshNew: "重新获取",
      directJump: "直达",
      codeFailedTitle: "验证码 <span class=\"spark-otp-code-highlight\">{code}</span> 校验失败，等待新邮件...",
      codeFailedTitleGeneric: "验证码校验失败，等待新邮件...",
      codeFailedSubtitle: "已阻止重复提交 · 后台正在监听最新验证码",
      failedBadge: "校验失败",
      excludedOldCode: "已排除旧码",
      notFound: "未找到",
      offline: "离线",
      readyToSend: "准备发送验证码到 {email}",
      sendCode: "发送验证码",
      sparkLogin: "Spark 登录",
      forceFill: "强制填充",
    }
  };

  function t(key, vars = {}) {
    let lang = currentLang;
    if (lang === "auto") {
      const navLang = (typeof navigator !== "undefined" && (navigator.language || navigator.userLanguage) || "").toLowerCase();
      lang = navLang.startsWith("zh") ? "zh" : "en";
    }
    const dict = I18N[lang] || I18N.en;
    let text = dict[key] || I18N.en[key] || key;
    for (const [k, v] of Object.entries(vars)) {
      text = text.replaceAll(`{${k}}`, v);
    }
    return text;
  }

  let eventSource = null;
  let pollInterval = null;
  let activeCode = null;
  let isListening = false;
  let watchingTimer = null;
  let watchingSeconds = 0;

  // Premium SVG Icons (Lucide-style, zero emojis)
  const ICONS = {
    key: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21 2-2 2m-1.5 1.5L14 9l-2-2-4 4a5.5 5.5 0 0 0 7.78 7.78l4-4-2-2 1.5-1.5M7 17l.01.01"/></svg>`,
    mail: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>`,
    check: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
    link: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>`,
    loader: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/></svg>`,
    alert: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`
  };

  // Determine target domain cleanly
  function detectTargetDomain() {
    try {
      if (window.top && window.top !== window.self && window.top.location.hostname) {
        const topHost = window.top.location.hostname.replace(/^www\./, "");
        if (topHost && topHost !== "localhost" && topHost !== "127.0.0.1") {
          // If frame domain is generic auth widget, prefer topHost
          if (["auth0.com", "clerk.dev", "supabase.co", "firebaseapp.com"].some(d => window.location.hostname.includes(d))) {
            return topHost;
          }
        }
      }
    } catch (e) {}

    const url = window.location.href;
    const match = url.match(/(?:login|verify-code)\/([a-zA-Z0-9\.\-]+)/i);
    if (match && match[1]) {
      return match[1];
    }
    const host = window.location.hostname.replace(/^www\./, "");
    return host || "localhost";
  }

  // Storage helper using sessionStorage (with in-memory fallback)
  const inMemoryStorage = {};
  function getStorageItem(key) {
    try {
      if (typeof window !== "undefined" && window.sessionStorage) {
        return window.sessionStorage.getItem(key);
      }
    } catch (e) {}
    return inMemoryStorage[key] || null;
  }

  function setStorageItem(key, value) {
    try {
      if (typeof window !== "undefined" && window.sessionStorage) {
        window.sessionStorage.setItem(key, value);
        return;
      }
    } catch (e) {}
    inMemoryStorage[key] = value;
  }

  function getAuthState(domain) {
    const d = domain || detectTargetDomain();
    try {
      const raw = getStorageItem(`spark_otp_auth_${d}`);
      if (raw) {
        const parsed = JSON.parse(raw);
        return {
          lastSubmittedCode: parsed.lastSubmittedCode || null,
          lastSubmittedMsgId: parsed.lastSubmittedMsgId || null,
          lastSubmittedAt: parsed.lastSubmittedAt || 0,
          failedCodes: Array.isArray(parsed.failedCodes) ? parsed.failedCodes : [],
          failedMessageIds: Array.isArray(parsed.failedMessageIds) ? parsed.failedMessageIds : [],
          submissionCounts: parsed.submissionCounts || {},
          lastFailedAt: parsed.lastFailedAt || 0
        };
      }
    } catch (e) {}
    return {
      lastSubmittedCode: null,
      lastSubmittedMsgId: null,
      lastSubmittedAt: 0,
      failedCodes: [],
      failedMessageIds: [],
      submissionCounts: {},
      lastFailedAt: 0
    };
  }

  function saveAuthState(stateOrDomain, domainOrState) {
    let state, domain;
    if (stateOrDomain && typeof stateOrDomain === "object") {
      state = stateOrDomain;
      domain = domainOrState;
    } else {
      state = domainOrState;
      domain = stateOrDomain;
    }
    const d = domain || detectTargetDomain();
    try {
      setStorageItem(`spark_otp_auth_${d}`, JSON.stringify(state || {}));
    } catch (e) {}
  }

  function recordCodeSubmitted(code, messageId, domain) {
    if (!code) return;
    const c = String(code).trim();
    const state = getAuthState(domain);
    state.lastSubmittedCode = c;
    state.lastSubmittedMsgId = messageId ? String(messageId).trim() : null;
    state.lastSubmittedAt = Date.now();
    state.submissionCounts[c] = (state.submissionCounts[c] || 0) + 1;
    saveAuthState(state, domain);
  }

  function recordCodeFailed(code, messageId, domain) {
    const state = getAuthState(domain);
    const c = code ? String(code).trim() : (state.lastSubmittedCode || null);
    const m = messageId ? String(messageId).trim() : (state.lastSubmittedMsgId || null);
    let isNewFailure = false;
    if (c && !state.failedCodes.includes(c)) {
      state.failedCodes.push(c);
      isNewFailure = true;
    }
    if (m && !state.failedMessageIds.includes(m)) {
      state.failedMessageIds.push(m);
      isNewFailure = true;
    }
    if (isNewFailure || !state.lastFailedAt) {
      state.lastFailedAt = Date.now();
    }
    saveAuthState(state, domain);
    return state;
  }

  function detectPageError() {
    // 1. URL search or hash param indicating failure (e.g. ?incorrect=true, ?error=..., ?failed=...)
    try {
      const search = (typeof window !== "undefined" && window.location && window.location.search) || "";
      const hash = (typeof window !== "undefined" && window.location && window.location.hash) || "";
      if (/(?:incorrect|error|failed|invalid|bad_code|bad-code)/i.test(search + " " + hash)) {
        return { hasError: true, reason: "url_param" };
      }
    } catch (e) {}

    // 2. Look for error containers and messages in DOM
    if (typeof document !== "undefined" && document.body) {
      const errorSelectors = [
        '[role="alert"]',
        '.alert-danger',
        '.alert-error',
        '.alert-warning',
        '.alert',
        '.error',
        '.error-message',
        '.notification-error',
        '.text-danger',
        '.invalid-feedback',
        '#error',
        '#login-error',
        '.login-error'
      ];
      const errorTextRegex = /(?:incorrect|invalid|wrong|expired|failed|not\s*valid|has\s*expired)\s*(?:verification\s*|security\s*|auth\s*|login\s*|one-time\s*)?(?:code|passcode|token|pin|otp)?|(?:code|passcode|token|pin|otp)\s*(?:is\s*)?(?:incorrect|invalid|wrong|expired|not\s*valid|has\s*expired)|验证码.*?(?:错误|不正确|有误|已过期|无效)|認証コード.*?(?:正しくありません|無効|切れています)/i;

      for (const sel of errorSelectors) {
        const els = document.querySelectorAll(sel);
        for (const el of els) {
          const text = (el.textContent || "").trim();
          if (text.length > 0 && text.length < 300 && errorTextRegex.test(text)) {
            return { hasError: true, reason: "dom_alert", text };
          }
        }
      }

      // Check general elements for exact Bandwagon "Incorrect code, please try again" or similar
      const paragraphs = document.querySelectorAll("p, div, span");
      for (const el of paragraphs) {
        if (el.children.length > 2) continue;
        const text = (el.textContent || "").trim();
        if (text.length > 0 && text.length < 150) {
          if (/incorrect\s*code(?:,\s*please\s*try\s*again)?/i.test(text) ||
              /invalid\s*(?:two-factor|verification)\s*code/i.test(text) ||
              /验证码错误/i.test(text)) {
            return { hasError: true, reason: "dom_text", text };
          }
        }
      }
    }

    return { hasError: false };
  }

  function isCodeRejected(code, messageId, receivedAtMs, domain) {
    if (!code) return true;
    const cleanCode = String(code).trim();
    const cleanMsgId = messageId ? String(messageId).trim() : null;
    const state = getAuthState(domain);
    const pageErr = detectPageError();

    // 1. Explicitly rejected/failed code (case-insensitive)
    if (state.failedCodes && state.failedCodes.some(fc => fc.toUpperCase() === cleanCode.toUpperCase())) {
      return true;
    }

    // 2. Explicitly rejected/failed message ID
    if (cleanMsgId && state.failedMessageIds && state.failedMessageIds.includes(cleanMsgId)) {
      return true;
    }

    // 3. Current code matches last submitted code and page has error or code was submitted
    if (state.lastSubmittedCode && cleanCode.toUpperCase() === state.lastSubmittedCode.toUpperCase()) {
      if (pageErr.hasError || (state.submissionCounts[cleanCode] || 0) >= 1) {
        return true;
      }
    }

    // 4. Max submit limit: if code was submitted >= 1 time already
    const submitCount = state.submissionCounts[cleanCode] || 0;
    if (submitCount >= 1) {
      return true;
    }

    // 5. Error banner guardrail: if error is on page, reject any code received before or at failure time
    const recMs = Number(receivedAtMs) || 0;
    if (pageErr.hasError) {
      const failureTime = state.lastFailedAt || Date.now();
      if (recMs > 0 && recMs <= failureTime) {
        return true;
      }
    }

    // 6. Timestamp check against lastFailedAt
    if (state.lastFailedAt && state.lastFailedAt > 0) {
      if (recMs > 0 && recMs <= state.lastFailedAt) {
        return true;
      }
    }

    return false;
  }

  function buildApiQuery(domain, account) {
    let q = `domain=${encodeURIComponent(domain)}`;
    if (account) {
      q += `&account=${encodeURIComponent(account)}`;
    }
    const state = getAuthState(domain);
    if (state.failedCodes && state.failedCodes.length > 0) {
      q += `&exclude_codes=${encodeURIComponent(state.failedCodes.join(","))}`;
    }
    if (state.failedMessageIds && state.failedMessageIds.length > 0) {
      q += `&exclude_message_ids=${encodeURIComponent(state.failedMessageIds.join(","))}`;
    }
    if (state.lastFailedAt && state.lastFailedAt > 0) {
      const sinceSec = Math.floor(state.lastFailedAt / 1000);
      q += `&since_time=${encodeURIComponent(sinceSec)}`;
    }
    return q;
  }

  function isInteractiveElement(el) {
    if (!el || el.disabled || el.readOnly) return false;
    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") return false;
    // Exception for shadcn/input-otp overlay input
    if (el.getAttribute("data-input-otp") === "true") return true;
    if (parseFloat(style.opacity) === 0 && !el.getAttribute("autocomplete")?.includes("one-time-code")) {
      return false;
    }
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0 && el.getAttribute("autocomplete") !== "one-time-code") {
      return false;
    }
    return true;
  }

  function isDisqualifiedInput(el) {
    if (!el) return true;
    const type = (el.type || "").toLowerCase();
    if (["hidden", "checkbox", "radio", "file", "submit", "button", "reset", "image", "date", "time", "datetime-local", "month", "week", "color", "range", "url"].includes(type)) {
      return true;
    }

    const name = (el.name || "").toLowerCase();
    const id = (el.id || "").toLowerCase();
    const placeholder = (el.placeholder || "").toLowerCase();
    const aria = (el.getAttribute("aria-label") || "").toLowerCase();
    const auto = (el.getAttribute("autocomplete") || "").toLowerCase();
    const testId = (el.getAttribute("data-testid") || "").toLowerCase();

    // Check associated label text
    let labelText = "";
    try {
      if (typeof document !== "undefined") {
        if (el.id) {
          const lbl = document.querySelector(`label[for="${el.id}"]`);
          if (lbl) labelText = (lbl.textContent || "").toLowerCase().trim();
        }
        if (!labelText && el.closest) {
          const parentLabel = el.closest("label");
          if (parentLabel) labelText = (parentLabel.textContent || "").toLowerCase().trim();
        }
      }
    } catch (e) {}

    const combined = `${name} ${id} ${placeholder} ${aria} ${testId} ${auto} ${labelText}`;

    // Segmented 1-char input is virtually always an OTP/PIN box
    if (el.getAttribute("maxlength") === "1" || el.getAttribute("size") === "1") {
      return false;
    }

    // Standard one-time-code / data-input-otp
    if (auto === "one-time-code" || el.getAttribute("data-input-otp") === "true") {
      return false;
    }

    // Explicit Positive OTP markers that override ambiguous keywords (e.g. phone_verification_code, email_code, devicecode)
    const isExplicitOtpMarker = /(?:two[-_ ]*factor|twofa|second[-_ ]*factor|one[-_ ]*time|otp|passcode|2fa|mfa|totp)/i.test(combined)
      || /(?:verification|verify|security|auth|login|device|email|phone|sms)[-_ ]*(?:verification[-_ ]*)?(?:code|passcode|pin\b|token)/i.test(combined)
      || /(?:devicecode|device_code|twofactorauthcode|twofactorcode|twofacode)/i.test(combined)
      || /(?:验证码|校验码|动态码|安全码|授权码|認証コード|確認コード|ワンタイム|mã\s*xác\s*thực|mã\s*xác\s*minh|mã\s*otp|รหัส\s*otp|รหัสยืนยัน)/i.test(combined);

    // Negative semantic patterns: fields that are definitively NOT OTP codes
    // 1. Promo, coupon, discounts, search, captcha, referral
    const promoAndSearch = /(?:promo|coupon|discount|voucher|referral|gift[-_ ]*card|search|captcha|query|keyword)/i;
    if (promoAndSearch.test(combined)) {
      return true;
    }

    // 2. Non-auth codes: country code, area code, postal/zip code, currency, tax, tracking, source, etc.
    const nonAuthCodes = /(?:postal|zip[-_ ]*code|country[-_ ]*code|area[-_ ]*code|currency[-_ ]*code|tax[-_ ]*code|tracking[-_ ]*code|source[-_ ]*code|product[-_ ]*code|reference[-_ ]*code|airport[-_ ]*code|language[-_ ]*code|barcode|qr[-_ ]*code|swift[-_ ]*code|bic[-_ ]*code)/i;
    if (nonAuthCodes.test(combined)) {
      return true;
    }

    // 3. Web & URLs (e.g. Company website in Kraken onboarding)
    const webUrls = /(?:website|web[-_ ]*url|domain|homepage|site[-_ ]*url|company[-_ ]*url|company[-_ ]*website)/i;
    if (webUrls.test(combined) || /^https?:\/\/|^www\./i.test(placeholder)) {
      return true;
    }

    // 4. Business, company, occupation, organization info
    const businessPatterns = /(?:company[-_ ]*name|business[-_ ]*name|business[-_ ]*activity|company[-_ ]*description|organization|organisation|industry|occupation|job[-_ ]*title|employer)/i;
    if (businessPatterns.test(combined) && !isExplicitOtpMarker) {
      return true;
    }

    // 5. Personal names & user identities
    const namePatterns = /(?:first[-_ ]*name|last[-_ ]*name|full[-_ ]*name|surname|family[-_ ]*name|given[-_ ]*name|middle[-_ ]*name|username|user[-_ ]*id|login[-_ ]*id|nickname|display[-_ ]*name|profile[-_ ]*name)/i;
    if (namePatterns.test(combined) && !isExplicitOtpMarker) {
      return true;
    }

    // 6. Address & geography
    const addressPatterns = /(?:street|address|city|state|province|region|apt|apartment|suite|building|floor)/i;
    if (addressPatterns.test(combined) && !isExplicitOtpMarker) {
      return true;
    }

    // 7. KYC / Identity documents
    const kycPatterns = /(?:tax[-_ ]*id|ein|ssn|social[-_ ]*security|vat[-_ ]*num|passport|national[-_ ]*id|id[-_ ]*num|identity[-_ ]*card|driver[-_ ]*licen[sc]e|doc[-_ ]*num)/i;
    if (kycPatterns.test(combined) && !isExplicitOtpMarker) {
      return true;
    }

    // 8. Payment & financial cards
    const paymentPatterns = /(?:credit[-_ ]*card|card[-_ ]*num|debit[-_ ]*card|cvv|cvc|card[-_ ]*security|expir(?:y|ation)|routing[-_ ]*num|iban|account[-_ ]*num|amount|price|balance)/i;
    if (paymentPatterns.test(combined) && !isExplicitOtpMarker) {
      return true;
    }

    // 9. Long descriptions, notes, comments
    const descriptionPatterns = /(?:description|details|summary|bio|about|notes?|comments?|messages?|feedback|review|reason|inquiry)/i;
    if (descriptionPatterns.test(combined) && !isExplicitOtpMarker) {
      return true;
    }

    // 10. Device non-code attributes (e.g. device_name, device_id, device_model)
    const deviceNonCode = /(?:device[-_ ]*name|device[-_ ]*alias|device[-_ ]*id|device[-_ ]*model|device[-_ ]*type)/i;
    if (deviceNonCode.test(combined) && !isExplicitOtpMarker) {
      return true;
    }

    // 11. Telecom / phone numbers (e.g. phone_number, mobile) unless it is phone_code / sms_code
    if (/(?:phone[-_ ]*num(?:ber)?|mobile[-_ ]*num(?:ber)?|telephone|fax)/i.test(combined)) {
      return true;
    }
    if ((/(?:^|[\W_])(?:phone|mobile)(?:[\W_]|$)/i.test(name) || /(?:^|[\W_])(?:phone|mobile)(?:[\W_]|$)/i.test(id)) && !isExplicitOtpMarker) {
      return true;
    }

    // If it matched an explicit OTP marker, it qualifies!
    if (isExplicitOtpMarker) {
      return false;
    }

    // Length sanity: typical OTP codes are 4-10 characters. Inputs with maxlength > 20 are general text
    const maxLenAttr = parseInt(el.getAttribute("maxlength"), 10);
    if (!isNaN(maxLenAttr) && maxLenAttr > 20) {
      return true;
    }

    // Plain passwords and emails (not matching isExplicitOtpMarker above) are disqualified
    if (type === "password" || type === "email") {
      return true;
    }

    if (/(?:^|[\W_])(?:email)(?:[\W_]|$)/i.test(name) || /(?:^|[\W_])(?:email)(?:[\W_]|$)/i.test(id)) {
      return true;
    }

    // Generic code or pin attribute matching
    if (/(?:^|[\W_])(?:code|pin)(?:[\W_]|$)/i.test(name) || /(?:^|[\W_])(?:code|pin)(?:[\W_]|$)/i.test(id) || id === "code") {
      return false;
    }

    return false;
  }

  function sortInputsByVisualOrder(inputs) {
    return inputs.slice().sort((a, b) => {
      const idxA = a.getAttribute("data-index") || a.getAttribute("tabindex");
      const idxB = b.getAttribute("data-index") || b.getAttribute("tabindex");
      if (idxA !== null && idxB !== null && !isNaN(idxA) && !isNaN(idxB)) {
        return parseInt(idxA, 10) - parseInt(idxB, 10);
      }
      const rectA = a.getBoundingClientRect();
      const rectB = b.getBoundingClientRect();
      if (Math.abs(rectA.top - rectB.top) > 15) {
        return rectA.top - rectB.top;
      }
      return rectA.left - rectB.left;
    });
  }

  // Universal OTP input finder
  function findOtpInputs() {
    if (!document.body) return [];

    // 1. Standard autocomplete="one-time-code"
    const standard = Array.from(document.querySelectorAll('input[autocomplete="one-time-code"]')).filter(isInteractiveElement);
    if (standard.length === 1) return standard;
    if (standard.length > 1) return sortInputsByVisualOrder(standard);

    // 2. React input-otp / shadcn
    const reactOtp = document.querySelector('input[data-input-otp="true"]');
    if (reactOtp && !reactOtp.disabled) return [reactOtp];

    // 3. Multi-box segmented inputs (4, 6, 8 inputs with maxlength="1")
    const singleChar = Array.from(document.querySelectorAll(
      'input[maxlength="1"]:not([type="hidden"])'
    )).filter(isInteractiveElement).filter(el => !isDisqualifiedInput(el));

    if (singleChar.length >= 4 && singleChar.length <= 8) {
      return sortInputsByVisualOrder(singleChar);
    }

    // 4. Targeted OTP Attribute / Name / ID / Placeholder matching
    const selectors = [
      'input[name*="twofactor" i]',
      'input[name*="two-factor" i]',
      'input[name*="two_factor" i]',
      'input[name*="twofa" i]',
      'input[name*="2fa" i]',
      'input[name*="devicecode" i]',
      'input[name*="device-code" i]',
      'input[name*="device_code" i]',
      'input[name*="otp" i]',
      'input[name*="passcode" i]',
      'input[name*="verification_code" i]',
      'input[name*="verification-code" i]',
      'input[name*="verificationcode" i]',
      'input[name*="verification_token" i]',
      'input[name*="verification_pin" i]',
      'input[name*="verify_code" i]',
      'input[name*="verify-code" i]',
      'input[name*="verifycode" i]',
      'input[name*="auth_code" i]',
      'input[name*="auth-code" i]',
      'input[name*="security_code" i]',
      'input[name*="security-code" i]',
      'input[name*="login_code" i]',
      'input[name*="login-code" i]',
      'input[name*="email_code" i]',
      'input[name*="email-code" i]',
      'input[name*="sms_code" i]',
      'input[name*="sms-code" i]',
      'input[name="code" i]',
      'input[name="pin" i]',
      'input[id*="twofactor" i]',
      'input[id*="two-factor" i]',
      'input[id*="two_factor" i]',
      'input[id*="twofa" i]',
      'input[id*="2fa" i]',
      'input[id*="devicecode" i]',
      'input[id*="device-code" i]',
      'input[id*="device_code" i]',
      'input[id*="otp" i]',
      'input[id*="passcode" i]',
      'input[id*="verification_code" i]',
      'input[id*="verification-code" i]',
      'input[id*="verificationcode" i]',
      'input[id*="verificationCode" i]',
      'input[id="inputVerificationCode"]',
      'input[id*="verify-code" i]',
      'input[id*="verify_code" i]',
      'input[id*="auth-code" i]',
      'input[id*="auth_code" i]',
      'input[id*="security-code" i]',
      'input[id*="security_code" i]',
      'input#code',
      'input#pin',
      'input[placeholder*="verification code" i]',
      'input[placeholder*="verification-code" i]',
      'input[placeholder*="verify code" i]',
      'input[placeholder*="device code" i]',
      'input[placeholder*="device verification" i]',
      'input[placeholder*="two-factor" i]',
      'input[placeholder*="two factor" i]',
      'input[placeholder*="security code" i]',
      'input[placeholder*="login code" i]',
      'input[placeholder*="6-digit" i]',
      'input[placeholder*="4-digit" i]',
      'input[placeholder*="one-time" i]',
      'input[placeholder*="验证码" i]',
      'input[placeholder*="校验码" i]',
      'input[placeholder*="动态码" i]',
      'input[placeholder*="安全码" i]',
      'input[placeholder*="認証コード" i]',
      'input[placeholder*="確認コード" i]',
      'input[placeholder*="ワンタイム" i]',
      'input[placeholder*="mã xác thực" i]',
      'input[placeholder*="mã xác minh" i]',
      'input[placeholder*="mã otp" i]',
      'input[placeholder*="รหัส otp" i]',
      'input[placeholder*="รหัสยืนยัน" i]',
      'input[aria-label*="verification code" i]',
      'input[aria-label*="verify code" i]',
      'input[aria-label*="device code" i]',
      'input[aria-label*="two-factor" i]',
      'input[aria-label*="one-time" i]',
      'input[aria-label*="security code" i]',
      'input[aria-label*="otp" i]',
      'input[aria-label*="验证码" i]',
      'input[aria-label*="認証コード" i]',
      'input[aria-label*="ワンタイム" i]',
      'input[aria-label*="mã xác thực" i]',
      'input[aria-label*="รหัส otp" i]',
      'input[data-testid*="otp" i]',
      'input[data-testid*="verification-code" i]',
      'input[data-testid*="verification_code" i]',
      'input[data-testid*="verify-code" i]'
    ];

    for (const sel of selectors) {
      const matches = Array.from(document.querySelectorAll(sel)).filter(isInteractiveElement).filter(el => !isDisqualifiedInput(el));
      if (matches.length === 1) return [matches[0]];
      if (matches.length >= 4 && matches.length <= 8) return sortInputsByVisualOrder(matches);
    }

    // 5. Label-based matching (handles WHMCS & custom forms where input has generic name/id but label has OTP text)
    const labelElements = Array.from(document.querySelectorAll("label, p, div, span, td, th, b, strong"));
    for (const lbl of labelElements) {
      if (lbl.children.length > 4) continue;
      const labelText = (lbl.textContent || "").trim();
      if (/(?:verification|security|login|device|two[-_ ]*factor|auth|one[-_ ]*time|sms|email)\s*(?:verification\s*)?(?:code|passcode|pin|token)|验证码|校验码|动态码|ワンタイム|認証コード/i.test(labelText)) {
        // 5a. Explicit label[for="id"]
        const forId = lbl.getAttribute("for");
        if (forId) {
          const targetInput = document.getElementById(forId);
          if (targetInput && isInteractiveElement(targetInput) && !isDisqualifiedInput(targetInput)) {
            return [targetInput];
          }
        }
        // 5b. Nested input inside label element
        const nested = lbl.querySelector('input[type="text"], input[type="tel"], input[type="number"], input[type="password"], input:not([type])');
        if (nested && isInteractiveElement(nested) && !isDisqualifiedInput(nested)) {
          return [nested];
        }
        // 5c. Form-group / control-group wrapper (standard in WHMCS / Bootstrap / Tailwind)
        const container = lbl.closest('.control-group, .form-group, .field, .form-item, fieldset, tr, div, form');
        if (container) {
          const groupInput = container.querySelector('input[type="text"], input[type="tel"], input[type="number"], input[type="password"], input:not([type])');
          if (groupInput && isInteractiveElement(groupInput) && !isDisqualifiedInput(groupInput)) {
            return [groupInput];
          }
        }
        // 5d. Sibling input
        let nextEl = lbl.nextElementSibling;
        while (nextEl) {
          if (nextEl.tagName === "INPUT" && isInteractiveElement(nextEl) && !isDisqualifiedInput(nextEl)) {
            return [nextEl];
          }
          const nextInput = nextEl.querySelector && nextEl.querySelector('input[type="text"], input[type="tel"], input[type="number"], input[type="password"], input:not([type])');
          if (nextInput && isInteractiveElement(nextInput) && !isDisqualifiedInput(nextInput)) {
            return [nextInput];
          }
          nextEl = nextEl.nextElementSibling;
        }
      }
    }

    // 6. Dedicated 2FA / OTP Form Context (e.g. WHMCS browser_auth.php, TOTP/2FA modal dialogs)
    const dedicatedAuthForms = document.querySelectorAll(
      'form[action*="browser_auth" i], form[action*="twofactor" i], form[action*="totp" i], form[action*="otp" i], form[id*="otp" i], form[class*="otp" i], form[id*="totp" i], form[class*="totp" i]'
    );
    for (const form of dedicatedAuthForms) {
      const inputs = Array.from(form.querySelectorAll('input[type="text"], input[type="tel"], input[type="number"], input:not([type])'))
        .filter(isInteractiveElement)
        .filter(el => !isDisqualifiedInput(el));
      if (inputs.length === 1) return [inputs[0]];
      if (inputs.length >= 4 && inputs.length <= 8) return sortInputsByVisualOrder(inputs);
    }

    // 7. contenteditable OTP components
    const editables = Array.from(document.querySelectorAll(
      '[contenteditable="true"][id*="otp" i], [contenteditable="true"][class*="otp" i], [contenteditable="true"][data-testid*="otp" i]'
    )).filter(el => el.offsetParent !== null);
    if (editables.length > 0) return [editables[0]];

    return [];
  }

  // Sniff recipient email address mentioned on page (e.g. "sent a 6-digit verification code to alex.turner@example.com")
  function findEmailOnPage() {
    if (typeof document === "undefined" || !document.body) return null;

    const systemEmailRegex = /(?:support|help|sales|contact|privacy|terms|billing|security|abuse|info|noreply|no-reply|service|mailer-daemon)@/i;
    const dummyDomainRegex = /(?:example\.com|domain\.com|yourdomain\.com|test\.com)/i;

    function sanitizeEmail(email) {
      if (!email) return "";
      return email.trim().replace(/^[<(\['"]+/, "").replace(/[>'\])".,;:!?]+$/, "").trim();
    }

    function isValidUserEmail(email) {
      const clean = sanitizeEmail(email).toLowerCase();
      if (!clean) return false;
      if (!/^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$/.test(clean)) return false;
      if (systemEmailRegex.test(clean) || dummyDomainRegex.test(clean)) return false;
      return true;
    }

    // 1. High-fidelity sentence matching: e.g. "sent a 6-digit verification code to alex.turner@example.com"
    const sentencePatterns = [
      /(?:sent\s+(?:a\s+)?(?:\d+[- ]*(?:digit|char)\s+)?(?:verification\s+|security\s+|login\s+|device\s+|auth\s+)?(?:code|passcode|email|link|pin)\s+to|(?:verification|security)\s+code\s+sent\s+to|code\s+(?:was|has\s+been)\s+sent\s+to|sent\s+to|sent\s+an\s+email\s+to|check\s+your\s+email\s+at|发送至|发送到|已将验证码发送(?:至|到)|已向.*?发送验证码)\s*:?\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)/i,
      /(?:to\s+protect\s+your\s+account[^\n]*?sent[^\n]*?to)\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)/i,
      /([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\s*(?:has\s+been\s+sent|receives?\s+(?:the|a)\s+code|接收验证码)/i
    ];

    const textNodes = Array.from(document.querySelectorAll("p, div, span, b, strong, em, td, li, h1, h2, h3, h4, section, main, article"));
    for (const node of textNodes) {
      if (node.children.length > 5) continue;
      const text = node.textContent || "";
      if (text.length > 500) continue;

      for (const pat of sentencePatterns) {
        const match = text.match(pat);
        if (match && match[1]) {
          const cleaned = sanitizeEmail(match[1]);
          if (isValidUserEmail(cleaned)) {
            return cleaned;
          }
        }
      }
    }

    // 2. Email inside or adjacent to the verification form or OTP input container
    const otpInputs = findOtpInputs();
    if (otpInputs.length > 0) {
      const container = otpInputs[0].closest("form, .card, .modal, [role='dialog'], .content, .main, #content, .login-container") || otpInputs[0].parentElement;
      if (container) {
        const tags = container.querySelectorAll("b, strong, em, .email, [data-email]");
        for (const tag of tags) {
          const t = sanitizeEmail(tag.textContent || "");
          if (isValidUserEmail(t)) return t;
        }
        const m = container.textContent.match(/[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g);
        if (m) {
          for (const em of m) {
            const cleaned = sanitizeEmail(em);
            if (isValidUserEmail(cleaned)) return cleaned;
          }
        }
      }
    }

    // 3. User profile / account info blocks on auth page (e.g. WHMCS sidebar "Account Information ... alex.turner@example.com")
    const accountInfoBlocks = document.querySelectorAll(".account-info, .account-information, #account-info, .user-info, .profile-info, [class*='account' i]");
    for (const block of accountInfoBlocks) {
      const m = block.textContent.match(/[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g);
      if (m) {
        for (const em of m) {
          const cleaned = sanitizeEmail(em);
          if (isValidUserEmail(cleaned)) return cleaned;
        }
      }
    }

    // 4. Emphasis tags (b, strong, em, i, code, span)
    const emphases = document.querySelectorAll("b, strong, em, i, code, span");
    for (const el of emphases) {
      if (el.children.length > 2) continue;
      const m = (el.textContent || "").match(/[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g);
      if (m) {
        for (const em of m) {
          const cleaned = sanitizeEmail(em);
          if (isValidUserEmail(cleaned)) return cleaned;
        }
      }
    }

    // 5. Global unique user email scan across the whole page (catches custom WHMCS templates, notices, and footers)
    const pageText = document.body.innerText || document.body.textContent || "";
    const allPageMatches = pageText.match(/[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g);
    if (allPageMatches) {
      const candidates = Array.from(new Set(allPageMatches.map(sanitizeEmail).filter(isValidUserEmail)));
      if (candidates.length === 1) {
        return candidates[0];
      }
    }

    return null;
  }

  // Find Email input field on page (primarily for Cloudflare Access or passwordless auth)
  function findEmailInput() {
    const isAuthPage = window.location.hostname.includes("cloudflareaccess.com") ||
                       document.querySelector('form[action*="access" i], form[id*="totp" i]');
    if (!isAuthPage) return null;

    const selectors = ['input#email', 'input[name="email"]', 'input[type="email"]', '.EmailInput'];
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && el.offsetParent !== null) return el;
    }
    return null;
  }

  function getOrCreatePill() {
    let container = document.getElementById("spark-otp-pill-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "spark-otp-pill-container";
      document.body.appendChild(container);
    }
    return container;
  }

  function renderPill(state, data = {}) {
    // Avoid blocking tiny iframes (e.g. 3DS hidden frames)
    if (window.self !== window.top && (window.innerHeight < 100 || window.innerWidth < 150)) {
      return;
    }
    const container = getOrCreatePill();
    if (state === "hidden") {
      container.style.display = "none";
      return;
    }
    container.style.display = "block";

    if (state === "email_ready") {
      container.innerHTML = `
        <div class="spark-otp-card">
          <div class="spark-otp-icon-wrap">${ICONS.mail}</div>
          <div class="spark-otp-content">
            <div class="spark-otp-title">${t("sparkLogin")}</div>
            <div class="spark-otp-subtitle">${t("readyToSend", { email: data.email })}</div>
          </div>
          <div class="spark-otp-actions">
            <button class="spark-otp-btn spark-otp-btn-primary" id="spark-btn-send-code">${t("sendCode")}</button>
          </div>
        </div>
      `;
      const btn = document.getElementById("spark-btn-send-code");
      if (btn) {
        btn.addEventListener("click", () => fillEmailAndSubmit(data.email));
      }
    } else if (state === "watching") {
      if (!watchingTimer) {
        watchingSeconds = 0;
        watchingTimer = setInterval(() => {
          watchingSeconds++;
          const timerEl = document.getElementById("spark-otp-timer");
          if (timerEl) {
            const mins = String(Math.floor(watchingSeconds / 60)).padStart(2, "0");
            const secs = String(watchingSeconds % 60).padStart(2, "0");
            timerEl.textContent = `${mins}:${secs}`;
          }
        }, 1000);
      }
      container.innerHTML = `
        <div class="spark-otp-card">
          <div class="spark-otp-icon-wrap pulse">${ICONS.loader}</div>
          <div class="spark-otp-content">
            <div class="spark-otp-title">${t("watchingTitle")}</div>
            <div class="spark-otp-subtitle">${t("watchingSubtitle")} <span class="spark-otp-meta-badge">${data.account || data.domain || t("allMailboxes")}</span> <span id="spark-otp-timer" class="spark-otp-timer-badge">00:00</span></div>
          </div>
          <div class="spark-otp-actions">
            <button class="spark-otp-btn spark-otp-btn-secondary" id="spark-btn-poll-now" title="${t("refresh")}">${t("refresh")}</button>
            <button class="spark-otp-btn spark-otp-btn-ghost" id="spark-btn-dismiss" title="×">×</button>
          </div>
        </div>
      `;
      const refreshBtn = document.getElementById("spark-btn-poll-now");
      if (refreshBtn) {
        refreshBtn.addEventListener("click", () => {
          refreshBtn.textContent = "...";
          pollOnce(data.domain, refreshBtn);
        });
      }
      const dismissBtn = document.getElementById("spark-btn-dismiss");
      if (dismissBtn) {
        dismissBtn.addEventListener("click", () => {
          stopListening();
          renderPill("hidden");
          const d = data.domain || detectTargetDomain();
          setStorageItem("spark_otp_dismissed_" + d, "1");
        });
      }
    } else if (state === "found") {
      if (watchingTimer) {
        clearInterval(watchingTimer);
        watchingTimer = null;
      }
      const remainingInfo = data.time_remaining_seconds
        ? t("remainingMin", { n: Math.max(1, Math.round(data.time_remaining_seconds / 60)) })
        : '';
      container.innerHTML = `
        <div class="spark-otp-card">
          <div class="spark-otp-icon-wrap success">${ICONS.key}</div>
          <div class="spark-otp-content">
            <div class="spark-otp-title">${t("codeFound")}<span class="spark-otp-code-highlight">${data.code}</span></div>
            <div class="spark-otp-subtitle">${data.filled ? t("autoFilled") : t("readyToFill")}${remainingInfo}</div>
          </div>
          <div class="spark-otp-actions">
            ${!data.filled ? `<button class="spark-otp-btn spark-otp-btn-primary" id="spark-otp-btn-fill">${t("fill")}</button>` : ''}
            <button class="spark-otp-btn spark-otp-btn-secondary" id="spark-otp-btn-copy">${t("copy")}</button>
            <button class="spark-otp-btn spark-otp-btn-secondary" id="spark-otp-btn-refresh-new" title="${t("refreshNew")}">${t("refreshNew")}</button>
            ${data.callback_url ? `<a class="spark-otp-btn spark-otp-btn-secondary" href="${data.callback_url}" target="_self">${ICONS.link} ${t("directJump")}</a>` : ''}
            <button class="spark-otp-btn spark-otp-btn-ghost" id="spark-btn-dismiss-found">×</button>
          </div>
        </div>
      `;

      const fillBtn = document.getElementById("spark-otp-btn-fill");
      if (fillBtn) {
        fillBtn.addEventListener("click", () => fillAndSubmit(data.code, true));
      }
      const copyBtn = document.getElementById("spark-otp-btn-copy");
      if (copyBtn) {
        copyBtn.addEventListener("click", () => {
          navigator.clipboard.writeText(data.code);
          copyBtn.textContent = t("copied");
          setTimeout(() => { copyBtn.textContent = t("copy"); }, 1500);
        });
      }
      const refNewBtn = document.getElementById("spark-otp-btn-refresh-new");
      if (refNewBtn) {
        refNewBtn.addEventListener("click", () => {
          activeCode = null;
          startListening();
        });
      }
      const dismissBtn = document.getElementById("spark-btn-dismiss-found");
      if (dismissBtn) {
        dismissBtn.addEventListener("click", () => {
          stopListening();
          renderPill("hidden");
        });
      }
    } else if (state === "code_failed") {
      if (watchingTimer) {
        clearInterval(watchingTimer);
        watchingTimer = null;
      }
      const titleHtml = data.code
        ? t("codeFailedTitle", { code: data.code })
        : t("codeFailedTitleGeneric");
      container.innerHTML = `
        <div class="spark-otp-card">
          <div class="spark-otp-icon-wrap warning">${ICONS.alert}</div>
          <div class="spark-otp-content">
            <div class="spark-otp-title">${titleHtml}</div>
            <div class="spark-otp-subtitle">${t("codeFailedSubtitle")} <span class="spark-otp-error-badge">${t("failedBadge")}</span></div>
          </div>
          <div class="spark-otp-actions">
            <button class="spark-otp-btn spark-otp-btn-secondary" id="spark-btn-poll-now" title="${t("refresh")}">${t("refresh")}</button>
            ${data.code ? `<button class="spark-otp-btn spark-otp-btn-secondary" id="spark-btn-force-fill" title="${t("forceFill")}">${t("forceFill")}</button>` : ''}
            <button class="spark-otp-btn spark-otp-btn-ghost" id="spark-btn-dismiss-failed" title="×">×</button>
          </div>
        </div>
      `;
      const refreshBtn = document.getElementById("spark-btn-poll-now");
      if (refreshBtn) {
        refreshBtn.addEventListener("click", () => {
          refreshBtn.textContent = "...";
          pollOnce(data.domain, refreshBtn);
        });
      }
      const forceFillBtn = document.getElementById("spark-btn-force-fill");
      if (forceFillBtn && data.code) {
        forceFillBtn.addEventListener("click", () => {
          const inputs = findOtpInputs();
          if (inputs.length === 1) {
            setInputValueWithReactSupport(inputs[0], data.code);
          } else if (inputs.length > 1) {
            for (let i = 0; i < inputs.length && i < data.code.length; i++) {
              setInputValueWithReactSupport(inputs[i], data.code[i]);
            }
          }
        });
      }
      const dismissBtn = document.getElementById("spark-btn-dismiss-failed");
      if (dismissBtn) {
        dismissBtn.addEventListener("click", () => {
          stopListening();
          renderPill("hidden");
        });
      }
    }
  }

  function setInputValueWithReactSupport(input, value) {
    input.focus();

    // Native prototype setter bypass for React/controlled inputs
    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")?.set ||
                         Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), "value")?.set;

    if (nativeSetter) {
      nativeSetter.call(input, value);
    } else {
      input.value = value;
    }

    // React _valueTracker update:
    // Setting tracker.setValue("") ensures React recognizes that the value changed and fires onChange
    const tracker = input._valueTracker;
    if (tracker) {
      tracker.setValue("");
    }

    // Dispatch simulated paste event (handles input-otp and onPaste handlers)
    try {
      const dt = new DataTransfer();
      dt.setData("text/plain", value);
      input.dispatchEvent(new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData: dt }));
    } catch (e) {}

    try {
      if (typeof InputEvent !== "undefined") {
        input.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: value }));
      }
    } catch (e) {}
    try {
      if (typeof Event !== "undefined") {
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
    } catch (e) {}
    try {
      if (typeof KeyboardEvent !== "undefined") {
        input.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, key: value }));
        input.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: value }));
      }
    } catch (e) {}
  }

  function isVerifyButton(btn) {
    const txt = (btn.textContent || btn.value || "").trim().toLowerCase();
    const verifyWords = ["verify", "continue", "submit", "confirm", "sign in", "log in", "next", "check", "validate", "验证", "确认", "登录", "認証", "次へ"];
    return verifyWords.some(w => txt.includes(w));
  }

  function triggerSubmit(targetElement, shouldSubmit) {
    if (!shouldSubmit) return;

    setTimeout(() => {
      // 1. Look for enclosing form only (do not blindly match search or unrelated forms)
      const form = targetElement.closest("form") || document.getElementById("totp-form");
      if (form) {
        const allSubmitBtns = Array.from(form.querySelectorAll('button[type="submit"], input[type="submit"], button:not([type]), input[type="button"]'));
        const verifySubmit = allSubmitBtns.find(b => isVerifyButton(b) && !b.disabled);
        if (verifySubmit) {
          verifySubmit.click();
          return;
        }
        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitBtn && !submitBtn.disabled) {
          submitBtn.click();
          return;
        }
        const anyBtn = form.querySelector("button");
        if (anyBtn && isVerifyButton(anyBtn) && !anyBtn.disabled) {
          anyBtn.click();
          return;
        }
        try {
          form.submit();
          return;
        } catch (e) {}
      }

      // 2. Look for verify button in modal/dialog container or page
      const container = targetElement.closest('[role="dialog"], [role="region"], .modal, .card, main') || document.body;
      const buttons = container ? container.querySelectorAll('button, [role="button"], input[type="button"], input[type="submit"]') : [];
      for (const btn of buttons) {
        if (isVerifyButton(btn) && !btn.disabled && btn.offsetParent !== null) {
          btn.click();
          return;
        }
      }
    }, 300);
  }

  function fillAndSubmit(code, submit = true, messageId = null, receivedAtMs = 0) {
    const cleanCode = String(code).trim();
    const domain = detectTargetDomain();
    const recMs = Number(receivedAtMs) || 0;
    if (isCodeRejected(cleanCode, messageId, recMs, domain)) {
      console.warn("[Spark OTP] Skipping rejected/failed code:", cleanCode);
      return false;
    }

    const state = getAuthState(domain);
    const alreadySubmitted = (state.submissionCounts[cleanCode] || 0) >= 1;
    const shouldActuallySubmit = submit && !alreadySubmitted;

    if (shouldActuallySubmit) {
      recordCodeSubmitted(cleanCode, messageId, domain);
    }

    const inputs = findOtpInputs();
    if (!inputs || inputs.length === 0) return false;

    // Case 1: contenteditable OTP component
    if (inputs.length === 1 && inputs[0].isContentEditable) {
      const el = inputs[0];
      el.focus();
      el.textContent = cleanCode;
      el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: cleanCode }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      triggerSubmit(el, shouldActuallySubmit);
      return true;
    }

    // Case 2: Single input (including React input-otp / shadcn)
    if (inputs.length === 1) {
      const input = inputs[0];
      setInputValueWithReactSupport(input, cleanCode);
      triggerSubmit(input, shouldActuallySubmit);
      return true;
    }

    // Case 3: Segmented multi-box inputs (4, 6, 8 digit inputs)
    if (inputs.length > 1) {
      // Attempt clipboard paste event on first input
      try {
        const dt = new DataTransfer();
        dt.setData("text/plain", cleanCode);
        const pasteEvt = new ClipboardEvent("paste", {
          bubbles: true,
          cancelable: true,
          clipboardData: dt
        });
        inputs[0].dispatchEvent(pasteEvt);
      } catch (e) {}

      // Fill each box individually
      for (let i = 0; i < inputs.length && i < cleanCode.length; i++) {
        const char = cleanCode[i];
        const inp = inputs[i];
        setInputValueWithReactSupport(inp, char);
        inp.dispatchEvent(new KeyboardEvent("keypress", { bubbles: true, key: char, charCode: char.charCodeAt(0) }));
      }

      triggerSubmit(inputs[inputs.length - 1], shouldActuallySubmit);
      return true;
    }

    return false;
  }

  function fillEmailAndSubmit(email) {
    const input = findEmailInput();
    if (!input) return;
    setInputValueWithReactSupport(input, email);

    setTimeout(() => {
      const form = input.closest("form") || document.getElementById("totp-form");
      if (form) {
        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitBtn) submitBtn.click();
        else form.submit();
      }
    }, 250);
  }

  function startListening() {
    if (isListening) return;
    const domain = detectTargetDomain();
    if (isDomainDisabled(domain)) return;
    if (getStorageItem("spark_otp_dismissed_" + domain) === "1") return;
    isListening = true;

    const detectedEmail = findEmailOnPage();
    const effectiveAccount = detectedEmail || selectedAccount || "";

    const pageErr = detectPageError();
    const authState = getAuthState(domain);

    if (pageErr.hasError) {
      const lastBadCode = authState.failedCodes.length > 0 ? authState.failedCodes[authState.failedCodes.length - 1] : (authState.lastSubmittedCode || "");
      renderPill("code_failed", { code: lastBadCode, domain, account: effectiveAccount });
    } else {
      renderPill("watching", { domain, account: effectiveAccount });
    }

    const query = buildApiQuery(domain, effectiveAccount);
    let streamUrl = `http://127.0.0.1:${serverPort}/api/stream?${query}`;

    try {
      if (eventSource) {
        eventSource.close();
      }
      eventSource = new EventSource(streamUrl);

      eventSource.addEventListener("otp", (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data && data.code) {
            const receivedMs = data.received_at ? (new Date(data.received_at).getTime() || 0) : 0;
            if (isCodeRejected(data.code, data.message_id, receivedMs, domain)) {
              renderPill("code_failed", {
                code: data.code,
                domain,
                account: effectiveAccount
              });
              return;
            }

            if (data.code !== activeCode) {
              activeCode = data.code;

              if (autoDirectJump && data.callback_url) {
                window.location.href = data.callback_url;
                return;
              }

              const filled = fillAndSubmit(data.code, autoSubmit, data.message_id, receivedMs);
              renderPill("found", {
                code: data.code,
                callback_url: data.callback_url,
                filled: filled && autoSubmit,
                time_remaining_seconds: data.time_remaining_seconds,
                message_id: data.message_id,
                received_at_ms: receivedMs
              });
              stopListening();
            }
          }
        } catch (err) {
          console.error("[Spark OTP] Error parsing event:", err);
        }
      });

      eventSource.onerror = () => {
        if (!pollInterval) {
          pollFallback(domain);
        }
      };
    } catch (err) {
      pollFallback(domain);
    }
  }

  function stopListening() {
    isListening = false;
    if (watchingTimer) {
      clearInterval(watchingTimer);
      watchingTimer = null;
      watchingSeconds = 0;
    }
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  let isPollingInflight = false;
  function pollFallback(domain) {
    if (pollInterval) return;
    pollInterval = setInterval(async () => {
      if (isPollingInflight) return;
      isPollingInflight = true;
      try {
        const detectedEmail = findEmailOnPage();
        const effectiveAccount = detectedEmail || selectedAccount || "";
        if (detectedEmail) {
          const badge = document.querySelector("#spark-otp-pill-container .spark-otp-meta-badge");
          if (badge && !badge.textContent.includes(detectedEmail)) {
            badge.textContent = `${domain} · ${detectedEmail}`;
          }
        }
        const query = buildApiQuery(domain, effectiveAccount);
        const apiUrl = `http://127.0.0.1:${serverPort}/api/otp?${query}`;
        const res = await fetch(apiUrl);
        if (res.ok) {
          const data = await res.json();
          if (data.success && data.otp && data.otp.code) {
            const receivedMs = data.otp.received_at ? (new Date(data.otp.received_at).getTime() || 0) : 0;
            if (isCodeRejected(data.otp.code, data.otp.message_id, receivedMs, domain)) {
              renderPill("code_failed", {
                code: data.otp.code,
                domain,
                account: effectiveAccount
              });
              return;
            }
            if (data.otp.code !== activeCode) {
              activeCode = data.otp.code;
              if (autoDirectJump && data.otp.callback_url) {
                window.location.href = data.otp.callback_url;
                return;
              }
              const filled = fillAndSubmit(data.otp.code, autoSubmit, data.otp.message_id, receivedMs);
              renderPill("found", {
                code: data.otp.code,
                callback_url: data.otp.callback_url,
                filled: filled && autoSubmit,
                time_remaining_seconds: data.otp.time_remaining_seconds,
                message_id: data.otp.message_id,
                received_at_ms: receivedMs
              });
              stopListening();
            }
          }
        }
      } catch (e) {
      } finally {
        isPollingInflight = false;
      }
    }, 2000);
  }

  async function pollOnce(domain, btn) {
    try {
      const d = domain || detectTargetDomain();
      const detectedEmail = findEmailOnPage();
      const effectiveAccount = detectedEmail || selectedAccount || "";
      const query = buildApiQuery(d, effectiveAccount);
      const apiUrl = `http://127.0.0.1:${serverPort}/api/otp?${query}`;
      const res = await fetch(apiUrl);
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.otp && data.otp.code) {
          const receivedMs = data.otp.received_at ? (new Date(data.otp.received_at).getTime() || 0) : 0;
          if (isCodeRejected(data.otp.code, data.otp.message_id, receivedMs, d)) {
            renderPill("code_failed", {
              code: data.otp.code,
              domain: d,
              account: effectiveAccount
            });
            if (btn) {
              btn.textContent = t("excludedOldCode");
              setTimeout(() => { btn.textContent = t("refresh"); }, 1500);
            }
            return;
          }
          activeCode = data.otp.code;
          if (autoDirectJump && data.otp.callback_url) {
            window.location.href = data.otp.callback_url;
            return;
          }
          const filled = fillAndSubmit(data.otp.code, autoSubmit, data.otp.message_id, receivedMs);
          renderPill("found", {
            code: data.otp.code,
            callback_url: data.otp.callback_url,
            filled: filled && autoSubmit,
            time_remaining_seconds: data.otp.time_remaining_seconds,
            message_id: data.otp.message_id,
            received_at_ms: receivedMs
          });
          return;
        }
      }
      if (btn) {
        btn.textContent = t("notFound");
        setTimeout(() => { btn.textContent = t("refresh"); }, 1500);
      }
    } catch (e) {
      if (btn) {
        btn.textContent = t("offline");
        setTimeout(() => { btn.textContent = t("refresh"); }, 1500);
      }
    }
  }

  function checkPage() {
    const domain = detectTargetDomain();
    if (isDomainDisabled(domain)) return;
    if (getStorageItem("spark_otp_dismissed_" + domain) === "1") return;
    const pageErr = detectPageError();
    let authState = getAuthState(domain);

    if (pageErr.hasError) {
      if (!authState.lastSubmittedCode) {
        const existingInputs = findOtpInputs();
        if (existingInputs.length > 0) {
          const val = existingInputs.map(inp => (inp.value || inp.textContent || "").trim()).join("");
          if (/^[a-zA-Z0-9]{4,10}$/.test(val)) {
            authState.lastSubmittedCode = val;
          }
        }
      }

      if (authState.lastSubmittedCode) {
        // The page reloaded with an error after submitting a code!
        // Immediately register that code as rejected/failed!
        authState = recordCodeFailed(authState.lastSubmittedCode, authState.lastSubmittedMsgId, domain);
      } else if (!authState.lastFailedAt) {
        authState.lastFailedAt = Date.now();
        saveAuthState(authState, domain);
      }
    }

    const otpInputs = findOtpInputs();
    const emailInput = findEmailInput();

    if (otpInputs.length > 0) {
      startListening();
    } else if (emailInput && !emailInput.value) {
      if (autoEmail) {
        fillEmailAndSubmit(defaultEmail);
      } else {
        renderPill("email_ready", { email: defaultEmail });
      }
    } else {
      // Dynamic SPA monitoring: observe DOM additions for OTP fields
      const observer = new MutationObserver(() => {
        if (isDomainDisabled(domain) || getStorageItem("spark_otp_dismissed_" + domain) === "1") {
          observer.disconnect();
          return;
        }
        const foundOtp = findOtpInputs();
        if (foundOtp.length > 0) {
          observer.disconnect();
          startListening();
        }
      });
      observer.observe(document.body || document.documentElement, { childList: true, subtree: true });
    }
  }

  function init() {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.sync) {
      chrome.storage.sync.get(["serverPort", "autoSubmit", "autoEmail", "defaultEmail", "selectedAccount", "autoDirectJump", "language", "disabledDomains"], (res) => {
        if (res.serverPort) serverPort = res.serverPort;
        if (typeof res.autoSubmit !== "undefined") autoSubmit = res.autoSubmit;
        if (typeof res.autoEmail !== "undefined") autoEmail = res.autoEmail;
        if (res.defaultEmail) defaultEmail = res.defaultEmail;
        if (res.selectedAccount) selectedAccount = res.selectedAccount;
        if (typeof res.autoDirectJump !== "undefined") autoDirectJump = res.autoDirectJump;
        if (res.language) currentLang = res.language;
        if (res.disabledDomains && Array.isArray(res.disabledDomains)) disabledDomains = res.disabledDomains;
        checkPage();
      });

      chrome.storage.onChanged.addListener((changes, area) => {
        if (area === "sync" || area === "local") {
          let needsRestart = false;
          if (changes.disabledDomains) {
            disabledDomains = changes.disabledDomains.newValue || [];
            if (isDomainDisabled(detectTargetDomain()) && isListening) {
              stopListening();
              renderPill("hidden");
            }
          }
          if (changes.language && changes.language.newValue) {
            currentLang = changes.language.newValue;
            needsRestart = true;
          }
          if (changes.serverPort && changes.serverPort.newValue) {
            serverPort = changes.serverPort.newValue;
            needsRestart = true;
          }
          if (changes.selectedAccount) {
            selectedAccount = changes.selectedAccount.newValue || "";
            needsRestart = true;
          }
          if (changes.autoSubmit) autoSubmit = changes.autoSubmit.newValue;
          if (changes.autoEmail) autoEmail = changes.autoEmail.newValue;
          if (changes.defaultEmail) defaultEmail = changes.defaultEmail.newValue;
          if (changes.autoDirectJump) autoDirectJump = changes.autoDirectJump.newValue;

          if (needsRestart && isListening) {
            stopListening();
            startListening();
          }
        }
      });
    } else {
      checkPage();
    }

    // Immediate user feedback upon clicking / tabbing into an actual OTP input field
    document.addEventListener("focusin", (e) => {
      if (e.target && (e.target.tagName === "INPUT" || e.target.isContentEditable)) {
        if (!isDisqualifiedInput(e.target)) {
          const otpInputs = findOtpInputs();
          if (otpInputs.includes(e.target)) {
            startListening();
          }
        }
      }
    }, { passive: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();


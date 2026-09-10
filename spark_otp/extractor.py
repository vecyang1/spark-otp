"""
Deterministic zero-LLM OTP Extraction Engine.
Supports universal auth providers, brand/domain matching, and open fallback extraction.
"""
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from .models import OTPResult, RuleDefinition
from .config import DEFAULT_RULES

COMMON_TLDS = {
    "com", "org", "net", "io", "so", "app", "co", "edu", "gov",
    "dev", "me", "ai", "site", "xyz", "cn", "jp", "uk", "de", "fr", "in", "cloud"
}

COMMON_SUBDOMAINS = {
    "www", "app", "auth", "login", "dash", "dashboard", "portal",
    "console", "admin", "api", "mail", "account", "accounts", "sso", "id"
}

OTP_INTENT_PATTERN = re.compile(
    r"(?i)(?:"
    r"verification\s*code|verify|security\s*code|login\s*code|access\s*code|"
    r"device\s*verification|device\s*auth|"
    r"one-time\s*password|one-time\s*code|one-time\s*pin|passcode|auth\s*code|authentication\s*code|"
    r"confirmation\s*code|secret\s*code|pin\s*code|two-factor|2fa|mfa|otp\b|"
    r"validation\s*code|validating\s*code|sign-in\s*code|single-use\s*code|"
    r"[a-z0-9\.-]+\s+code\b|"
    r"3d\s*secure|one-time\s*passcode|"
    r"验证码|动态码|校验码|安全码|授权码|登录码|一次性密码|验证代码|身份验证码|"
    r"認証コード|確認コード|ワンタイムパスワード|セキュリティコード|認証用コード|パスコード|"
    r"รหัส\s*otp|รหัสยืนยัน|เลขรหัส\s*otp|รหัสผ่านแบบใช้ครั้งเดียว|"
    r"mã\s*xác\s*thực|mã\s*xác\s*minh|mã\s*otp|mã\s*xác\s*nhận|mã\s*đăng\s*nhập"
    r")"
)

def get_domain_brand(domain: str) -> str:
    """Extract primary brand name from domain (e.g. 'dash.cloudflare.com' -> 'cloudflare', 'myapp.cloud' -> 'myapp')."""
    d = domain.lower().strip()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0].split(":")[0]
    d = re.sub(r"^www\.", "", d)
    parts = d.split(".")
    if len(parts) <= 1:
        return d

    # Check for two-part ccTLDs like co.jp, co.uk, com.cn
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "edu", "gov", "ac"} and len(parts[-1]) == 2:
        return parts[-3]

    return parts[-2]

def parse_email_date(date_str: str) -> Optional[datetime]:
    """Parse date string commonly emitted by Spark CLI."""
    date_str = date_str.strip()
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%d/%m/%Y %H:%M",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    clean = re.sub(r"[+-]\d{2}:?\d{2}$", "", date_str)
    for fmt in formats:
        try:
            return datetime.strptime(clean.strip(), fmt)
        except ValueError:
            continue
    return None

def parse_thread_headers(thread_text: str) -> Dict[str, str]:
    """Extract metadata headers from thread output."""
    headers = {}
    for line in thread_text.splitlines():
        line = line.strip()
        match = re.match(r"^(ID|Subject|From|To|Date|Type|Flags):\s*(.*)$", line)
        if match:
            headers[match.group(1).lower()] = match.group(2).strip()
    return headers

def get_thread_body(thread_text: str) -> str:
    """Return body of thread text with metadata headers removed across all messages."""
    lines = []
    for line in thread_text.splitlines():
        stripped = line.strip()
        if re.match(r"^(ID|Subject|From|To|Date|Type|Flags|Labels|Link|Thread|Messages):\s*", stripped) or stripped.startswith("─"):
            continue
        lines.append(line)
    return "\n".join(lines)

def domain_matches(
    domain_filter: Optional[str],
    extracted_domain: Optional[str],
    associated_domains: Optional[List[str]],
    sender: str,
    subject: str,
    thread_text: str
) -> bool:
    """Match page domain against rule metadata and email text."""
    if not domain_filter:
        return True

    df = domain_filter.lower().strip()
    df_clean = re.sub(r"^https?://", "", df).split("/")[0].split(":")[0]
    df_clean = re.sub(r"^www\.", "", df_clean)
    brand = get_domain_brand(df_clean)

    # 1. If rule explicitly binds an extracted domain from subject (e.g. Cloudflare Access)
    if extracted_domain:
        ed = extracted_domain.lower().strip()
        return df == ed or df_clean == ed or df in ed or ed in df

    # 2. Associated domains defined in rule
    if associated_domains:
        if (re.match(r"^(bwh\d*|bawagon|bandwagon)(\.[a-z]{2,})?$", df_clean) or brand in ("bawagon", "bandwagon")) and any(ad in ("bandwagonhost.com", "64clouds.com", "bwh81.net", "bawagon") for ad in associated_domains):
            return True
        for ad in associated_domains:
            ad = ad.lower()
            if df_clean == ad or df_clean.endswith("." + ad) or ad.endswith("." + df_clean) or (len(brand) >= 3 and brand in ad):
                return True

    # 3. Direct domain substring match
    if df_clean in subject.lower() or df_clean in sender.lower() or df_clean in thread_text.lower():
        return True

    # 4. Brand match (verifying no conflicting subdomain of the same root domain is mentioned)
    if len(brand) >= 3:
        parts = df_clean.split(".")
        root_domain = ".".join(parts[-2:]) if len(parts) >= 2 else df_clean
        if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "edu", "gov", "ac"} and len(parts[-1]) == 2:
            root_domain = ".".join(parts[-3:])
        
        conflicting_domains = re.findall(r"([a-z0-9\.-]+\." + re.escape(root_domain) + r")", (subject + "\n" + thread_text).lower())
        has_conflict = any(cd != df_clean and not cd.startswith("www.") for cd in conflicting_domains)
        if has_conflict:
            return False

        brand_clean = re.sub(r"[^a-z0-9]", "", brand)
        sender_clean = re.sub(r"[^a-z0-9]", "", sender.lower())
        subject_clean = re.sub(r"[^a-z0-9]", "", subject.lower())
        text_clean = re.sub(r"[^a-z0-9]", "", thread_text.lower())

        if f"@{brand}." in sender.lower() or f"<{brand}@" in sender.lower() or brand in sender.lower() or brand in subject.lower():
            return True

        if brand_clean in sender_clean or brand_clean in subject_clean or brand_clean in text_clean:
            return True

        if (re.match(r"^(bwh\d*|bawagon)$", brand) or brand in ("bawagon", "bandwagon")) and any(alias in sender_clean or alias in subject_clean or alias in text_clean for alias in ("bandwagon", "bawagon", "64clouds", "kiwivm")):
            return True

    return False

def clean_extracted_code(code_str: str) -> str:
    """Normalize extracted code string."""
    cleaned = code_str.strip()
    # Strip markdown bold/italic asterisks or quotes
    cleaned = re.sub(r"^[\*\"'_`#]+|[\*\"'_`#]+$", "", cleaned).strip()
    # Normalize Google G-XXXXXX to XXXXXX
    if re.match(r"^G-\d{6}$", cleaned, re.IGNORECASE):
        cleaned = cleaned[2:]
    # Normalize Facebook FB-XXXXX to XXXXX
    elif re.match(r"^FB-\d{5,6}$", cleaned, re.IGNORECASE):
        cleaned = cleaned[3:]
    # Normalize numeric hyphenated/spaced codes (e.g. 123-456, 123 456, 1234 5678)
    elif re.match(r"^\d{3,4}[-\s]\d{3,4}$", cleaned):
        cleaned = re.sub(r"[-\s]", "", cleaned)
    return cleaned

def extract_universal_otp(
    thread_text: str,
    headers: Dict[str, str],
    email_dt: datetime,
    domain_filter: Optional[str] = None,
    now: Optional[datetime] = None,
    max_age_seconds: int = 600,
) -> Optional[OTPResult]:
    """Universal intelligent fallback OTP matcher based on proximity, keyword analysis, and markdown normalization."""
    subject = headers.get("subject", "")
    sender = headers.get("from", "")
    msg_id = headers.get("id", "0")

    # 1. Check for OTP intent across subject and body
    has_otp_intent = bool(
        OTP_INTENT_PATTERN.search(subject) or
        OTP_INTENT_PATTERN.search(thread_text)
    )
    if not has_otp_intent:
        return None

    # Reject known adversarial patterns (e.g. pure error codes without verification context)
    if re.search(r"(?i)error\s+code\s*:\s*\d+", thread_text) and not re.search(r"(?i)(?:verification|security|login)\s*code", thread_text):
        return None

    # 2. If domain filter is present, ensure domain or brand matches
    if domain_filter:
        df = domain_filter.lower().strip()
        df_clean = re.sub(r"^https?://", "", df).split("/")[0].split(":")[0]
        df_clean = re.sub(r"^www\.", "", df_clean)
        brand = get_domain_brand(df_clean)
        matched = False
        brand_clean = re.sub(r"[^a-z0-9]", "", brand)
        sender_clean = re.sub(r"[^a-z0-9]", "", sender.lower())
        subject_clean = re.sub(r"[^a-z0-9]", "", subject.lower())
        text_clean = re.sub(r"[^a-z0-9]", "", thread_text.lower())

        if df_clean in subject.lower() or df_clean in sender.lower() or df_clean in thread_text.lower():
            matched = True
        elif len(brand) >= 3:
            parts = df_clean.split(".")
            root_domain = ".".join(parts[-2:]) if len(parts) >= 2 else df_clean
            if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "edu", "gov", "ac"} and len(parts[-1]) == 2:
                root_domain = ".".join(parts[-3:])
            conflicting_domains = re.findall(r"([a-z0-9\.-]+\." + re.escape(root_domain) + r")", (subject + "\n" + thread_text).lower())
            has_conflict = any(cd != df_clean and not cd.startswith("www.") for cd in conflicting_domains)
            if not has_conflict:
                brand_clean = re.sub(r"[^a-z0-9]", "", brand)
                sender_clean = re.sub(r"[^a-z0-9]", "", sender.lower())
                subject_clean = re.sub(r"[^a-z0-9]", "", subject.lower())
                text_clean = re.sub(r"[^a-z0-9]", "", thread_text.lower())

                if f"@{brand}." in sender.lower() or f"<{brand}@" in sender.lower() or brand in sender.lower() or brand in subject.lower():
                    matched = True
                elif len(brand_clean) >= 3 and (brand_clean in sender_clean or brand_clean in subject_clean or brand_clean in text_clean):
                    matched = True
                elif (re.match(r"^(bwh\d*|bawagon)$", brand) or brand in ("bawagon", "bandwagon")) and any(alias in sender_clean or alias in subject_clean or alias in text_clean for alias in ("bandwagon", "bawagon", "64clouds", "kiwivm")):
                    matched = True
        if not matched:
            return None

    body_text = get_thread_body(thread_text)
    raw_search_text = subject + "\n" + body_text
    
    # Normalize markdown asterisks around numbers/codes (e.g. "** 521006**" -> " 521006 ")
    normalized_text = re.sub(r"\*{1,3}\s*([0-9a-zA-Z\s-]+?)\s*\*{1,3}", r" \1 ", raw_search_text)

    if now:
        diff = (now - email_dt).total_seconds()
        if diff < -30.0:
            return None
        age_seconds = max(0.0, diff)
    else:
        age_seconds = 0.0

    # Detect explicit expiration TTL in English, Chinese, Japanese (hours, minutes)
    detected_ttl = None
    exp_patterns = [
        (r"(?i)(?:expires\s+(?:in|after)|valid\s+(?:for|in))\s*(\d+)\s*hour", 3600),
        (r"(?i)(?:expires\s+(?:in|after)|valid\s+(?:for|in))\s*(\d+)\s*minute", 60),
        (r"(?i)(?:有效时间|有效期|有效期限)(?:为|：|:)?\s*(\d+)\s*(?:小时|小時|時間)", 3600),
        (r"(?i)(\d+)\s*(?:个)?(?:小时|小時|時間)(?:之?内)?有效", 3600),
        (r"(?i)(?:有效时间|有效期|有效期限)(?:为|：|:)?\s*(\d+)\s*分钟", 60),
        (r"(?i)(\d+)\s*分钟(?:之?内)?有效", 60),
        (r"(?i)有効(?:期限|時間)(?:は|：|:)?\s*(\d+)\s*分", 60),
        (r"(?i)(\d+)\s*分(?:间|間)?有效", 60),
    ]
    for pat, mult in exp_patterns:
        m = re.search(pat, raw_search_text)
        if m:
            for g in m.groups():
                if g:
                    detected_ttl = int(g) * mult
                    break
            if detected_ttl:
                break

    ttl = detected_ttl if detected_ttl is not None else max_age_seconds
    remaining = int(ttl - age_seconds)
    if remaining <= 0 or age_seconds > max(ttl, max_age_seconds):
        return None

    # 3. Proximity-based code patterns evaluated against normalized & raw text
    patterns = [
        # Thai OTP (รหัส OTP 867679)
        r"(?i)(?:รหัส\s*otp|รหัสยืนยัน)\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{4,8})\b",
        # Vietnamese OTP
        r"(?i)(?:mã\s*xác\s*thực|mã\s*xác\s*minh|mã\s*otp|mã\s*xác\s*nhận|mã\s*đăng\s*nhập)\s*(?:của\s*bạn\s*)?(?:là)?\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{4,8})\b",
        # 3D Secure / Banking PIN
        r"(?i)(?:one-time\s*pin[^\n]*is:?|one-time\s*pin\s*is:?|pin\s*is:?)\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{4,8})\b",
        # Brand specific code (e.g. "Your Dia code is 882228", "TidyCal Code: 182105")
        r"(?i)\b(?:your|here’s your|here's your)?\s*[a-z0-9\.-]+\s+code\s+(?:is|为|为：|是|是：|は|:|：)\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{3,4}[-\s][0-9]{3,4}|[0-9]{4,8}|[0-9a-zA-Z]{5,8})\b",
        # Facebook confirmation code (FB-51412)
        r"(?i)\b(FB-[0-9]{5,6})\b",
        # Slack / Alphanumeric hyphenated code (e.g. UZW-XAD)
        r"(?i)\b([A-Za-z0-9]{3}-[A-Za-z0-9]{3})\b",
        # Validation code (SOLIDWORKS, etc.)
        r"(?i)(?:validation\s*code|validating\s*code)\s*[:#：]?\s*(?:\*\*\s*)?([0-9a-zA-Z]{5,8})\b",
        # Explicit Chinese/Japanese OTP pattern (验证码是：335265, 验证码为：335265, 验证码：842075)
        r"(?i)(?:验证码|校验码|动态码|安全码|授权码|認証コード|ワンタイムパスワード)\s*(?:是|为)?[：:]\s*(?:\*\*\s*)?([0-9]{4,8})\b",
        # Subject or line start code (e.g. "434490 is your verification code")
        r"(?i)(?:^|[\r\n])\s*(?:\[[^\]]*\]\s*)?([0-9]{4,8})\s+(?:is\s+your|is\s+the|is)\b",
        # Subject email or device verification code (e.g. "Email verification code: 861326", "device verification code: 181174")
        r"(?i)(?:email\s+|device\s+)?(?:verification|login|security|access|confirmation)\s*code\s*[:#：]\s*([0-9]{4,8})\b",
        # Standard keyword proximity
        r"(?i)(?:"
        r"verification\s*code|verify|security\s*code|login\s*code|access\s*code|"
        r"one-time\s*password|one-time\s*code|passcode|auth\s*code|authentication\s*code|"
        r"confirmation\s*code|secret\s*code|pin\s*code|two-factor|2fa|otp\b|"
        r"验证码|动态码|校验码|安全码|授权码|"
        r"認証コード|確認コード|ワンタイムパスワード"
        r")\s*(?:code|password|passcode)?(?:\s+(?:to\s+[a-z\s]{1,25}|is|为|为：|是|是：|は))?\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{3,4}[-\s][0-9]{3,4}|[0-9]{4,8}|[0-9a-zA-Z]{5,8})\b",
        r"(?i)(?:"
        r"verification\s*code|verify|security\s*code|login\s*code|access\s*code|"
        r"one-time\s*password|one-time\s*code|passcode|auth\s*code|authentication\s*code|"
        r"confirmation\s*code|secret\s*code|pin\s*code|two-factor|2fa|otp\b|"
        r"验证码|动态码|校验码|安全码|授权码|"
        r"認証コード|確認コード|ワンタイムパスワード"
        r")\s*(?:is|为|为：|是|是：|は|:|：)\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{3,4}[-\s][0-9]{3,4}|[0-9]{4,8}|[0-9a-zA-Z]{5,8})\b",
        r"(?i)(?<!error\s)(?<!status\s)(?<!reference\s)(?<!id\s)(?<!message\s)\b(?:code|passcode|otp|动态码|验证码|安全码|校验码|認証コード|ワンタイムパスワード)\s*(?:is|为|为：|是|是：|は)?\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{3,4}[-\s][0-9]{3,4}|[0-9]{4,8}|[0-9a-zA-Z]{5,8})\b",
        r"(?i)\b([0-9]{3,4}[-\s][0-9]{3,4}|[0-9]{4,8})\b\s*(?:is\s+your|is\s+the|为您的|是您的|为|是|がお客様の|です|となります)\s*(?:one-time|one\s*time|verification|security|login|access|confirmation)?\s*(?:code|passcode|验证码|动态码|認証コード|ワンタイムパスワード)?",
        r"(?i)(?:code|passcode|otp)[:\s]+(?:\*\*\s*)?([0-9a-zA-Z]{5,8})\b",
        r"(?m)^\s*(?:\*\*\s*)?([0-9]{3,4}[-\s][0-9]{3,4}|[0-9]{4,8})\s*(?:\*\*)?\s*$",
    ]

    disqualified_words = {
        "expires", "expire", "minutes", "minute", "seconds", "second", "hours", "hour",
        "valid", "before", "account", "please", "ignore", "action", "verify", "online",
        "access", "device", "request", "support", "security", "welcome", "system",
        "update", "details", "contact", "status", "cancel", "manage", "portal"
    }

    for search_corpus in [normalized_text, raw_search_text]:
        for pat in patterns:
            for match in re.finditer(pat, search_corpus):
                code_candidate = match.group(1).strip()
                code_candidate = clean_extracted_code(code_candidate)

                if code_candidate.lower() in disqualified_words:
                    continue

                # Disqualify reference numbers or tracking numbers immediately preceding
                start_pos = max(0, match.start() - 35)
                prefix_text = search_corpus[start_pos:match.start()].lower()
                if re.search(r"(?:reference|ref\s*#?|order\s*#?|tracking|เลขที่อ้างอิง|error\s*code|message\s*id|msg\s*id)", prefix_text):
                    continue

                # Disqualify floating decimals / currency
                if "." in code_candidate or any(c in code_candidate for c in ("$", "¥", "€", "£")):
                    continue

                # Disqualify dates / years unless explicitly labeled
                if code_candidate in {"2024", "2025", "2026", "2027"} and "code" not in match.group(0).lower():
                    continue

                # Disqualify common HTTP status codes if context is ambiguous
                if code_candidate in {"500", "404", "502", "503"} and "verification" not in match.group(0).lower():
                    continue

                if code_candidate == msg_id:
                    continue

                # Check minimum length (at least 4 chars)
                if len(code_candidate) < 4:
                    continue

                # Reject purely alphabetic words
                if code_candidate.isalpha():
                    continue

                # If candidate contains letters, require at least one digit OR valid uppercase hyphenated format (e.g. UZW-XAD)
                has_digit = any(c.isdigit() for c in code_candidate)
                if not has_digit:
                    if "-" in code_candidate:
                        parts = code_candidate.split("-")
                        if not (len(parts) == 2 and all(p.isupper() and len(p) == 3 for p in parts)):
                            continue
                    else:
                        continue

                return OTPResult(
                    code=code_candidate,
                    service="universal_otp",
                    domain=domain_filter,
                    callback_url=None,
                    message_id=msg_id,
                    subject=subject,
                    sender=sender,
                    received_at=email_dt.isoformat(),
                    expires_at=(email_dt + timedelta(seconds=ttl)).isoformat(),
                    is_expired=False,
                    time_remaining_seconds=remaining,
                )

    return None

def extract_otp_from_thread(
    thread_text: str,
    domain_filter: Optional[str] = None,
    rules: List[RuleDefinition] = DEFAULT_RULES,
    now: Optional[datetime] = None,
    max_age_seconds: int = 600,
) -> Optional[OTPResult]:
    """
    Extract OTP from full thread text matching against rules and domain.
    Returns OTPResult if a valid, non-expired OTP is found.
    """
    if now is None:
        now = datetime.now()

    headers = parse_thread_headers(thread_text)
    subject = headers.get("subject", "")
    sender = headers.get("from", "")
    date_str = headers.get("date", "")
    msg_id = headers.get("id", "0")

    if not date_str:
        return None

    email_dt = parse_email_date(date_str)
    if not email_dt:
        return None

    age_seconds = (now - email_dt).total_seconds()
    if age_seconds < -30.0:
        return None
    if age_seconds < 0:
        age_seconds = 0

    rule_max_ttl = max((r.default_ttl_seconds for r in rules), default=600)
    effective_max_age = max(max_age_seconds, rule_max_ttl)
    if age_seconds > effective_max_age:
        return None

    body_text = get_thread_body(thread_text)
    search_text = subject + "\n" + body_text

    # 1. Evaluate predefined rule matrix
    for rule in rules:
        if not re.search(rule.sender_pattern, sender):
            continue

        sub_match = re.search(rule.subject_pattern, subject)
        if not sub_match:
            continue

        extracted_domain = None
        if rule.domain_group and sub_match.lastindex and sub_match.lastindex >= rule.domain_group:
            extracted_domain = sub_match.group(rule.domain_group).strip()

        if not domain_matches(
            domain_filter=domain_filter,
            extracted_domain=extracted_domain,
            associated_domains=rule.associated_domains,
            sender=sender,
            subject=subject,
            thread_text=thread_text
        ):
            continue

        code_match = re.search(rule.code_regex, search_text)
        if not code_match:
            continue
        
        # Get first non-empty group
        raw_code = None
        for g in code_match.groups():
            if g:
                raw_code = g.strip()
                break
        if not raw_code:
            continue

        code = clean_extracted_code(raw_code)
        if code == msg_id:
            continue

        callback_url = None
        if rule.callback_regex:
            cb_match = re.search(rule.callback_regex, thread_text)
            if cb_match:
                callback_url = cb_match.group(1).strip()

        detected_ttl = None
        for pat, mult in [
            (r"(?i)(?:expires\s+(?:in|after)|valid\s+(?:for|in))\s*(\d+)\s*hour", 3600),
            (r"(?i)(?:expires\s+(?:in|after)|valid\s+(?:for|in))\s*(\d+)\s*minute", 60),
            (r"(?i)(?:有效时间|有效期|有效期限)(?:为|：|:)?\s*(\d+)\s*(?:小时|小時|時間)", 3600),
            (r"(?i)(\d+)\s*(?:个)?(?:小时|小時|時間)(?:之?内)?有效", 3600),
            (r"(?i)(?:有效时间|有效期|有效期限)(?:为|：|:)?\s*(\d+)\s*分钟", 60),
            (r"(?i)(\d+)\s*分钟(?:之?内)?有效", 60),
            (r"(?i)有効(?:期限|時間)(?:は|：|:)?\s*(\d+)\s*分", 60),
            (r"(?i)(\d+)\s*分(?:间|間)?有效", 60),
        ]:
            m = re.search(pat, search_text)
            if m:
                for g in m.groups():
                    if g:
                        detected_ttl = int(g) * mult
                        break
                if detected_ttl:
                    break

        ttl = detected_ttl if detected_ttl is not None else rule.default_ttl_seconds
        expires_at_dt = email_dt + timedelta(seconds=ttl)
        remaining = int(ttl - age_seconds)
        if remaining <= 0 or age_seconds > max(ttl, max_age_seconds):
            return None

        return OTPResult(
            code=code,
            service=rule.name,
            domain=extracted_domain or domain_filter,
            callback_url=callback_url,
            message_id=msg_id,
            subject=subject,
            sender=sender,
            received_at=email_dt.isoformat(),
            expires_at=expires_at_dt.isoformat(),
            is_expired=False,
            time_remaining_seconds=remaining,
        )

    # 2. Universal intelligent fallback matcher
    return extract_universal_otp(
        thread_text=thread_text,
        headers=headers,
        email_dt=email_dt,
        domain_filter=domain_filter,
        now=now,
        max_age_seconds=max_age_seconds
    )

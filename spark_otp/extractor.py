"""
Deterministic zero-LLM OTP Extraction Engine.
Supports universal auth providers, brand/domain matching, and open fallback extraction.
"""
import re
import html
import unicodedata
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

SECOND_LEVEL_TLDS = {
    # Commercial & Corporate
    "co", "com", "ltd", "plc", "biz", "firm", "corp",
    # Network, Internet & Infrastructure
    "net", "ne", "ad", "web", "nic",
    # Organization
    "org", "or", "gr", "asn", "ngo",
    # Academic & Education
    "edu", "ac", "ed", "sch", "school", "k12", "hs", "ms", "es",
    # Government & Municipal
    "gov", "go", "gob", "govt", "lg", "muni", "mil", "mod",
    # Personal & Identity
    "me", "id", "idv", "pe", "per", "name",
    # General, Geographic & Misc
    "gen", "info", "ind", "res", "re", "cloud",
}

COMMON_SERVICE_SUBDOMAINS = {
    "www", "help", "support", "contact", "docs", "doc", "faq", "about", "blog",
    "news", "cdn", "static", "assets", "img", "media", "mail", "email",
    "mailer", "mx", "smtp", "api", "status", "legal", "terms", "privacy",
    "link", "click", "track", "go", "app", "auth", "login", "portal", "secure",
    "accounts", "account", "signup", "register", "signin", "member", "members",
    "console", "dash", "dashboard", "sso", "id"
}

KNOWN_EMAIL_TLDS = {
    "com", "org", "net", "edu", "gov", "mil", "int", "io", "ai", "co", "app",
    "dev", "me", "so", "gg", "tv", "cc", "xyz", "info", "biz", "pro", "name",
    "cloud", "site", "tech", "online", "store", "live", "mail", "email",
    "uk", "jp", "cn", "de", "fr", "in", "au", "ca", "us", "eu", "nl", "ch",
    "se", "no", "fi", "es", "it", "br", "mx", "kr", "tw", "hk", "sg", "vn",
    "th", "id", "my", "ph", "nz", "za", "il", "ae", "pl", "cz", "at", "be",
    "dk", "ie", "pt", "ro", "ru", "ua", "tr", "ar", "cl", "pe", "co", "is",
}

VALID_STANDALONE_MULTI_WORD_TLDS = {
    "academy", "account", "accounts", "aero", "agency", "airforce", "apartments",
    "apple", "archi", "army", "art", "asia", "associates", "attorney", "auction",
    "audio", "author", "auto", "autos", "cab", "cafe", "call", "cam", "camp",
    "capital", "cards", "care", "careers", "casa", "cash", "casino", "catering",
    "center", "claims", "cleaning", "click", "clinic", "clothing", "cloud", "club",
    "coach", "codes", "coffee", "college", "cologne", "comcast", "community",
    "company", "compare", "computer", "consulting", "contact", "cooking", "cool",
    "coop", "country", "coupons", "courses", "deals", "degree", "delivery",
    "democrat", "dental", "dentist", "design", "digital", "direct", "domains",
    "education", "email", "engineering", "express", "finance", "foundation",
    "free", "frogans", "frontier", "global", "groups", "health", "holdings",
    "hosting", "inc", "industries", "info", "ink", "institute", "insurance",
    "insure", "international", "investments", "management", "market", "marketing",
    "media", "memorial", "menu", "mobile", "modern", "netflix", "network",
    "office", "online", "organic", "partners", "portal", "properties", "report",
    "review", "school", "search", "security", "select", "server", "services",
    "simple", "single", "social", "software", "solar", "solutions", "soy",
    "status", "store", "stream", "studio", "support", "switch", "systems",
    "target", "technology", "travel", "university", "ventures", "vision",
    "wallet", "website", "window", "worker", "world",
}

GLUE_SPLIT_TLDS = (
    "cloud", "email", "store", "info", "site", "tech", "live", "mail",
    "com", "net", "org", "edu", "gov", "mil", "xyz", "app", "dev", "biz", "pro",
    "io", "ai", "co", "me", "so", "uk", "jp", "cn", "de", "fr", "au", "ca",
    "us", "eu", "tv", "cc", "gg", "in", "kr", "tw", "hk", "sg", "nl",
)

GLUED_EMAIL_SUFFIX_PREFIXES = (
    "verification", "verify", "passcode", "security", "continue", "confirm",
    "account", "support", "resend", "submit", "cancel", "signin", "signup",
    "change", "please", "button", "expire", "enter", "check", "login", "wrong",
    "inbox", "email", "click", "paste", "didn", "code", "mail", "step", "next",
    "back", "help", "edit", "sent", "copy", "open", "view", "your", "this",
    "that", "here", "otp", "not",
)

STRONG_OTP_INTENT_PATTERN = re.compile(
    r"(?i)(?:"
    # English (explicit auth/OTP intent; excludes generic "<word> code" catchall like promo/zip code)
    r"verification\s*code|security\s*code|login\s*code|sign[-\s]?in\s*code|access\s*code|"
    r"device\s*verification|device\s*auth|"
    r"one[-\s]?time\s*(?:password|code|pin|passcode)|single[-\s]?use\s*code|"
    r"temporary\s*(?:code|passcode|pin)|passcode|auth(?:entication)?\s*code|"
    r"confirmation\s*code|secret\s*code|pin\s*code|two[-\s]?factor|\b2fa\b|\bmfa\b|\botp\b|"
    r"validation\s*code|validating\s*code|3d\s*secure|"
    r"verify\s+your\s+(?:email|account|identity|login|device)|"
    r"complete\s+your\s+(?:login|sign[-\s]?in|verification)|"
    r"(?:sign|log)\s+in\s+to\s+your|"
    # Chinese (Simplified & Traditional)
    r"验证码|动态码|校验码|安全码|授权码|登录码|一次性密码|验证代码|身份验证码|"
    r"驗證碼|動態碼|校驗碼|安全碼|授權碼|登錄碼|一次性密碼|驗證代碼|身分驗證碼|"
    # Japanese
    r"認証コード|確認コード|ワンタイムパスワード|セキュリティコード|認証用コード|パスコード|"
    # Korean
    r"인증\s*번호|인증\s*코드|확인\s*코드|보안\s*코드|일회용\s*비밀\s*번호|일회용\s*번호|otp\s*번호|"
    # Spanish & Portuguese
    r"código\s*de\s*verificación|codigo\s*de\s*verificacion|código\s*de\s*verificação|codigo\s*de\s*verificacao|"
    r"código\s*de\s*seguridad|código\s*de\s*segurança|codigo\s*de\s*seguranca|"
    r"código\s*de\s*confirmación|código\s*de\s*confirmação|codigo\s*de\s*confirmacao|"
    r"código\s*de\s*acceso|código\s*de\s*un\s*solo\s*uso|clave\s*de\s*verificación|clave\s*de\s*confirmación|"
    r"código\s*de\s*autenticação|senha\s*descartável|senha\s*de\s*uso\s*único|"
    # French
    r"code\s*de\s*vérification|code\s*de\s*verification|code\s*de\s*sécurité|code\s*de\s*confirmation|"
    r"code\s*d['’]accès|code\s*d['’]authentification|mot\s*de\s*passe\s*à\s*usage\s*unique|code\s*à\s*usage\s*unique|"
    # German
    r"verifizierungscode|bestätigungscode|bestaetigungscode|sicherheitscode|einmalpasswort|einmalkennwort|authentifizierungscode|einmalcode|"
    # Russian
    r"код\s*подтверждения|код\s*верификации|проверочный\s*код|код\s*безопасности|одноразовый\s*пароль|код\s*авторизации|"
    # Italian
    r"codice\s*di\s*verifica|codice\s*di\s*sicurezza|codice\s*di\s*conferma|codice\s*monouso|password\s*monouso|"
    # Vietnamese
    r"mã\s*xác\s*thực|mã\s*xác\s*minh|mã\s*otp|mã\s*xác\s*nhận|mã\s*đăng\s*nhập|mật\s*khẩu\s*một\s*lần|"
    # Thai
    r"รหัส\s*otp|รหัสยืนยัน|เลขรหัส\s*otp|รหัสผ่านแบบใช้ครั้งเดียว|รหัสความปลอดภัย|"
    # Indonesian / Malay
    r"kode\s*verifikasi|kode\s*konfirmasi|kode\s*keamanan|kata\s*sandi\s*sekali\s*pakai|kod\s*pengesahan|kod\s*keselamatan|"
    # Arabic
    r"رمز\s*التحقق|كود\s*التحقق|رمز\s*التأكيد|كلمة\s*مرور\s*لمرة\s*واحدة|رمز\s*الأمان|"
    # Hindi
    r"सत्यापन\s*कोड|प्रमाणीकरण\s*कोड|सुरक्षा\s*कोड|ओटीपी\s*कोड|वन-टाइम\s*पासवर्ड"
    r")"
)

EXPLICIT_OTP_CODE_NOUN_PATTERN = re.compile(
    r"(?i)(?:"
    # Requires an explicit OTP/auth code noun (excludes footer-only "verify your email" / "sign in to your")
    r"verification\s*code|security\s*code|login\s*code|sign[-\s]?in\s*code|access\s*code|"
    r"device\s*verification|device\s*auth|"
    r"one[-\s]?time\s*(?:password|code|pin|passcode)|single[-\s]?use\s*code|"
    r"temporary\s*(?:code|passcode|pin)|passcode|auth(?:entication)?\s*code|"
    r"confirmation\s*code|secret\s*code|pin\s*code|two[-\s]?factor|\b2fa\b|\bmfa\b|\botp\b|"
    r"validation\s*code|validating\s*code|3d\s*secure|"
    r"验证码|动态码|校验码|安全码|授权码|登录码|一次性密码|验证代码|身份验证码|"
    r"驗證碼|動態碼|校驗碼|安全碼|授權碼|登錄碼|一次性密碼|驗證代碼|身分驗證碼|"
    r"認証コード|確認コード|ワンタイムパスワード|セキュリティコード|認証用コード|パスコード|"
    r"인증\s*번호|인증\s*코드|확인\s*코드|보안\s*코드|일회용\s*비밀\s*번호|일회용\s*번호|otp\s*번호|"
    r"código\s*de\s*verificación|codigo\s*de\s*verificacion|código\s*de\s*verificação|codigo\s*de\s*verificacao|"
    r"código\s*de\s*seguridad|código\s*de\s*segurança|código\s*de\s*confirmación|código\s*de\s*confirmación|"
    r"code\s*de\s*vérification|code\s*de\s*verification|code\s*de\s*sécurité|code\s*de\s*confirmation|"
    r"verifizierungscode|bestätigungscode|bestaetigungscode|sicherheitscode|einmalpasswort|einmalcode|"
    r"код\s*подтверждения|код\s*верификации|проверочный\s*код|код\s*безопасности|"
    r"codice\s*di\s*verifica|codice\s*di\s*sicurezza|codice\s*di\s*conferma|"
    r"mã\s*xác\s*thực|mã\s*xác\s*minh|mã\s*otp|mã\s*xác\s*nhận|mã\s*đăng\s*nhập|"
    r"รหัส\s*otp|รหัสยืนยัน|kode\s*verifikasi|kode\s*konfirmasi|رمز\s*التحقق|सत्यापन\s*कोड"
    r")"
)

NON_AUTH_CODE_PREFIX_RE = re.compile(
    r"(?i)\b(?:promo|coupon|discount|voucher|referral|gift|redeem|invite|"
    r"postal|zip|area|country|currency|airport|tracking|order|invoice|"
    r"error|status|http|exit|color|hex|source|dress|bar|qr|swift|iban|bic|"
    r"sort|routing|product|item|sku|part|model|serial|batch|lot|reference|"
    r"ref|claim|booking|flight|hotel|reservation|use|apply)\s*(?:code|number|id|#)?\s*[:#：]?\s*$"
)

PURE_ALPHA_OTP_DISQUALIFIED_WORDS = {
    # Auth / OTP / Email / UI / CTA terms (6-8 letters)
    "verify", "verified", "getcode", "clickme", "signin", "signup", "signout", "logout",
    "submit", "button", "expire", "expires",
    # Months, weekdays, seasons, and common marketing/promo words (6-8 letters)
    "january", "february", "august", "october", "november", "december",
    "monday", "tuesday", "thursday", "friday", "saturday", "sunday",
    "summer", "winter", "spring", "autumn",
    "holiday", "weekend", "savings", "bargain", "freeship", "shipping",
    "checkout", "shopping", "festival", "birthday", "newyear", "starter",
    "premium", "forever", "loyalty", "vipclub", "blackfri", "cybermon",
    "expired", "please", "account", "accounts", "privacy", "confirm", "access",
    "secure", "security", "passcode", "password", "request", "support", "welcome",
    "system", "systems", "update", "updated", "details", "contact", "status",
    "cancel", "manage", "portal", "ignore", "action", "actions", "online", "device",
    "devices", "before", "minute", "minutes", "second", "seconds", "hourly",
    "follow", "prompt", "select", "return", "reload", "resend", "refresh", "change",
    "changes", "changed", "create", "created", "delete", "deleted", "remove",
    "removed", "enable", "enabled", "disable", "active", "inactive", "locked",
    "unlock", "denied", "failed", "passed", "client", "clients", "server", "servers",
    "domain", "domains", "sender", "senders", "header", "headers", "footer", "footers",
    "message", "subject", "emails", "mailer", "cookie", "cookies", "tokens", "rights",
    "policy", "safety", "report", "reports", "optout", "member", "members", "people",
    "person", "friend", "groups", "events", "agenda", "remind", "timers", "recent",
    "latest", "newest", "oldest", "custom", "global", "public", "private", "manual",
    "direct", "simple", "single", "double", "triple", "notice", "notices", "thanks",
    "regard", "regards", "sincere", "assist", "option", "options", "prefer", "prefers",
    "digest", "weekly", "monthly", "annual", "upgrade", "pricing", "offers", "coupon",
    "coupons", "reward", "rewards", "points", "deposit", "summary", "metrics",
    "history", "archive", "folders", "drafts", "outbox", "attach", "browser",
    "desktop", "android", "windows", "network", "connect", "service", "company",
    "product", "project", "channel", "invited", "invite", "started", "finish",
    "proceed", "session", "invalid", "missing", "unknown", "default", "example",
    "testing", "pending", "waiting", "loading", "protect", "trusted", "reserve",
    "reserved", "caution", "warning", "failure", "success", "complete", "continue",
    "receive", "received", "entered", "already", "another", "because", "between",
    "without", "through", "against", "however", "nothing", "someone", "anyone",
    "everyone", "believe", "replied", "forward", "content", "section", "article",
    "general", "special", "primary", "current", "present", "express", "process",
    "version", "release", "preview", "limited", "instant", "quickly", "safely",
    "exactly", "finally", "shortly", "usually", "whether", "neither", "further",
    "control", "problem", "working", "running", "stopped", "sending", "getting",
    "setting", "settings", "logging", "signing", "opening", "closing", "reading",
    "writing", "copying", "pasting", "sharing", "viewing", "editing", "saving",
    "posting", "finding", "keeping", "holding", "showing", "telling", "helping",
    "asking", "calling", "passing", "failing", "checking", "trying", "coming",
    "making", "taking", "giving", "having", "moving", "paying", "buying", "adding",
    "ending", "office", "number", "numbers", "letter", "letters", "digits", "symbol",
    "format", "length", "height", "weight", "widths", "colors", "colours", "styles",
    "hidden", "accept", "reject", "approve", "decline", "refuse", "dismiss",
    "skipped", "resume", "repeat", "reboot", "repair", "revert", "commit", "deploy",
    "launch", "publish", "revoke", "rotate", "extend", "refund", "refunds", "charge",
    "charged", "payout", "payouts", "payday", "salary", "budget", "profit", "revenue",
    "discount", "voucher", "promos", "ticket", "tickets", "booking", "flight",
    "flights", "hotels", "travel", "depart", "arrive", "driver", "pickup", "dropoff",
    "delivery", "courier", "parcel", "shipper", "shipped", "customs", "duties",
    "prices", "quotes", "totals", "amount", "balance", "credit", "credits", "debits",
    "checks", "branch", "banking", "saving", "invest", "equity", "shares", "trading",
    "broker", "wallet", "mining", "staking", "levels", "silver", "golden", "bronze",
    "vendor", "partner", "agency", "studio", "school", "course", "lesson", "module",
    "degree", "campus", "health", "doctor", "clinic", "patient", "recipe", "dinner",
    "coffee", "market", "stores", "retail", "outlet", "brands", "models", "series",
    "design", "review", "rating", "comments", "thread", "topics", "forums", "boards",
    "guests", "speaker", "record", "replay", "stream", "camera", "volume", "bright",
    "screen", "mirror", "remote", "laptop", "tablet", "mobile", "iphone", "macbook",
    "router", "signal", "cables", "battery", "energy", "memory", "backup", "clouds",
    "cluster", "region", "builds", "orders", "billing", "invoice", "receipt",
    "payment", "address", "profile", "tracked", "deliver", "package", "copied",
    "pasted", "shared", "linked", "unlink", "issued", "signed", "frozen", "paused",
    "closed", "opened", "needed", "wanted", "called", "posted", "search", "filter",
    "sorted", "rename", "upload", "download", "export", "import", "restore",
    # HTML / CSS / Programming / Placeholders
    "border", "center", "margin", "margins", "padding", "strong", "normal", "italic",
    "family", "bottom", "inline", "script", "scripts", "styling", "values", "string",
    "object", "arrays", "tables", "column", "layout", "themes", "shadow", "radius",
    "stroke", "vector", "canvas", "window", "dialog", "modals", "banner", "toasts",
    "badges", "labels", "inputs", "fields", "toggle", "slider", "switch", "picker",
    "scroll", "cursor", "opaque", "darker", "dashed", "dotted", "smooth", "linear",
    "radial", "spring", "bounce", "easing", "motion", "frames", "pixels", "inches",
    "meters", "dollar", "crypto", "ledger", "assets", "stocks", "trades", "charts",
    "graphs", "trends", "alerts", "notify", "routes", "anchor", "target", "source",
    "origin", "agents", "robots", "spider", "crawls", "cached", "tunnel", "bridge",
    "socket", "packet", "buffer", "thread", "worker", "daemon", "kernel", "plugin",
    "addons", "static", "images", "videos", "photos", "doctype", "charset", "public",
    "return", "export", "import", "sizeof", "typeof", "struct", "switch", "repeat",
    "ffffff", "cccccc", "eeeeee", "dddddd", "bbbbbb", "aaaaaa", "xxxxxx", "zzzzzz",
    "abcdef", "abcdefg", "abcdefgh", "fedcba", "qwerty", "asdfgh", "zxcvbn",
    "sample", "tester", "deadbeef", "cafebabe", "verdana", "tahoma", "roboto",
    "inherit", "display", "charset", "content", "bgcolor", "valign", "nowrap",
    # Common major brand / provider names (6-8 letters)
    "google", "github", "stripe", "vercel", "notion", "openai", "claude", "gemini",
    "amazon", "paypal", "discord", "shopify", "twitter", "icloud", "proton",
    "outlook", "hotmail", "foxmail", "twilio", "stytch", "resend", "postmark",
    "mailgun", "sendgrid", "workos", "linear", "framer", "webflow", "zapier",
    "hubspot", "zendesk", "datadog", "sentry", "grafana", "fastly", "akamai",
    "firebase", "supabase", "netlify", "heroku", "docker", "gitlab", "render",
    "railway", "paddle", "square", "klarna", "revolut", "mercury", "chrome",
    "safari", "firefox", "dropbox", "spotify", "netflix", "airbnb", "booking",
    "expedia", "alibaba", "tencent", "baidu", "oracle", "vmware", "redhat",
    "ubuntu", "debian", "python", "nodejs", "docker", "readdle", "spark",
}

PURE_ALPHA_OTP_PATTERNS = [
    # 1a. Explicit OTP label + assignment ("Your login code is: SFXNRE", "Verification Code:\nFWUOYO")
    re.compile(
        r"(?i)(?:your\s+(?:[a-z0-9\.-]+\s+)?(?:verification|login|sign[-\s]?in|security|confirmation|authentication|access|auth|one[-\s]?time|single[-\s]?use|temporary|2fa|mfa|email|device)\s+(?:code|passcode|pin)|"
        r"(?:verification|login|sign[-\s]?in|security|confirmation|authentication|access|auth|one[-\s]?time|single[-\s]?use|temporary|validation|validating|2fa|mfa|email|device)\s+(?:code|passcode|pin))"
        r"\s*(?:is\s*[:#：]?|[:#：])\s*(?:[\r\n]\s*)?(?:[\*`\"']+\s*)?(?-i:([A-Z]{6,8}))(?![A-Za-z0-9])"
    ),
    # 1b. Multiline OTP prompt followed by uppercase code ("Your verification code\n\nKXMPTQ", "Use the code below to sign in:\nBVGKLM")
    re.compile(
        r"(?i)(?:your\s+(?:[a-z0-9\.-]+\s+)?(?:verification|login|sign[-\s]?in|security|confirmation|authentication|access|auth|one[-\s]?time|single[-\s]?use|temporary|2fa|mfa)\s+(?:code|passcode|pin)|"
        r"use\s+the\s+(?:verification\s+|login\s+|security\s+)?code\s+below(?:\s+to\s+[^\r\n:.]{1,40})?|"
        r"enter\s+(?:the\s+|this\s+)?(?:following\s+)?(?:verification\s+|login\s+|security\s+)?code(?:\s+below)?(?:\s+when\s+prompted|\s+to\s+[^\r\n:.]{1,40})?)"
        r"\s*[:#：]?[\r\n]+\s*(?:[\*`\"']+\s*)?(?-i:([A-Z]{6,8}))(?![A-Za-z0-9])"
    ),
    # 1c. Generic explicit code/passcode/otp assignment (strictly guarded against non-auth/promo prefixes
    # and gated by EXPLICIT_OTP_CODE_NOUN_PATTERN in extract_pure_alpha_otp_code)
    re.compile(
        r"(?i)(?<!error\s)(?<!status\s)(?<!reference\s)(?<!promo\s)(?<!coupon\s)(?<!discount\s)"
        r"(?<!postal\s)(?<!zip\s)(?<!area\s)(?<!country\s)(?<!tracking\s)(?<!gift\s)"
        r"(?<!referral\s)(?<!voucher\s)(?<!invite\s)(?<!color\s)(?<!hex\s)(?<!source\s)"
        r"(?<!product\s)(?<!booking\s)(?<!flight\s)(?<!hotel\s)(?<!order\s)"
        r"(?<!use\s)(?<!apply\s)(?<!redeem\s)"
        r"\b(?:(?:your\s+(?:[a-z0-9\.-]+\s+)?)?code|passcode|otp)"
        r"\s*(?:is\s*[:#：]?|[:#：])\s*(?:[\r\n]\s*)?(?:[\*`\"']+\s*)?(?-i:([A-Z]{6,8}))(?![A-Za-z0-9])"
    ),
    # 1d. Multilingual explicit OTP label + assignment
    re.compile(
        r"(?i)(?:验证码|动态码|校验码|安全码|授权码|驗證碼|動態碼|校驗碼|"
        r"認証コード|確認コード|ワンタイムパスワード|인증\s*번호|인증\s*코드|확인\s*코드|"
        r"código\s*de\s*verificación|codigo\s*de\s*verificacion|código\s*de\s*verificação|"
        r"code\s*de\s*vérification|code\s*de\s*verification|verifizierungscode|bestätigungscode|"
        r"код\s*подтверждения|codice\s*di\s*verifica|mã\s*xác\s*thực|รหัส\s*otp|kode\s*verifikasi|"
        r"رمز\s*التحقق|सत्यापन\s*कोड)"
        r"\s*(?:是|为|は|는|은|es|é|est|ist|lautet|это|è|adalah|là|هو|है)?\s*[:#：]?\s*(?:[\r\n]\s*)?(?:[\*`\"']+\s*)?(?-i:([A-Z]{6,8}))(?![A-Za-z0-9])"
    ),
    # 2. Leading-code format ("SFXNRE is your verification code")
    re.compile(
        r"(?-i:\b([A-Z]{6,8})\b)\s+(?i:is\s+(?:your|the)\s+(?:[a-z0-9\.-]+\s+){0,2}"
        r"(?:one[-\s]?time|single[-\s]?use|temporary|verification|security|login|sign[-\s]?in|access|confirmation|authentication|auth)?\s*"
        r"(?:code|passcode|otp|pin)\b)"
    ),
]

PURE_ALPHA_PREV_LINE_CUE_RE = re.compile(
    r"(?i)(?:verification|login|sign[-\s]?in|security|confirmation|authentication|access|one[-\s]?time|single[-\s]?use|temporary|2fa|mfa)\s*(?:code|passcode|pin)|"
    r"\b(?:code|passcode|otp)\s*(?:is|below|follows)?\s*[:#：]?\s*$|"
    r"use\s+the\s+code\s+below|enter\s+(?:the\s+|this\s+)?(?:following\s+)?code|"
    r"验证码|动态码|校验码|認証コード|確認コード|인증\s*번호|인증\s*코드|código\s*de\s*verificación|code\s*de\s*vérification|verifizierungscode"
)

PURE_ALPHA_NEXT_LINE_CUE_RE = re.compile(
    r"(?i)(?:this\s+code\s+(?:will\s+)?expire|code\s+(?:will\s+)?expire|expires?\s+(?:in|after)|valid\s+(?:for|in)|"
    r"enter\s+this\s+code|use\s+this\s+code|do\s+not\s+share\s+this\s+code|"
    r"if\s+you\s+did\s*n['’]?t\s+request|if\s+you\s+did\s+not\s+request|"
    r"有效|有効|분\s*이내|minuto|minuten|минут|phút|นาที|menit)"
)

OTP_INTENT_PATTERN = re.compile(
    r"(?i)(?:"
    # English
    r"verification\s*code|verify|security\s*code|login\s*code|access\s*code|"
    r"device\s*verification|device\s*auth|"
    r"one-time\s*password|one-time\s*code|one-time\s*pin|passcode|auth\s*code|authentication\s*code|"
    r"confirmation\s*code|secret\s*code|pin\s*code|two-factor|2fa|mfa|otp\b|"
    r"validation\s*code|validating\s*code|sign-in\s*code|single-use\s*code|"
    r"[a-z0-9\.-]+\s+code\b|"
    r"3d\s*secure|one-time\s*passcode|"
    # Chinese (Simplified & Traditional)
    r"验证码|动态码|校验码|安全码|授权码|登录码|一次性密码|验证代码|身份验证码|"
    r"驗證碼|動態碼|校驗碼|安全碼|授權碼|登錄碼|一次性密碼|驗證代碼|身分驗證碼|"
    # Japanese
    r"認証コード|確認コード|ワンタイムパスワード|セキュリティコード|認証用コード|パスコード|"
    # Korean
    r"인증\s*번호|인증\s*코드|확인\s*코드|보안\s*코드|일회용\s*비밀\s*번호|일회용\s*번호|otp\s*번호|"
    # Spanish & Portuguese
    r"código\s*de\s*verificación|codigo\s*de\s*verificacion|código\s*de\s*verificação|codigo\s*de\s*verificacao|"
    r"código\s*de\s*seguridad|código\s*de\s*segurança|codigo\s*de\s*seguranca|"
    r"código\s*de\s*confirmación|código\s*de\s*confirmação|codigo\s*de\s*confirmacao|"
    r"código\s*de\s*acceso|código\s*de\s*un\s*solo\s*uso|clave\s*de\s*verificación|clave\s*de\s*confirmación|"
    r"código\s*de\s*autenticação|senha\s*descartável|senha\s*de\s*uso\s*único|"
    # French
    r"code\s*de\s*vérification|code\s*de\s*verification|code\s*de\s*sécurité|code\s*de\s*confirmation|"
    r"code\s*d['’]accès|code\s*d['’]authentification|mot\s*de\s*passe\s*à\s*usage\s*unique|code\s*à\s*usage\s*unique|"
    # German
    r"verifizierungscode|bestätigungscode|bestaetigungscode|sicherheitscode|einmalpasswort|einmalkennwort|authentifizierungscode|einmalcode|"
    # Russian
    r"код\s*подтверждения|код\s*верификации|проверочный\s*код|код\s*безопасности|одноразовый\s*пароль|код\s*авторизации|"
    # Italian
    r"codice\s*di\s*verifica|codice\s*di\s*sicurezza|codice\s*di\s*conferma|codice\s*monouso|password\s*monouso|"
    # Vietnamese
    r"mã\s*xác\s*thực|mã\s*xác\s*minh|mã\s*otp|mã\s*xác\s*nhận|mã\s*đăng\s*nhập|mật\s*khẩu\s*một\s*lần|"
    # Thai
    r"รหัส\s*otp|รหัสยืนยัน|เลขรหัส\s*otp|รหัสผ่านแบบใช้ครั้งเดียว|รหัสความปลอดภัย|"
    # Indonesian / Malay
    r"kode\s*verifikasi|kode\s*konfirmasi|kode\s*keamanan|kata\s*sandi\s*sekali\s*pakai|kod\s*pengesahan|kod\s*keselamatan|"
    # Arabic
    r"رمز\s*التحقق|كود\s*التحقق|رمز\s*التأكيد|كلمة\s*مرور\s*لمرة\s*واحدة|رمز\s*الأمان|"
    # Hindi
    r"सत्यापन\s*कोड|प्रमाणीकरण\s*कोड|सुरक्षा\s*कोड|ओटीपी\s*कोड|वन-टाइम\s*पासवर्ड"
    r")"
)

EXP_PATTERNS = [
    # English
    (r"(?i)(?:expires?\s+(?:in|after)|valid\s+(?:for|in)|within)\s*(\d+)\s*hour", 3600),
    (r"(?i)(?:expires?\s+(?:in|after)|valid\s+(?:for|in)|within)\s*(\d+)\s*minute", 60),
    # Chinese (Simplified & Traditional)
    (r"(?i)(?:有效时间|有效期|有效期限)(?:为|：|:)?\s*(\d+)\s*(?:小时|小時|時間)", 3600),
    (r"(?i)(\d+)\s*(?:个)?(?:小时|小時|時間)(?:之?内)?有效", 3600),
    (r"(?i)(?:有效时间|有效期|有效期限)(?:为|：|:)?\s*(\d+)\s*分钟", 60),
    (r"(?i)(\d+)\s*分钟(?:之?内)?有效", 60),
    # Japanese
    (r"(?i)有効(?:期限|時間)(?:は[、\s]*[^\d\n]{0,35}|：|:)?\s*(\d+)\s*分", 60),
    (r"(?i)有効(?:期限|時間)(?:は[、\s]*[^\d\n]{0,35}|：|:)?\s*(\d+)\s*(?:時間|時間間)", 3600),
    (r"(?i)(\d+)\s*分(?:以内|間以内|间以内|間|间)?(?:有效|以内)", 60),
    (r"(?i)(\d+)\s*(?:時間|時間間|小时|小時)(?:以内|間以内|间以内)?(?:有效|以内)", 3600),
    # Korean
    (r"(?i)(\d+)\s*분(?:간)?\s*(?:동안)?\s*유효", 60),
    (r"(?i)(\d+)\s*분\s*이내", 60),
    (r"(?i)유효\s*시간(?:은|:)?\s*(\d+)\s*분", 60),
    (r"(?i)(\d+)\s*시간(?:동안)?\s*유효", 3600),
    # Spanish & Portuguese
    (r"(?i)(?:válido|valido)\s*(?:por|durante)\s*(\d+)\s*hora", 3600),
    (r"(?i)(?:válido|valido)\s*(?:por|durante)\s*(\d+)\s*minuto", 60),
    (r"(?i)(?:expira|caduca)\s*en\s*(\d+)\s*minuto", 60),
    (r"(?i)(?:expira|caduca)\s*en\s*(\d+)\s*hora", 3600),
    # French
    (r"(?i)(?:valable|valide)\s*(?:pendant|durant)\s*(\d+)\s*heure", 3600),
    (r"(?i)(?:valable|valide)\s*(?:pendant|durant)\s*(\d+)\s*minute", 60),
    (r"(?i)expire\s*dans\s*(\d+)\s*minute", 60),
    (r"(?i)expire\s*dans\s*(\d+)\s*heure", 3600),
    # German
    (r"(?i)(?:gültig|gueltig)\s*(?:für|fuer)\s*(\d+)\s*stunde", 3600),
    (r"(?i)(?:gültig|gueltig)\s*(?:für|fuer)\s*(\d+)\s*minute", 60),
    (r"(?i)läuft\s*in\s*(\d+)\s*minute", 60),
    # Russian
    (r"(?i)действителен\s*(?:в\s*течение)?\s*(\d+)\s*час", 3600),
    (r"(?i)действителен\s*(?:в\s*течение)?\s*(\d+)\s*минут", 60),
    (r"(?i)истекает\s*через\s*(\d+)\s*минут", 60),
    # Italian
    (r"(?i)valido\s*per\s*(\d+)\s*or", 3600),
    (r"(?i)valido\s*per\s*(\d+)\s*minut", 60),
    (r"(?i)scade\s*(?:tra|in)\s*(\d+)\s*minut", 60),
    # Vietnamese
    (r"(?i)(?:hiệu\s*lực|hết\s*hạn)\s*(?:trong|sau)\s*(\d+)\s*giờ", 3600),
    (r"(?i)(?:hiệu\s*lực|hết\s*hạn)\s*(?:trong|sau)\s*(\d+)\s*phút", 60),
    (r"(?i)có\s*hiệu\s*lực\s*(\d+)\s*phút", 60),
    # Thai
    (r"(?i)(?:มีอายุ|หมดอายุภายใน|ภายใน)\s*(\d+)\s*ชั่วโมง", 3600),
    (r"(?i)(?:มีอายุ|หมดอายุภายใน|ภายใน)\s*(\d+)\s*นาที", 60),
    # Indonesian / Malay
    (r"(?i)(?:berlaku|sah)\s*(?:selama)?\s*(\d+)\s*jam", 3600),
    (r"(?i)(?:berlaku|sah)\s*(?:selama)?\s*(\d+)\s*menit", 60),
    (r"(?i)kedaluwarsa\s*dalam\s*(\d+)\s*menit", 60),
    # Arabic
    (r"(?i)(?:صالح\s*لمدة|ينتهي\s*خلال)\s*(\d+)\s*ساعة", 3600),
    (r"(?i)(?:صالح\s*لمدة|ينتهي\s*خلال)\s*(\d+)\s*دقيقة", 60),
    # Hindi
    (r"(?i)(\d+)\s*घंटे\s*के\s*लिए\s*मान्य", 3600),
    (r"(?i)(\d+)\s*मिनट\s*के\s*लिए\s*मान्य", 60),
]

def detect_ttl(text: str) -> Optional[int]:
    """Detect explicit expiration TTL in English, Chinese, Japanese (seconds)."""
    norm_text = unicodedata.normalize("NFKC", text)
    for pat, mult in EXP_PATTERNS:
        m = re.search(pat, norm_text)
        if m:
            for g in m.groups():
                if g:
                    return int(g) * mult
    return None

def clean_domain(domain: str) -> str:
    """Strip protocol, port, path, and leading www."""
    d = domain.lower().strip()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0].split(":")[0]
    return re.sub(r"^www\.", "", d)

def sanitize_account_email(account: Optional[str]) -> Optional[str]:
    """
    Defensively normalize an account/email query string and strip glued DOM suffixes
    such as 'user@example.com' + 'Verification', 'user@example.com' + 'VERIFICATION',
    'user@example.com' + '.Enter', angle brackets, 'mailto:', or trailing CJK/punctuation.
    Preserves legitimate multi-word TLDs (e.g. '.company', '.network', '.codes').
    """
    if account is None:
        return None
    raw = str(account)
    # Remove invisible zero-width chars and normalize NBSP
    raw = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", raw).replace("\u00a0", " ").strip()
    if not raw:
        return None

    # Strip leading mailto:
    raw = re.sub(r"(?i)^mailto:", "", raw).strip()

    # Extract email inside angle brackets if present (e.g. "Alex <user@example.com>")
    angle_match = re.search(r"<([^\s<>@]+@[^\s<>@]+)>", raw)
    if angle_match:
        raw = angle_match.group(1).strip()

    if "@" not in raw:
        return raw

    # Extract the first email-like token if surrounded by prose/whitespace
    email_tok_match = re.search(r"[^\s<>\"',;()]+@[^\s<>\"',;()]+", raw)
    if email_tok_match:
        raw = email_tok_match.group(0)

    local, domain_raw = raw.rsplit("@", 1)
    local = local.strip(" \"'<>()[]{}:;,")
    # Truncate domain at first non-ASCII character (e.g. glued CJK label)
    domain_raw = re.split(r"[^\x20-\x7e]", domain_raw, maxsplit=1)[0]
    domain_raw = domain_raw.strip(" .\"'<>()[]{}:;,!?|\\/~")
    if not local or not domain_raw:
        return None

    labels = [lbl for lbl in domain_raw.split(".") if lbl]
    if len(labels) < 2:
        return f"{local.lower()}@{domain_raw.lower()}"

    # Strip dot-glued trailing UI suffixes after a valid TLD (e.g. '.com' + '.Enter' or '.com' + '.Verification')
    def _is_dot_glued_ui_label(lbl_raw: str) -> bool:
        lbl_alpha = re.sub(r"[^A-Za-z]+.*$", "", lbl_raw)
        lbl_low = lbl_alpha.lower()
        if not lbl_low:
            return True
        # Never strip valid 2-letter ccTLDs (e.g. .co.uk, .com.au, .com.cn)
        if len(lbl_low) == 2 and lbl_low in KNOWN_EMAIL_TLDS:
            return False
        if any(lbl_low.startswith(w) for w in GLUED_EMAIL_SUFFIX_PREFIXES):
            return True
        return False

    if len(labels) >= 3:
        for idx in range(len(labels) - 2, 0, -1):
            anchor = labels[idx].lower()
            if anchor in KNOWN_EMAIL_TLDS:
                trailing = labels[idx + 1:]
                if trailing and all(_is_dot_glued_ui_label(t) for t in trailing):
                    labels = labels[: idx + 1]
                    break

    tld_raw = labels[-1]
    if not tld_raw.lower().startswith("xn--"):
        # Strip any trailing digits or symbols glued onto the TLD (e.g. '.com' + '123')
        tld_raw = re.sub(r"[^A-Za-z]+.*$", "", tld_raw)
        if not tld_raw:
            return f"{local.lower()}@{domain_raw.lower()}"

        # 1. Mixed-case boundary inside TLD (e.g. 'com' + 'Verification', 'com' + 'VERIFICATION', 'uk' + 'Enter')
        case_split = re.match(r"^([a-z]{2,10})([A-Z][A-Za-z]*)$", tld_raw)
        if case_split and (case_split.group(1) in KNOWN_EMAIL_TLDS or len(case_split.group(1)) == 2):
            tld_clean = case_split.group(1)
        else:
            tld_lower = tld_raw.lower()
            tld_clean = tld_lower
            # 2. All-lowercase / all-uppercase glued UI suffix (only if not a valid standalone TLD)
            if tld_lower not in VALID_STANDALONE_MULTI_WORD_TLDS:
                for prefix in GLUE_SPLIT_TLDS:
                    if tld_lower.startswith(prefix) and len(tld_lower) > len(prefix):
                        remainder = tld_lower[len(prefix):]
                        if any(remainder.startswith(w) for w in GLUED_EMAIL_SUFFIX_PREFIXES):
                            tld_clean = prefix
                            break
    else:
        tld_clean = tld_raw.lower()

    clean_domain_str = ".".join([lbl.lower() for lbl in labels[:-1]] + [tld_clean.lower()])
    return f"{local.lower()}@{clean_domain_str}"

def recipient_matches_account(recipient: Optional[str], account: Optional[str]) -> bool:
    """Boundary-aware check that an email recipient header matches the sanitized requested account."""
    acc_clean = sanitize_account_email(account)
    if not acc_clean or not recipient:
        return False
    acc_lower = acc_clean.strip().lower()
    rec_lower = recipient.strip().lower()
    if not rec_lower:
        return False
    if "@" in acc_lower:
        return bool(re.search(r"(?<![a-z0-9._%+-])" + re.escape(acc_lower) + r"(?![a-z0-9._%+-])", rec_lower))
    return acc_lower in rec_lower

def _strip_html_body(body_text: str) -> str:
    """Convert raw HTML email body (e.g. cache.sqlite fallback) into clean plain text without CSS/JS noise."""
    if not body_text or not re.search(
        r"<(?:!doctype|html|head|body|style|script|table|tr|td|th|div|p|br|span)\b",
        body_text,
        re.IGNORECASE,
    ):
        return body_text
    cleaned = re.sub(r"(?is)<style\b[^>]*>.*?</style>", " ", body_text)
    cleaned = re.sub(r"(?is)<script\b[^>]*>.*?</script>", " ", cleaned)
    cleaned = re.sub(r"(?s)<!--.*?-->", " ", cleaned)
    cleaned = re.sub(
        r"(?i)</?(?:tr|td|th|div|p|br|li|h[1-6]|table|tbody|thead|section|article|header|footer|hr)\b[^>]*>",
        "\n",
        cleaned,
    )
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in cleaned.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()

def _is_valid_pure_alpha_otp(
    candidate: str,
    search_corpus: str,
    match_start: int,
    match_end: int,
    full_match_start: int,
    sender: str = "",
    domain_filter: Optional[str] = None,
    brand_hint: Optional[str] = None,
) -> bool:
    """
    Strict anti-false-positive validator for pure uppercase alphabetic OTP codes (6-8 ASCII letters).
    Rejects normal English/UI/HTML/CSS words, brand/domain tokens, URLs, mixed-case echoes,
    repeated-character placeholders, and shouty ALL-CAPS headings/buttons.
    """
    if not candidate or not (6 <= len(candidate) <= 8):
        return False
    if not (candidate.isascii() and candidate.isalpha() and candidate.isupper()):
        return False
    # Reject repeated-char placeholders (AAAAAA, XXXXXX, ABABAB, FFFFFF)
    if len(set(candidate)) < 3:
        return False

    cand_lower = candidate.lower()
    if cand_lower in PURE_ALPHA_OTP_DISQUALIFIED_WORDS:
        return False

    # Reject non-auth code prefixes immediately preceding the match (promo/coupon/tracking/zip/etc.)
    prefix_window = search_corpus[max(0, full_match_start - 40):match_start]
    if NON_AUTH_CODE_PREFIX_RE.search(prefix_window):
        return False

    # Reject brand / sender / domain / page-hint tokens dynamically
    brand_tokens = set()
    for src in (sender or "", domain_filter or "", brand_hint or ""):
        for tok in re.findall(r"[a-zA-Z]{4,}", src.lower()):
            brand_tokens.add(tok)
    if domain_filter:
        for tok in get_domain_tokens(domain_filter):
            brand_tokens.add(tok.lower())
    if brand_hint:
        for tok in extract_brand_hint_tokens(brand_hint):
            brand_tokens.add(tok.lower())
    if cand_lower in brand_tokens:
        return False
    sender_alpha = re.sub(r"[^a-z]", "", (sender or "").lower())
    domain_alpha = re.sub(r"[^a-z]", "", clean_domain(domain_filter or ""))
    if cand_lower in sender_alpha or (domain_alpha and cand_lower in domain_alpha):
        return False

    # Reject tokens that also appear in lowercase or Title Case anywhere in the email (real words / brands)
    for m in re.finditer(r"(?i)\b" + re.escape(candidate) + r"\b", search_corpus):
        if m.group(0) != candidate:
            return False

    # Reject tokens embedded inside URLs, query params, HTML attributes, hex colors, or filenames
    tok_start = match_start
    while tok_start > 0 and not search_corpus[tok_start - 1].isspace():
        tok_start -= 1
    tok_end = match_end
    while tok_end < len(search_corpus) and not search_corpus[tok_end].isspace():
        tok_end += 1
    enclosing_raw = search_corpus[tok_start:tok_end]
    if any(sym in enclosing_raw for sym in ("://", "/", "?", "=", "@", "#", "&", "%", "<", ">", "_")):
        return False
    prefix_in_tok = search_corpus[tok_start:match_start]
    suffix_in_tok = search_corpus[match_end:tok_end]
    if not re.match(r"^[\*`\"')\]}.,;!?。，、】」』》]*$", suffix_in_tok):
        return False
    if not (
        re.match(r"^[\*`\"'(\[{【「『《]*$", prefix_in_tok)
        or re.search(r"[:：][\*`\"'(\[{【「『《]*$", prefix_in_tok)
    ):
        return False

    # Reject tokens sitting inside ALL-CAPS headings/CTA buttons on the same line
    line_start = search_corpus.rfind("\n", 0, match_start) + 1
    line_end = search_corpus.find("\n", match_end)
    if line_end == -1:
        line_end = len(search_corpus)
    before_on_line = search_corpus[line_start:match_start]
    after_on_line = search_corpus[match_end:line_end]

    if re.search(r"\b[A-Z]{2,}[ \t]+[\*`\"'(\[{]*$", before_on_line):
        return False
    has_explicit_assignment_before = bool(
        re.search(r"(?:[:：]|(?i:\bis))\s*[\*`\"'(\[{]*$", before_on_line)
    )
    if not has_explicit_assignment_before and re.match(r"^[\*`\"')\]},]*[ \t]+[A-Z]{2,}\b", after_on_line):
        return False

    return True

def extract_pure_alpha_otp_code(
    search_corpus: str,
    sender: str = "",
    domain_filter: Optional[str] = None,
    brand_hint: Optional[str] = None,
) -> Optional[str]:
    """
    Extract a 6-8 uppercase ASCII alphabetic OTP code (e.g. 'SFXNRE', 'FWUOYO')
    only when strong auth/OTP intent and tight contextual anchors are present.
    """
    if not STRONG_OTP_INTENT_PATTERN.search(search_corpus):
        return None
    has_explicit_otp_noun = bool(EXPLICIT_OTP_CODE_NOUN_PATTERN.search(search_corpus))

    # Tier 1 & 2: explicit OTP assignment and leading-code formats
    # Pattern index 2 (bare `code:`) requires an explicit OTP-code noun so marketing emails
    # with footer text like "Click to verify your email address" cannot unlock bare "Use code: ...".
    for pat_idx, pat in enumerate(PURE_ALPHA_OTP_PATTERNS):
        if pat_idx == 2 and not has_explicit_otp_noun:
            continue
        for match in pat.finditer(search_corpus):
            raw_cand = match.group(1)
            if not raw_cand:
                continue
            cand = clean_extracted_code(raw_cand)
            if _is_valid_pure_alpha_otp(
                candidate=cand,
                search_corpus=search_corpus,
                match_start=match.start(1),
                match_end=match.end(1),
                full_match_start=match.start(),
                sender=sender,
                domain_filter=domain_filter,
                brand_hint=brand_hint,
            ):
                return cand

    # Tier 3: standalone uppercase code line sandwiched by OTP prompt or expiry cues
    if not has_explicit_otp_noun:
        return None
    lines = search_corpus.splitlines(keepends=True)
    offsets: List[int] = []
    pos = 0
    for ln in lines:
        offsets.append(pos)
        pos += len(ln)

    for idx, ln in enumerate(lines):
        m = re.match(r"^(\s*(?:[\*`\"']+\s*)?)([A-Z]{6,8})(?:\s*[\*`\"']+)?\s*$", ln.rstrip("\r\n"))
        if not m:
            continue
        cand = m.group(2)
        cand_start = offsets[idx] + len(m.group(1))
        cand_end = cand_start + len(cand)

        prev_non_empty = ""
        for j in range(idx - 1, -1, -1):
            s = lines[j].strip()
            if s:
                prev_non_empty = s
                break
        next_non_empty = ""
        for j in range(idx + 1, len(lines)):
            s = lines[j].strip()
            if s:
                next_non_empty = s
                break

        prev_has_cue = bool(prev_non_empty and PURE_ALPHA_PREV_LINE_CUE_RE.search(prev_non_empty))
        next_has_cue = bool(next_non_empty and PURE_ALPHA_NEXT_LINE_CUE_RE.search(next_non_empty))
        if not (prev_has_cue or next_has_cue):
            continue

        if _is_valid_pure_alpha_otp(
            candidate=cand,
            search_corpus=search_corpus,
            match_start=cand_start,
            match_end=cand_end,
            full_match_start=offsets[idx],
            sender=sender,
            domain_filter=domain_filter,
            brand_hint=brand_hint,
        ):
            return cand

    return None

def get_root_domain(domain: str) -> str:
    """
    Extract authoritative root domain (eTLD+1) from hostname (e.g.
    'secure.sakura.ad.jp' -> 'sakura.ad.jp',
    'dash.cloudflare.com' -> 'cloudflare.com',
    'app.service.co.uk' -> 'service.co.uk').
    """
    d = clean_domain(domain)
    parts = d.split(".")
    if len(parts) <= 2:
        return d
    # Check for ccTLD second level domains like sakura.ad.jp, bbc.co.uk, service.com.cn
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in SECOND_LEVEL_TLDS:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])

def get_domain_brand(domain: str) -> str:
    """Extract primary brand name from domain (e.g. 'dash.cloudflare.com' -> 'cloudflare', 'secure.sakura.ad.jp' -> 'sakura')."""
    d = clean_domain(domain)
    parts = d.split(".")
    if len(parts) <= 1:
        return d

    # Check for two-part ccTLDs like ad.jp, ne.jp, co.uk, com.cn, com.au
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in SECOND_LEVEL_TLDS:
        return parts[-3]

    return parts[-2]

GENERIC_HINT_STOPWORDS = {
    "sign", "signin", "signing", "log", "login", "logging", "logged", "continue", "welcome",
    "verify", "verification", "security", "code", "passcode", "otp", "two", "factor", "2fa",
    "totp", "auth", "authentication", "authenticate", "account", "accounts", "portal",
    "dashboard", "console", "admin", "app", "application", "web", "website", "site", "page",
    "home", "enter", "your", "email", "address", "get", "send", "sent", "with", "for", "from",
    "the", "and", "into", "onto", "back", "next", "step", "one", "time", "password", "magic",
    "link", "session", "user", "member", "client", "server", "cloud", "workspace", "issues",
    "projects", "settings", "localhost", "http", "https", "com", "org", "net", "io", "ai"
}

def _expand_phonetic_brand_variants(token: str) -> List[str]:
    """Generate phonetic C/K spelling variants for app/brand tokens (e.g. 'multika' <-> 'multica')."""
    t = re.sub(r"[^a-z0-9]", "", (token or "").lower())
    if not t:
        return []
    variants = [t]
    if len(t) >= 5:
        for src, dst in (("ka", "ca"), ("ca", "ka"), ("ko", "co"), ("co", "ko"), ("ku", "cu"), ("cu", "ku")):
            if src in t:
                v = t.replace(src, dst)
                if v not in variants:
                    variants.append(v)
        if t.endswith("ik"):
            v = t[:-2] + "ic"
            if v not in variants:
                variants.append(v)
        elif t.endswith("ic"):
            v = t[:-2] + "ik"
            if v not in variants:
                variants.append(v)
    return variants

def get_domain_tokens(domain: str) -> List[str]:
    """
    Extract primary root brand AND non-generic subdomain application tokens (plus phonetic variants)
    from a hostname so self-hosted subdomain deployments reconcile with application brand tokens.
    """
    d = clean_domain(domain)
    if not d:
        return []
    brand = get_domain_brand(d)
    parts = d.split(".")
    tokens: List[str] = []
    if brand:
        for v in _expand_phonetic_brand_variants(brand):
            if v not in tokens:
                tokens.append(v)

    # Extract subdomain labels preceding the root brand
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in SECOND_LEVEL_TLDS:
        sub_parts = parts[:-3]
    elif len(parts) >= 3:
        sub_parts = parts[:-2]
    else:
        sub_parts = []

    for sub in sub_parts:
        sub_clean = sub.strip().lower()
        if (
            len(sub_clean) >= 3
            and sub_clean not in COMMON_SERVICE_SUBDOMAINS
            and sub_clean not in COMMON_SUBDOMAINS
            and sub_clean not in COMMON_TLDS
        ):
            for v in _expand_phonetic_brand_variants(sub_clean):
                if v not in tokens:
                    tokens.append(v)
    return tokens

def extract_brand_hint_tokens(brand_hint: Optional[str]) -> List[str]:
    """Extract candidate brand/service tokens from a page title or login heading (e.g. 'Sign in to Multica' -> ['multica', 'multika'])."""
    if not brand_hint:
        return []
    raw_words = re.findall(r"[a-zA-Z0-9]{3,}", brand_hint.lower())
    tokens: List[str] = []
    for w in raw_words:
        if w in GENERIC_HINT_STOPWORDS or w in COMMON_SERVICE_SUBDOMAINS or w in COMMON_TLDS:
            continue
        if w.isdigit():
            continue
        for v in _expand_phonetic_brand_variants(w):
            if v not in tokens:
                tokens.append(v)
    return tokens

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
    thread_text: str,
    brand_hint: Optional[str] = None,
) -> bool:
    """Match page domain (including subdomain app tokens and optional page brand hints) against rule metadata and email text."""
    if not domain_filter:
        return True

    df_clean = clean_domain(domain_filter)
    brand = get_domain_brand(df_clean)
    root_domain = get_root_domain(df_clean)
    domain_tokens = get_domain_tokens(df_clean)
    hint_tokens = extract_brand_hint_tokens(brand_hint)

    # 1. If rule explicitly binds an extracted domain from subject (e.g. Cloudflare Access)
    if extracted_domain:
        ed = clean_domain(extracted_domain)
        if df_clean == ed or df_clean in ed or ed in df_clean:
            return True
        # If visiting domain did not match extracted domain directly, check rule's associated domains
        # (e.g. visiting tenant.cloudflareaccess.com for an access code bound to app.example.com)
        if associated_domains:
            for ad in associated_domains:
                ad_clean = clean_domain(ad)
                ad_root = get_root_domain(ad_clean)
                if df_clean == ad_clean or df_clean.endswith("." + ad_clean) or ad_clean.endswith("." + df_clean) or root_domain == ad_root or (len(brand) >= 3 and brand in ad_clean):
                    return True
        return False

    # 2. Associated domains defined in rule
    if associated_domains:
        if (re.match(r"^(bwh\d*|bawagon|bandwagon)(\.[a-z]{2,})?$", df_clean) or brand in ("bawagon", "bandwagon")) and any(ad in ("bandwagonhost.com", "64clouds.com", "bwh81.net", "bawagon") for ad in associated_domains):
            return True
        for ad in associated_domains:
            ad_clean = clean_domain(ad)
            ad_root = get_root_domain(ad_clean)
            if (
                df_clean == ad_clean
                or df_clean.endswith("." + ad_clean)
                or ad_clean.endswith("." + df_clean)
                or root_domain == ad_root
                or (len(brand) >= 3 and brand in ad_clean)
                or any(tok == ad_clean or (len(tok) >= 4 and tok in ad_clean) for tok in domain_tokens + hint_tokens)
            ):
                return True

    # 3. Direct visiting domain substring match
    corpus = (subject + "\n" + sender + "\n" + thread_text).lower()
    if df_clean in corpus:
        return True

    # 4. Brand, subdomain app token, and page brand hint match (verifying no conflicting tenant subdomain or explicit subject target domain)
    if len(brand) >= 3:
        explicit_subject_targets = [
            clean_domain(m)
            for m in re.findall(r"(?i)\bfor\s+([a-z0-9][a-z0-9\.-]+\.[a-z]{2,})\b", subject)
        ]
        for target_dom in explicit_subject_targets:
            target_root = get_root_domain(target_dom)
            if (
                target_dom != df_clean
                and not df_clean.endswith("." + target_dom)
                and not target_dom.endswith("." + df_clean)
                and target_root != root_domain
            ):
                return False

        conflicting_domains = set(re.findall(r"([a-z0-9\.-]+\." + re.escape(root_domain) + r")", corpus))
        # If the visiting domain itself is explicitly present in the email, it is an explicit match, not a conflict
        if df_clean not in conflicting_domains:
            # Exclude common infrastructure/service subdomains from being flagged as tenant conflicts
            non_infra_conflicts = [
                cd for cd in conflicting_domains
                if cd != df_clean
                and not df_clean.endswith("." + cd)
                and not cd.endswith("." + df_clean)
                and not cd.startswith("www.")
                and cd.split(".")[0] not in COMMON_SERVICE_SUBDOMAINS
            ]
            if non_infra_conflicts:
                return False

        brand_clean = re.sub(r"[^a-z0-9]", "", brand)
        sender_clean = re.sub(r"[^a-z0-9]", "", sender.lower())
        subject_clean = re.sub(r"[^a-z0-9]", "", subject.lower())
        text_clean = re.sub(r"[^a-z0-9]", "", thread_text.lower())

        if f"@{brand}." in sender.lower() or f"<{brand}@" in sender.lower() or brand in sender.lower() or brand in subject.lower() or root_domain in sender.lower():
            return True

        if brand_clean in sender_clean or brand_clean in subject_clean or brand_clean in text_clean:
            return True

        if (re.match(r"^(bwh\d*|bawagon)$", brand) or brand in ("bawagon", "bandwagon")) and any(alias in sender_clean or alias in subject_clean or alias in text_clean for alias in ("bandwagon", "bawagon", "64clouds", "kiwivm")):
            return True

        # Check non-generic subdomain tokens (e.g. 'multika' / 'multica' from 'multika.example.com') and page brand hints
        for tok in domain_tokens + hint_tokens:
            if tok == brand_clean or len(tok) < 4:
                continue
            if re.search(r"(?i)\b" + re.escape(tok) + r"\b", corpus) or tok in subject_clean or tok in sender_clean:
                return True

    return False

def clean_extracted_code(code_str: str) -> str:
    """Normalize extracted code string."""
    cleaned = unicodedata.normalize("NFKC", code_str).strip()
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
    allow_expired: bool = False,
    brand_hint: Optional[str] = None,
) -> Optional[OTPResult]:
    """Universal intelligent fallback OTP matcher based on proximity, keyword analysis, and markdown normalization."""
    thread_text = unicodedata.normalize("NFKC", thread_text)
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

    # 2. If domain filter is present, ensure domain or brand matches via SSOT domain_matches
    if domain_filter:
        if not domain_matches(
            domain_filter=domain_filter,
            extracted_domain=None,
            associated_domains=None,
            sender=sender,
            subject=subject,
            thread_text=thread_text,
            brand_hint=brand_hint,
        ):
            return None

    body_text = _strip_html_body(get_thread_body(thread_text))
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
    detected_ttl = detect_ttl(raw_search_text)
    ttl = detected_ttl if detected_ttl is not None else max_age_seconds
    remaining = int(ttl - age_seconds)
    is_expired = remaining <= 0
    if not allow_expired and (remaining <= 0 or age_seconds > max(ttl, max_age_seconds)):
        return None

    # 3. Proximity-based code patterns evaluated against normalized & raw text
    patterns = [
        # Thai OTP (รหัส OTP 867679, รหัสยืนยัน: 867679)
        r"(?i)(?:รหัส\s*otp|รหัสยืนยัน)\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{4,8})(?!\d)",
        # Vietnamese OTP (mã xác thực: 867679)
        r"(?i)(?:mã\s*xác\s*thực|mã\s*xác\s*minh|mã\s*otp|mã\s*xác\s*nhận|mã\s*đăng\s*nhập)\s*(?:của\s*bạn\s*)?(?:là)?\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{4,8})(?!\d)",
        # Korean OTP (인증번호: 867679, 인증번호는 867679 입니다)
        r"(?i)(?:인증\s*번호|인증\s*코드|확인\s*코드|보안\s*코드|일회용\s*비밀\s*번호)\s*(?:는|은|:)?\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{4,8})(?!\d)",
        # Spanish & Portuguese OTP (código de verificación: 867679, código de verificação é 867679)
        r"(?i)(?:código\s*de\s*verificación|codigo\s*de\s*verificacion|código\s*de\s*verificação|codigo\s*de\s*verificacao|código\s*de\s*seguridad|código\s*de\s*segurança|codigo\s*de\s*seguranca|código\s*de\s*confirmación|código\s*de\s*confirmação|codigo\s*de\s*confirmacao|código\s*de\s*autenticação|código\s*de\s*acceso|senha\s*descartável)\s*(?:es|é|:)?\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{4,8})(?!\d)",
        # French OTP (code de vérification: 867679)
        r"(?i)(?:code\s*de\s*vérification|code\s*de\s*verification|code\s*de\s*sécurité|code\s*de\s*confirmation|code\s*d['’]accès)\s*(?:est|:)?\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{4,8})(?!\d)",
        # German OTP (Verifizierungscode: 867679, Verifizierungscode lautet 867679)
        r"(?i)(?:verifizierungscode|bestätigungscode|bestaetigungscode|sicherheitscode|einmalpasswort|einmalcode)\s*(?:ist|lautet|:)?\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{4,8})(?!\d)",
        # Russian OTP (код подтверждения: 867679)
        r"(?i)(?:код\s*подтверждения|код\s*верификации|проверочный\s*код|код\s*безопасности|одноразовый\s*пароль)\s*(?:это|:)?\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{4,8})(?!\d)",
        # Italian OTP (codice di verifica: 867679)
        r"(?i)(?:codice\s*di\s*verifica|codice\s*di\s*sicurezza|codice\s*di\s*conferma|codice\s*monouso)\s*(?:è|:)?\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{4,8})(?!\d)",
        # Indonesian / Malay OTP (kode verifikasi: 867679, kode verifikasi Anda adalah 867679)
        r"(?i)(?:kode\s*verifikasi|kode\s*konfirmasi|kode\s*keamanan|kod\s*pengesahan)\s*(?:anda|kamu)?\s*(?:adalah|:)?\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{4,8})(?!\d)",
        # Arabic OTP (رمز التحقق: 867679, رمز التحقق الخاص بك هو 867679)
        r"(?i)(?:رمز\s*التحقق|كود\s*التحقق|رمز\s*التأكيد|رمز\s*الأمان)\s*(?:الخاص\s*بك|بك)?\s*(?:هو|:)?\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{4,8})(?!\d)",
        # Hindi OTP (सत्यापन कोड: 867679)
        r"(?i)(?:सत्यापन\s*कोड|प्रमाणीकरण\s*कोड|सुरक्षा\s*कोड|ओटीपी\s*कोड)\s*(?:है|:)?\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{4,8})(?!\d)",
        # 3D Secure / Banking PIN
        r"(?i)(?:one-time\s*pin[^\n]*is:?|one-time\s*pin\s*is:?|pin\s*is:?)\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{4,8})(?!\d)",
        # Brand specific code (e.g. "Your Dia code is 882228", "TidyCal Code: 182105")
        r"(?i)\b(?:your|here’s your|here's your)?\s*[a-z0-9\.-]+\s+code\s+(?:is|为|为：|是|是：|は|:|：)\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{3,4}[-\s][0-9]{3,4}|[0-9]{4,8}|[0-9a-zA-Z]{5,8})(?![0-9a-zA-Z])",
        # Facebook confirmation code (FB-51412)
        r"(?i)\b(FB-[0-9]{5,6})\b",
        # Slack / Alphanumeric hyphenated code (e.g. UZW-XAD)
        r"(?i)\b([A-Za-z0-9]{3}-[A-Za-z0-9]{3})\b",
        # Validation code (SOLIDWORKS, etc.)
        r"(?i)(?:validation\s*code|validating\s*code)\s*[:#：]?\s*(?:\*\*\s*)?([0-9a-zA-Z]{5,8})(?![0-9a-zA-Z])",
        # Explicit Chinese/Japanese OTP pattern (验证码是：335265, 验证码为：335265, 验证码：842075, 認証コード: 945521)
        r"(?i)(?:验证码|校验码|动态码|安全码|授权码|驗證碼|校驗碼|動態碼|安全碼|認証コード|確認コード|ワンタイムパスワード)\s*(?:是|为)?[：:]\s*(?:\*\*\s*)?([0-9]{4,8})(?!\d)",
        # Subject or line start code (e.g. "434490 is your verification code")
        r"(?i)(?:^|[\r\n])\s*(?:\[[^\]]*\]\s*)?([0-9]{4,8})\s+(?:is\s+your|is\s+the|is)\b",
        # Subject email or device verification/authentication code (e.g. "Email verification code: 861326", "Your SiteGround authentication code: 648551")
        r"(?i)(?:email\s+|device\s+)?(?:verification|authentication|login|security|access|confirmation)\s*code\s*[:#：]\s*([0-9]{4,8})(?!\d)",
        # "Use the code below to authenticate / verify:" multiline block
        r"(?i)use\s+the\s+code\s+below\s+to\s+(?:authenticate|verify|log\s*in|sign\s*in)\s*[:#：]?[\s\r\n]+(?:\*\*\s*)?([0-9]{4,8})(?!\d)",
        # Standard keyword proximity (multilingual)
        r"(?i)(?:"
        r"verification\s*code|verify|security\s*code|login\s*code|access\s*code|"
        r"one-time\s*password|one-time\s*code|passcode|auth\s*code|authentication\s*code|"
        r"confirmation\s*code|secret\s*code|pin\s*code|two-factor|2fa|otp\b|"
        r"验证码|动态码|校验码|安全码|授权码|驗證碼|動態碼|校驗碼|"
        r"認証コード|確認コード|ワンタイムパスワード|"
        r"인증\s*번호|인증\s*코드|확인\s*코드|"
        r"código\s*de\s*verificación|code\s*de\s*vérification|verifizierungscode|bestätigungscode|"
        r"код\s*подтверждения|codice\s*di\s*verifica|mã\s*xác\s*thực|รหัส\s*otp|kode\s*verifikasi"
        r")\s*(?:code|password|passcode)?(?:\s+(?:to\s+[a-z\s]{1,25}|is|为|为：|是|是：|は|es|est|ist|это|è))?\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{3,4}[-\s][0-9]{3,4}|[0-9]{4,8}|[0-9a-zA-Z]{5,8})(?![0-9a-zA-Z])",
        r"(?i)(?:"
        r"verification\s*code|verify|security\s*code|login\s*code|access\s*code|"
        r"one-time\s*password|one-time\s*code|passcode|auth\s*code|authentication\s*code|"
        r"confirmation\s*code|secret\s*code|pin\s*code|two-factor|2fa|otp\b|"
        r"验证码|动态码|校验码|安全码|授权码|驗證碼|動態碼|校驗碼|"
        r"認証コード|確認コード|ワンタイムパスワード|"
        r"인증\s*번호|인증\s*코드|확인\s*코드|"
        r"código\s*de\s*verificación|code\s*de\s*vérification|verifizierungscode|bestätigungscode|"
        r"код\s*подтверждения|codice\s*di\s*verifica|mã\s*xác\s*thực|รหัส\s*otp|kode\s*verifikasi"
        r")\s*(?:is|为|为：|是|是：|は|es|est|ist|это|è|:|：)\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{3,4}[-\s][0-9]{3,4}|[0-9]{4,8}|[0-9a-zA-Z]{5,8})(?![0-9a-zA-Z])",
        r"(?i)(?<!error\s)(?<!status\s)(?<!reference\s)(?<!id\s)(?<!message\s)\b(?:code|passcode|otp|动态码|验证码|安全码|校验码|認証コード|ワンタイムパスワード|인증번호|인증코드)\s*(?:is|为|为：|是|是：|は|es|est|ist|это|è)?\s*[:#：]?\s*(?:\*\*\s*)?([0-9]{3,4}[-\s][0-9]{3,4}|[0-9]{4,8}|[0-9a-zA-Z]{5,8})(?![0-9a-zA-Z])",
        r"(?i)\b([0-9]{3,4}[-\s][0-9]{3,4}|[0-9]{4,8})\b\s*(?:is\s+your|is\s+the|为您的|是您的|为|是|がお客様の|です|となります|입니다|es\s+su|est\s+votre|ist\s+Ihr)\s*(?:one-time|one\s*time|verification|security|login|access|confirmation)?\s*(?:code|passcode|验证码|动态码|認証コード|ワンタイムパスワード|인증번호)?",
        r"(?i)(?:code|passcode|otp)[:\s]+(?:\*\*\s*)?([0-9a-zA-Z]{5,8})(?![0-9a-zA-Z])",
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

                # Disqualify reference numbers or tracking numbers immediately preceding on the same line
                line_start_pos = search_corpus.rfind("\n", 0, match.start()) + 1
                start_pos = max(line_start_pos, match.start() - 35)
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
                    is_expired=is_expired,
                    time_remaining_seconds=max(0, remaining),
                )

    # 4. Pure uppercase alphabetic OTP fallback (6-8 uppercase ASCII letters in strong OTP context)
    # Runs strictly AFTER all digit-bearing / hyphenated patterns so numeric codes always take priority.
    pure_alpha_code = extract_pure_alpha_otp_code(
        search_corpus=raw_search_text,
        sender=sender,
        domain_filter=domain_filter,
        brand_hint=brand_hint,
    )
    if pure_alpha_code and pure_alpha_code != msg_id:
        return OTPResult(
            code=pure_alpha_code,
            service="universal_otp",
            domain=domain_filter,
            callback_url=None,
            message_id=msg_id,
            subject=subject,
            sender=sender,
            received_at=email_dt.isoformat(),
            expires_at=(email_dt + timedelta(seconds=ttl)).isoformat(),
            is_expired=is_expired,
            time_remaining_seconds=max(0, remaining),
        )

    return None

def extract_otp_from_thread(
    thread_text: str,
    domain_filter: Optional[str] = None,
    rules: List[RuleDefinition] = DEFAULT_RULES,
    now: Optional[datetime] = None,
    max_age_seconds: int = 600,
    allow_expired: bool = False,
    brand_hint: Optional[str] = None,
) -> Optional[OTPResult]:
    """
    Extract OTP from full thread text matching against rules and domain.
    Returns OTPResult if a valid, non-expired OTP is found.
    """
    thread_text = unicodedata.normalize("NFKC", thread_text)
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
    if not allow_expired and age_seconds > effective_max_age:
        return None

    body_text = get_thread_body(thread_text)
    clean_body_text = _strip_html_body(body_text)
    search_text = subject + "\n" + body_text
    clean_search_text = (subject + "\n" + clean_body_text) if clean_body_text != body_text else search_text

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
            thread_text=thread_text,
            brand_hint=brand_hint,
        ):
            # When a provider rule authoritatively extracts an explicit target domain
            # (e.g. Cloudflare Access `for app.example.com`) and it does not
            # match the requested domain_filter, reject the email outright instead of
            # falling through to generic/universal rules.
            if extracted_domain:
                return None
            continue

        code_match = re.search(rule.code_regex, search_text)
        if not code_match and clean_search_text != search_text:
            code_match = re.search(rule.code_regex, clean_search_text)
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
                for g in cb_match.groups():
                    if g:
                        callback_url = html.unescape(g.strip())
                        break

        detected_ttl = detect_ttl(clean_search_text)
        ttl = detected_ttl if detected_ttl is not None else rule.default_ttl_seconds
        expires_at_dt = email_dt + timedelta(seconds=ttl)
        remaining = int(ttl - age_seconds)
        is_expired = remaining <= 0
        if not allow_expired and (remaining <= 0 or age_seconds > max(ttl, max_age_seconds)):
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
            is_expired=is_expired,
            time_remaining_seconds=max(0, remaining),
        )

    # 2. Universal intelligent fallback matcher
    return extract_universal_otp(
        thread_text=thread_text,
        headers=headers,
        email_dt=email_dt,
        domain_filter=domain_filter,
        now=now,
        max_age_seconds=max_age_seconds,
        allow_expired=allow_expired,
        brand_hint=brand_hint,
    )

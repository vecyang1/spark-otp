"""
Configurable settings and rules for Spark OTP.
"""
import os
import json
from typing import List, Dict, Any
from .models import RuleDefinition

DEFAULT_RULES = [
    RuleDefinition(
        name="cloudflare_access",
        sender_pattern=r"(?i)(?:cloudflare|noreply@notify\.cloudflare\.com)",
        subject_pattern=r"(?i)Cloudflare Access login code for ([\w\.-]+)",
        code_regex=r"(?i)(?:Your login code:\s*|Your Cloudflare Access code.*?\n\s*)([0-9]{6})",
        callback_regex=r"\[Log in\]\((https://[^\s\)]+cloudflareaccess\.com/cdn-cgi/access/callback[^\s\)]+)\)",
        domain_group=1,
        default_ttl_seconds=600,
        associated_domains=["cloudflare.com", "cloudflareaccess.com"],
    ),
    RuleDefinition(
        name="github_auth",
        sender_pattern=r"(?i)(?:github|noreply@github\.com)",
        subject_pattern=r"(?i)(?:verification|auth|device|two-factor|launch).*code|GitHub",
        code_regex=r"(?i)(?:verification code is:?\s*|device verification code:\s*|verification code:\s*|code:\s*|code is:?\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["github.com"],
    ),
    RuleDefinition(
        name="google_auth",
        sender_pattern=r"(?i)(?:google|no-reply@accounts\.google\.com|accounts\.google\.com|noreply@google\.com)",
        subject_pattern=r"(?i)(?:verification code|security code|Google.*code|verify (?:your )?email)",
        code_regex=r"(?i)(?:G-(\d{6})|(?:verification|security)?\s*code(?: is)?:?\s*(\d{6})|(?:use this code to verify.*?|code.*?(?:belongs to you|verify).*?)\s*(\d{6}))",
        default_ttl_seconds=600,
        associated_domains=["google.com", "accounts.google.com"],
    ),
    RuleDefinition(
        name="aws_amazon",
        sender_pattern=r"(?i)(?:aws|amazon|no-reply-aws@amazon\.com|account-update@amazon\.com)",
        subject_pattern=r"(?i)(?:Amazon|AWS).*(?:verification|code|password|sign-in)",
        code_regex=r"(?i)(?:verification code is:?\s*|verification code:\s*|one-time code:\s*|passcode:\s*|code:\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["amazon.com", "aws.amazon.com"],
    ),
    RuleDefinition(
        name="microsoft_auth",
        sender_pattern=r"(?i)(?:microsoft|accountprotection\.microsoft\.com|account-security-noreply)",
        subject_pattern=r"(?i)(?:Microsoft|security code|account code|single-use code)",
        code_regex=r"(?i)(?:security code:?\s*|single-use code is:?\s*|code:?\s*|use\s+)([0-9]{6,7})\b",
        default_ttl_seconds=600,
        associated_domains=["microsoft.com", "microsoftonline.com", "live.com", "azure.com", "office.com"],
    ),
    RuleDefinition(
        name="stripe_auth",
        sender_pattern=r"(?i)(?:stripe|support@stripe\.com|notifications@stripe\.com)",
        subject_pattern=r"(?i)(?:Stripe|verification code|login code)",
        code_regex=r"(?i)(?:verification code is:?\s*|code is:?\s*|code:\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["stripe.com"],
    ),
    RuleDefinition(
        name="supabase_auth",
        sender_pattern=r"(?i)(?:supabase|noreply@mail\.supabase\.com|noreply@supabase\.io)",
        subject_pattern=r"(?i)(?:Supabase|confirm your signup|login code|verification code)",
        code_regex=r"(?i)(?:confirmation code is:?\s*|code is:?\s*|token is:?\s*|code:\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["supabase.com", "supabase.io", "supabase.co"],
    ),
    RuleDefinition(
        name="vercel_auth",
        sender_pattern=r"(?i)(?:vercel|registration@vercel\.com|notifications@vercel\.com)",
        subject_pattern=r"(?i)(?:Vercel|verification code|login code)",
        code_regex=r"(?i)(?:verification code is:?\s*|verification code:\s*|code:?\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["vercel.com"],
    ),
    RuleDefinition(
        name="notion_auth",
        sender_pattern=r"(?i)(?:notion|mail\.notion\.so|notify@notion\.so)",
        subject_pattern=r"(?i)(?:Notion|temporary passcode|login code|verification code)",
        code_regex=r"(?i)(?:temporary passcode is:?\s*|passcode:?\s*|code:\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["notion.so", "notion.site"],
    ),
    RuleDefinition(
        name="discord_auth",
        sender_pattern=r"(?i)(?:discord|noreply@discord\.com)",
        subject_pattern=r"(?i)(?:Discord|verification code|security code)",
        code_regex=r"(?i)(?:verification code is:?\s*|code is:?\s*|code:\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["discord.com"],
    ),
    RuleDefinition(
        name="steam_guard",
        sender_pattern=r"(?i)(?:steampowered|valve|noreply@steampowered\.com)",
        subject_pattern=r"(?i)(?:Steam Guard|access from new|verification)",
        code_regex=r"(?i)(?:Steam Guard code:?\s*|login code:?\s*|code:\s*)([0-9A-Z]{5})\b",
        default_ttl_seconds=600,
        associated_domains=["steampowered.com", "steamcommunity.com"],
    ),
    RuleDefinition(
        name="twitter_x",
        sender_pattern=r"(?i)(?:twitter|x\.com|info@twitter\.com|verify@x\.com)",
        subject_pattern=r"(?i)(?:confirmation code|verification code|X confirmation)",
        code_regex=r"(?i)(?:confirmation code is:?\s*|code:?\s*)([0-9a-zA-Z]{6,8})\b",
        default_ttl_seconds=600,
        associated_domains=["twitter.com", "x.com"],
    ),
    RuleDefinition(
        name="shopify_auth",
        sender_pattern=r"(?i)(?:shopify|mailer@shopify\.com)",
        subject_pattern=r"(?i)(?:Shopify|verification code|security code)",
        code_regex=r"(?i)(?:verification code is:?\s*|code:?\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["shopify.com", "myshopify.com"],
    ),
    RuleDefinition(
        name="apple_auth",
        sender_pattern=r"(?i)(?:apple|appleid@id\.apple\.com)",
        subject_pattern=r"(?i)(?:Apple ID|Apple Account|verification code)",
        code_regex=r"(?i)(?:Apple ID code is:?\s*|code is:?\s*|code:\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["apple.com", "icloud.com"],
    ),
    RuleDefinition(
        name="slack_auth",
        sender_pattern=r"(?i)(?:slack|feedback@slack\.com|no-reply@slack\.com)",
        subject_pattern=r"(?i)(?:Slack|confirmation code|sign in to Slack)",
        code_regex=r"(?i)(?:confirmation code is:?\s*|code is:?\s*|\n\s*)([0-9A-Za-z]{3}-[0-9A-Za-z]{3}|[0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["slack.com"],
    ),
    RuleDefinition(
        name="adobe_auth",
        sender_pattern=r"(?i)(?:adobe|message@adobe\.com)",
        subject_pattern=r"(?i)(?:Adobe|verification code)",
        code_regex=r"(?i)(?:verification code is:?\s*(?:\*\*\s*)?|code is:?\s*(?:\*\*\s*)?|\*\*\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["adobe.com", "adobe.io"],
    ),
    RuleDefinition(
        name="tidycal_auth",
        sender_pattern=r"(?i)(?:tidycal|service@tidycal\.com)",
        subject_pattern=r"(?i)(?:TidyCal|Verify your device|New booking)",
        code_regex=r"(?i)(?:\[TidyCal Code:\s*([0-9]{6})\]|🔑\s*TidyCal Verification Code[^\n]*\n\s*([0-9]{6})|verify it's you\.\s*([0-9]{6}))",
        default_ttl_seconds=900,
        associated_domains=["tidycal.com"],
    ),
    RuleDefinition(
        name="dia_auth",
        sender_pattern=r"(?i)(?:diabrowser\.com|dia)",
        subject_pattern=r"(?i)(?:Dia code)",
        code_regex=r"(?i)(?:Dia code is\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["diabrowser.com"],
    ),
    RuleDefinition(
        name="solidworks_3ds",
        sender_pattern=r"(?i)(?:3ds\.com|solidworks)",
        subject_pattern=r"(?i)(?:SOLIDWORKS|validation code)",
        code_regex=r"(?i)(?:validation code:\s*)([0-9A-Za-z]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["3ds.com", "solidworks.com"],
    ),
    RuleDefinition(
        name="marqeta_3ds_banking",
        sender_pattern=r"(?i)(?:marqeta|saphirstein|bk\.mufg\.jp|bank)",
        subject_pattern=r"(?i)(?:3D Secure|One Time Passcode|振込|デビット)",
        code_regex=r"(?i)(?:One-time PIN[^\n]*is:\s*|\bPIN is:?\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["marqeta.com", "mufg.jp"],
    ),
    RuleDefinition(
        name="openai_auth",
        sender_pattern=r"(?i)(?:openai|noreply@tm\.openai\.com)",
        subject_pattern=r"(?i)(?:OpenAI|verification code)",
        code_regex=r"(?i)(?:verification code is:?\s*|code is:?\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["openai.com", "chatgpt.com"],
    ),
    RuleDefinition(
        name="atlassian_auth",
        sender_pattern=r"(?i)(?:atlassian|noreply@atlassian\.com|notifications@atlassian\.com)",
        subject_pattern=r"(?i)(?:Atlassian|verification code|login code|passcode)",
        code_regex=r"(?i)(?:verification code is:?\s*|code is:?\s*|code:\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["atlassian.com", "atlassian.net", "jira.com", "trello.com"],
    ),
    RuleDefinition(
        name="clerk_auth",
        sender_pattern=r"(?i)(?:clerk|notifications@clerk\.com)",
        subject_pattern=r"(?i)(?:(\d{6})\s+is\s+your\s+verification\s+code|verification\s+code)",
        code_regex=r"(?i)(?:(\d{6})\s+is\s+your\s+Clerk\s+verification\s+code|\*\*\s*(\d{6})\s*\*\*|verification\s+code:\s*(\d{6})|code:\s*(\d{6}))",
        default_ttl_seconds=600,
        associated_domains=["clerk.com", "clerk.dev"],
    ),
    RuleDefinition(
        name="surfshark_2fa",
        sender_pattern=r"(?i)(?:surfshark|account\.surfshark\.com)",
        subject_pattern=r"(?i)(?:Surfshark.*code|2FA\s+code)",
        code_regex=r"(?i)(?:Surfshark\s+2FA\s+code\s+is\s*|code\s+is\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["surfshark.com"],
    ),
    RuleDefinition(
        name="sony_auth",
        sender_pattern=r"(?i)(?:sony|account\.sony\.com|email02\.account\.sony\.com)",
        subject_pattern=r"(?i)(?:Sony.*Verification Code|Sign-in Verification Code)",
        code_regex=r"(?i)(?:verification code is:?\s*|code:?\s*|\n\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["sony.com", "playstation.com"],
    ),
    RuleDefinition(
        name="pandaremit_auth",
        sender_pattern=r"(?i)(?:pandaremit|熊猫速汇)",
        subject_pattern=r"(?i)(?:Panda Remit|Verification Code)",
        code_regex=r"(?i)(?:([0-9]{6})\s+is\s+Your\s+Panda\s+Remit|verification code is:?\s*([0-9]{6})|code:\s*([0-9]{6}))",
        default_ttl_seconds=600,
        associated_domains=["pandaremit.com"],
    ),
    RuleDefinition(
        name="volcengine_auth",
        sender_pattern=r"(?i)(?:volcengine\.com|火山引擎)",
        subject_pattern=r"(?i)(?:验证码|身份验证)",
        code_regex=r"(?i)(?:验证码(?:是|为|)[：:]\s*|动态码(?:是|为|)[：:]\s*)([0-9]{6})\b",
        default_ttl_seconds=600,
        associated_domains=["volcengine.com", "coze.com", "coze.cn"],
    ),
    RuleDefinition(
        name="bandwagon_auth",
        sender_pattern=r"(?i)(?:bandwagon\s*host|64clouds|kiwivm|it7|noreply@64clouds\.com)",
        subject_pattern=r"(?i)(?:device\s*verification|verification|security\s*code|bandwagon)",
        code_regex=r"(?i)(?:(?:device\s+)?verification\s+code:?\s*|code:?\s*)([0-9]{4,8})\b",
        default_ttl_seconds=3600,
        associated_domains=[
            "bandwagonhost.com",
            "bwh81.net",
            "bwh88.net",
            "bwh89.net",
            "bwh1.net",
            "bwh8.net",
            "bwh9.net",
            "64clouds.com",
            "kiwivm.it7.net",
            "it7.net",
            "bawagon.com",
            "bawagon",
            "bandwagon",
        ],
        filter_query="from:64clouds.com OR from:bandwagonhost.com OR from:it7.net",
    ),
    RuleDefinition(
        name="generic_otp",
        sender_pattern=r".*",
        subject_pattern=r"(?i)(?:verification|login|security|access|auth|otp|one-time|verify|confirm|passcode|validation|device).*code|(?:device\s+)?verification\b|验证码|动态码|校验码|安全码|授权码|認証コード|確認コード|ワンタイムパスワード",
        code_regex=r"(?i)(?:your\s+(?:device\s+)?(?:verification|login|security|confirmation|access)?\s*code\s*(?:is|为|:)\s*|(?:device\s+)?verification\s*code:?\s*|code is:?|code:\s*|passcode:\s*|validation code:\s*|验证码(?:是|为|)[：:]?\s*|动态码(?:是|为|)[：:]?\s*|校验码(?:是|为|)[：:]?\s*|認証コード(?:は|：|:)\s*|ワンタイムパスワード(?:は|：|:)\s*)([0-9]{4,8}|[0-9A-Za-z]{5,8})\b",
        default_ttl_seconds=600,
    )
]

class Config:
    def __init__(self, config_path: str = None):
        self.host = os.environ.get("SPARK_OTP_HOST", "127.0.0.1")
        self.port = int(os.environ.get("SPARK_OTP_PORT", "9428"))
        self.spark_bin = os.environ.get("SPARK_BIN_PATH", "/usr/local/bin/spark")
        self.max_email_age_seconds = int(os.environ.get("SPARK_OTP_MAX_AGE", "600"))
        self.email_page_size = int(os.environ.get("SPARK_OTP_PAGE_SIZE", "35"))
        self.uptime_kuma_push_url = os.environ.get("UPTIME_KUMA_PUSH_URL", None)
        self.sentry_dsn = os.environ.get("SENTRY_DSN", None)
        self.telemetry_enabled = os.environ.get("SPARK_OTP_TELEMETRY", "1").lower() in ("1", "true", "yes")
        self.log_path = os.environ.get("SPARK_OTP_LOG_PATH", None)
        self.sqlite_db_path = os.environ.get("SPARK_OTP_SQLITE_PATH", "auto")
        self.apple_mail_sqlite_path = os.environ.get("APPLE_MAIL_SQLITE_PATH", "auto")
        self.apple_mail_enabled = os.environ.get("SPARK_OTP_APPLE_MAIL_ENABLED", "1").lower() in ("1", "true", "yes")
        self.rules: List[RuleDefinition] = DEFAULT_RULES
        
        if config_path and os.path.exists(config_path):
            self.load_from_file(config_path)

    def load_from_file(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.host = data.get("host", self.host)
            self.port = data.get("port", self.port)
            self.spark_bin = data.get("spark_bin", self.spark_bin)
            self.max_email_age_seconds = data.get("max_email_age_seconds", self.max_email_age_seconds)
            self.email_page_size = data.get("email_page_size", self.email_page_size)
            self.uptime_kuma_push_url = data.get("uptime_kuma_push_url", self.uptime_kuma_push_url)
            self.sentry_dsn = data.get("sentry_dsn", self.sentry_dsn)
            self.telemetry_enabled = data.get("telemetry_enabled", self.telemetry_enabled)
            self.log_path = data.get("log_path", self.log_path)
            self.sqlite_db_path = data.get("sqlite_db_path", self.sqlite_db_path)
            self.apple_mail_sqlite_path = data.get("apple_mail_sqlite_path", self.apple_mail_sqlite_path)
            self.apple_mail_enabled = data.get("apple_mail_enabled", self.apple_mail_enabled)
            if "custom_rules" in data:
                custom = [
                    RuleDefinition(**r) for r in data["custom_rules"]
                ]
                self.rules = custom + self.rules

config = Config()


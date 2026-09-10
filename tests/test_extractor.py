"""
TDD Tests for Spark OTP Extractor.
"""
import unittest
from datetime import datetime, timedelta
from spark_otp.extractor import extract_otp_from_thread, parse_email_date, get_domain_brand
from spark_otp.config import DEFAULT_RULES
from tests.fixtures import (
    REAL_CLOUDFLARE_FINANCE_EMAIL,
    REAL_CLOUDFLARE_STATUS_EMAIL,
    ADVERSARIAL_SPAM_EMAIL,
    ADVERSARIAL_AMBIGUOUS_NUMBERS,
    GITHUB_VERIFY_EMAIL,
    GOOGLE_VERIFY_EMAIL,
    AWS_VERIFY_EMAIL,
    MICROSOFT_VERIFY_EMAIL,
    STRIPE_VERIFY_EMAIL,
    SUPABASE_VERIFY_EMAIL,
    VERCEL_VERIFY_EMAIL,
    NOTION_VERIFY_EMAIL,
    STEAM_GUARD_EMAIL,
    SLACK_VERIFY_EMAIL,
    UNIVERSAL_SAAS_EMAIL,
    UNIVERSAL_CHINESE_OTP_EMAIL,
    UNIVERSAL_JAPANESE_OTP_EMAIL,
    NON_OTP_RECEIPT_EMAIL,
    ATLASSIAN_VERIFY_EMAIL,
    SPACED_OTP_EMAIL,
    JAPANESE_ONETIME_PASSWORD_EMAIL,
    CHINESE_DYNAMIC_CODE_EMAIL,
    REAL_BANDWAGON_VERIFY_EMAIL,
)

class TestExtractor(unittest.TestCase):
    def test_parse_email_date(self):
        dt = parse_email_date("2026-09-07 19:35")
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 9)
        self.assertEqual(dt.day, 7)
        self.assertEqual(dt.hour, 19)
        self.assertEqual(dt.minute, 35)

    def test_get_domain_brand(self):
        self.assertEqual(get_domain_brand("github.com"), "github")
        self.assertEqual(get_domain_brand("dashboard.stripe.com"), "stripe")
        self.assertEqual(get_domain_brand("console.aws.amazon.com"), "amazon")
        self.assertEqual(get_domain_brand("finance.acme-cloud.net"), "acme-cloud")
        self.assertEqual(get_domain_brand("https://auth.notion.so/login"), "notion")

    def test_extract_real_cloudflare_finance_email(self):
        now = datetime(2026, 9, 7, 19, 36)
        date_str = "2026-09-07 19:35"
        raw = REAL_CLOUDFLARE_FINANCE_EMAIL.format(date_str=date_str)
        
        result = extract_otp_from_thread(raw, domain_filter="finance.acme-cloud.net", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "266134")
        self.assertEqual(result.service, "cloudflare_access")
        self.assertEqual(result.domain, "finance.acme-cloud.net")
        self.assertIn("acme-corp.cloudflareaccess.com", result.callback_url)
        self.assertFalse(result.is_expired)
        self.assertGreater(result.time_remaining_seconds, 500)

    def test_domain_filter_rejection(self):
        now = datetime(2026, 9, 7, 19, 36)
        date_str = "2026-09-07 19:35"
        raw = REAL_CLOUDFLARE_FINANCE_EMAIL.format(date_str=date_str)
        
        # When looking for status.acme-cloud.net, finance email should NOT match
        result = extract_otp_from_thread(raw, domain_filter="status.acme-cloud.net", now=now)
        self.assertIsNone(result)

    def test_extract_real_cloudflare_status_email(self):
        now = datetime(2026, 9, 7, 18, 38)
        date_str = "2026-09-07 18:36"
        raw = REAL_CLOUDFLARE_STATUS_EMAIL.format(date_str=date_str)
        
        result = extract_otp_from_thread(raw, domain_filter="status.acme-cloud.net", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "431449")
        self.assertEqual(result.service, "cloudflare_access")
        self.assertEqual(result.domain, "status.acme-cloud.net")
        self.assertFalse(result.is_expired)

    def test_github_auth_extraction(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = GITHUB_VERIFY_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="github.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "849302")
        self.assertEqual(result.service, "github_auth")

    def test_google_auth_normalization(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = GOOGLE_VERIFY_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="accounts.google.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "582914")  # G-582914 normalized to 582914
        self.assertEqual(result.service, "google_auth")

    def test_aws_auth_extraction(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = AWS_VERIFY_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="console.aws.amazon.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "318492")
        self.assertEqual(result.service, "aws_amazon")

    def test_microsoft_auth_extraction(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = MICROSOFT_VERIFY_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="login.microsoftonline.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "6291845")
        self.assertEqual(result.service, "microsoft_auth")

    def test_stripe_subdomain_matching(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = STRIPE_VERIFY_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="dashboard.stripe.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "719402")
        self.assertEqual(result.service, "stripe_auth")

    def test_supabase_auth_extraction(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = SUPABASE_VERIFY_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="app.supabase.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "482019")
        self.assertEqual(result.service, "supabase_auth")

    def test_vercel_auth_extraction(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = VERCEL_VERIFY_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="vercel.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "938471")
        self.assertEqual(result.service, "vercel_auth")

    def test_notion_auth_extraction(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = NOTION_VERIFY_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="notion.so", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "184920")
        self.assertEqual(result.service, "notion_auth")

    def test_steam_guard_alphanumeric_extraction(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = STEAM_GUARD_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="steamcommunity.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "5K9P2")
        self.assertEqual(result.service, "steam_guard")

    def test_slack_hyphen_normalization(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = SLACK_VERIFY_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="app.slack.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "384912")  # 384-912 normalized to 384912
        self.assertEqual(result.service, "slack_auth")

    def test_universal_saas_fallback(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = UNIVERSAL_SAAS_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="myapp.cloud", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "772910")
        self.assertEqual(result.service, "universal_otp")

    def test_universal_chinese_otp(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = UNIVERSAL_CHINESE_OTP_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="platform.cn", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "839201")

    def test_universal_japanese_otp(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = UNIVERSAL_JAPANESE_OTP_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="service.co.jp", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "618492")

    def test_cross_service_mismatch_rejection(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = GITHUB_VERIFY_EMAIL.format(date_str="2026-09-07 19:38")
        # When browsing stripe.com, GitHub email must not be autofilled!
        result = extract_otp_from_thread(raw, domain_filter="stripe.com", now=now)
        self.assertIsNone(result)

    def test_non_otp_order_receipt_rejection(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = NON_OTP_RECEIPT_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, now=now)
        self.assertIsNone(result, "Commercial receipt or tracking code must not be extracted as OTP")

    def test_expired_code_rejection(self):
        now = datetime(2026, 9, 7, 18, 15)
        date_str = "2026-09-07 18:00"
        raw = REAL_CLOUDFLARE_FINANCE_EMAIL.format(date_str=date_str)
        
        result = extract_otp_from_thread(raw, domain_filter="finance.acme-cloud.net", now=now)
        self.assertIsNone(result, "Expired OTP code must not be returned as valid")

    def test_adversarial_spam_rejection(self):
        now = datetime(2026, 9, 7, 19, 0)
        date_str = "2026-09-07 19:00"
        raw = ADVERSARIAL_SPAM_EMAIL.format(date_str=date_str)
        
        result = extract_otp_from_thread(raw, now=now)
        self.assertIsNone(result, "Spam / service errors should not be misidentified as OTP")

    def test_adversarial_ambiguous_numbers_rejection(self):
        now = datetime(2026, 9, 7, 17, 15)
        date_str = "2026-09-07 17:14"
        raw = ADVERSARIAL_AMBIGUOUS_NUMBERS.format(date_str=date_str)
        
        result = extract_otp_from_thread(raw, now=now)
        self.assertIsNone(result, "Phone numbers, zip codes, salary numbers should not be detected as OTP")

    def test_atlassian_subdomain_extraction(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = ATLASSIAN_VERIFY_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="myteam.atlassian.net", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "581943")
        self.assertEqual(result.service, "atlassian_auth")

    def test_spaced_otp_code_extraction(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = SPACED_OTP_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="security-service.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "482109")  # "482 109" normalized to "482109"

    def test_japanese_onetime_password_extraction(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = JAPANESE_ONETIME_PASSWORD_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="portal.co.jp", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "925184")

    def test_chinese_dynamic_code_extraction(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = CHINESE_DYNAMIC_CODE_EMAIL.format(date_str="2026-09-07 19:38")
        result = extract_otp_from_thread(raw, domain_filter="service.cn", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "739102")

    def test_subdomain_cross_conflict_rejection(self):
        now = datetime(2026, 9, 7, 19, 40)
        raw = REAL_CLOUDFLARE_FINANCE_EMAIL.format(date_str="2026-09-07 19:38")
        # When browsing a different subdomain on same root domain, conflicting email must be rejected
        result = extract_otp_from_thread(raw, domain_filter="status.acme-cloud.net", now=now)
        self.assertIsNone(result)

    def test_adobe_markdown_bold_extraction(self):
        now = datetime(2026, 8, 28, 22, 45)
        raw = """
ID: 718092
Subject: Verification code
From: Adobe Creative Cloud <message@adobe.com>
To: Alex Turner <alex.turner@oakridge.edu>
Date: 2026-08-28 22:44
Type: Email

Adobe

Your verification code is:
** 521006**
Your account can’t be accessed without this verification code.
"""
        result = extract_otp_from_thread(raw, domain_filter="adobe.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "521006")
        self.assertEqual(result.service, "adobe_auth")

    def test_dia_browser_brand_code_extraction(self):
        now = datetime(2025, 6, 3, 22, 32)
        raw = """
ID: 100177
Subject: Here’s your Dia code
From: no-reply@diabrowser.com
To: Alex Turner <alex.turner@oakridge.edu>
Date: 2025-06-03 22:31
Type: Email

Your Dia code is 882228.
Enter this code into Dia to continue. Do not share this code with anyone else.
"""
        result = extract_otp_from_thread(raw, domain_filter="diabrowser.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "882228")
        self.assertEqual(result.service, "dia_auth")

    def test_solidworks_alphanumeric_validation_code(self):
        now = datetime(2021, 6, 6, 16, 18)
        raw = """
ID: 76990
Subject: Your SOLIDWORKS ID validation code
From: noreply@3ds.com
To: alex.turner@example.com
Date: 2021-06-06 16:17
Type: Email

Validation code: 34P514
Please note: This code will expire in 10 mins.
"""
        result = extract_otp_from_thread(raw, domain_filter="3ds.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "34P514")
        self.assertEqual(result.service, "solidworks_3ds")

    def test_slack_alphanumeric_hyphenated_code(self):
        now = datetime(2022, 7, 31, 22, 48)
        raw = """
ID: 68262
Subject: Slack confirmation code: UZW-XAD
From: Slack <no-reply-lVnLAA12zg49UO7QzbfB6qRP@slack.com>
To: alex.turner@example.com
Date: 2022-07-31 22:47
Type: Email

Slack confirmation code: UZW-XAD
Your confirmation code is below:
UZW-XAD
"""
        result = extract_otp_from_thread(raw, domain_filter="slack.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "UZW-XAD")
        self.assertEqual(result.service, "slack_auth")

    def test_marqeta_3ds_banking_pin(self):
        now = datetime(2026, 5, 18, 18, 54)
        raw = """
ID: 240274
Subject: One Time Passcode for 3D Secure
From: Saphirstein <noreply@marqeta.com>
To: Alex Turner <alex.turner@example.com>
Date: 2026-05-18 18:53
Type: Email

One-time PIN for the transaction of 0.00 at OPENAI using Saphirstein card 0550 is:
718606

Expires in 10 minutes.
"""
        result = extract_otp_from_thread(raw, domain_filter="marqeta.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "718606")
        self.assertEqual(result.service, "marqeta_3ds_banking")

    def test_thai_ais_otp_and_reference_rejection(self):
        now = datetime(2025, 5, 22, 20, 21)
        raw = """
ID: 96921
Subject: รหัส OTP เพื่อยืนยันอีเมล myID OTP to verify your myID email
From: myAIS@ais.co.th
To: alex.turner@example.com
Date: 2025-05-22 20:20
Type: Email

เรียนผู้ใช้บริการ myAIS
รหัส OTP 867679
เลขที่อ้างอิง 0719
รหัสนี้มีอายุ 15 นาที
"""
        result = extract_otp_from_thread(raw, domain_filter="ais.co.th", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "867679")
        # Ensure reference code 0719 was rejected in favor of OTP 867679
        self.assertNotEqual(result.code, "0719")

    def test_facebook_fb_prefix_normalization(self):
        now = datetime(2021, 10, 12, 15, 58)
        raw = """
ID: 68791
Subject: FB-51412 is your Facebook confirmation code
From: Facebook <registration@facebookmail.com>
To: Alex Turner <alex.turner@example.com>
Date: 2021-10-12 15:57
Type: Email

You recently registered for Facebook.
FB-51412 is your Facebook confirmation code
"""
        result = extract_otp_from_thread(raw, domain_filter="facebook.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "51412")

    def test_stytch_bhuman_login_code(self):
        now = datetime(2023, 11, 26, 20, 17)
        raw = """
ID: 62018
Subject: Your one-time login code for BHuman
From: Login <login@stytch.com>
To: alex.turner@example.com
Date: 2023-11-26 20:16
Type: Email

Your login request to BHuman
806496 is your one-time code to log in to your account. Your code expires in 5 minutes.
"""
        result = extract_otp_from_thread(raw, domain_filter="bhuman.ai", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "806496")

    def test_adversarial_word_disqualification(self):
        now = datetime(2026, 9, 7, 20, 0)
        raw = """
ID: 99999
Subject: Security alert about your account
From: service@test.com
Date: 2026-09-07 19:58
Type: Email

Your code expires in 5 minutes. Please verify your account.
"""
        result = extract_otp_from_thread(raw, domain_filter="test.com", now=now)
        self.assertIsNone(result)

    def test_volcengine_chinese_shi_extraction(self):
        now = datetime(2026, 3, 11, 14, 35)
        raw = """
ID: 167617
Subject: 安全邮箱变更-验证码
From: 火山引擎 <no-reply@notice.volcengine.com>
To: alex.turner@example.com
Date: 2026-03-11 14:32
Type: Email

安全邮箱变更-验证码 您好： 感谢使用火山引擎，您正在进行身份验证，您的验证码是：335265（10分钟内有效），请勿向任何人提供此验证码。
"""
        result = extract_otp_from_thread(raw, domain_filter="volcengine.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "335265")
        self.assertEqual(result.service, "volcengine_auth")

    def test_getmacapp_chinese_colon_extraction(self):
        now = datetime(2025, 7, 6, 20, 10)
        raw = """
ID: 107208
Subject: 验证码
From: 割麦网 <support@getmacapp.com>
To: alex.turner@example.com
Date: 2025-07-06 20:07
Type: Email

验证码：842075
致力于让您的Mac电脑无所不能
"""
        result = extract_otp_from_thread(raw, domain_filter="getmacapp.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "842075")

    def test_clerk_auth_extraction(self):
        now = datetime(2026, 9, 4, 23, 10)
        raw = """
ID: 719724
Subject: 434490 is your verification code
From: Clerk <notifications@clerk.com>
To: alex.turner@example.com
Date: 2026-09-04 23:06
Type: Email

434490 is your Clerk verification code
Enter the following verification code when prompted:
** 434490**
"""
        result = extract_otp_from_thread(raw, domain_filter="clerk.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "434490")
        self.assertEqual(result.service, "clerk_auth")

    def test_surfshark_2fa_extraction(self):
        now = datetime(2026, 9, 6, 21, 26)
        raw = """
ID: 719983
Subject: Your Surfshark 2FA code is 871330
From: Surfshark <no-reply@account.surfshark.com>
To: alex.turner@example.com
Date: 2026-09-06 21:24
Type: Email

Your Surfshark 2FA code is 871330.
Valid for 10 minutes.
"""
        result = extract_otp_from_thread(raw, domain_filter="surfshark.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "871330")
        self.assertEqual(result.service, "surfshark_2fa")

    def test_sony_signin_extraction(self):
        now = datetime(2026, 8, 17, 20, 0)
        raw = """
ID: 715905
Subject: Your Sony Sign-in Verification Code
From: Sony <sony@email02.account.sony.com>
To: marcus.vance@techcorp.io
Date: 2026-08-17 19:56
Type: Email

Verification Code: 735880
The verification code will expire 10 minutes after it was issued.
"""
        result = extract_otp_from_thread(raw, domain_filter="sony.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "735880")
        self.assertEqual(result.service, "sony_auth")

    def test_google_subject_code_extraction(self):
        now = datetime(2022, 11, 2, 8, 25)
        raw = """
ID: 719353
Subject: Email verification code: 861326
From: Google <noreply@google.com>
To: Marcus Vance <marcus.vance@techcorp.io>
Date: 2022-11-02 08:23
Type: Email

(body unavailable - not synced yet)
"""
        result = extract_otp_from_thread(raw, domain_filter="google.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "861326")

    def test_pandaremit_extraction(self):
        now = datetime(2026, 5, 27, 13, 52)
        raw = """
ID: 680638
Subject: 677016 is Your Panda Remit Verification Code
From: [PandaRemit]熊猫速汇 <welcome@notify.pandaremit.com>
To: alex.turner@example.com
Date: 2026-05-27 13:49
Type: Email

677016 is Your Panda Remit Verification Code
"""
        result = extract_otp_from_thread(raw, domain_filter="pandaremit.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "677016")
        self.assertEqual(result.service, "pandaremit_auth")

    def test_multi_message_thread_id_isolation(self):
        now = datetime(2026, 9, 7, 10, 55)
        raw = """
Thread: Your verification code: 334455
Messages: 2
────────────────────────────────────────────────────────────────────────
  ID: 720142
  Subject: Your verification code: 334455
  From: Marcus Vance <marcus.vance@techcorp.io>
  Date: 2026-09-07 10:53
  Type: Email

  (body unavailable - not synced yet)
────────────────────────────────────────────────────────────────────────
  ID: 720144
  Subject: Your verification code: 334455
  From: Marcus Vance <marcus.vance@techcorp.io>
  Date: 2026-09-07 10:53
  Type: Email

  Your verification code is 334455.
"""
        result = extract_otp_from_thread(raw, domain_filter="techcorp.io", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "334455")
        # Ensure message ID 720142 was not mistaken as code
        self.assertNotEqual(result.code, "720142")
        self.assertNotEqual(result.code, "720144")

    def test_explicit_short_expiry_rejection(self):
        # Stated expiry: 3 minutes. Evaluated at 4 minutes -> must be rejected!
        now = datetime(2026, 9, 7, 10, 4)
        raw = """
ID: 999111
Subject: Your Quick Login Code
From: Quick <noreply@quickservice.com>
Date: 2026-09-07 10:00
Type: Email

Your verification code is 445566. This code expires in 3 minutes.
"""
        result = extract_otp_from_thread(raw, domain_filter="quickservice.com", now=now)
        self.assertIsNone(result, "Code with 3-minute expiry must be rejected at 4 minutes")

    def test_valid_for_minutes_expiry_rejection(self):
        # Stated: "valid for 5 minutes". Evaluated at 6 minutes -> must be rejected!
        now = datetime(2026, 9, 7, 10, 6)
        raw = """
ID: 999222
Subject: Security Passcode
From: App <noreply@myapp.io>
Date: 2026-09-07 10:00
Type: Email

Your verification code: 829103
This code is valid for 5 minutes.
"""
        result = extract_otp_from_thread(raw, domain_filter="myapp.io", now=now)
        self.assertIsNone(result, "Code stating valid for 5 minutes must be rejected at 6 minutes")

    def test_chinese_expiry_rejection_and_acceptance(self):
        raw = """
ID: 999333
Subject: 身份验证
From: 火山引擎 <no-reply@notice.volcengine.com>
Date: 2026-03-11 14:32
Type: Email

感谢使用，您的验证码是：335265（10分钟内有效），请勿向任何人提供此验证码。
"""
        # Evaluated at 12 minutes -> expired!
        now_exp = datetime(2026, 3, 11, 14, 44)
        result_exp = extract_otp_from_thread(raw, domain_filter="volcengine.com", now=now_exp)
        self.assertIsNone(result_exp, "Chinese 10分钟内有效 code must be rejected at 12 minutes")

        # Evaluated at 7 minutes -> valid with 180s left!
        now_val = datetime(2026, 3, 11, 14, 39)
        result_val = extract_otp_from_thread(raw, domain_filter="volcengine.com", now=now_val)
        self.assertIsNotNone(result_val)
        self.assertEqual(result_val.code, "335265")
        self.assertEqual(result_val.time_remaining_seconds, 180)

    def test_japanese_expiry_rejection_and_acceptance(self):
        raw = """
ID: 999444
Subject: ワンタイムパスワードのご案内
From: サービス <support@service.co.jp>
Date: 2026-09-07 10:00
Type: Email

認証コード：771239
※有効期限：10分
"""
        # Evaluated at 12 minutes -> expired!
        now_exp = datetime(2026, 9, 7, 10, 12)
        result_exp = extract_otp_from_thread(raw, domain_filter="service.co.jp", now=now_exp)
        self.assertIsNone(result_exp, "Japanese 有効期限：10分 code must be rejected at 12 minutes")

        # Evaluated at 6 minutes -> valid with 240s left!
        now_val = datetime(2026, 9, 7, 10, 6)
        result_val = extract_otp_from_thread(raw, domain_filter="service.co.jp", now=now_val)
        self.assertIsNotNone(result_val)
        self.assertEqual(result_val.code, "771239")
        self.assertEqual(result_val.time_remaining_seconds, 240)

    def test_extract_bandwagon_host_official_domain(self):
        now = datetime(2026, 9, 8, 20, 36)
        raw = REAL_BANDWAGON_VERIFY_EMAIL.format(date_str="2026-09-08 20:34")
        result = extract_otp_from_thread(raw, domain_filter="bandwagonhost.com", now=now)
        self.assertIsNotNone(result)
        self.assertEqual(result.code, "181174")
        self.assertEqual(result.service, "bandwagon_auth")
        self.assertEqual(result.time_remaining_seconds, 3480)
        self.assertFalse(result.is_expired)

    def test_extract_bandwagon_host_mirrors(self):
        now = datetime(2026, 9, 8, 20, 36)
        raw = REAL_BANDWAGON_VERIFY_EMAIL.format(date_str="2026-09-08 20:34")
        for mirror in ["bwh81.net", "bwh88.net", "bwh89.net", "64clouds.com", "kiwivm.it7.net"]:
            result = extract_otp_from_thread(raw, domain_filter=mirror, now=now)
            self.assertIsNotNone(result, f"Failed for mirror: {mirror}")
            self.assertEqual(result.code, "181174")
            self.assertEqual(result.service, "bandwagon_auth")

    def test_extract_bandwagon_hour_ttl(self):
        # Email date: 2026-09-08 20:34, valid for 1 hour
        raw = REAL_BANDWAGON_VERIFY_EMAIL.format(date_str="2026-09-08 20:34")

        # 1. Evaluated at 40 minutes later -> should be valid with 1200s left!
        now_valid = datetime(2026, 9, 8, 21, 14)
        result_valid = extract_otp_from_thread(raw, domain_filter="bwh81.net", now=now_valid)
        self.assertIsNotNone(result_valid)
        self.assertEqual(result_valid.code, "181174")
        self.assertEqual(result_valid.time_remaining_seconds, 1200)

        # 2. Evaluated at 65 minutes later -> expired!
        now_expired = datetime(2026, 9, 8, 21, 39)
        result_expired = extract_otp_from_thread(raw, domain_filter="bwh81.net", now=now_expired)
        self.assertIsNone(result_expired, "Bandwagon code should expire after 1 hour (3600s)")

    def test_extract_bandwagon_bawagon_alias(self):
        now = datetime(2026, 9, 8, 20, 36)
        raw = REAL_BANDWAGON_VERIFY_EMAIL.format(date_str="2026-09-08 20:34")
        for alias in ["bawagon", "bawagon.com", "bandwagon", "bwh81.com", "bwh88.org"]:
            result = extract_otp_from_thread(raw, domain_filter=alias, now=now)
            self.assertIsNotNone(result, f"Failed for alias: {alias}")
            self.assertEqual(result.code, "181174")
            self.assertEqual(result.service, "bandwagon_auth")

    def test_extract_bandwagon_custom_max_age_boundary(self):
        # Email date: 2026-09-08 20:34 (age: 25 minutes = 1500s)
        # Custom max_age_seconds = 1200 (20 minutes), but rule default TTL is 3600 (1 hour)
        # It must NOT be dropped by line 418 early pre-filter
        now = datetime(2026, 9, 8, 20, 59)
        raw = REAL_BANDWAGON_VERIFY_EMAIL.format(date_str="2026-09-08 20:34")
        result = extract_otp_from_thread(raw, domain_filter="bawagon", max_age_seconds=1200, now=now)
        self.assertIsNotNone(result, "Should respect rule max TTL 3600s over custom max_age 1200s")
        self.assertEqual(result.code, "181174")
        self.assertEqual(result.time_remaining_seconds, 2100)

if __name__ == "__main__":
    unittest.main()



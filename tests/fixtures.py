# Test fixtures for Spark OTP testing

REAL_CLOUDFLARE_FINANCE_EMAIL = """
Thread: Cloudflare Access login code for finance.acme-cloud.net
Messages: 1
Labels: alex.turner@example.com:Important
Link: https://sparkmailapp.com/dpl/bl?token=QTphbGV4LnR1cm5lckBnbWFpbC5jb207SUQ6bW9ja19zcGFya190b2tlbl9zYW1wbGVfMTIz
────────────────────────────────────────────────────────────────────────

  ID: 720205
  Subject: Cloudflare Access login code for finance.acme-cloud.net
  From: Cloudflare <noreply@notify.cloudflare.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  Your login code: 266134
  
  ** [Your Cloudflare Access code](https://www.cloudflare.com/)**
  266134
  This code expires after 10 minutes or if you request a new code.
  
  ** Prefer not to use the code?**
  Finish logging in to finance.acme-cloud.net below.
  
  [Log in](https://acme-corp.cloudflareaccess.com/cdn-cgi/access/callback?nonce=PiKmnmCs4Zj8YycuuYQIH6Sjjnu7MTc4ODc4NDUyMw&code=266134&secret=iBeStTQlddszUAMe96ebYGUJb0kRSQpI)
  
  Copyright © Cloudflare, Inc.
  101 Townsend Street, San Francisco, CA 94107
  [www.cloudflare.com](https://www.cloudflare.com/) | [Community](https://community.cloudflare.com/)
"""

REAL_CLOUDFLARE_STATUS_EMAIL = """
Thread: Cloudflare Access login code for status.acme-cloud.net
Messages: 1
Labels: alex.turner@example.com:Important
────────────────────────────────────────────────────────────────────────

  ID: 720198
  Subject: Cloudflare Access login code for status.acme-cloud.net
  From: Cloudflare <noreply@notify.cloudflare.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email
  Flags: unread

  Your login code: 431449
  
  ** [Your Cloudflare Access code](https://www.cloudflare.com/)**
  431449
  This code expires after 10 minutes or if you request a new code.
  
  ** Prefer not to use the code?**
  Finish logging in to status.acme-cloud.net below.
  
  [Log in](https://acme-corp.cloudflareaccess.com/cdn-cgi/access/callback?nonce=te4hrDL1oLG5HuHIYcXKAO6dBs2XMTc4ODc4MDk1Mg&code=431449&secret=S1ezF3Z8HGtEfDPbBQXc6RsmFbK4jUqs)
"""

ADVERSARIAL_SPAM_EMAIL = """
  ID: 720188
  Subject: Check automation errors on your account
  From: Albato <support@albato.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  Hello, your webhook automation 849201 failed with status 500.
  Error code: 500129
  Please check your settings at https://albato.com.
"""

ADVERSARIAL_AMBIGUOUS_NUMBERS = """
  ID: 720191
  Subject: Job opportunity in Tokyo
  From: Indeed <no-reply@indeed.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  Salary range: 500,000 JPY to 800,000 JPY. Reference ID: 948201.
  Call us at 03-1234-5678. Zip: 100-0001.
"""

GITHUB_VERIFY_EMAIL = """
  ID: 720250
  Subject: [GitHub] Please verify your device
  From: GitHub <noreply@github.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  Hey alexturner!
  A sign in attempt requires further verification.
  Your verification code is: 849302
  This code will expire in 10 minutes.
"""

GOOGLE_VERIFY_EMAIL = """
  ID: 720251
  Subject: Google Verification Code
  From: Google <no-reply@accounts.google.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  G-582914 is your Google verification code.
  Do not share this code with anyone.
"""

AWS_VERIFY_EMAIL = """
  ID: 720252
  Subject: Amazon Web Services Sign-In Verification
  From: Amazon Web Services <no-reply-aws@amazon.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  To authenticate, please use the following one-time code:
  Verification code: 318492
  This code expires in 10 minutes.
"""

MICROSOFT_VERIFY_EMAIL = """
  ID: 720253
  Subject: Microsoft account security code
  From: Microsoft account team <account-security-noreply@accountprotection.microsoft.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  Please use this security code for your Microsoft account:
  Security code: 6291845
  If you didn't request this code, you can safely ignore this email.
"""

STRIPE_VERIFY_EMAIL = """
  ID: 720254
  Subject: Your Stripe verification code
  From: Stripe <support@stripe.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  Use this code to complete sign in to Stripe Dashboard:
  Your verification code is: 719402
  Expires in 10 minutes.
"""

SUPABASE_VERIFY_EMAIL = """
  ID: 720255
  Subject: Confirm your signup to Supabase
  From: Supabase <noreply@mail.supabase.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  Welcome to Supabase!
  Your confirmation code is: 482019
"""

VERCEL_VERIFY_EMAIL = """
  ID: 720256
  Subject: Vercel Login Verification
  From: Vercel <registration@vercel.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  Please verify your login to Vercel.
  Verification code: 938471
"""

NOTION_VERIFY_EMAIL = """
  ID: 720257
  Subject: Your Notion login code
  From: Notion <notify@notion.so>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  We received a request to log in to Notion.
  Your temporary passcode is: 184920
"""

STEAM_GUARD_EMAIL = """
  ID: 720258
  Subject: Your Steam account: Access from new computer
  From: Steam Support <noreply@steampowered.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  Here is the Steam Guard code you need to login:
  Steam Guard code: 5K9P2
"""

SLACK_VERIFY_EMAIL = """
  ID: 720259
  Subject: Your Slack confirmation code
  From: Slack <feedback@slack.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  Here is your confirmation code:
  384-912
"""

UNIVERSAL_SAAS_EMAIL = """
  ID: 720260
  Subject: Login code for myapp.cloud
  From: MyApp Authentication <auth@myapp.cloud>
  To: alex.turner@acme-cloud.net
  Date: {date_str}
  Type: Email

  Enter the following verification code to log in: 772910.
  Expires in 10 minutes.
"""

UNIVERSAL_CHINESE_OTP_EMAIL = """
  ID: 720261
  Subject: 【某某平台】登录验证码通知
  From: 安全中心 <security@platform.cn>
  To: alex.turner@acme-cloud.net
  Date: {date_str}
  Type: Email

  您正在尝试登录系统，您的验证码为：839201。10分钟内有效，请勿向任何人泄露。
"""

UNIVERSAL_JAPANESE_OTP_EMAIL = """
  ID: 720262
  Subject: 【サービス】ログイン認証コードのお知らせ
  From: サポート窓口 <noreply@service.co.jp>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  いつもご利用いただきありがとうございます。
  認証コードは 618492 です。
  有効期限は10分間です。
"""

NON_OTP_RECEIPT_EMAIL = """
  ID: 720263
  Subject: Your order receipt #829104
  From: Store <orders@store.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  Thank you for your order #829104.
  Tracking code: 9948201.
  Total charged: $49.99.
"""

SAMPLE_SPARK_ACCOUNTS_OUTPUT = """
Email Account: alex.turner@example.com (Access: read-only)
├── Calendar: Alex's calendar - read-write ("alex.turner@example.com:Alex's calendar")

Email Account: marcus.vance@techcorp.io "marcus.vance@techcorp.io" (Access: read-only)

Email Account: alex.turner@acme-cloud.net "alex.turner@acme-cloud.net" (Access: read-only)
"""

ATLASSIAN_VERIFY_EMAIL = """
  ID: 720270
  Subject: Your Atlassian verification code
  From: Atlassian Security <noreply@atlassian.com>
  To: alex.turner@acme-cloud.net
  Date: {date_str}
  Type: Email

  Your verification code is: 581943.
  This code will expire in 10 minutes.
"""

SPACED_OTP_EMAIL = """
  ID: 720271
  Subject: Verification code for your account
  From: Secure Auth <auth@security-service.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  Your login verification code is: 482 109
  Expires in 10 minutes.
"""

JAPANESE_ONETIME_PASSWORD_EMAIL = """
  ID: 720272
  Subject: ワンタイムパスワードのご案内
  From: 会員サポート <support@portal.co.jp>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  ワンタイムパスワードは 925184 です。
  有効期限は10分間です。
"""

CHINESE_DYNAMIC_CODE_EMAIL = """
  ID: 720273
  Subject: 账号动态码通知
  From: 安全中心 <notify@service.cn>
  To: alex.turner@acme-cloud.net
  Date: {date_str}
  Type: Email

  本次登录动态码为：739102，10分钟内有效。
"""

REAL_BANDWAGON_VERIFY_EMAIL = """
Thread: Device verification
Messages: 1
Labels: alex.turner@example.com:Important
Link: https://sparkmailapp.com/dpl/bl?token=QTphbGV4LnR1cm5lckBnbWFpbC5jb207SUQ6bW9ja19zcGFya190b2tlbl9zYW1wbGVfMTIz
────────────────────────────────────────────────────────────────────────

  ID: 721250
  Subject: Device verification
  From: Bandwagon Host <noreply@64clouds.com>
  To: alex.turner@example.com
  Date: {date_str}
  Type: Email

  Your device verification code: 181174. It is valid for 1 hour. Do NOT share this code with anyone.
  
  Successful password authentication from:
  
  Google Chrome on macOS
  Austin, Texas, United States. IP: 198.51.100.42 [Business, Spectrum]
  
  
  Regards
  Bandwagon Host
"""



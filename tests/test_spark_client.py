import unittest
from unittest.mock import patch, MagicMock
from spark_otp.spark_client import parse_emails_table_output, parse_accounts_output, SparkClient
from spark_otp.models import EmailSummary
from tests.fixtures import SAMPLE_SPARK_ACCOUNTS_OUTPUT, REAL_CLOUDFLARE_FINANCE_EMAIL

RAW_EMAILS_OUTPUT = """
Emails in Unified Inbox

  ID      Account                 From                            Date              Subject                                             Flags
  720205  alex.turner@gmail.com   Cloudflare <noreply@notify.cl…  2026-09-07 19:35  Cloudflare Access login code for finance.acme-cloud.net…  
  720203  alex.turner@gmail.com   "マイナビスカウティング" <ags-support@my…  2026-09-07 19:03  【ピックアップ】編集部おススメ！関東の注目求人25選                          unread
  720198  alex.turner@gmail.com   Cloudflare <noreply@notify.cl…  2026-09-07 18:36  Cloudflare Access login code for status.acme-cloud.net…   unread

Page 1 of 67 (996 total emails)
"""

class TestSparkClient(unittest.TestCase):
    def test_parse_emails_table(self):
        emails = parse_emails_table_output(RAW_EMAILS_OUTPUT)
        self.assertEqual(len(emails), 3)
        
        self.assertEqual(emails[0].message_id, "720205")
        self.assertEqual(emails[0].account, "alex.turner@gmail.com")
        self.assertIn("Cloudflare", emails[0].sender)
        self.assertEqual(emails[0].date_str, "2026-09-07 19:35")
        self.assertIn("Cloudflare Access login code for finance.acme-cloud.net", emails[0].subject)

        self.assertEqual(emails[2].message_id, "720198")
        self.assertIn("status.acme-cloud", emails[2].subject)
        self.assertEqual(emails[2].flags, "unread")

    def test_parse_accounts_output(self):
        accounts = parse_accounts_output(SAMPLE_SPARK_ACCOUNTS_OUTPUT)
        self.assertEqual(len(accounts), 3)
        self.assertEqual(accounts[0], "alex.turner@gmail.com")
        self.assertEqual(accounts[1], "marcus.vance@techcorp.io")
        self.assertEqual(accounts[2], "alex.turner@acme-cloud.net")

    def test_parse_accounts_output_empty(self):
        accounts = parse_accounts_output("")
        self.assertEqual(accounts, [])

    @patch("subprocess.run")
    def test_spark_client_get_accounts(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=SAMPLE_SPARK_ACCOUNTS_OUTPUT)
        client = SparkClient(spark_bin="/usr/local/bin/spark", sqlite_path="disabled")
        accounts = client.get_accounts()
        self.assertEqual(len(accounts), 3)
        self.assertEqual(mock_run.call_count, 1)
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0][1], "accounts")

    @patch("subprocess.run")
    def test_spark_client_get_latest_otp_with_account(self, mock_run):
        from datetime import datetime
        fresh_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        raw_emails = RAW_EMAILS_OUTPUT.replace("2026-09-07 19:35", fresh_time)
        mock_emails_res = MagicMock(returncode=0, stdout=raw_emails)
        mock_thread_res = MagicMock(returncode=0, stdout=REAL_CLOUDFLARE_FINANCE_EMAIL.format(date_str=fresh_time))
        mock_run.side_effect = [mock_emails_res, mock_thread_res]

        client = SparkClient(spark_bin="/usr/local/bin/spark", sqlite_path="disabled")
        otp = client.get_latest_otp(
            domain="finance.acme-cloud.net",
            account="alex.turner@gmail.com",
            max_age_seconds=600
        )
        self.assertIsNotNone(otp)
        self.assertEqual(otp.code, "266134")
        self.assertEqual(otp.service, "cloudflare_access")

    @patch("subprocess.run")
    def test_spark_client_japanese_onetime_password_matching(self, mock_run):
        from datetime import datetime
        fresh_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        japanese_emails_table = f"""
Emails in Unified Inbox

  ID      Account                 From                            Date              Subject                                             Flags
  720272  alex.turner@gmail.com   会員サポート <support@portal.co.jp>  {fresh_time}  ワンタイムパスワードのご案内                                 unread
"""
        from tests.fixtures import JAPANESE_ONETIME_PASSWORD_EMAIL
        mock_emails_res = MagicMock(returncode=0, stdout=japanese_emails_table)
        mock_thread_res = MagicMock(returncode=0, stdout=JAPANESE_ONETIME_PASSWORD_EMAIL.format(date_str=fresh_time))
        mock_run.side_effect = [mock_emails_res, mock_thread_res]

        client = SparkClient(spark_bin="/usr/local/bin/spark", sqlite_path="disabled")
        otp = client.get_latest_otp(
            domain="portal.co.jp",
            max_age_seconds=600
        )
        self.assertIsNotNone(otp, "Japanese OTP email with ワンタイムパスワード in subject must be recognized and fetched")
        self.assertEqual(otp.code, "925184")

    @patch("subprocess.run")
    def test_spark_client_subdomain_brand_matching(self, mock_run):
        from datetime import datetime
        fresh_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        stripe_emails_table = f"""
Emails in Unified Inbox

  ID      Account                 From                            Date              Subject                                             Flags
  720254  alex.turner@gmail.com   Stripe <support@stripe.com>     {fresh_time}  Stripe 2FA Verification                             unread
"""
        from tests.fixtures import STRIPE_VERIFY_EMAIL
        mock_emails_res = MagicMock(returncode=0, stdout=stripe_emails_table)
        mock_thread_res = MagicMock(returncode=0, stdout=STRIPE_VERIFY_EMAIL.format(date_str=fresh_time))
        mock_run.side_effect = [mock_emails_res, mock_thread_res]

        client = SparkClient(spark_bin="/usr/local/bin/spark", sqlite_path="disabled")
        # When browsing dashboard.stripe.com, brand should be resolved to stripe, not dashboard!
        otp = client.get_latest_otp(
            domain="dashboard.stripe.com",
            max_age_seconds=600
        )
        self.assertIsNotNone(otp, "Subdomain dashboard.stripe.com must correctly match stripe emails")
        self.assertEqual(otp.code, "719402")

    @patch("subprocess.run")
    def test_spark_client_expired_date_fast_skip(self, mock_run):
        """Verify that expired emails are skipped instantly without calling `spark thread`."""
        expired_emails_table = """
Emails in Unified Inbox

  ID      Account                 From                            Date              Subject                                             Flags
  720254  alex.turner@gmail.com   Stripe <support@stripe.com>     2020-01-01 10:00  Stripe 2FA Verification                             unread
"""
        mock_emails_res = MagicMock(returncode=0, stdout=expired_emails_table)
        mock_run.return_value = mock_emails_res

        client = SparkClient(spark_bin="/usr/local/bin/spark", sqlite_path="disabled")
        otp = client.get_latest_otp(
            domain="stripe.com",
            max_age_seconds=600
        )
        self.assertIsNone(otp)
        # mock_run was called ONLY once (spark emails), and NEVER for `spark thread`
        self.assertEqual(mock_run.call_count, 1)

    def test_attachment_and_compound_flag_parsing(self):
        """Verify that 'attachment' and compound flags are cleanly stripped from subject and stored in flags."""
        table = """
Emails in alex.turner@acme-cloud.net

  ID      Account                      From                            Date              Subject                                             Flags
  720217  alex.turner@acme-cloud.net   mail <mail@direct-11.bk.mufg.jp> 2026-09-07 21:00  （三菱ＵＦＪ銀行）振込受付のお知らせ                                  attachment
  720211  alex.turner@acme-cloud.net   mail <mail@debit.bk.mufg.jp>    2026-09-07 20:10  【三菱ＵＦＪ‐ＶＩＳＡデビット】ご利用のお知らせ                            unread attachment
"""
        emails = parse_emails_table_output(table)
        self.assertEqual(len(emails), 2)
        self.assertEqual(emails[0].flags, "attachment")
        self.assertEqual(emails[0].subject, "（三菱ＵＦＪ銀行）振込受付のお知らせ")
        self.assertEqual(emails[1].flags, "unread attachment")
        self.assertEqual(emails[1].subject, "【三菱ＵＦＪ‐ＶＩＳＡデビット】ご利用のお知らせ")

    @patch("subprocess.run")
    def test_spark_client_unrelated_domain_thread_skip(self, mock_run):
        """Verify that recent OTP emails for other services are skipped without invoking spark thread."""
        from datetime import datetime
        fresh_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        emails_table = f"""
Emails in Unified Inbox

  ID      Account                 From                            Date              Subject                                             Flags
  720181  alex.turner@gmail.com   XinChaoVi Operations <hello@x…  {fresh_time}  [TidyCal Code: 182105] Verify your device on Tidy…  unread
  720198  alex.turner@gmail.com   Cloudflare <noreply@notify.cl…  {fresh_time}  Cloudflare Access login code for status.acme-cloud.net… unread
  719983  alex.turner@gmail.com   Surfshark <no-reply@account.s…  {fresh_time}  Your Surfshark 2FA code is 871330                   unread
"""
        mock_emails_res = MagicMock(returncode=0, stdout=emails_table)
        mock_run.return_value = mock_emails_res

        client = SparkClient(spark_bin="/usr/local/bin/spark", sqlite_path="disabled")
        # Querying for stripe.com when inbox only has TidyCal, Cloudflare, Surfshark
        otp = client.get_latest_otp(
            domain="stripe.com",
            max_age_seconds=600
        )
        self.assertIsNone(otp)
        # mock_run should ONLY be called once (for spark emails), and NEVER for spark thread!
        self.assertEqual(mock_run.call_count, 1)

    @patch("subprocess.run")
    def test_spark_client_bandwagon_host_detection(self, mock_run):
        """Verify that Bandwagon Host and bwh mirror domains successfully trigger thread fetch and OTP extraction."""
        from datetime import datetime
        fresh_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        emails_table = f"""
Emails in Unified Inbox

  ID      Account                 From                            Date              Subject                                             Flags
  721250  alex.turner@gmail.com   Bandwagon Host <noreply@64clo…  {fresh_time}  Device verification                                 
"""
        thread_content = f"""
  ID: 721250
  Subject: Device verification
  From: Bandwagon Host <noreply@64clouds.com>
  To: alex.turner@gmail.com
  Date: {fresh_time}
  Type: Email

  Your device verification code: 181174. It is valid for 1 hour. Do NOT share this code with anyone.
"""
        def fake_run(cmd, *args, **kwargs):
            if "emails" in cmd:
                return MagicMock(returncode=0, stdout=emails_table)
            elif "thread" in cmd:
                return MagicMock(returncode=0, stdout=thread_content)
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = fake_run
        client = SparkClient(spark_bin="/usr/local/bin/spark", sqlite_path="disabled")

        for d in ["bandwagonhost.com", "bwh81.net", "bwh88.net", "64clouds.com", "bawagon", "bawagon.com", "bwh81.com"]:
            otp = client.get_latest_otp(domain=d, max_age_seconds=600)
            self.assertIsNotNone(otp, f"Expected OTP for {d}")
            self.assertEqual(otp.code, "181174")
            self.assertEqual(otp.service, "bandwagon_auth")

    @patch("subprocess.run")
    def test_spark_client_account_fallback(self, mock_run):
        """Verify that querying an account with no matching OTP falls back to Unified Inbox."""
        from datetime import datetime
        fresh_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        empty_acc_table = """
Emails in dev.team@acme-cloud.net

  ID      Account                 From                            Date              Subject                                             Flags
  721242  dev.team@acme-cloud.net Guitar Tricks <admin@guitartr…  2026-09-08 20:05  FINAL HOURS: $99/year ends tonight at midnight      unread
"""
        unified_table = f"""
Emails in Unified Inbox

  ID      Account                 From                            Date              Subject                                             Flags
  721250  alex.turner@gmail.com   Bandwagon Host <noreply@64clo…  {fresh_time}  Device verification                                 
"""
        thread_content = f"""
  ID: 721250
  Subject: Device verification
  From: Bandwagon Host <noreply@64clouds.com>
  To: alex.turner@gmail.com
  Date: {fresh_time}
  Type: Email

  Your device verification code: 181174. It is valid for 1 hour. Do NOT share this code with anyone.
"""
        def fake_run(cmd, *args, **kwargs):
            if "emails" in cmd:
                if "dev.team@acme-cloud.net" in cmd:
                    return MagicMock(returncode=0, stdout=empty_acc_table)
                return MagicMock(returncode=0, stdout=unified_table)
            elif "thread" in cmd:
                return MagicMock(returncode=0, stdout=thread_content)
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = fake_run
        client = SparkClient(spark_bin="/usr/local/bin/spark", sqlite_path="disabled")

        # Querying specifically with account="dev.team@acme-cloud.net"
        otp = client.get_latest_otp(domain="bwh81.net", account="dev.team@acme-cloud.net")
        self.assertIsNotNone(otp)
        self.assertEqual(otp.code, "181174")
        self.assertEqual(otp.service, "bandwagon_auth")

    @patch("subprocess.run")
    def test_spark_client_targeted_filter_query(self, mock_run):
        """Verify that targeted rule filter query (e.g. from:64clouds.com) is executed first."""
        from datetime import datetime
        fresh_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        filtered_table = f"""
Emails in Unified Inbox (filter: from:64clouds.com)

  ID      Account                 From                            Date              Subject              Flags
  721250  alex.turner@gmail.com   Bandwagon Host <noreply@64clo…  {fresh_time}  Device verification  
"""
        thread_content = f"""
  ID: 721250
  Subject: Device verification
  From: Bandwagon Host <noreply@64clouds.com>
  To: alex.turner@gmail.com
  Date: {fresh_time}
  Type: Email

  Your device verification code: 181174. It is valid for 1 hour. Do NOT share this code with anyone.
"""
        executed_cmds = []
        def fake_run(cmd, *args, **kwargs):
            executed_cmds.append(cmd)
            if "emails" in cmd:
                return MagicMock(returncode=0, stdout=filtered_table)
            elif "thread" in cmd:
                return MagicMock(returncode=0, stdout=thread_content)
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = fake_run
        client = SparkClient(spark_bin="/usr/local/bin/spark", sqlite_path="disabled")
        otp = client.get_latest_otp(domain="bawagon", account="dev.team@acme-cloud.net")
        self.assertIsNotNone(otp)
        self.assertEqual(otp.code, "181174")

        # Verify that the very first emails command included the rule filter query
        first_emails_cmd = next(c for c in executed_cmds if "emails" in c)
        self.assertIn("--filter", first_emails_cmd)
        filter_idx = first_emails_cmd.index("--filter")
        filter_val = first_emails_cmd[filter_idx + 1]
        self.assertIn("from:64clouds.com", filter_val)
        self.assertIn("from:bandwagonhost.com", filter_val)

    @patch("subprocess.run")
    def test_spark_client_bandwagonhost_com_sender(self, mock_run):
        """Verify that emails sent from support@bandwagonhost.com or noreply@bandwagonhost.com match bandwagon_auth."""
        from datetime import datetime
        fresh_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        filtered_table = f"""
Emails in Unified Inbox (filter: from:64clouds.com OR from:bandwagonhost.com OR from:it7.net)

  ID      Account                 From                                Date              Subject              Flags
  721299  dev.team@acme-cloud.net Bandwagon Host <support@bandwagon…  {fresh_time}  Device verification  
"""
        thread_content = f"""
  ID: 721299
  Subject: Device verification
  From: Bandwagon Host <support@bandwagonhost.com>
  To: dev.team@acme-cloud.net
  Date: {fresh_time}
  Type: Email

  Your device verification code: 948201. It is valid for 1 hour. Do NOT share this code with anyone.
"""
        def fake_run(cmd, *args, **kwargs):
            if "emails" in cmd:
                return MagicMock(returncode=0, stdout=filtered_table)
            elif "thread" in cmd:
                return MagicMock(returncode=0, stdout=thread_content)
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = fake_run
        client = SparkClient(spark_bin="/usr/local/bin/spark", sqlite_path="disabled")
        otp = client.get_latest_otp(domain="bwh81.net", account="dev.team@acme-cloud.net")
        self.assertIsNotNone(otp)
        self.assertEqual(otp.code, "948201")
        self.assertEqual(otp.service, "bandwagon_auth")

if __name__ == "__main__":
    unittest.main()


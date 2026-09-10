"""
Spark CLI Client Wrapper.
"""
import os
import sqlite3
import subprocess
import shutil
import re
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from .models import EmailSummary, OTPResult
from .config import config, DEFAULT_RULES
from .extractor import extract_otp_from_thread, get_domain_brand, OTP_INTENT_PATTERN, parse_email_date, domain_matches

def parse_emails_table_output(raw_output: str) -> List[EmailSummary]:
    """Parse `spark emails` table output into EmailSummary items."""
    results = []
    lines = raw_output.splitlines()
    in_table = False
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("ID") and "Account" in stripped:
            in_table = True
            continue
        if stripped.startswith("Page ") or stripped.startswith("Emails in"):
            continue
        if not in_table:
            continue
            
        match = re.match(
            r"^\s*(\d+)\s+([^\s]+@[^\s]+|\"[^\"]+\")\s+(.*?)\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+(.*)$",
            line
        )
        if match:
            msg_id = match.group(1).strip()
            account = match.group(2).strip()
            sender = match.group(3).strip()
            date_str = match.group(4).strip()
            rest = match.group(5).strip()
            
            flags = ""
            flags_match = re.search(
                r"\s+((?:unread|read|starred|pinned|attachment|replied|forwarded|draft)(?:\s+(?:unread|read|starred|pinned|attachment|replied|forwarded|draft))*)$",
                rest,
                re.IGNORECASE
            )
            if flags_match:
                flags = flags_match.group(1).strip()
                subject = rest[:flags_match.start()].strip()
            else:
                subject = rest
                
            results.append(EmailSummary(
                message_id=msg_id,
                account=account,
                sender=sender,
                date_str=date_str,
                subject=subject,
                flags=flags
            ))
    return results

def parse_accounts_output(raw_output: str) -> List[str]:
    """Parse `spark accounts` output to extract email addresses."""
    accounts = []
    for line in raw_output.splitlines():
        match = re.search(r"Email Account:\s*([^\s@]+@[^\s@]+)", line)
        if match:
            acc = match.group(1).strip().strip('"')
            if acc not in accounts:
                accounts.append(acc)
    return accounts

class SparkClient:
    def __init__(self, spark_bin: Optional[str] = None, sqlite_path: Optional[str] = None):
        self.spark_bin = spark_bin if spark_bin is not None else config.spark_bin
        self.sqlite_path = sqlite_path
        if spark_bin is None and not shutil.which(self.spark_bin):
            found = shutil.which("spark")
            if found:
                self.spark_bin = found

    def _find_sqlite_db(self) -> Optional[Path]:
        """Locate Spark Desktop SQLite database on macOS."""
        target = self.sqlite_path if self.sqlite_path is not None else getattr(config, "sqlite_db_path", "auto")
        if target in ("disabled", "off", "0", ""):
            return None
        if target and target != "auto":
            p = Path(os.path.expanduser(target))
            if p.is_file() and os.access(p, os.R_OK):
                return p
            return None

        candidates = [
            Path(os.path.expanduser("~/Library/Application Support/Spark Mail/core-data/messages.sqlite")),
            Path(os.path.expanduser("~/Library/Containers/com.readdle.SparkDesktop-setapp/Data/Library/Application Support/Spark Mail/core-data/messages.sqlite")),
            Path(os.path.expanduser("~/Library/Application Support/Spark Mail Helper/core-data/messages.sqlite")),
        ]
        for p in candidates:
            if p.is_file() and os.access(p, os.R_OK):
                return p
        return None

    def _get_otp_from_sqlite(
        self,
        domain: Optional[str],
        max_age: int,
        account: Optional[str],
        current_time: datetime,
        exclude_codes: Optional[List[str]] = None,
        exclude_message_ids: Optional[List[str]] = None,
        since_time: Optional[float] = None
    ) -> Optional[OTPResult]:
        """
        Direct SQLite fast-path lookup (<5ms).
        Bypasses Spark CLI IPC latency, avoids thread deduplication bugs,
        and directly reads real-time incoming messages from Spark's local store.
        """
        db_path = self._find_sqlite_db()
        if not db_path:
            return None

        rule_max_ttl = max((r.default_ttl_seconds for r in config.rules), default=600)
        effective_max_age = max(max_age, rule_max_ttl)
        since_timestamp = current_time.timestamp() - effective_max_age
        if since_time is not None and since_time > since_timestamp:
            since_timestamp = since_time
        until_timestamp = current_time.timestamp() + 30.0

        try:
            uri = f"file:{db_path}?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=2.0) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT pk, messageFrom, messageTo, subject, shortBody, receivedDate, unseen
                    FROM messages
                    WHERE receivedDate >= ? AND receivedDate <= ?
                    ORDER BY receivedDate DESC
                    LIMIT 80
                    """,
                    (since_timestamp, until_timestamp)
                )
                rows = cursor.fetchall()
        except Exception:
            return None

        if not rows:
            return None

        # Sort messages matching preferred_account first, followed by others.
        # Recency-aware guard: if another account has an OTP that is substantially fresher
        # (>180s newer) than the target account's newest message, prioritize the fresh attempt
        # so a stale OTP from an old default account doesn't hijack a live login attempt.
        if account:
            acc_clean = account.strip().lower()
            matching_acc = [r for r in rows if r[2] and acc_clean in r[2].lower()]
            other_acc = [r for r in rows if not (r[2] and acc_clean in r[2].lower())]
            if matching_acc and other_acc:
                newest_match_ts = matching_acc[0][5]
                newest_other_ts = other_acc[0][5]
                if newest_other_ts > newest_match_ts + 180:
                    rows = other_acc + matching_acc
                else:
                    rows = matching_acc + other_acc
            elif matching_acc:
                rows = matching_acc
            else:
                rows = other_acc

        exclude_codes_set = set(str(c).strip().upper() for c in exclude_codes) if exclude_codes else set()
        exclude_msg_ids_set = set(str(m).strip() for m in exclude_message_ids) if exclude_message_ids else set()

        for pk, sender, recipient, subject, short_body, received_ts, unseen in rows:
            if exclude_msg_ids_set and str(pk) in exclude_msg_ids_set:
                continue
            if since_time is not None and received_ts <= since_time:
                continue
            sender = sender or ""
            recipient = recipient or ""
            subject = subject or ""
            short_body = short_body or ""
            dt_str = datetime.fromtimestamp(received_ts).strftime("%Y-%m-%d %H:%M:%S")

            thread_text = f"ID: {pk}\nSubject: {subject}\nFrom: {sender}\nTo: {recipient}\nDate: {dt_str}\n\n{short_body}\n"

            res = extract_otp_from_thread(
                thread_text=thread_text,
                domain_filter=domain,
                rules=config.rules,
                now=current_time,
                max_age_seconds=max_age
            )
            if res:
                if exclude_codes_set and res.code.strip().upper() in exclude_codes_set:
                    continue
                if exclude_msg_ids_set and res.message_id in exclude_msg_ids_set:
                    continue
                return res

            # If short_body was truncated or did not yield code, but domain/sender matches, fetch full thread
            if domain and domain_matches(domain, None, None, sender, subject, short_body):
                full_thread = self.fetch_thread(str(pk))
                if full_thread:
                    res_full = extract_otp_from_thread(
                        thread_text=full_thread,
                        domain_filter=domain,
                        rules=config.rules,
                        now=current_time,
                        max_age_seconds=max_age
                    )
                    if res_full:
                        if exclude_codes_set and res_full.code.strip().upper() in exclude_codes_set:
                            continue
                        if exclude_msg_ids_set and res_full.message_id in exclude_msg_ids_set:
                            continue
                        return res_full

        return None

    def is_available(self) -> bool:
        """Check if spark CLI or Spark SQLite database is available and responsive."""
        if self._find_sqlite_db() is not None:
            return True
        if not shutil.which(self.spark_bin):
            return False
        try:
            res = subprocess.run(
                [self.spark_bin, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return res.returncode == 0
        except Exception:
            return False

    def get_accounts(self) -> List[str]:
        """List all accounts configured in Spark Desktop."""
        try:
            res = subprocess.run(
                [self.spark_bin, "accounts"],
                capture_output=True,
                text=True,
                timeout=15
            )
            if res.returncode != 0:
                return []
            return parse_accounts_output(res.stdout)
        except Exception:
            return []

    def list_recent_emails(
        self,
        page_size: Optional[int] = None,
        folder: Optional[str] = None,
        filter_query: Optional[str] = None
    ) -> List[EmailSummary]:
        """Fetch recent emails from Unified Inbox or a specific folder/account."""
        ps = page_size if page_size is not None else getattr(config, "email_page_size", 35)
        try:
            cmd = [self.spark_bin, "emails", "--page-size", str(ps)]
            if filter_query:
                cmd.extend(["--filter", filter_query])
            if folder:
                cmd.append(folder)

            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )
            if res.returncode != 0:
                return []
            return parse_emails_table_output(res.stdout)
        except Exception:
            return []

    def fetch_thread(self, message_id: str) -> str:
        """Fetch thread details for a specific message ID."""
        try:
            res = subprocess.run(
                [self.spark_bin, "thread", str(message_id)],
                capture_output=True,
                text=True,
                timeout=15
            )
            if res.returncode != 0:
                return ""
            return res.stdout
        except Exception:
            return ""

    def _search_emails_for_otp(
        self,
        emails: List[EmailSummary],
        domain: Optional[str],
        max_age: int,
        current_time: datetime,
        preferred_account: Optional[str] = None,
        exclude_codes: Optional[List[str]] = None,
        exclude_message_ids: Optional[List[str]] = None,
        since_time: Optional[float] = None
    ) -> Optional[OTPResult]:
        df_clean = ""
        brand = ""
        if domain:
            df = domain.lower().strip()
            df_clean = re.sub(r"^https?://", "", df).split("/")[0].split(":")[0]
            df_clean = re.sub(r"^www\.", "", df_clean)
            brand = get_domain_brand(df_clean)

        # If a preferred account is specified, prioritize emails from that account
        sorted_emails = emails
        if preferred_account:
            pref = [e for e in emails if e.account == preferred_account]
            others = [e for e in emails if e.account != preferred_account]
            sorted_emails = pref + others

        exclude_codes_set = set(str(c).strip().upper() for c in exclude_codes) if exclude_codes else set()
        exclude_msg_ids_set = set(str(m).strip() for m in exclude_message_ids) if exclude_message_ids else set()

        for email in sorted_emails:
            if exclude_msg_ids_set and str(email.message_id) in exclude_msg_ids_set:
                continue
            # Pre-filter by summary date: if older than cutoff, skip instantly without calling thread fetch.
            # For domain-specific searches, allow a 2x TTL window (min 2 hours) to account for Spark CLI thread
            # summaries where root message timestamp is slightly older than recent reply/code.
            if email.date_str:
                parsed_date = parse_email_date(email.date_str)
                if parsed_date:
                    if since_time is not None and parsed_date.timestamp() <= since_time:
                        continue
                    age = (current_time - parsed_date).total_seconds()
                    allowed_cutoff = max(max_age * 2, 7200) if domain else max_age
                    if age > allowed_cutoff:
                        continue

            potential_match = False
            if domain:
                # 1. Check if associated with any known rule
                for rule in config.rules:
                    rule_matches_domain = False
                    if rule.associated_domains:
                        if (re.match(r"^(bwh\d*|bawagon|bandwagon)(\.[a-z]{2,})?$", df_clean) or brand in ("bawagon", "bandwagon")) and any(ad in ("bandwagonhost.com", "64clouds.com", "bwh81.net", "bawagon") for ad in rule.associated_domains):
                            rule_matches_domain = True
                        else:
                            for ad in rule.associated_domains:
                                ad = ad.lower()
                                if df_clean == ad or df_clean.endswith("." + ad) or ad.endswith("." + df_clean) or (len(brand) >= 3 and brand in ad):
                                    rule_matches_domain = True
                                    break
                    if rule_matches_domain and re.search(rule.sender_pattern, email.sender) and re.search(rule.subject_pattern, email.subject):
                        potential_match = True
                        break

                # 2. Cloudflare Access special case (authenticates arbitrary domains via subject)
                if not potential_match and re.search(r"(?i)cloudflare", email.sender):
                    cf_match = re.search(r"(?i)for\s+([a-zA-Z0-9\.-]+)", email.subject)
                    if cf_match:
                        cf_target = cf_match.group(1).lower().rstrip("….").strip()
                        if cf_target and (cf_target in df_clean or df_clean.startswith(cf_target)):
                            potential_match = True

                # 3. Check if clean domain or brand appears in sender or subject (with space collapsing)
                if not potential_match:
                    sender_lower = email.sender.lower()
                    subject_lower = email.subject.lower()
                    brand_clean = re.sub(r"[^a-z0-9]", "", brand)
                    sender_clean = re.sub(r"[^a-z0-9]", "", sender_lower)
                    subject_clean = re.sub(r"[^a-z0-9]", "", subject_lower)

                    if df_clean in sender_lower or df_clean in subject_lower:
                        potential_match = True
                    elif len(brand_clean) >= 3 and (brand_clean in sender_clean or brand_clean in subject_clean):
                        potential_match = True
                    elif (re.match(r"^(bwh\d*|bawagon)$", brand) or brand in ("bawagon", "bandwagon")) and any(alias in sender_clean or alias in subject_clean for alias in ("bandwagon", "bawagon", "64clouds", "kiwivm")):
                        potential_match = True
                    elif len(brand) >= 3 and (brand in sender_lower or brand in subject_lower):
                        # Verify no conflicting subdomain
                        parts = df_clean.split(".")
                        root_domain = ".".join(parts[-2:]) if len(parts) >= 2 else df_clean
                        if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "edu", "gov", "ac"} and len(parts[-1]) == 2:
                            root_domain = ".".join(parts[-3:])
                        conflicting = re.findall(r"([a-z0-9\.-]+\." + re.escape(root_domain) + r")", subject_lower)
                        if not any(cd != df_clean and not cd.startswith("www.") for cd in conflicting):
                            potential_match = True
            else:
                # No domain filter: any rule or OTP intent matches
                for rule in config.rules:
                    if re.search(rule.sender_pattern, email.sender) or re.search(rule.subject_pattern, email.subject):
                        potential_match = True
                        break
                
                if not potential_match and OTP_INTENT_PATTERN.search(email.subject):
                    potential_match = True

            if not potential_match:
                continue

            thread_text = self.fetch_thread(email.message_id)
            if not thread_text:
                continue

            otp_result = extract_otp_from_thread(
                thread_text=thread_text,
                domain_filter=domain,
                rules=config.rules,
                now=current_time,
                max_age_seconds=max_age
            )
            if otp_result:
                if exclude_codes_set and otp_result.code.strip().upper() in exclude_codes_set:
                    continue
                if exclude_msg_ids_set and otp_result.message_id in exclude_msg_ids_set:
                    continue
                return otp_result

        return None

    def get_latest_otp(
        self,
        domain: Optional[str] = None,
        max_age_seconds: Optional[int] = None,
        account: Optional[str] = None,
        now: Optional[datetime] = None,
        exclude_codes: Optional[List[str]] = None,
        exclude_message_ids: Optional[List[str]] = None,
        since_time: Optional[float] = None,
        **kwargs
    ) -> Optional[OTPResult]:
        """
        Finds the most recent matching OTP email and extracts code.
        Optimized multi-tiered search:
        1. Targeted rule filter query (runs in ~0.2s, immune to inbox noise/overflow).
        2. Unified Inbox listing with preferred account sorting.
        3. Specific account folder fallback if explicitly requested and not found in Unified Inbox.
        """
        max_age = max_age_seconds if max_age_seconds is not None else config.max_email_age_seconds
        page_size = getattr(config, "email_page_size", 35)
        current_time = now or kwargs.get("current_time") or datetime.now()

        matching_rule = None
        if domain:
            df = domain.lower().strip()
            df_clean = re.sub(r"^https?://", "", df).split("/")[0].split(":")[0]
            df_clean = re.sub(r"^www\.", "", df_clean)
            brand = get_domain_brand(df_clean)
            for rule in config.rules:
                if rule.associated_domains:
                    if (re.match(r"^(bwh\d*|bawagon|bandwagon)(\.[a-z]{2,})?$", df_clean) or brand in ("bawagon", "bandwagon")) and any(ad in ("bandwagonhost.com", "64clouds.com", "bwh81.net", "bawagon") for ad in rule.associated_domains):
                        matching_rule = rule
                        break
                    for ad in rule.associated_domains:
                        ad = ad.lower()
                        if df_clean == ad or df_clean.endswith("." + ad) or ad.endswith("." + df_clean) or (len(brand) >= 3 and brand in ad):
                            matching_rule = rule
                            break
                    if matching_rule:
                        break

        # Tier 0: Direct SQLite Fast-Path (<5ms, real-time message stream, immune to thread deduplication)
        sqlite_res = self._get_otp_from_sqlite(
            domain=domain,
            max_age=max_age,
            account=account,
            current_time=current_time,
            exclude_codes=exclude_codes,
            exclude_message_ids=exclude_message_ids,
            since_time=since_time
        )
        if sqlite_res:
            return sqlite_res

        # Tier 1: Targeted rule filter query (runs in ~0.2s, immune to inbox noise/overflow)
        if matching_rule and matching_rule.filter_query:
            filter_emails = self.list_recent_emails(page_size=15, folder=None, filter_query=matching_rule.filter_query)
            if filter_emails:
                res = self._search_emails_for_otp(
                    filter_emails,
                    domain,
                    max_age,
                    current_time,
                    preferred_account=account,
                    exclude_codes=exclude_codes,
                    exclude_message_ids=exclude_message_ids,
                    since_time=since_time
                )
                if res:
                    return res

        # Tier 2: Unified Inbox (contains all accounts, prioritized by preferred_account)
        unified_emails = self.list_recent_emails(page_size=max(page_size, 40), folder=None)
        if unified_emails:
            res = self._search_emails_for_otp(
                unified_emails,
                domain,
                max_age,
                current_time,
                preferred_account=account,
                exclude_codes=exclude_codes,
                exclude_message_ids=exclude_message_ids,
                since_time=since_time
            )
            if res:
                return res

        # Tier 3: Specific account mailbox fallback
        if account:
            acc_emails = self.list_recent_emails(page_size=page_size, folder=account)
            if acc_emails:
                res = self._search_emails_for_otp(
                    acc_emails,
                    domain,
                    max_age,
                    current_time,
                    exclude_codes=exclude_codes,
                    exclude_message_ids=exclude_message_ids,
                    since_time=since_time
                )
                if res:
                    return res

        return None

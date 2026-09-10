"""
Data contracts and models for Spark OTP Autofill.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List

@dataclass
class EmailSummary:
    message_id: str
    account: str
    sender: str
    date_str: str
    subject: str
    flags: str = ""

@dataclass
class OTPResult:
    code: str
    service: str
    domain: Optional[str]
    callback_url: Optional[str]
    message_id: str
    subject: str
    sender: str
    received_at: str  # ISO-8601 string
    expires_at: str   # ISO-8601 string
    is_expired: bool
    time_remaining_seconds: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class RuleDefinition:
    name: str
    sender_pattern: str
    subject_pattern: str
    code_regex: str
    callback_regex: Optional[str] = None
    domain_group: Optional[int] = None
    default_ttl_seconds: int = 600
    associated_domains: Optional[List[str]] = None
    filter_query: Optional[str] = None

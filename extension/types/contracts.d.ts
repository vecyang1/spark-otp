/**
 * Authoritative Type Contracts for Spark OTP Client (Chrome Extension & Userscript)
 * Generated from OpenAPI 3.0 / models.py schema contract.
 */

export interface OTPResult {
  code: string;
  service: string;
  domain: string | null;
  callback_url: string | null;
  message_id: string;
  subject: string;
  sender: string;
  received_at: string; // ISO-8601 string
  expires_at: string;  // ISO-8601 string
  is_expired: boolean;
  time_remaining_seconds: number;
}

export interface OTPResponse {
  success: boolean;
  otp?: OTPResult;
  message?: string;
  metrics: {
    duration_ms: number;
    timestamp: number;
  };
}

export interface HealthResponse {
  status: "ok" | "degraded" | "error";
  spark_available: boolean;
  timestamp: number;
  port: number;
  metrics: TelemetryMetrics;
}

export interface AccountListResponse {
  success: boolean;
  accounts: string[];
  count: number;
  metrics: {
    duration_ms: number;
  };
}

export interface TelemetryMetrics {
  uptime_seconds: number;
  total_requests: number;
  hits: number;
  misses: number;
  errors: number;
  hit_rate_pct: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  otp_total: number;
  otp_hits: number;
  otp_hit_rate_pct: number;
  otp_avg_latency_ms: number;
  kuma_configured: boolean;
  sentry_configured: boolean;
  log_file: string;
  recent_events?: Array<{
    timestamp: string;
    endpoint: string;
    duration_ms: number;
    status: "hit" | "miss" | "error";
    domain?: string | null;
    account?: string | null;
    service?: string | null;
    code_masked?: string | null;
    error?: string | null;
  }>;
}

export interface TelemetryResponse {
  success: boolean;
  telemetry: TelemetryMetrics;
}

export interface SparkOtpSettings {
  serverPort: number;
  autoSubmit: boolean;
  autoEmail: boolean;
  defaultEmail: string;
  selectedAccount: string;
  autoDirectJump: boolean;
}

export type PillState =
  | "hidden"
  | "watching"
  | "found"
  | "email_ready"
  | "code_failed"
  | "race_guarded"
  | "resend_sent"
  | "waiting_new_code"
  | "manual_required";

/** One candidate code observed by the content script, with its race-guard verdict. */
export interface RaceGuardCandidate {
  code: string | null;
  message_id: string | null;
  received_at: string | null;
  received_at_ms: number;
  received_at_human: string | null;
  /** accepted = newer than the lower bound and submitted; excluded_stale = older than the login-request bound; rejected = failed the page/blacklist checks */
  verdict: "accepted" | "excluded_stale" | "rejected";
  reason: string | null;
  since_time_ms: number;
  since_time: number;
  observed_at: number;
}

/** Per-domain login-attempt timeline rendered by the popup Page Detection Inspector. */
export interface RaceGuardReport {
  domain: string;
  email: string | null;
  login_request_at: number;
  login_request_at_iso: string | null;
  login_request_source: string | null;
  last_resend_at: number;
  last_resend_at_iso: string | null;
  last_resend_reason: string | null;
  resend_count: number;
  resend_limit: number;
  resend_cooldown_ms: number;
  resend_cooldown_remaining_ms: number;
  last_failed_at: number;
  last_failed_at_iso: string | null;
  last_failed_reason: string | null;
  page_load_at_ms: number;
  page_fallback_ms: number;
  since_time_ms: number;
  /** Effective lower bound (epoch seconds) sent to /api/otp and /api/stream as since_time. */
  since_time: number;
  since_source: "login_request" | "resend" | "page_fallback";
  failed_codes: string[];
  last_observation: RaceGuardCandidate | null;
  candidates: RaceGuardCandidate[];
}

/** Payload returned by the content script for SPARK_OTP_DIAGNOSE_PAGE. */
export interface PageDiagnosisReport {
  domain: string;
  frame_host: string;
  is_iframe: boolean;
  domain_disabled: boolean;
  email_only_mode: boolean;
  custom_blocked_terms: string[];
  detected_email: string | null;
  brand_hint: string | null;
  email_input_detected: boolean;
  otp_input_count: number;
  detected_channel: string;
  page_channel: string;
  page_rule_id: string;
  verdict: string;
  page_verdict: string;
  race_guard: RaceGuardReport;
  candidates: Array<{
    label: string;
    input_summary: string;
    qualified: boolean;
    disqualified: boolean;
    channel: string;
    rule_id: string;
    reason: string;
  }>;
}

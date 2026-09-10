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

export type PillState = "hidden" | "watching" | "found" | "email_ready";

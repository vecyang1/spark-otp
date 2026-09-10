"""
Authoritative Data Contracts and Schema Definitions for Spark OTP.
Serves as the Single Source of Truth (SSOT) for API contracts and generates
OpenAPI 3.0.3 and JSON Schema specifications.
"""
from typing import Dict, Any

OPENAPI_SPEC: Dict[str, Any] = {
    "openapi": "3.0.3",
    "info": {
        "title": "Spark OTP Bridge API",
        "description": "Local zero-LLM high-speed OTP extraction bridge for Spark Desktop",
        "version": "1.3.0"
    },
    "servers": [
        {"url": "http://127.0.0.1:9428", "description": "Localhost Daemon"}
    ],
    "paths": {
        "/api/health": {
            "get": {
                "summary": "Check daemon and Spark CLI health",
                "responses": {
                    "200": {
                        "description": "Health status",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"}
                            }
                        }
                    }
                }
            }
        },
        "/api/accounts": {
            "get": {
                "summary": "List configured Spark mail accounts",
                "responses": {
                    "200": {
                        "description": "Account list",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/AccountListResponse"}
                            }
                        }
                    }
                }
            }
        },
        "/api/otp": {
            "get": {
                "summary": "Retrieve latest OTP code for a domain or account",
                "parameters": [
                    {
                        "name": "domain",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "description": "Target website domain or shorthand (e.g. bandwagonhost.com, bawagon)"
                    },
                    {
                        "name": "account",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "description": "Specific email account (e.g. alex.turner@example.com)"
                    },
                    {
                        "name": "max_age",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer", "default": 600},
                        "description": "Maximum age of OTP in seconds"
                    },
                    {
                        "name": "exclude_codes",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "description": "Comma-separated list of known bad/rejected OTP codes to exclude"
                    },
                    {
                        "name": "exclude_message_ids",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "description": "Comma-separated list of message IDs to exclude"
                    },
                    {
                        "name": "since_time",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "number"},
                        "description": "Only return OTPs received strictly after this unix timestamp"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "OTP result (hit or miss)",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/OTPResponse"}
                            }
                        }
                    },
                    "500": {
                        "description": "Internal server error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        }
                    }
                }
            }
        },
        "/api/stream": {
            "get": {
                "summary": "Server-Sent Events (SSE) realtime push stream",
                "parameters": [
                    {
                        "name": "domain",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "account",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "max_age",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"}
                    },
                    {
                        "name": "exclude_codes",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "exclude_message_ids",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "since_time",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "number"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "SSE Event stream with event: otp and : keepalive",
                        "content": {
                            "text/event-stream": {
                                "schema": {"type": "string"}
                            }
                        }
                    }
                }
            }
        },
        "/api/telemetry": {
            "get": {
                "summary": "Get privacy-masked runtime metrics and rolling stats",
                "responses": {
                    "200": {
                        "description": "Telemetry metrics",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TelemetryResponse"}
                            }
                        }
                    }
                }
            }
        },
        "/api/schema": {
            "get": {
                "summary": "JSON Schema definitions for contracts",
                "responses": {
                    "200": {
                        "description": "Contract schemas",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        }
                    }
                }
            }
        },
        "/api/openapi.json": {
            "get": {
                "summary": "OpenAPI 3.0 specification",
                "responses": {
                    "200": {
                        "description": "Full OpenAPI document",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        }
                    }
                }
            }
        }
    },
    "components": {
        "schemas": {
            "OTPResult": {
                "type": "object",
                "required": [
                    "code", "service", "domain", "callback_url", "message_id",
                    "subject", "sender", "received_at", "expires_at",
                    "is_expired", "time_remaining_seconds"
                ],
                "properties": {
                    "code": {"type": "string", "example": "181174"},
                    "service": {"type": "string", "example": "bandwagon_auth"},
                    "domain": {"type": ["string", "null"], "example": "bandwagonhost.com"},
                    "callback_url": {"type": ["string", "null"], "example": None},
                    "message_id": {"type": "string", "example": "721250"},
                    "subject": {"type": "string", "example": "Device verification"},
                    "sender": {"type": "string", "example": "Bandwagon Host <noreply@auth.example.com>"},
                    "received_at": {"type": "string", "format": "date-time", "example": "2026-09-08T20:34:00"},
                    "expires_at": {"type": "string", "format": "date-time", "example": "2026-09-08T21:34:00"},
                    "is_expired": {"type": "boolean", "example": False},
                    "time_remaining_seconds": {"type": "integer", "example": 1778}
                }
            },
            "OTPResponse": {
                "type": "object",
                "required": ["success", "metrics"],
                "properties": {
                    "success": {"type": "boolean"},
                    "otp": {"$ref": "#/components/schemas/OTPResult"},
                    "message": {"type": "string"},
                    "metrics": {
                        "type": "object",
                        "properties": {
                            "duration_ms": {"type": "number"},
                            "timestamp": {"type": "number"}
                        }
                    }
                }
            },
            "HealthResponse": {
                "type": "object",
                "required": ["status", "spark_available", "timestamp", "port", "metrics"],
                "properties": {
                    "status": {"type": "string", "example": "ok"},
                    "spark_available": {"type": "boolean", "example": True},
                    "timestamp": {"type": "number"},
                    "port": {"type": "integer", "example": 9428},
                    "metrics": {"type": "object"}
                }
            },
            "AccountListResponse": {
                "type": "object",
                "required": ["success", "accounts", "count", "metrics"],
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "accounts": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "count": {"type": "integer", "example": 2},
                    "metrics": {
                        "type": "object",
                        "properties": {
                            "duration_ms": {"type": "number"}
                        }
                    }
                }
            },
            "TelemetryResponse": {
                "type": "object",
                "required": ["success", "telemetry"],
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "telemetry": {"type": "object"}
                }
            },
            "ErrorResponse": {
                "type": "object",
                "required": ["success", "error", "metrics"],
                "properties": {
                    "success": {"type": "boolean", "example": False},
                    "error": {"type": "string"},
                    "metrics": {"type": "object"}
                }
            }
        }
    }
}

SCHEMAS = OPENAPI_SPEC["components"]["schemas"]

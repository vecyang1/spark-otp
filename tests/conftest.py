import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

import pytest
from spark_otp.config import config
from spark_otp.telemetry import telemetry


@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch, tmp_path):
    """Ensure tests run in deterministic isolation without reading live macOS Spark SQLite
    or polluting production ~/.spark_otp/telemetry.jsonl."""
    isolated_log = tmp_path / "test_telemetry.jsonl"
    monkeypatch.setenv("SPARK_OTP_SQLITE_PATH", "disabled")
    monkeypatch.setenv("SPARK_OTP_LOG_PATH", str(isolated_log))
    config.sqlite_db_path = "disabled"
    config.log_path = str(isolated_log)
    prev_log_path = telemetry.log_file_path
    telemetry.log_file_path = Path(isolated_log)
    yield
    config.sqlite_db_path = os.environ.get("SPARK_OTP_SQLITE_PATH", "auto")
    config.log_path = os.environ.get("SPARK_OTP_LOG_PATH", None)
    telemetry.log_file_path = prev_log_path

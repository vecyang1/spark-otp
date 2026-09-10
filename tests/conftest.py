import os
import pytest
from spark_otp.config import config

@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch):
    """Ensure tests run in deterministic isolation without reading live macOS Spark SQLite by default."""
    monkeypatch.setenv("SPARK_OTP_SQLITE_PATH", "disabled")
    config.sqlite_db_path = "disabled"
    yield
    config.sqlite_db_path = os.environ.get("SPARK_OTP_SQLITE_PATH", "auto")

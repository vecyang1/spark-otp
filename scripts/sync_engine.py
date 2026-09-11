#!/usr/bin/env python3
"""
Single Source of Truth (SSOT) Synchronization Utility for Spark OTP.

Extracts the authoritative DOM detection engine from `extension/content.js`
and synchronizes it into `userscript/spark-otp.user.js`, ensuring zero drift,
zero ghost logic, and zero snippet rot across both targets.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_JS = REPO_ROOT / "extension" / "content.js"
USERSCRIPT_JS = REPO_ROOT / "userscript" / "spark-otp.user.js"

START_MARKER = "// === BEGIN CORE DOM DETECTION ENGINE (SSOT) ==="
END_MARKER = "// === END CORE DOM DETECTION ENGINE (SSOT) ==="

def extract_ssot_block(content: str) -> str:
    start_idx = content.find(START_MARKER)
    if start_idx == -1:
        raise ValueError(f"Start marker '{START_MARKER}' not found in source")
    end_idx = content.find(END_MARKER, start_idx)
    if end_idx == -1:
        raise ValueError(f"End marker '{END_MARKER}' not found in source")
    
    return content[start_idx:end_idx + len(END_MARKER)]

def sync(check_only: bool = False) -> bool:
    if not CONTENT_JS.exists():
        print(f"Error: {CONTENT_JS} not found", file=sys.stderr)
        return False
    if not USERSCRIPT_JS.exists():
        print(f"Error: {USERSCRIPT_JS} not found", file=sys.stderr)
        return False

    content_text = CONTENT_JS.read_text(encoding="utf-8")
    ssot_block = extract_ssot_block(content_text)

    userscript_text = USERSCRIPT_JS.read_text(encoding="utf-8")

    # If userscript already has markers, extract and compare
    if START_MARKER in userscript_text and END_MARKER in userscript_text:
        current_user_block = extract_ssot_block(userscript_text)
        if current_user_block == ssot_block:
            print("✓ SSOT Check Passed: extension/content.js and userscript/spark-otp.user.js are in 100% parity.")
            return True
        elif check_only:
            print("✗ SSOT Check FAILED: DOM detection engine in userscript drifted from extension/content.js!", file=sys.stderr)
            print("Run `python3 scripts/sync_engine.py` or `spark-otp sync` to synchronize.", file=sys.stderr)
            return False
        else:
            new_userscript = (
                userscript_text[:userscript_text.find(START_MARKER)]
                + ssot_block
                + userscript_text[userscript_text.find(END_MARKER) + len(END_MARKER):]
            )
            USERSCRIPT_JS.write_text(new_userscript, encoding="utf-8")
            print("✓ SSOT Synchronized: updated userscript/spark-otp.user.js from extension/content.js")
            return True
    else:
        # Initial injection: replace legacy block
        legacy_start = userscript_text.find("  function isInteractiveElement(el) {")
        legacy_end = userscript_text.find("  function setInputValue(input, value) {")
        if legacy_start == -1 or legacy_end == -1:
            raise ValueError("Could not find insertion points in userscript/spark-otp.user.js")

        new_userscript = (
            userscript_text[:legacy_start]
            + ssot_block + "\n\n"
            + userscript_text[legacy_end:]
        )
        USERSCRIPT_JS.write_text(new_userscript, encoding="utf-8")
        print("✓ SSOT Initialized: injected SSOT block into userscript/spark-otp.user.js")
        return True

if __name__ == "__main__":
    check_mode = "--check" in sys.argv
    success = sync(check_only=check_mode)
    sys.exit(0 if success else 1)

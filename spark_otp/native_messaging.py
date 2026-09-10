"""
Chrome Native Messaging Host for Spark OTP.
Allows Chrome Extension to query local Spark CLI directly via stdin/stdout without a background port.
"""
import sys
import json
import struct
import os
from .spark_client import SparkClient

def read_message():
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) < 4:
        return None
    message_length = struct.unpack("@I", raw_length)[0]
    message_bytes = sys.stdin.buffer.read(message_length)
    return json.loads(message_bytes.decode("utf-8"))

def send_message(message_dict):
    encoded = json.dumps(message_dict).encode("utf-8")
    length = struct.pack("@I", len(encoded))
    sys.stdout.buffer.write(length)
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()

def handle_native_messaging():
    client = SparkClient()
    while True:
        try:
            msg = read_message()
            if msg is None:
                break
            action = msg.get("action", "get_otp")
            domain = msg.get("domain")
            max_age = msg.get("max_age", 600)

            if action == "get_otp":
                otp = client.get_latest_otp(domain=domain, max_age_seconds=max_age)
                if otp:
                    send_message({"success": True, "otp": otp.to_dict()})
                else:
                    send_message({"success": False, "message": "No valid OTP found"})
            elif action == "health":
                send_message({"success": True, "spark_available": client.is_available()})
            else:
                send_message({"success": False, "error": f"Unknown action: {action}"})
        except Exception as e:
            send_message({"success": False, "error": str(e)})
            break

def install_host_manifest(extension_id: str = "*"):
    """Install native messaging manifest for Google Chrome on macOS."""
    manifest_dir = os.path.expanduser("~/Library/Application Support/Google/Chrome/NativeMessagingHosts")
    os.makedirs(manifest_dir, exist_ok=True)
    
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cli.py"))
    
    manifest = {
        "name": "com.spark_otp.native",
        "description": "Spark OTP Native Messaging Host",
        "path": sys.executable,
        "type": "stdio",
        "allowed_origins": [
            f"chrome-extension://{extension_id}/" if extension_id != "*" else "chrome-extension://*"
        ]
    }
    
    # Wrap with runner script if needed
    runner_path = os.path.join(manifest_dir, "spark_otp_host.sh")
    with open(runner_path, "w") as f:
        f.write(f"#!/usr/bin/env bash\nexec \"{sys.executable}\" \"{script_path}\" native\n")
    os.chmod(runner_path, 0o755)

    manifest["path"] = runner_path
    target_json = os.path.join(manifest_dir, "com.spark_otp.native.json")
    with open(target_json, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Native messaging manifest installed to {target_json}")
    return target_json

"""
CLI entry point for Spark OTP toolchain.
"""
import argparse
import sys
import json
import time
from .spark_client import SparkClient
from .server import create_server
from .config import config

def main():
    parser = argparse.ArgumentParser(
        prog="spark-otp",
        description="Extract and autofill email verification codes from Spark Desktop"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Command: get
    get_parser = subparsers.add_parser("get", help="Get the latest OTP code")
    get_parser.add_argument("--domain", "-d", help="Filter by target website domain (e.g. dashboard.stripe.com)")
    get_parser.add_argument("--account", "-A", help="Filter by specific email account (e.g. alex.turner@example.com)")
    get_parser.add_argument("--max-age", "-a", type=int, default=600, help="Max code age in seconds (default: 600)")
    get_parser.add_argument("--json", action="store_true", help="Output full JSON result")

    # Command: serve
    serve_parser = subparsers.add_parser("serve", help="Run local HTTP bridge daemon")
    serve_parser.add_argument("--host", default=config.host, help="Bind address (default: 127.0.0.1)")
    serve_parser.add_argument("--port", "-p", type=int, default=config.port, help="Bind port (default: 9428)")

    # Command: watch
    watch_parser = subparsers.add_parser("watch", help="Watch for incoming OTP codes in terminal")
    watch_parser.add_argument("--domain", "-d", help="Filter by target website domain")
    watch_parser.add_argument("--account", "-A", help="Filter by specific email account")
    watch_parser.add_argument("--interval", "-i", type=float, default=2.0, help="Check interval in seconds")

    # Command: accounts
    subparsers.add_parser("accounts", help="List all email accounts configured in Spark Desktop")

    # Command: health
    subparsers.add_parser("health", help="Check Spark CLI readiness")

    # Command: schema
    subparsers.add_parser("schema", help="Output JSON Schemas for API contracts")

    # Command: openapi
    subparsers.add_parser("openapi", help="Output OpenAPI 3.0 specification")

    # Command: daemon
    daemon_parser = subparsers.add_parser("daemon", help="Manage background daemon service")
    daemon_parser.add_argument("action", choices=["start", "stop", "restart", "status", "logs", "enable-autostart", "disable-autostart"], help="Daemon action")

    # Command: native
    subparsers.add_parser("native", help="Run Chrome Native Messaging stdio host")

    # Command: install-native
    inst_parser = subparsers.add_parser("install-native", help="Install Chrome Native Messaging Host manifest")
    inst_parser.add_argument("--extension-id", default="*", help="Allowed Chrome Extension ID (default: *)")

    args = parser.parse_args()

    if not args.command or args.command == "get":
        domain = getattr(args, "domain", None)
        account = getattr(args, "account", None)
        max_age = getattr(args, "max_age", 600)
        as_json = getattr(args, "json", False)

        client = SparkClient()
        if not client.is_available():
            print("Error: Spark CLI is not available. Please ensure Spark Desktop is running.", file=sys.stderr)
            sys.exit(1)

        otp = client.get_latest_otp(domain=domain, max_age_seconds=max_age, account=account)
        if not otp:
            if as_json:
                print(json.dumps({"success": False, "message": "No valid OTP found"}))
            else:
                print(f"No valid OTP found for domain: {domain or 'any'} (account: {account or 'all'})")
            sys.exit(1)

        if as_json:
            print(json.dumps({"success": True, "otp": otp.to_dict()}, indent=2))
        else:
            print(otp.code)
            if otp.callback_url:
                print(f"Callback URL: {otp.callback_url}")

    elif args.command == "serve":
        client = SparkClient()
        print(f"Starting Spark OTP bridge on http://{args.host}:{args.port}...")
        server = create_server(host=args.host, port=args.port, client=client)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
            server.server_close()

    elif args.command == "watch":
        client = SparkClient()
        account = getattr(args, "account", None)
        print(f"Watching Spark for OTP codes (domain: {args.domain or 'all'}, account: {account or 'all'})... Press Ctrl+C to stop.")
        last_id = None
        try:
            while True:
                otp = client.get_latest_otp(domain=args.domain, max_age_seconds=600, account=account)
                if otp and otp.message_id != last_id:
                    last_id = otp.message_id
                    print(f"\n[OTP DETECTED] Code: {otp.code} | Domain: {otp.domain} | Sender: {otp.sender}")
                    if otp.callback_url:
                        print(f"  Callback: {otp.callback_url}")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped watching.")

    elif args.command == "accounts":
        client = SparkClient()
        accounts = client.get_accounts()
        if not accounts:
            print("No accounts found or Spark CLI unavailable.")
            sys.exit(1)
        print("Configured Spark Accounts:")
        for acc in accounts:
            print(f"  • {acc}")

    elif args.command == "health":
        client = SparkClient()
        ready = client.is_available()
        print(f"Spark CLI available: {ready} ({client.spark_bin})")
        sys.exit(0 if ready else 1)

    elif args.command == "schema":
        from .contracts import SCHEMAS
        print(json.dumps(SCHEMAS, indent=2))

    elif args.command == "openapi":
        from .contracts import OPENAPI_SPEC
        print(json.dumps(OPENAPI_SPEC, indent=2))

    elif args.command == "daemon":
        import subprocess
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent / "scripts" / "manage_daemon.sh"
        if not script.exists():
            print(f"Error: Daemon script not found at {script}", file=sys.stderr)
            sys.exit(1)
        res = subprocess.run(["bash", str(script), args.action])
        sys.exit(res.returncode)

    elif args.command == "native":
        from .native_messaging import handle_native_messaging
        handle_native_messaging()

    elif args.command == "install-native":
        from .native_messaging import install_host_manifest
        install_host_manifest(args.extension_id)

if __name__ == "__main__":
    main()

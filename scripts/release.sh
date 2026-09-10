#!/usr/bin/env bash
# Spark OTP Release Packaging & Publishing Helper
# Delegates to canonical github-ops publish_release.py tool

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLISH_SCRIPT="${HOME}/.gemini/config/skills/github-ops/scripts/publish_release.py"

if [[ ! -f "$PUBLISH_SCRIPT" ]]; then
  echo "ERROR: Canonical github-ops release tool not found at $PUBLISH_SCRIPT" >&2
  exit 1
fi

TAG="${1:-}"
if [[ -z "$TAG" ]]; then
  echo "Usage: ./scripts/release.sh <tag> [additional args...]"
  echo "Example: ./scripts/release.sh v1.3.4"
  exit 1
fi
shift

python3 "$PUBLISH_SCRIPT" \
  --repo "$REPO_DIR" \
  --tag "$TAG" \
  --assets "$REPO_DIR/extension" "$REPO_DIR/userscript/spark-otp.user.js" \
  --allow-emails "example.com" "gmail.com" "acme-cloud.net" "stripe-auth.com" "cloudflare.com" "bandwagonhost.com" "64clouds.com" "fedex.com" "adobe.com" "sentry.io" "nowhere.com" "domain.com" "albato.com" "cloudservice.com" "oakridge.edu" "notify.cl" \
  "$@"

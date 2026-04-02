#!/usr/bin/env bash
# Deploy mundmaus.de website to server.
# Usage: tools/deploy-website.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEBSITE_DIR="$(dirname "$SCRIPT_DIR")/website"
REMOTE="mbs:/srv/mundmaus/"

echo "Deploying mundmaus.de..."
rsync -av --delete --exclude='ota' "$WEBSITE_DIR/" "$REMOTE"
echo "Done. Check: https://mundmaus.de"

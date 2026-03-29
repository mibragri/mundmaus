#!/usr/bin/env bash
# Deploy mundmaus.de static site to MBS server.
# Replaces WordPress Docker with static files served by Caddy.
#
# Usage: deploy.sh [--skip-wp-stop]

set -euo pipefail

MBS="mbs"
SITE_DIR="site"
REMOTE_DIR="/srv/mundmaus"
CADDY_FILE="/home/mbraig/docker/shared/Caddyfile"
DOMAIN="mundmaus.de"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
fail()  { echo -e "${RED}[x]${NC} $1"; exit 1; }

SKIP_WP_STOP=false
[[ "${1:-}" == "--skip-wp-stop" ]] && SKIP_WP_STOP=true

# ── Pre-flight ──────────────────────────────────────────────────
info "Pre-flight checks..."

[[ -d "$SITE_DIR" ]] || fail "Site directory '$SITE_DIR' not found"
[[ -f "$SITE_DIR/index.html" ]] || fail "index.html not found in $SITE_DIR"
[[ -f "$SITE_DIR/styles.css" ]] || fail "styles.css not found in $SITE_DIR"
[[ -d "$SITE_DIR/fonts" ]] || fail "fonts/ directory not found in $SITE_DIR"

ssh -q "$MBS" "echo ok" || fail "Cannot SSH to $MBS"
info "SSH to $MBS: OK"

# ── Create remote directory ─────────────────────────────────────
info "Creating remote directory $REMOTE_DIR..."
ssh "$MBS" "sudo mkdir -p $REMOTE_DIR && sudo chown mbraig:mbraig $REMOTE_DIR"

# ── Sync static files ───────────────────────────────────────────
info "Syncing site files..."
rsync -avz --delete "$SITE_DIR/" "$MBS:$REMOTE_DIR/"
info "Files synced to $MBS:$REMOTE_DIR/"

# ── Backup Caddyfile ────────────────────────────────────────────
info "Backing up Caddyfile..."
ssh "$MBS" "cp $CADDY_FILE ${CADDY_FILE}.bak.mundmaus.\$(date +%Y%m%d_%H%M%S)"

# ── Update Caddyfile ────────────────────────────────────────────
info "Updating Caddy config for $DOMAIN..."

ssh "$MBS" python3 - "$CADDY_FILE" "$DOMAIN" "$REMOTE_DIR" <<'PYEOF'
import sys

caddyfile, domain, site_dir = sys.argv[1], sys.argv[2], sys.argv[3]

with open(caddyfile, 'r') as f:
    content = f.read()

new_block = f"""{domain}, www.{domain} {{
    root * {site_dir}
    file_server
    encode gzip
}}"""

# Find the domain block by tracking brace depth
lines = content.split('\n')
start_idx = None
end_idx = None
depth = 0
for i, line in enumerate(lines):
    if start_idx is None and domain in line and '{' in line:
        start_idx = i
        depth = line.count('{') - line.count('}')
        if depth == 0:
            end_idx = i
            break
    elif start_idx is not None:
        depth += line.count('{') - line.count('}')
        if depth <= 0:
            end_idx = i
            break

if start_idx is not None and end_idx is not None:
    lines[start_idx:end_idx+1] = new_block.split('\n')
    print(f"Replaced existing {domain} block (lines {start_idx}-{end_idx})")
else:
    lines.append('')
    lines.extend(new_block.split('\n'))
    print(f"Added new {domain} block")

with open(caddyfile, 'w') as f:
    f.write('\n'.join(lines))
PYEOF

# ── Validate and reload Caddy ───────────────────────────────────
info "Validating Caddy config..."
ssh "$MBS" "sudo docker exec caddy caddy validate --config /etc/caddy/Caddyfile" || fail "Caddy config invalid!"

info "Reloading Caddy..."
ssh "$MBS" "sudo docker exec caddy caddy reload --config /etc/caddy/Caddyfile"

# ── Stop WordPress containers ───────────────────────────────────
if [[ "$SKIP_WP_STOP" == false ]]; then
    info "Stopping mundmaus WordPress containers..."
    ssh "$MBS" "cd /home/mbraig/docker/mundmaus 2>/dev/null && sudo docker compose stop 2>/dev/null" || warn "No WordPress containers found (already stopped?)"
else
    warn "Skipping WordPress stop (--skip-wp-stop)"
fi

# ── Smoke test ──────────────────────────────────────────────────
info "Smoke test..."
sleep 2
HTTP_CODE=$(ssh "$MBS" "curl -s -o /dev/null -w '%{http_code}' http://localhost:80 -H 'Host: $DOMAIN'" 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" == "200" ]]; then
    info "Smoke test passed (HTTP $HTTP_CODE)"
else
    warn "Smoke test returned HTTP $HTTP_CODE (might need DNS or external check)"
fi

# ── Done ────────────────────────────────────────────────────────
echo ""
info "Deploy complete!"
info "  Site: https://$DOMAIN"
info "  Files: $MBS:$REMOTE_DIR"
info "  Caddy: reloaded"
echo ""

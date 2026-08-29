#!/usr/bin/env bash
# Deploy mundmaus.de website to server.
# Usage: tools/deploy-website.sh [--yes]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEBSITE_DIR="$(dirname "$SCRIPT_DIR")/website"
REMOTE="mbs:/srv/mundmaus/"

# Pre-flight: game completeness check
if ! bash "$SCRIPT_DIR/check-games.sh"; then
    echo "ERROR: Game check failed. Fix missing items before deploying."
    exit 1
fi

# Pre-flight: the source tree must actually contain the site.
#
# `rsync --delete` against an empty or half-populated website/ removes the live
# site and still exits 0 — an interrupted checkout or one of this project's
# agent worktrees is enough to produce that. A *missing* directory is safe
# (rsync exits 23 and set -e fires); an empty one is not. check-games.sh only
# greps website/index.html, so styles.css, the legal pages, img/ and fonts/ were
# entirely unguarded.
for required in index.html styles.css datenschutz.html impressum.html; do
    if [[ ! -s "$WEBSITE_DIR/$required" ]]; then
        echo "ERROR: $WEBSITE_DIR/$required is missing or empty — refusing to deploy."
        echo "       --delete would strip it from the live site."
        exit 1
    fi
done
for required_dir in img fonts; do
    if ! compgen -G "$WEBSITE_DIR/$required_dir/*" > /dev/null; then
        echo "ERROR: $WEBSITE_DIR/$required_dir/ is missing or empty — refusing to deploy."
        exit 1
    fi
done

# '/ota/' is anchored: it protects the OTA tree at the deploy root, rather than
# any directory named 'ota' at any depth.
RSYNC_ARGS=(-av --delete --exclude='/ota/')

echo "Deploying mundmaus.de..."
echo "--- dry run (nothing changed yet) ---"
rsync "${RSYNC_ARGS[@]}" --dry-run "$WEBSITE_DIR/" "$REMOTE"

if [[ "${1:-}" != "--yes" ]]; then
    read -rp "Apply the above to the LIVE site? [y/N] " reply
    if [[ "$reply" != "y" && "$reply" != "Y" ]]; then
        echo "Aborted — nothing was changed."
        exit 1
    fi
fi

rsync "${RSYNC_ARGS[@]}" "$WEBSITE_DIR/" "$REMOTE"
echo "Done. Check: https://mundmaus.de"

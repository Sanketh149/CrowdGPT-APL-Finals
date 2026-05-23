#!/usr/bin/env bash
# Paste your GitHub PAT below (Settings → Developer settings → Personal access tokens → Classic)
# Scopes needed: repo
GITHUB_PAT="PASTE_YOUR_PAT_HERE"

REPO="https://${GITHUB_PAT}@github.com/Sanketh149/CrowdGPT-APL-Finals.git"

cd "$(dirname "$0")"
git remote set-url origin "$REPO"
git push -u origin main
echo "Done! Reset remote to HTTPS (without token)"
git remote set-url origin "https://github.com/Sanketh149/CrowdGPT-APL-Finals.git"

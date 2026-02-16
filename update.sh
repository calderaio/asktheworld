#!/bin/bash
# Fetches fresh data from Reddit and pushes to GitHub Pages.
# Run from anywhere: ./update.sh

set -e
cd "$(dirname "$0")"

# Use Homebrew python3 (cron uses a minimal PATH)
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting update..."

echo "Fetching fresh data from r/AskTheWorld..."
python3 fetch.py

echo ""
echo "Pushing to GitHub..."
git add data.json
git diff --staged --quiet && echo "No changes to push." && exit 0
git commit -m "Update data.json $(date '+%Y-%m-%d %H:%M')"

# Use gh CLI for auth (works without keyring access in cron)
GH_TOKEN=$(gh auth token 2>/dev/null || true)
if [ -n "$GH_TOKEN" ]; then
  git -c "http.https://github.com/.extraheader=Authorization: basic $(echo -n "x-access-token:$GH_TOKEN" | base64)" push
else
  git push
fi

echo ""
echo "Done! Site will deploy in ~30 seconds."

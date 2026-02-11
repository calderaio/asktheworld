#!/bin/bash
# Fetches fresh data from Reddit and pushes to GitHub Pages.
# Run from anywhere: ./update.sh

set -e
cd "$(dirname "$0")"

echo "Fetching fresh data from r/AskTheWorld..."
python3 fetch.py

echo ""
echo "Pushing to GitHub..."
git add data.json
git diff --staged --quiet && echo "No changes to push." && exit 0
git commit -m "Update data.json $(date '+%Y-%m-%d %H:%M')"
git push

echo ""
echo "Done! Site will deploy in ~30 seconds."

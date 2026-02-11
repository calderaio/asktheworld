#!/usr/bin/env python3
"""
Fetches top posts and comments from r/AskTheWorld and outputs data.json
for the map visualization.

Uses PRAW (Reddit OAuth API) for reliable access with proper rate limits.
Set these environment variables:
  REDDIT_CLIENT_ID
  REDDIT_CLIENT_SECRET
"""

import json
import os
import re
import sys

import praw

SUBREDDIT = "AskTheWorld"
NUM_POSTS = 5
BASE = "https://www.reddit.com"

# Mapping from flair country names to GeoJSON country names
FLAIR_TO_GEOJSON = {
    "Korea South": "South Korea",
    "Korea North": "North Korea",
    "Czech Republic": "Czech Republic",
    "Czechia": "Czech Republic",
    "USA": "United States of America",
    "United States": "United States of America",
    "US": "United States of America",
    "UK": "United Kingdom",
    "England": "United Kingdom",
    "Scotland": "United Kingdom",
    "Wales": "United Kingdom",
    "Northern Ireland": "United Kingdom",
    "Bosnia": "Bosnia and Herzegovina",
    "DR Congo": "Democratic Republic of the Congo",
    "Congo": "Republic of the Congo",
    "Russia": "Russian Federation",
    "Taiwan": "Taiwan",
    "Palestine": "Palestine",
    "Ivory Coast": "Ivory Coast",
    "Cote d'Ivoire": "Ivory Coast",
    "Turkiye": "Turkey",
    "Türkiye": "Turkey",
}


def extract_country(flair_text):
    """Extract country name from flair like ':india: India' or just 'India'."""
    if not flair_text:
        return None
    text = re.sub(r":[a-z_]+:", "", flair_text).strip()
    text = re.sub(r"[\U0001F1E0-\U0001F1FF\U0001F3F4\U000E0061-\U000E007F]+", "", text)
    text = re.sub(r"[\U0001F300-\U0001F9FF\u2600-\u27BF]+", "", text)
    text = text.strip()
    if not text:
        return None
    skip_patterns = [
        "living in", "in ", "->", "multiple", "the milky way",
        "proudly", "regretfully", "48 arab"
    ]
    lower = text.lower()
    for pat in skip_patterns:
        if lower.startswith(pat):
            return None
    if "," in text:
        parts = [p.strip() for p in text.split(",")]
        for part in reversed(parts):
            if part in FLAIR_TO_GEOJSON:
                return FLAIR_TO_GEOJSON[part]
            if len(part) > 2 and not any(c.isdigit() for c in part):
                text = part
                break
    if "/" in text:
        text = text.split("/")[0].strip()
    if " in " in text:
        text = text.split(" in ")[0].strip()
    text = re.sub(r"\(.*?\)", "", text).strip()
    text = text.strip(" -–—·•")
    if not text or len(text) < 2:
        return None
    return FLAIR_TO_GEOJSON.get(text, text)


def process_comments(submission):
    """Get the best comment per country from a submission."""
    submission.comment_sort = "top"
    submission.comments.replace_more(limit=0)

    best = {}
    for comment in submission.comments:
        if comment.body in ("[removed]", "[deleted]"):
            continue
        body = comment.body.strip()
        if len(body) < 20 or body.startswith("http"):
            continue

        country = extract_country(comment.author_flair_text)
        if not country:
            continue

        if country not in best or comment.score > best[country]["upvotes"]:
            if len(body) > 500:
                body = body[:497] + "..."
            best[country] = {
                "comment": body,
                "author": f"u/{comment.author.name}" if comment.author else "[deleted]",
                "upvotes": comment.score,
                "permalink": f"{BASE}{comment.permalink}",
            }
    return best


def main():
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Error: Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables.")
        print("Create an app at https://www.reddit.com/prefs/apps (select 'script' type).")
        sys.exit(1)

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent="AskTheWorldMap/2.0 (GitHub Actions bot)",
    )

    subreddit = reddit.subreddit(SUBREDDIT)
    print(f"Fetching top posts from r/{SUBREDDIT}...")

    # Get hot posts, sorted by most comments
    posts = list(subreddit.hot(limit=15))
    posts = [p for p in posts if not p.stickied]
    posts.sort(key=lambda p: p.num_comments, reverse=True)
    selected = posts[:NUM_POSTS]

    output = []
    for i, submission in enumerate(selected):
        print(f"\n[{i+1}/{len(selected)}] {submission.title[:70]}...")
        print(f"  {submission.num_comments} comments, score {submission.score}")

        countries = process_comments(submission)
        print(f"  Found {len(countries)} countries")

        output.append({
            "post_title": submission.title,
            "post_url": f"{BASE}{submission.permalink}",
            "countries": countries,
        })

    # Write to the directory where the script lives (for GitHub Actions)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(script_dir, "data.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    total_countries = set()
    for post in output:
        total_countries.update(post["countries"].keys())
    print(f"\nDone! Saved {len(output)} posts with {len(total_countries)} unique countries to {out_path}")


if __name__ == "__main__":
    main()

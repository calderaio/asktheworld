#!/usr/bin/env python3
"""
Fetches top posts and comments from r/AskTheWorld and outputs data.json
for the map visualization.

Uses Reddit's public .json endpoints (no API key needed).
Rate-limited to be respectful.
"""

import json
import os
import re
import time
import urllib.request

SUBREDDIT = "AskTheWorld"
NUM_POSTS = 5
BASE = "https://www.reddit.com"
USER_AGENT = "AskTheWorldMap/1.0 (educational project; GitHub Actions bot)"

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


def fetch_json(url):
    """Fetch JSON from Reddit."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


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


def fetch_comments(permalink):
    """Fetch top-level comments for a post, sorted by top."""
    url = f"{BASE}{permalink}.json?sort=top&limit=500"
    data = fetch_json(url)
    comments = data[1]["data"]["children"]

    best = {}
    for c in comments:
        if c["kind"] != "t1":
            continue
        d = c["data"]
        if d.get("body") in ("[removed]", "[deleted]"):
            continue
        body = d["body"].strip()
        if len(body) < 20 or body.startswith("http"):
            continue

        country = extract_country(d.get("author_flair_text"))
        if not country:
            continue

        if country not in best or d["score"] > best[country]["upvotes"]:
            if len(body) > 500:
                body = body[:497] + "..."
            best[country] = {
                "comment": body,
                "author": f"u/{d['author']}",
                "upvotes": d["score"],
                "permalink": f"{BASE}{d['permalink']}",
            }
    return best


def main():
    print(f"Fetching top posts from r/{SUBREDDIT}...")
    url = f"{BASE}/r/{SUBREDDIT}/hot.json?limit=15"
    data = fetch_json(url)

    posts = []
    for p in data["data"]["children"]:
        d = p["data"]
        if d.get("stickied"):
            continue
        posts.append({
            "title": d["title"],
            "permalink": d["permalink"],
            "url": f"{BASE}{d['permalink']}",
            "score": d["score"],
            "num_comments": d["num_comments"],
        })

    posts.sort(key=lambda p: p["num_comments"], reverse=True)
    selected = posts[:NUM_POSTS]

    output = []
    for i, post in enumerate(selected):
        print(f"\n[{i+1}/{len(selected)}] {post['title'][:70]}...")
        print(f"  {post['num_comments']} comments, score {post['score']}")

        countries = fetch_comments(post["permalink"])
        print(f"  Found {len(countries)} countries")

        output.append({
            "post_title": post["title"],
            "post_url": post["url"],
            "countries": countries,
        })

        # Rate limit: be respectful
        if i < len(selected) - 1:
            time.sleep(3)

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

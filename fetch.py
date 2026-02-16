#!/usr/bin/env python3
"""
Fetches top posts and comments from r/AskTheWorld and outputs data.json
for the map visualization.

Uses PRAW (Reddit OAuth) when REDDIT_CLIENT_ID is set (for GitHub Actions).
Falls back to public .json endpoints for local development.
"""

import json
import os
import re
import sys
import time
import urllib.request

SUBREDDIT = "AskTheWorld"
NUM_POSTS = 10
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


def best_comment(existing, body, author, score, permalink):
    """Update best-per-country dict if this comment is better."""
    if len(body) > 500:
        body = body[:497] + "..."
    return {
        "comment": body,
        "author": author,
        "upvotes": score,
        "permalink": permalink,
    }


# ---------- PRAW-based fetching (for GitHub Actions) ----------

def fetch_with_praw():
    import praw

    client_id = os.environ["REDDIT_CLIENT_ID"]
    client_secret = os.environ["REDDIT_CLIENT_SECRET"]

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=USER_AGENT,
    )

    subreddit = reddit.subreddit(SUBREDDIT)
    print(f"Fetching top posts from r/{SUBREDDIT} (via PRAW)...")

    posts = [p for p in subreddit.hot(limit=15) if not p.stickied]
    posts.sort(key=lambda p: p.num_comments, reverse=True)
    selected = posts[:NUM_POSTS]

    output = []
    for i, submission in enumerate(selected):
        print(f"\n[{i+1}/{len(selected)}] {submission.title[:70]}...")
        print(f"  {submission.num_comments} comments, score {submission.score}")

        submission.comment_sort = "top"
        submission.comments.replace_more(limit=0)

        countries = {}
        for comment in submission.comments:
            if comment.body in ("[removed]", "[deleted]"):
                continue
            body = comment.body.strip()
            if len(body) < 20 or body.startswith("http"):
                continue
            country = extract_country(comment.author_flair_text)
            if not country:
                continue
            author_name = f"u/{comment.author.name}" if comment.author else "[deleted]"
            if country not in countries or comment.score > countries[country]["upvotes"]:
                countries[country] = best_comment(
                    countries.get(country), body, author_name,
                    comment.score, f"{BASE}{comment.permalink}"
                )

        print(f"  Found {len(countries)} countries")
        output.append({
            "post_title": submission.title,
            "post_url": f"{BASE}{submission.permalink}",
            "created_utc": submission.created_utc,
            "countries": countries,
        })

    return output


# ---------- Public JSON fetching (for local dev) ----------

def fetch_json(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt < retries - 1:
                print(f"  Retry {attempt + 1}/{retries} after error: {e}")
                time.sleep(3)
            else:
                raise


def fetch_with_public_api():
    print(f"Fetching top posts from r/{SUBREDDIT} (via public JSON)...")
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
            "created_utc": d["created_utc"],
        })

    posts.sort(key=lambda p: p["num_comments"], reverse=True)
    selected = posts[:NUM_POSTS]

    output = []
    for i, post in enumerate(selected):
        print(f"\n[{i+1}/{len(selected)}] {post['title'][:70]}...")
        print(f"  {post['num_comments']} comments, score {post['score']}")

        comments_url = f"{BASE}{post['permalink']}.json?sort=top&limit=500"
        cdata = fetch_json(comments_url)
        comments = cdata[1]["data"]["children"]

        countries = {}
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
            if country not in countries or d["score"] > countries[country]["upvotes"]:
                countries[country] = best_comment(
                    countries.get(country), body, f"u/{d['author']}",
                    d["score"], f"{BASE}{d['permalink']}"
                )

        print(f"  Found {len(countries)} countries")
        output.append({
            "post_title": post["title"],
            "post_url": post["url"],
            "created_utc": post["created_utc"],
            "countries": countries,
        })

        if i < len(selected) - 1:
            time.sleep(3)

    return output


# ---------- Main ----------

def main():
    use_praw = os.environ.get("REDDIT_CLIENT_ID") and os.environ.get("REDDIT_CLIENT_SECRET")

    if use_praw:
        output = fetch_with_praw()
    else:
        print("No REDDIT_CLIENT_ID set, using public JSON endpoints (local dev mode).")
        output = fetch_with_public_api()

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

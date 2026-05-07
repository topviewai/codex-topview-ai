#!/usr/bin/env python3
"""
Fetch full Reddit post content via JSON API (bypasses opencli truncation).

Usage:
    python3 fetch_reddit_post.py <subreddit> <post_id>
    python3 fetch_reddit_post.py seedance2pro 1se5fap

Output: JSON with author, title, score, date, full selftext.
Requires: full_network permission (curl to reddit.com).
"""
import subprocess, json, sys, datetime

def fetch_post(subreddit, post_id):
    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}/.json"
    result = subprocess.run(
        ["curl", "-s", "-H", "User-Agent: Mozilla/5.0", url],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        return None

    data = json.loads(result.stdout)
    post = data[0]["data"]["children"][0]["data"]
    ts = post.get("created_utc", 0)
    return {
        "author": post.get("author", ""),
        "title": post.get("title", ""),
        "score": post.get("score", 0),
        "date": datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d"),
        "selftext": post.get("selftext", ""),
        "url": f"https://www.reddit.com/r/{subreddit}/comments/{post_id}/",
    }

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: fetch_reddit_post.py <subreddit> <post_id>")
        sys.exit(1)
    result = fetch_post(sys.argv[1], sys.argv[2])
    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Failed to fetch post", file=sys.stderr)
        sys.exit(1)

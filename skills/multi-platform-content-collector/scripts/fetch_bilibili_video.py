#!/usr/bin/env python3
"""
Fetch Bilibili video metadata + description via public API.

Usage:
    python3 fetch_bilibili_video.py <BV号>
    python3 fetch_bilibili_video.py BV1GW9KBzEGA

Output: JSON with author, title, desc, date, views, likes.
"""
import subprocess, json, sys, datetime

def fetch_video(bvid):
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    result = subprocess.run(
        ["curl", "-s", url], capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        return None

    data = json.loads(result.stdout).get("data", {})
    stat = data.get("stat", {})
    owner = data.get("owner", {})
    ts = data.get("pubdate", 0)
    return {
        "author": owner.get("name", ""),
        "title": data.get("title", ""),
        "desc": data.get("desc", ""),
        "date": datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d") if ts else "N/A",
        "views": stat.get("view", 0),
        "likes": stat.get("like", 0),
        "url": f"https://www.bilibili.com/video/{bvid}",
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: fetch_bilibili_video.py <BV号>")
        sys.exit(1)
    result = fetch_video(sys.argv[1])
    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Failed to fetch video", file=sys.stderr)
        sys.exit(1)

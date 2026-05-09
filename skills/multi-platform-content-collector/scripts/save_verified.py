#!/usr/bin/env python3
"""
Safely append a verified entry to the collector JSONL file.

Replaces shell 'echo' to avoid escaping issues with quotes, newlines,
backslashes, and $ signs that frequently appear in collected text.

Usage:
    python3 save_verified.py <platform> <author> <date> <likes> <url> <prompt>
    python3 save_verified.py --from-file /tmp/entry.json

    # With custom output path:
    python3 save_verified.py --output /tmp/my_verified.jsonl <platform> <author> <date> <likes> <url> <prompt>

    # Read prompt from stdin (for very long prompts):
    echo "long text..." | python3 save_verified.py --prompt-stdin <platform> <author> <date> <likes> <url>

Output: Appends one JSON line to /tmp/collector_verified.jsonl (default)
"""
import json
import os
import sys

DEFAULT_OUTPUT = "/tmp/collector_verified.jsonl"


def save_entry(entry: dict, output_path: str):
    """Append a single entry to the JSONL file."""
    os.makedirs(os.path.dirname(output_path) or "/tmp", exist_ok=True)
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    count = 0
    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    platform = entry.get("platform", "N/A")
    author = entry.get("author") or entry.get("source") or "N/A"
    metric = entry.get("likes", entry.get("score", entry.get("views", "N/A")))
    print(f"[{count}] Saved: {platform} | {author} | metric={metric}")
    return count


def main():
    output_path = DEFAULT_OUTPUT
    from_file = None
    prompt_stdin = False
    positional = []

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--output" and i + 1 < len(args):
            output_path = args[i + 1]
            i += 2
        elif args[i] == "--from-file" and i + 1 < len(args):
            from_file = args[i + 1]
            i += 2
        elif args[i] == "--prompt-stdin":
            prompt_stdin = True
            i += 1
        else:
            positional.append(args[i])
            i += 1

    if from_file:
        with open(from_file, "r", encoding="utf-8") as f:
            entry = json.load(f)
        save_entry(entry, output_path)
        return

    if prompt_stdin:
        if len(positional) < 5:
            print("Usage: ... | python3 save_verified.py --prompt-stdin <platform> <author> <date> <likes> <url>",
                  file=sys.stderr)
            sys.exit(1)
        prompt = sys.stdin.read()
    else:
        if len(positional) < 6:
            print("Usage: python3 save_verified.py <platform> <author> <date> <likes> <url> <prompt>",
                  file=sys.stderr)
            print("       python3 save_verified.py --from-file /tmp/entry.json", file=sys.stderr)
            sys.exit(1)
        prompt = positional[5]

    entry = {
        "platform": positional[0],
        "author": positional[1],
        "date": positional[2],
        "likes": positional[3],
        "url": positional[4],
        "prompt": prompt,
    }
    save_entry(entry, output_path)


if __name__ == "__main__":
    main()

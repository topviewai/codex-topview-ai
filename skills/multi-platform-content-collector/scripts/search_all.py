#!/usr/bin/env python3
"""
Multi-platform search orchestrator.

Runs broad, high-engagement searches across Twitter, TikTok, YouTube, Reddit,
and Bilibili. In `--mode prompt`, it also runs prompt-focused suffix searches.
Deduplicates by URL, sorts by engagement descending, and writes results to a
JSONL file.

Each platform's number of API calls and per-call limit is derived from
`--target` (the desired final verified count) divided by the number of active
platforms. Browser-driven platforms (twitter, tiktok) are additionally capped
to a small number of calls to avoid the user-visible "Chrome page keeps
refreshing" loop.

Usage:
    # default: target 20 entries, all 5 platforms
    python3 search_all.py "seedance 2.0"

    # prompt-specific preset
    python3 search_all.py "seedance 2.0" --mode prompt

    # limit to specific platforms
    python3 search_all.py "kling ai" --platforms youtube,reddit

    # ask for fewer entries (smaller, faster)
    python3 search_all.py "sora" --target 5 --platforms youtube

    # ask for more entries
    python3 search_all.py "veo" --target 50 --platforms youtube,reddit,bilibili

    # custom output, skip browser-driven platforms
    python3 search_all.py "kling" --skip-browser --output /tmp/my.jsonl

Output: /tmp/candidates.jsonl (one JSON object per line, sorted by likes desc)
Dependencies: Python 3 stdlib + opencli CLI
"""
import argparse
import json
import math
import os
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass

DEFAULT_OUTPUT = "/tmp/candidates.jsonl"
DEFAULT_TARGET = 20                  # default number of verified entries the agent aims for
OPENCLI_TIMEOUT = 30

# Browser-driven adapters call `navigate` on every invocation, which forces
# Chrome to reload the target site. To avoid the user-visible "page keeps
# refreshing" loop, we throttle these adapters and circuit-break on the
# first failure (likely auth/anti-bot block).
BROWSER_PLATFORMS = {"twitter", "tiktok"}
BROWSER_BURST_DELAY_S = 2.0          # min sleep between consecutive calls to the same browser site
BROWSER_FAIL_THRESHOLD = 1           # consecutive failures before tripping the breaker
BROWSER_MAX_BASE_ROUNDS = 2          # hard cap on broad queries per browser platform per run
BROWSER_MAX_SUFFIX_ROUNDS = 1        # hard cap on prompt-suffixed queries per browser platform per run
_PLATFORM_FAIL_COUNT: dict[str, int] = {}
_PLATFORM_TRIPPED: set[str] = set()
_PLATFORM_LAST_CALL: dict[str, float] = {}


@dataclass(frozen=True)
class PlatformBudget:
    """How aggressively to search a single platform in a single run.

    `base_rounds`   : number of broad / high-engagement queries to issue
    `suffix_rounds` : number of prompt-suffixed queries to issue
    `limit_per_call`: --limit value passed to each opencli search call
    """
    base_rounds: int
    suffix_rounds: int
    limit_per_call: int

    @property
    def total_calls(self) -> int:
        return self.base_rounds + self.suffix_rounds


def compute_budget(platform: str, target: int, n_platforms: int) -> PlatformBudget:
    """Translate a global target count into a per-platform call budget.

    We assume ~1/3 candidates per platform actually carry a usable prompt,
    so we over-provision the per-platform raw count to ~3x the share.
    Browser-driven platforms get an extra hard cap to avoid the
    "Chrome page keeps refreshing" symptom.
    """
    target = max(1, int(target))
    n_platforms = max(1, int(n_platforms))
    per_share = math.ceil(target / n_platforms)
    raw_target = per_share * 3

    if raw_target <= 5:
        base, suffix, limit = 1, 1, 8
    elif raw_target <= 15:
        base, suffix, limit = 2, 1, 15
    elif raw_target <= 40:
        base, suffix, limit = 2, 2, 20
    elif raw_target <= 80:
        base, suffix, limit = 3, 3, 25
    else:
        base, suffix, limit = 4, 3, 30

    if platform in BROWSER_PLATFORMS:
        base = min(base, BROWSER_MAX_BASE_ROUNDS)
        suffix = min(suffix, BROWSER_MAX_SUFFIX_ROUNDS)

    return PlatformBudget(base_rounds=base, suffix_rounds=suffix, limit_per_call=limit)

# ---------------------------------------------------------------------------
# Keyword variant expansion
# ---------------------------------------------------------------------------

def expand_keyword(kw: str) -> list[str]:
    """Generate spelling variants from a keyword.

    "seedance 2.0" -> seedance 2.0, seedance2.0, seedance2, seedance 2, Seedance 2.0, seedance
    "kling ai"     -> kling ai, klingai, Kling ai, kling
    """
    kw = kw.strip()
    variants = {kw}

    no_spaces = re.sub(r"\s+", "", kw)
    variants.add(no_spaces)  # "seedance2.0" / "klingai"

    no_spaces_no_dots = re.sub(r"[\s.]+", "", kw)
    variants.add(no_spaces_no_dots)  # "seedance20" / "klingai"

    stripped_minor = re.sub(r"\.\d+$", "", kw)
    if stripped_minor != kw:
        variants.add(stripped_minor)  # "seedance 2"
        variants.add(re.sub(r"\s+", "", stripped_minor))  # "seedance2"

    base_word = re.split(r"[\s.\d]+", kw)[0]
    if len(base_word) >= 3:
        variants.add(base_word)  # "seedance" / "kling"

    variants.add(kw.capitalize())
    variants.add(kw.lower())

    variants.discard("")
    return list(variants)


def keyword_no_spaces(kw: str) -> str:
    return re.sub(r"[\s.]+", "", kw).lower()

# ---------------------------------------------------------------------------
# opencli runner
# ---------------------------------------------------------------------------

def run_opencli(args: list[str], timeout: int = OPENCLI_TIMEOUT) -> list[dict] | None:
    """Run an opencli command and parse JSON output. Returns list of items or None.

    For browser-driven platforms (Twitter / TikTok), enforces a throttle between
    consecutive calls and a circuit breaker that short-circuits further calls
    after `BROWSER_FAIL_THRESHOLD` consecutive failures (typically auth /
    anti-bot blocks). This prevents the visible "browser page keeps refreshing
    but nothing happens" loop.
    """
    platform = args[0] if args else ""

    if platform in _PLATFORM_TRIPPED:
        return None

    if platform in BROWSER_PLATFORMS:
        last = _PLATFORM_LAST_CALL.get(platform)
        if last is not None:
            wait = BROWSER_BURST_DELAY_S - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        _PLATFORM_LAST_CALL[platform] = time.monotonic()

    cmd = ["opencli"] + args + ["-f", "json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            _record_failure(platform, f"exit={result.returncode}")
            return None
        text = result.stdout.strip()
        if not text:
            _record_failure(platform, "empty stdout")
            return None
        data = json.loads(text)
        items = None
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for key in ("results", "items", "data", "posts", "videos"):
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
            if items is None:
                items = [data]

        if items:
            _PLATFORM_FAIL_COUNT[platform] = 0
        else:
            _record_failure(platform, "no items")
        return items
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        print(f"  [WARN] opencli failed: {' '.join(cmd[:6])}... -> {e}", file=sys.stderr)
        _record_failure(platform, str(e)[:80])
        return None


def _record_failure(platform: str, reason: str) -> None:
    """Track failures per platform and trip the breaker if threshold reached."""
    if platform not in BROWSER_PLATFORMS:
        return
    _PLATFORM_FAIL_COUNT[platform] = _PLATFORM_FAIL_COUNT.get(platform, 0) + 1
    if (_PLATFORM_FAIL_COUNT[platform] >= BROWSER_FAIL_THRESHOLD
            and platform not in _PLATFORM_TRIPPED):
        _PLATFORM_TRIPPED.add(platform)
        print(
            f"  [CIRCUIT-BREAK] {platform}: tripped after {_PLATFORM_FAIL_COUNT[platform]} "
            f"failures ({reason}). Skipping remaining {platform} calls in this run.",
            file=sys.stderr,
        )

# ---------------------------------------------------------------------------
# Platform-specific search & normalization
# ---------------------------------------------------------------------------

PROMPT_SUFFIXES_EN = [
    "prompt", "prompt I used", "the prompt was", "my prompt",
    "here is the prompt", "prompt included", "full prompt",
]
PROMPT_SUFFIXES_ZH = [
    "提示词", "附提示词", "提示词分享", "prompt",
]


def _pick_suffixes(pool: list[str], n: int = 3) -> list[str]:
    return random.sample(pool, min(n, len(pool)))


def search_twitter(variants: list[str], kw_no_space: str, budget: PlatformBudget) -> list[dict]:
    """Search X/Twitter under the given budget.

    Browser-based adapter: each call navigates Chrome to twitter.com and
    triggers a refresh. We rely on the per-platform budget cap (already
    clamped for browser platforms in `compute_budget`) and the circuit
    breaker in `run_opencli` to keep this from spiraling.
    """
    items = []
    limit = str(budget.limit_per_call)

    v = random.choice(variants)
    base_queries = [
        ([v, "min_faves:50"], {"--filter": "top", "--limit": limit}),
        ([kw_no_space, "min_faves:50"], {"--filter": "top", "--limit": limit}),
    ][: budget.base_rounds]
    for extra_words, params in base_queries:
        query = " ".join(extra_words)
        cmd = ["twitter", "search", query]
        for k, val in params.items():
            cmd += [k, val]
        results = run_opencli(cmd)
        if results:
            items.extend(results)

    for suffix in _pick_suffixes(PROMPT_SUFFIXES_EN, budget.suffix_rounds):
        results = run_opencli([
            "twitter", "search", f"{random.choice(variants)} {suffix}",
            "--filter", "top", "--limit", limit,
        ])
        if results:
            items.extend(results)

    normalized = []
    for it in items:
        url = it.get("url", "")
        if not url:
            continue
        normalized.append({
            "platform": "X (Twitter)",
            "author": it.get("author", ""),
            "date": (it.get("created_at") or "N/A")[:10],
            "likes": _to_int(it.get("likes", 0)),
            "url": url,
            "title": "",
            "text": it.get("text", ""),
        })
    return normalized


def search_tiktok(variants: list[str], kw_no_space: str, budget: PlatformBudget) -> list[dict]:
    """Search TikTok under the given budget.

    Each `tiktok search` invocation forces Chrome to navigate to
    https://www.tiktok.com/explore (settleMs: 5000) before issuing the search
    fetch — calling it many times in a row produces a visible "refresh forever"
    loop. The budget for `tiktok` is hard-clamped in `compute_budget` and we
    additionally circuit-break on the first failure.
    """
    items = []
    limit = str(budget.limit_per_call)

    v = random.choice(variants)
    base_queries = [
        v,
        kw_no_space,
    ][: budget.base_rounds]
    for q in base_queries:
        results = run_opencli(["tiktok", "search", q, "--limit", limit])
        if results:
            items.extend(results)

    for suffix in _pick_suffixes(PROMPT_SUFFIXES_EN, budget.suffix_rounds):
        results = run_opencli([
            "tiktok", "search", f"{random.choice(variants)} {suffix}",
            "--limit", limit,
        ])
        if results:
            items.extend(results)

    normalized = []
    for it in items:
        url = it.get("url", "")
        if not url:
            continue
        normalized.append({
            "platform": "TikTok",
            "author": it.get("author", ""),
            "date": "N/A",
            "likes": _to_int(it.get("likes", 0)),
            "url": url,
            "title": "",
            "text": it.get("desc", ""),
        })
    return normalized


def search_youtube(variants: list[str], kw_no_space: str, budget: PlatformBudget) -> list[dict]:
    items = []
    limit = str(budget.limit_per_call)

    v = random.choice(variants)
    round_a = [
        (v, "--sort", "views", "--upload", "month", "--limit", limit),
        (v, "--sort", "relevance", "--upload", "month", "--limit", limit),
        (v, "--sort", "rating", "--upload", "month", "--limit", limit),
        (kw_no_space, "--sort", "date", "--upload", "month", "--limit", limit),
    ][: budget.base_rounds]
    for query, *params in round_a:
        results = run_opencli(["youtube", "search", query] + params)
        if results:
            items.extend(results)

    sorts = ["date", "relevance", "views"]
    for i, suffix in enumerate(_pick_suffixes(PROMPT_SUFFIXES_EN, budget.suffix_rounds)):
        sort = sorts[i % len(sorts)]
        results = run_opencli([
            "youtube", "search", f"{random.choice(variants)} {suffix}",
            "--sort", sort, "--upload", "month", "--limit", limit,
        ])
        if results:
            items.extend(results)

    normalized = []
    for it in items:
        url = it.get("url", "")
        if not url:
            continue
        normalized.append({
            "platform": "YouTube",
            "author": it.get("channel", ""),
            "date": (it.get("published") or "N/A")[:10],
            "likes": _to_int(it.get("views", 0)),
            "url": url,
            "title": it.get("title", ""),
            "text": "",
        })
    return normalized


def search_reddit(variants: list[str], kw_no_space: str, budget: PlatformBudget) -> list[dict]:
    items = []
    limit = str(budget.limit_per_call)

    v = random.choice(variants)
    round_a = [
        (v, "--sort", "top", "--time", "month", "--limit", limit),
        (v, "--sort", "hot", "--time", "month", "--limit", limit),
        (kw_no_space, "--sort", "top", "--time", "month", "--limit", limit),
        (kw_no_space, "--sort", "new", "--time", "month", "--limit", limit),
    ][: budget.base_rounds]
    for query, *params in round_a:
        results = run_opencli(["reddit", "search", query] + params)
        if results:
            items.extend(results)

    sorts = ["new", "top", "relevance"]
    times = ["month", "week", "month"]
    for i, suffix in enumerate(_pick_suffixes(PROMPT_SUFFIXES_EN, budget.suffix_rounds)):
        results = run_opencli([
            "reddit", "search", f"{random.choice(variants)} {suffix}",
            "--sort", sorts[i % len(sorts)],
            "--time", times[i % len(times)],
            "--limit", limit,
        ])
        if results:
            items.extend(results)

    normalized = []
    for it in items:
        url = it.get("url", "")
        if not url:
            continue
        normalized.append({
            "platform": "Reddit",
            "author": it.get("author", ""),
            "date": "N/A",
            "likes": _to_int(it.get("score", 0)),
            "url": url,
            "title": it.get("title", ""),
            "text": "",
        })
    return normalized


def search_bilibili(variants: list[str], kw_no_space: str, budget: PlatformBudget) -> list[dict]:
    items = []
    limit = str(budget.limit_per_call)

    v = random.choice(variants)
    round_a = [
        (v, "--limit", limit),
        (kw_no_space, "--limit", limit),
        (v, "--page", "2", "--limit", limit),
        (kw_no_space, "--page", "2", "--limit", limit),
    ][: budget.base_rounds]
    for query, *params in round_a:
        results = run_opencli(["bilibili", "search", query] + params)
        if results:
            items.extend(results)

    for suffix in _pick_suffixes(PROMPT_SUFFIXES_ZH, budget.suffix_rounds):
        results = run_opencli([
            "bilibili", "search", f"{random.choice(variants)} {suffix}",
            "--limit", limit,
        ])
        if results:
            items.extend(results)

    normalized = []
    for it in items:
        url = it.get("url", "")
        if not url:
            continue
        normalized.append({
            "platform": "Bilibili",
            "author": it.get("author", ""),
            "date": "N/A",
            "likes": _to_int(it.get("score", 0)),
            "url": url,
            "title": it.get("title", ""),
            "text": "",
        })
    return normalized

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_int(val) -> int:
    """Parse engagement numbers, handling K/M/B suffixes (e.g. '3.2K' -> 3200)."""
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    if isinstance(val, str):
        val = val.strip().replace(",", "")
        multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
        for suffix, mult in multipliers.items():
            if val.lower().endswith(suffix):
                try:
                    return int(float(val[:-1]) * mult)
                except ValueError:
                    break
        cleaned = re.sub(r"[^\d]", "", val)
        return int(cleaned) if cleaned else 0
    return 0


def _normalize_url(url: str) -> str:
    """Strip query params and trailing slashes for dedup."""
    url = url.split("?")[0].rstrip("/")
    return url

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

PLATFORM_FUNCS = {
    "twitter": search_twitter,
    "tiktok": search_tiktok,
    "youtube": search_youtube,
    "reddit": search_reddit,
    "bilibili": search_bilibili,
}


def main():
    parser = argparse.ArgumentParser(description="Multi-platform content search orchestrator")
    parser.add_argument("keyword", help="Search keyword (e.g. 'seedance 2.0')")
    parser.add_argument("--mode", choices=["general", "prompt"], default="general",
                        help="Search mode. 'general' collects candidates for any user-defined data need; "
                             "'prompt' adds prompt-oriented suffix queries.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output JSONL path")
    parser.add_argument("--platforms", default=None,
                        help="Comma-separated platform list. "
                             "Allowed: twitter, tiktok, youtube, reddit, bilibili. "
                             "Default: all five.")
    parser.add_argument("--target", type=int, default=DEFAULT_TARGET,
                        help=f"How many verified entries the agent eventually wants (default: {DEFAULT_TARGET}). "
                             "Drives per-platform call count and per-call --limit.")
    parser.add_argument("--skip-browser", action="store_true",
                        help="Skip browser-driven platforms (twitter, tiktok). "
                             "Useful when Bridge/Extension is offline or anti-bot blocks are active.")
    parser.add_argument("--budget-only", action="store_true",
                        help="Print the per-platform budget and exit without making any opencli calls. "
                             "Use this for a quick dry-run before a real search.")
    args = parser.parse_args()

    variants = expand_keyword(args.keyword)
    kw_no_space = keyword_no_spaces(args.keyword)

    platforms = list(PLATFORM_FUNCS.keys())
    if args.platforms:
        platforms = [p.strip().lower() for p in args.platforms.split(",")]
        unknown = [p for p in platforms if p not in PLATFORM_FUNCS]
        if unknown:
            print(f"[WARN] Unknown platform(s): {unknown}. Allowed: {list(PLATFORM_FUNCS.keys())}",
                  file=sys.stderr)
        platforms = [p for p in platforms if p in PLATFORM_FUNCS]

    if args.skip_browser:
        before = list(platforms)
        platforms = [p for p in platforms if p not in BROWSER_PLATFORMS]
        skipped = [p for p in before if p in BROWSER_PLATFORMS]
        if skipped:
            print(f"[INFO] --skip-browser: skipping {', '.join(skipped)}")

    if not platforms:
        print("[ERROR] No platforms left to search after filters. Aborting.", file=sys.stderr)
        sys.exit(2)

    budgets: dict[str, PlatformBudget] = {
        p: compute_budget(p, args.target, len(platforms)) for p in platforms
    }
    if args.mode == "general":
        budgets = {
            p: PlatformBudget(
                base_rounds=budgets[p].total_calls,
                suffix_rounds=0,
                limit_per_call=budgets[p].limit_per_call,
            )
            for p in platforms
        }

    print(f"Keyword:    {args.keyword}")
    print(f"Mode:       {args.mode}")
    print(f"Variants:   {variants}")
    print(f"Target:     {args.target} verified entries (final goal)")
    print(f"Platforms:  {platforms}")
    print(f"Budget:")
    for p, b in budgets.items():
        marker = " [browser]" if p in BROWSER_PLATFORMS else ""
        print(f"  {p:<9} base={b.base_rounds} suffix={b.suffix_rounds} "
              f"limit={b.limit_per_call} (={b.total_calls} calls){marker}")
    print(f"Output:     {args.output}")

    if args.budget_only:
        print("\n[--budget-only] dry-run requested, exiting without searching.")
        return

    all_candidates: list[dict] = []
    platform_counts: dict[str, int] = {}

    for pname in platforms:
        func = PLATFORM_FUNCS.get(pname)
        if not func:
            print(f"[WARN] Unknown platform: {pname}, skipping", file=sys.stderr)
            continue
        budget = budgets[pname]
        print(f"\n--- Searching {pname} (base={budget.base_rounds}, "
              f"suffix={budget.suffix_rounds}, limit={budget.limit_per_call}) ---")
        try:
            results = func(variants, kw_no_space, budget)
            platform_counts[pname] = len(results)
            all_candidates.extend(results)
            print(f"  Found {len(results)} raw results")
        except Exception as e:
            print(f"  [ERROR] {pname} search failed: {e}", file=sys.stderr)
            platform_counts[pname] = 0

    seen_urls: set[str] = set()
    deduped: list[dict] = []
    for c in all_candidates:
        norm_url = _normalize_url(c["url"])
        if norm_url not in seen_urls:
            seen_urls.add(norm_url)
            deduped.append(c)

    deduped.sort(key=lambda x: x["likes"], reverse=True)

    os.makedirs(os.path.dirname(args.output) or "/tmp", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for c in deduped:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"\n=== Search Complete ===")
    print(f"Raw results:   {len(all_candidates)}")
    print(f"After dedup:   {len(deduped)}")
    for pname, count in platform_counts.items():
        dedup_count = sum(1 for c in deduped if c["platform"].lower().startswith(pname[:3]))
        print(f"  {pname}: {count} raw -> {dedup_count} unique")
    if deduped:
        print(f"Top likes:     {deduped[0]['likes']} ({deduped[0]['platform']})")
        print(f"Lowest likes:  {deduped[-1]['likes']} ({deduped[-1]['platform']})")
    if _PLATFORM_TRIPPED:
        print(
            f"Tripped:       {sorted(_PLATFORM_TRIPPED)} "
            f"(short-circuited mid-run; consider --skip-browser or check Bridge/login)",
            file=sys.stderr,
        )
    print(f"Output:        {args.output}")


if __name__ == "__main__":
    main()

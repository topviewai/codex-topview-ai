---
name: social-media-uploader
description: "Upload videos to TikTok, Instagram, and YouTube via the social-upload CLI. Supports single/multi-platform batch upload with platform-native scheduled publishing. Uses Chrome debug browser with existing login sessions — zero credentials needed. Use when: 上传视频, 发布视频, 上传到TikTok, 上传到Instagram, 上传到YouTube, 社交媒体上传, 全平台发布, 定时发布, scheduled upload, upload video, post video"
version: 1.0.0
author: shenyajing
tags: [social-media, upload, tiktok, instagram, youtube, video, schedule, automation, chrome, cdp]
---

# Social Media Video Uploader

> Upload videos to TikTok / Instagram / YouTube via `social-upload` CLI. Reuses Chrome debug browser login sessions — zero credentials, zero risk.

Local install: use `C:\Users\chia1\.codex\tools\seo-browser-uploader\.venv\Scripts\social-upload.exe` from any working directory.

## Install & Run

```bash
# Install (in project venv)
.venv/bin/pip install -e .

# Verify
.venv/bin/social-upload --help

# macOS
.venv/bin/social-upload <platform> --video "path" --title "title" --description "desc"

# Windows
.venv\Scripts\social-upload <platform> --video "path" --title "title" --description "desc"
```

## Prerequisites

1. Chrome running in **debug mode** (port 9222) with target platforms logged in
2. Python venv with `social-upload` CLI installed

```bash
# Start Chrome debug mode
bash scripts/start_chrome_debug.sh        # macOS
scripts\start_chrome_debug.bat            # Windows

# Verify Chrome debug port
curl -s http://localhost:9222/json/version
```

> **Security**: Never handles credentials. Users must log in manually in the debug browser. Script auto-exits if not logged in.

## Platform Routing

| Keywords | Command |
|----------|---------|
| TikTok、抖音国际版 | `social-upload tiktok` |
| Instagram、ins、IG | `social-upload instagram` |
| YouTube、油管、YT | `social-upload youtube` |
| 全平台、所有平台 | Execute all three sequentially |

## Command Reference

### TikTok

```bash
# Basic upload
social-upload tiktok --video "path.mp4" --title "Title" --description "Desc"

# With cover image
social-upload tiktok --video "path.mp4" --title "Title" --description "Desc" --cover "cover.jpg"

# Scheduled publish (platform-native, video uploads immediately, goes public at scheduled time)
social-upload tiktok --video "path.mp4" --title "Title" --description "Desc" --schedule "2026-04-16 08:00"

# Visibility control
social-upload tiktok --video "path.mp4" --title "Title" --description "Desc" --visibility friends

# With custom profile (for ai_generated, disclose_content, etc.)
social-upload tiktok --video "path.mp4" --title "Title" --description "Desc" --profile config.json

# Dry run (fill form only, don't publish)
social-upload tiktok --video "path.mp4" --title "Title" --description "Desc" --no-publish

# Resume from checkpoint
social-upload tiktok --video "path.mp4" --title "Title" --description "Desc" --resume-from publish
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--video` | ✅ | Video file path |
| `--title` | ✅ | Video title |
| `--description` | ✅ | Video description |
| `--cover` | ❌ | Cover image path (default: platform auto-select) |
| `--schedule` | ❌ | Schedule time `"YYYY-MM-DD HH:MM"` |
| `--visibility` | ❌ | `everyone` (default) / `friends` / `only_me` |
| `--profile` | ❌ | JSON config for advanced options |
| `--no-publish` | ❌ | Fill form without publishing |
| `--resume-from` | ❌ | Resume from a checkpoint step |

**Profile-only options**: `ai_generated`, `disclose_content`, `allow_comments`, `allow_reuse`, `high_quality`

### Instagram

```bash
# Basic upload (uses --caption, NOT --title/--description)
social-upload instagram --video "path.mp4" --caption "Your caption text #hashtags"
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--video` | ✅ | Video file path |
| `--caption` | ✅ | Post caption text |

**Platform constraints**:
- ❌ No `--schedule` (Instagram web doesn't support scheduled publishing)
- ❌ No `--visibility` (Instagram has no visibility settings)
- Profile option: `share_to_feed` (default: true)

### YouTube

```bash
# Basic upload
social-upload youtube --video "path.mp4" --title "Title" --description "Desc"

# Scheduled publish
social-upload youtube --video "path.mp4" --title "Title" --description "Desc" --schedule "2026-04-16 08:00"

# Unlisted visibility
social-upload youtube --video "path.mp4" --title "Title" --description "Desc" --visibility unlisted
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--video` | ✅ | Video file path |
| `--title` | ✅ | Video title (≤95 chars) |
| `--description` | ✅ | Video description (≤4900 chars) |
| `--schedule` | ❌ | Schedule time `"YYYY-MM-DD HH:MM"` |
| `--visibility` | ❌ | `public` (default) / `unlisted` / `private` |
| `--profile` | ❌ | JSON config for advanced options |

**Profile-only options**: `made_for_kids`, `tags`, `category`

**Note**: Scheduled publish auto-sets visibility to PUBLIC. If schedule setup fails, script aborts to prevent accidental immediate publication.

### Utility Commands

```bash
# Restart debug browser
social-upload restart-browser

# Get repair suggestions after failure
social-upload suggest-selectors --run-id <run_id>

# Fix broken button selector
social-upload fix-selector --target <platform> --key <button_name> --selector "new_selector"

# View/fix interaction recipes (schedule, visibility)
social-upload show-recipe --target <platform> --recipe schedule_recipe
social-upload fix-recipe --target <platform> --recipe <name> --step <step_id> --selector "new_selector"

# Extract browser DOM for diagnosis
social-upload diag
```

## Configuration

### Default Values (no profile needed)

| Platform | Field | Default |
|----------|-------|---------|
| TikTok | visibility | `everyone` |
| TikTok | allow_comments | `true` |
| TikTok | allow_reuse | `true` |
| TikTok | disclose_content | `false` |
| TikTok | ai_generated | `false` |
| TikTok | high_quality | `true` |
| Instagram | share_to_feed | `true` |
| YouTube | made_for_kids | `false` |
| YouTube | visibility | `public` |

### Custom Profile JSON

For options beyond `--schedule` and `--visibility`, create a profile JSON:

```json
{
  "tiktok": {
    "ai_generated": true,
    "disclose_content": true
  },
  "youtube": {
    "made_for_kids": false,
    "tags": ["vlog", "travel"],
    "category": "Entertainment"
  }
}
```

Save to `~/.social_uploader/profiles/` and pass via `--profile path.json`.

**Priority**: CLI args > profile file > defaults.

## Platform Constraints

| Constraint | Trigger | Behavior |
|------------|---------|----------|
| Instagram no schedule | `--schedule` on Instagram | Ignored, publishes immediately |
| Instagram no visibility | `--visibility` on Instagram | Ignored |
| TikTok only_me + schedule conflict | `--visibility only_me` + `--schedule` | Schedule ignored, only visibility applied |

## Execution Model

- **Background execution**: Commands run 3-5 minutes. Use `block_until_ms: 0` for background mode
- **Progress monitoring**: Poll terminal output every 10-15s, watch for ✅/❌/🎉 symbols
- **Exit codes**: `0` = success, `1` = failure
- **Multi-platform**: Execute sequentially (TikTok → Instagram → YouTube). One failure doesn't block others

## Self-Repair

When upload fails, the CLI outputs `DIAG|` diagnostic lines:

| Error | Meaning | Fix |
|-------|---------|-----|
| `selector_not_found` | Button selector broken | `fix-selector` auto-repair |
| `state_mismatch` | State detection text outdated | `fix-pattern` auto-repair |
| `recipe_step_failed` | Interaction recipe step failed | `show-recipe` → `fix-recipe` → `--resume-from` |
| `file_rejected` | Video rejected by platform | Check video format/encoding |
| `login_required` | Not logged in | Log in manually, `--resume-from` retry |
| `timeout` | Network timeout | Check connection, retry |

Element finder uses dual-track approach:
- **Track A (fast)**: `button_config.json` selector list, 1.5s quick try
- **Track B (AI)**: UltimateLocator with AgentQL AI API for semantic element discovery
- **Fallback**: Both miss → `DIAG|` output for agent intervention

## Key Files

| File | Role |
|------|------|
| `src/social_uploader/uploaders/tiktok.py` | TikTok upload logic |
| `src/social_uploader/uploaders/instagram.py` | Instagram upload logic |
| `src/social_uploader/uploaders/youtube.py` | YouTube upload logic |
| `src/social_uploader/button_config.json` | Button selector config |
| `src/social_uploader/state_patterns.json` | Interaction recipes |
| `src/social_uploader/profiles/default.json` | Default config |
| `src/social_uploader/command_entry.py` | CLI entry point |
| `scripts/start_chrome_debug.sh` | Chrome debug launcher |

## Examples

### Single Platform — Default Settings

```bash
.venv/bin/social-upload tiktok --video "/Users/xxx/vlog.mp4" --title "Weekend Vlog" --description "A fun weekend trip"
```

### Multi-Platform Upload

```bash
# 1. TikTok (scheduled)
.venv/bin/social-upload tiktok --video "vlog.mp4" --title "Weekend" --description "Fun trip" --schedule "2026-04-16 08:00"

# 2. Instagram (immediate, no schedule support)
.venv/bin/social-upload instagram --video "vlog.mp4" --caption "Weekend trip 🎉 #vlog"

# 3. YouTube (scheduled)
.venv/bin/social-upload youtube --video "vlog.mp4" --title "Weekend" --description "Fun trip" --schedule "2026-04-16 08:00"
```

### Switch Chrome Account

```bash
.venv/bin/social-upload restart-browser
bash scripts/start_chrome_debug.sh
# Log into new account in debug browser, then re-run upload
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Browser not connected | `bash scripts/start_chrome_debug.sh` then `curl -s http://localhost:9222/json/version` |
| Not logged in | Script auto-exits. Log in manually in debug browser |
| CLI not found | `.venv/bin/pip install -e .` |
| Wrong Chrome account | `social-upload restart-browser` → restart debug browser → re-login |
| Element not found | Auto self-repair via `DIAG|` pipeline |

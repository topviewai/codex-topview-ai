# TopView AI Codex Plugin

TopView AI for Codex helps with the full content production loop: research competitors and trends, write stronger video scripts and prompts, generate media assets and Storyboard previews with TopView AI, organize outputs, and publish finished videos to social platforms.

The plugin package is located at:

```text
topview-ai/0.4.0/
```

## What This Plugin Does

- Content research: collect structured public sources, competitor examples, creator lists, comments, trend signals, links, metrics, and AI prompts from platforms such as YouTube, Reddit, Bilibili, TikTok, and X when available.
- Video writing: turn rough ideas into creative angles, hooks, scripts, shot lists, storyboards, and model-ready prompts.
- Video generation: create text-to-video, image-to-video, reference-based video, and Storyboard preview images through TopView AI.
- Image workflows: generate images, edit images, remove backgrounds, and create product model showcase visuals.
- Avatar and voice workflows: create presenter-style talking avatar videos, text-to-speech audio, and voice-related assets.
- Board workflows: organize generated assets and return editable TopView board links.
- Social publishing: upload finished videos to TikTok, Instagram, and YouTube through the local social-upload workflow with safe dry-run support.

## Repository Layout

- `topview-ai/0.4.0/.codex-plugin/plugin.json`: TopView AI plugin manifest.
- `topview-ai/0.4.0/skills/topview-skill/`: main TopView AI workflow router and Python toolkit.
- `topview-ai/0.4.0/skills/multi-platform-content-collector/`: public web and social content collection workflow.
- `topview-ai/0.4.0/skills/video-script-writer/`: video creative strategy, script, storyboard, and prompt writer.
- `topview-ai/0.4.0/skills/social-media-uploader/`: TikTok, Instagram, and YouTube publishing workflow.
- `topview-ai/0.4.0/tools/seo-browser-uploader/`: local browser-based social upload CLI.

## Requirements

TopView generation requires a TopView account, available credits, Python 3.10 or newer, and network access to `https://www.topview.ai`.

Social publishing requires Chrome running with remote debugging on port `9222`, with the target social account already logged in. The uploader supports dry runs and should not publish without explicit user confirmation.

For detailed plugin usage, see [`topview-ai/0.4.0/README.md`](topview-ai/0.4.0/README.md).

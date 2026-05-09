# TopView AI Codex Plugin

TopView AI for Codex helps with the full content production loop: research competitors and trends, write stronger video scripts and prompts, generate media assets and Storyboard previews with TopView AI, organize outputs, and publish finished videos to social platforms.

## Install With One Message

```text
Please install the TopView AI plugin zip I uploaded. The goal is to make it referenceable as [@topview-ai](plugin://topview-ai@local). Do not only add the marketplace; extract the zip to %USERPROFILE%\Documents\Codex\local-marketplaces\topview-ai, set the marketplace name to local, enable [plugins."topview-ai@local"] in the Codex config, and copy topview-ai\0.4.0 to %USERPROFILE%\.codex\plugins\cache\local\topview-ai\0.4.0. When finished, remind me to restart Codex and start a new chat to test the reference.
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

- `.codex-plugin/plugin.json`: TopView AI plugin manifest.
- `skills/topview-skill/`: main TopView AI workflow router and Python toolkit.
- `skills/multi-platform-content-collector/`: public web and social content collection workflow.
- `skills/video-script-writer/`: video creative strategy, script, storyboard, and prompt writer.
- `skills/social-media-uploader/`: TikTok, Instagram, and YouTube publishing workflow.
- `tools/seo-browser-uploader/`: local browser-based social upload CLI.

## Requirements

TopView generation requires a TopView account, available credits, Python 3.10 or newer, and network access to `https://www.topview.ai`.

Social publishing requires Chrome running with remote debugging on port `9222`, with the target social account already logged in. The uploader supports dry runs and should not publish without explicit user confirmation.

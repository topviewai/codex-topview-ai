# TopView AI Codex Plugin

TopView AI for Codex helps with the full content production loop: research competitors and trends, write stronger video scripts and prompts, generate media assets and Storyboard previews with TopView AI, organize outputs, and publish finished videos to social platforms.

## Install With One Message

```text
Please install the TopView AI Codex plugin from https://github.com/topviewai/codex-topview-ai.git and make sure it is fully referenceable as [@topview-ai](plugin://topview-ai@local).

This is a required full local installation flow. Do not stop after adding a marketplace, and do not only clone the repository. You must complete every step below:

1. Clone or download the GitHub repository into:
   %USERPROFILE%\Documents\Codex\local-marketplaces\topview-ai

2. Treat this local marketplace as the `local` marketplace. If any marketplace metadata or config entry is created or edited, the marketplace name/id must be `local`.

3. Enable the plugin in the Codex config by adding or updating:
   [plugins."topview-ai@local"]
   enabled = true

4. Copy the actual plugin package into the Codex plugin cache at:
   %USERPROFILE%\.codex\plugins\cache\local\topview-ai\0.4.0

   Important: in the current GitHub repository, the plugin package files are at the repository root. The files and folders that must be copied into the cache directory include `.codex-plugin`, `skills`, `tools`, `assets`, `results`, and `README.md`. If the source is a zip that contains `topview-ai\0.4.0`, copy the contents of that `topview-ai\0.4.0` directory instead.

5. After installation, verify that the install is complete. Check that all of these exist:
   %USERPROFILE%\Documents\Codex\local-marketplaces\topview-ai
   %USERPROFILE%\.codex\plugins\cache\local\topview-ai\0.4.0\.codex-plugin\plugin.json
   %USERPROFILE%\.codex\plugins\cache\local\topview-ai\0.4.0\skills\topview-skill\SKILL.md
   %USERPROFILE%\.codex\plugins\cache\local\topview-ai\0.4.0\skills\social-media-uploader\SKILL.md
   %USERPROFILE%\.codex\plugins\cache\local\topview-ai\0.4.0\tools\seo-browser-uploader

6. Open `.codex-plugin\plugin.json` from the cache directory and confirm that the plugin name is `topview-ai` and the version is `0.4.0`.

7. Only after all checks pass, tell me that installation is complete, remind me to restart Codex, and tell me to start a new chat and test:
   [@topview-ai](plugin://topview-ai@local)

If any required file, config entry, or cache directory is missing, do not claim success. Fix the installation first, then run the verification checks again.
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

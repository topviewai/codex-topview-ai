# TopView AI Codex Plugin

TopView AI for Codex turns a short creative request into a complete marketing-content workflow. It helps Codex research public web and social content, write high-quality Seedance video prompts, generate videos, images, talking avatars, product visuals, and voice outputs through TopView AI, then publish finished videos to TikTok, Instagram, and YouTube.

## Install With One Message

Send this to Codex:

```text
Please install the TopView AI Codex plugin from https://github.com/topviewai/codex-topview-ai.git and tell me when I should restart Codex.
```

Codex can add this marketplace by running:

```bash
codex plugin marketplace add https://github.com/topviewai/codex-topview-ai.git
```

After installation, restart Codex if prompted. Then start a new chat and mention TopView AI, or use `@topview-ai` / one of its bundled skills.

## What This Plugin Does

- Content research: collect structured public sources, competitor examples, creator lists, comments, trend signals, links, metrics, and AI prompts from platforms such as YouTube, Reddit, Bilibili, TikTok, and X when available.
- Prompt and script writing: turn rough ideas into Seedance 2.0 prompts, shot lists, storyboards, hooks, and short-form video scripts.
- Video generation: create text-to-video, image-to-video, and reference-based video outputs through TopView AI.
- Image workflows: generate images, edit images, remove backgrounds, and create product model showcase visuals.
- Avatar and voice workflows: create presenter-style talking avatar videos, text-to-speech audio, and voice-related assets.
- Board workflows: organize generated assets and return editable TopView board links.
- Social publishing: upload finished videos to TikTok, Instagram, and YouTube through the local social-upload workflow with safe dry-run support.

## Example Prompts

```text
Research trending AI product video ideas on YouTube and Reddit, then organize 20 directions we can turn into videos.
```

```text
Turn this product selling point into a Seedance 2.0 video prompt for a 15-second TikTok ad.
```

```text
Use TopView AI to generate a short product showcase video, then run a private YouTube upload test.
```

```text
Collect high-performing competitor hooks on TikTok and summarize reusable hook templates.
```

## Bundled Skills

- `topview-skill`: main TopView AI workflow router for generation, editing, boards, account usage, and publishing handoff.
- `multi-platform-content-collector`: public web and social content collection for research, competitors, creators, comments, trends, and prompt examples.
- `seedance2-prompt-writer`: Seedance 2.0 prompt, script, storyboard, and shot-list writer.
- `social-media-uploader`: TikTok, Instagram, and YouTube publishing workflow using the local `social-upload` CLI.

## Repository Layout

- `.agents/plugins/marketplace.json`: Codex plugin marketplace entry.
- `topview-ai/0.4.0/.codex-plugin/plugin.json`: TopView AI plugin manifest.
- `topview-ai/0.4.0/skills/`: bundled skills and their helper scripts.
- `topview-ai/0.4.0/assets/`: plugin logo assets.

## Requirements

TopView generation requires a TopView account and available credits. The plugin guides Codex to run the local TopView Python scripts and send a direct login link when authentication is needed.

Social publishing requires a Chrome debug browser on port `9222` with the target social account already logged in. The uploader uses dry runs before real publishing and should not publish without explicit user confirmation.

Content collection uses public sources by default. Browser-driven platforms such as TikTok and X should only be enabled when requested and when the user's existing browser login state is available.

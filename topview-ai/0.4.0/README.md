# TopView AI Codex Plugin

TopView AI for Codex helps with the full content production loop: research what to make, write stronger prompts and scripts, generate media assets with TopView AI, organize outputs, and publish finished videos to social platforms.

Ask Codex to install this plugin with one message:

```text
Please install the TopView AI Codex plugin from https://github.com/topviewai/codex-topview-ai.git and tell me when I should restart Codex.
```

Codex can add the marketplace by running:

```bash
codex plugin marketplace add https://github.com/topviewai/codex-topview-ai.git
```

TopView AI lets Codex collect public content research, write Seedance prompts, generate and edit marketing media through TopView's Python toolkit, then publish finished videos to social platforms.

Typical tasks include competitor research, trend discovery, AI video prompt collection, Seedance 2.0 prompt writing, product video generation, talking avatar creation, background removal, product model shots, text-to-speech, board management, and safe social publishing dry runs.

## Capabilities

- Prompt writing: Seedance 2.0 video prompts, scripts, shot lists, and storyboards.
- Content research: collect structured public sources, competitor content, creators, comments, trends, links, and AI prompts across platforms.
- Video generation: text-to-video, image-to-video, and reference-based video.
- Image generation and editing: text-to-image, image edits, and style changes.
- Talking avatars: presenter-style videos from photos and scripts.
- Product workflows: background removal and model showcase images.
- Voice workflows: text-to-speech, voice search, and voice cloning.
- Board workflows: organize generated results and return editable TopView board links.
- Social publishing: upload videos to TikTok, Instagram, and YouTube through a logged-in Chrome debug browser.

## Example Prompts

```text
Research recent high-performing AI video ad topics and turn them into creative briefs for TopView generation.
```

```text
Turn this product introduction into a Seedance 2.0 storyboard prompt, then generate the video with TopView AI.
```

```text
Run a YouTube dry-run upload for the generated video, then ask me before publishing.
```

## Layout

- `.codex-plugin/plugin.json`: plugin manifest.
- `skills/topview-skill/SKILL.md`: compact Codex-facing workflow.
- `skills/multi-platform-content-collector/SKILL.md`: multi-platform public content collection workflow.
- `skills/seedance2-prompt-writer/SKILL.md`: Seedance prompt and storyboard writer.
- `skills/social-media-uploader/SKILL.md`: TikTok, Instagram, and YouTube upload workflow.
- `skills/topview-skill/references/`: focused module docs.
- `skills/topview-skill/scripts/`: TopView Python toolkit.

## Notes

Generation requires a TopView account and credits. The skill handles login by sending the user a direct TopView login link in chat.

Social publishing requires a Chrome debug browser on port 9222 with the target platform already logged in. The uploader supports safe dry runs with `--no-publish`.

Content collection uses public sources by default. Browser-driven platforms such as TikTok and X should only be enabled when the user explicitly asks for them and the existing browser login state is available.

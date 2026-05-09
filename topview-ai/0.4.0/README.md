# TopView AI Codex Plugin

TopView AI for Codex helps with the full content production loop: research competitors and trends, write stronger video scripts and prompts, generate media assets and Storyboard previews with TopView AI, organize outputs, and publish finished videos to social platforms.

Ask Codex to install this plugin from a shared zip with one message:

```text
Install the TopView AI Codex plugin from the zip I attached. Please extract it to %USERPROFILE%\Documents\Codex\local-marketplaces\topview-ai, make the marketplace id local, copy topview-ai/0.4.0 into %USERPROFILE%\.codex\plugins\cache\local\topview-ai\0.4.0, enable topview-ai@local, then tell me to restart Codex and start a new chat.
```

From the extracted repository root, the installer is:

```powershell
.\install-local-referenceable.ps1
```

After restart, verify the plugin in a new chat with:

```text
[@topview-ai](plugin://topview-ai@local) Write a 15-second product video script and generation prompt.
```

## Environment Requirements

- Codex Desktop or Codex CLI with local plugin support.
- Python 3.10 or newer available to Codex. The TopView scripts use modern Python type syntax that is not compatible with Python 3.9.
- Python packages listed in `skills/topview-skill/scripts/requirements.txt` installed for the Python runtime that runs the scripts:
  - `requests>=2.28.0`
  - `python-dotenv>=1.0.0`
- Network access to `https://www.topview.ai` for login, account checks, and generation API calls.
- A TopView account with available credits for generation tasks.
- Local credential storage access. Login saves credentials to `%USERPROFILE%\.topview\credentials.json` on Windows, or `~/.topview/credentials.json` on macOS/Linux.
- For social publishing only: Chrome running with remote debugging on port `9222`, with TikTok, Instagram, or YouTube already logged in.

Codex Desktop may include a bundled Python runtime, but plugin installers should not assume every user has that runtime or that it already contains the required packages. If a login or generation script fails with missing packages, install the requirements into the same Python environment used by Codex.

TopView AI lets Codex collect public content research, write scripts and model-ready prompts, generate and edit marketing media through TopView's Python toolkit, then publish finished videos to social platforms.

Typical tasks include competitor research, trend discovery, AI video prompt collection, video scriptwriting, storyboard and shot-list planning, product video generation, talking avatar creation, background removal, product model shots, text-to-speech, board management, and safe social publishing dry runs.

## Video Workflow

For new video creation requests, the plugin is expected to follow this sequence:

1. Analyze the user's production goal.
2. Ask for any missing inputs needed to make a good brief.
3. Write a first draft script, storyboard, or model-ready prompt.
4. Show the draft to the user and wait for confirmation or revisions.
5. After script confirmation, ask whether to generate a Storyboard preview image（分镜图）for visual confirmation. The user can skip this and go directly to video generation.
6. Only after confirmation or skip decision, generate the video with TopView.

This workflow is intentional. The plugin should not jump directly from a one-line request to video generation unless the user explicitly asks to skip review.

## Capabilities

- Video writing: creative angles, hooks, scripts, shot lists, storyboards, and model-ready prompts.
- Content research: collect structured public sources, competitor content, creators, comments, trends, links, and AI prompts across platforms.
- Video generation: text-to-video, image-to-video, and reference-based video.
- Image generation and editing: text-to-image, image edits, Storyboard grid previews, and style changes.
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
Turn this product introduction into a short-form video script and storyboard prompt, then generate the video with TopView AI.
```

```text
Run a YouTube dry-run upload for the generated video, then ask me before publishing.
```

## Layout

- `.codex-plugin/plugin.json`: plugin manifest.
- `skills/topview-skill/SKILL.md`: compact Codex-facing workflow.
- `skills/multi-platform-content-collector/SKILL.md`: multi-platform public content collection workflow.
- `skills/video-script-writer/SKILL.md`: video creative strategy, script, storyboard, and prompt writer.
- `skills/social-media-uploader/SKILL.md`: TikTok, Instagram, and YouTube upload workflow.
- `skills/topview-skill/references/`: focused module docs.
- `skills/topview-skill/scripts/`: TopView Python toolkit.

## Notes

Generation requires a TopView account and credits. The skill handles login by sending the user a direct TopView login link in chat.

Social publishing requires a Chrome debug browser on port 9222 with the target platform already logged in. The uploader supports safe dry runs with `--no-publish`.

Content collection uses public sources by default. Browser-driven platforms such as TikTok and X should only be enabled when the user explicitly asks for them and the existing browser login state is available.

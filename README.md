# TopView AI Codex Plugin

TopView AI for Codex helps with the full content production loop: research competitors and trends, write stronger video scripts and prompts, generate media assets and Storyboard previews with TopView AI, organize outputs, and publish finished videos to social platforms.

## Install With One Message

Please install the TopView AI Codex plugin from https://github.com/topviewai/codex-topview-ai.git and make sure it is fully referenceable as [@topview-ai](plugin://topview-ai@local).

This is a required full local installation flow. Do not stop after cloning the repository, do not only add the marketplace, and do not only copy the plugin cache. You must complete every step below.

### 1. Install And Verify Required Environment Dependencies

Install and verify all runtime dependencies before registering the plugin. Do not claim installation success if any required command or Python package is missing.

Required for core TopView generation:

- Codex Desktop or Codex CLI with local plugin support.
- Python 3.10 or newer. The TopView scripts use modern Python type syntax that is not compatible with Python 3.9.
- Python packages for `skills/topview-skill/scripts/`:
  - `requests>=2.28.0`
  - `python-dotenv>=1.0.0`

Required for `multi-platform-content-collector`:

- `opencli` CLI available on `PATH`.
- `curl` available on `PATH` for Reddit and Bilibili detail fetch scripts.
- Browser Bridge / OpenCLI browser support available for browser-driven platforms such as X/Twitter, TikTok, Xiaohongshu, Weibo, and Douyin.
- Existing browser login sessions for browser-driven platforms that require login. Never ask the user for passwords.

Required for social publishing:

- Chrome running with remote debugging on port `9222`.
- Target TikTok, Instagram, or YouTube account already logged in inside that debug browser.
- Python package dependencies for `tools/seo-browser-uploader/`:
  - `DrissionPage>=4.0`
  - `requests>=2.28`
  - `openai>=1.0`
  - `jinja2>=3.1`

Minimum verification commands:

```bash
python --version
opencli doctor
curl --version
```

Install Python dependencies into the same Python environment that Codex will use:

```bash
python -m pip install -r skills/topview-skill/scripts/requirements.txt
python -m pip install -e tools/seo-browser-uploader
```

### 2. Clone The Repository

Clone or download the GitHub repository into:

```text
%USERPROFILE%\Documents\Codex\local-marketplaces\topview-ai
```

On macOS/Linux, use the equivalent path:

```text
~/Documents/Codex/local-marketplaces/topview-ai
```

### 3. Create The Codex Marketplace Structure

Codex does not discover a plugin by scanning the repository root directly. The local marketplace must include a marketplace index and a plugin package directory:

```text
topview-ai/
  .agents/
    plugins/
      marketplace.json
  plugins/
    topview-ai/
      .codex-plugin/
      skills/
      tools/
      assets/
      results/
      README.md
```

Copy the actual plugin package files from the repository root into:

```text
%USERPROFILE%\Documents\Codex\local-marketplaces\topview-ai\plugins\topview-ai
```

On macOS/Linux:

```text
~/Documents/Codex/local-marketplaces/topview-ai/plugins/topview-ai
```

The copied files and folders must include:

```text
.codex-plugin
skills
tools
assets
results
README.md
```

### 4. Add The Marketplace Index

Create this file:

```text
%USERPROFILE%\Documents\Codex\local-marketplaces\topview-ai\.agents\plugins\marketplace.json
```

On macOS/Linux:

```text
~/Documents/Codex/local-marketplaces/topview-ai/.agents/plugins/marketplace.json
```

With this content:

```json
{
  "name": "local",
  "interface": {
    "displayName": "Local"
  },
  "plugins": [
    {
      "name": "topview-ai",
      "source": {
        "source": "local",
        "path": "./plugins/topview-ai"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

The marketplace name/id must be exactly `local`, and the plugin source path must be exactly `./plugins/topview-ai`.

### 5. Copy The Plugin Into The Codex Cache

Some Codex Desktop builds do not load a newly registered local plugin until the plugin package also exists in the local plugin cache. This cache copy is required.

Copy the same plugin package files into:

```text
%USERPROFILE%\.codex\plugins\cache\local\topview-ai\0.4.0
```

On macOS/Linux:

```text
~/.codex/plugins/cache/local/topview-ai/0.4.0
```

That cache directory must contain the plugin package files directly:

```text
0.4.0/
  .codex-plugin/
    plugin.json
  skills/
  tools/
  assets/
  results/
  README.md
```

Do not put an extra nested `topview-ai` or `plugins/topview-ai` folder inside the cache directory.

### 6. Register The Local Marketplace

Run:

```bash
codex plugin marketplace add ~/Documents/Codex/local-marketplaces/topview-ai
```

On Windows, use:

```powershell
codex plugin marketplace add "$env:USERPROFILE\Documents\Codex\local-marketplaces\topview-ai"
```

After registration, make sure the marketplace id/name is `local`.

### 7. Enable The Plugin

Add or update this entry in the Codex config file:

```toml
[plugins."topview-ai@local"]
enabled = true
```

The config file is usually located at:

```text
~/.codex/config.toml
```

On Windows, the equivalent path is usually:

```text
%USERPROFILE%\.codex\config.toml
```

### 8. Verify The Installation

Do not claim installation success until both the marketplace package and the cache package are present.

Check that all of these marketplace files exist:

```text
~/Documents/Codex/local-marketplaces/topview-ai/.agents/plugins/marketplace.json
~/Documents/Codex/local-marketplaces/topview-ai/plugins/topview-ai/.codex-plugin/plugin.json
~/Documents/Codex/local-marketplaces/topview-ai/plugins/topview-ai/skills/topview-skill/SKILL.md
~/Documents/Codex/local-marketplaces/topview-ai/plugins/topview-ai/skills/social-media-uploader/SKILL.md
~/Documents/Codex/local-marketplaces/topview-ai/plugins/topview-ai/tools/seo-browser-uploader
```

Also check that all of these cache files exist:

```text
~/.codex/plugins/cache/local/topview-ai/0.4.0/.codex-plugin/plugin.json
~/.codex/plugins/cache/local/topview-ai/0.4.0/skills/topview-skill/SKILL.md
~/.codex/plugins/cache/local/topview-ai/0.4.0/skills/social-media-uploader/SKILL.md
~/.codex/plugins/cache/local/topview-ai/0.4.0/tools/seo-browser-uploader
```

Open both plugin manifests:

```text
~/Documents/Codex/local-marketplaces/topview-ai/plugins/topview-ai/.codex-plugin/plugin.json
~/.codex/plugins/cache/local/topview-ai/0.4.0/.codex-plugin/plugin.json
```

Confirm both contain:

```json
{
  "name": "topview-ai",
  "version": "0.4.0"
}
```

If the plugin still does not appear, verify that `marketplace.json` exists, that it points to `./plugins/topview-ai`, and that the cache directory path is exactly `~/.codex/plugins/cache/local/topview-ai/0.4.0`.

### 9. Restart Codex

Fully quit and restart the Codex app. Opening a new chat is not enough if the plugin list was already loaded.

After restart, start a new chat and test:

```text
[@topview-ai](plugin://topview-ai@local)
```

If the plugin does not appear in the plugin list, do not claim installation success. Fix the marketplace index, plugin package directory, config entry, and cache package directory first, then repeat the verification checks.

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

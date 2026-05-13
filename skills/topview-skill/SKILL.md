---
name: topview-skill
description: Use when the user wants TopView AI to plan, research, script, generate, edit, organize, or publish marketing media from Codex: competitor content collection, video creative strategy, scripts, storyboards, AI video prompts, TopView video/image/avatar/voice generation, TopView boards, or publishing finished videos to TikTok, Instagram, and YouTube.
metadata:
  tags: topview, avatar, video, scriptwriting, publishing, image, voice, ai, api, i2v, t2v, text2image, image_edit, tts, board, research, content-collection
  requires:
    bins: [python3]
  primaryEnv: TOPVIEW_API_KEY
---

# TopView AI

Use TopView AI for the full content production loop: research what to make, write the video concept/script, generate or edit assets through TopView's Python toolkit, organize outputs, then publish finished videos when the user confirms.

For public web or social research requests, use `multi-platform-content-collector` to gather structured sources, creators, comments, prompts, trend signals, competitor content, or feedback. When the user's goal is ads, creative strategy, or competitor learning, turn the findings into reusable angles, hooks, and claims to test.

For video requests, always start with `video-script-writer` before any generation call. First analyze the request, ask for missing production inputs, write a first-draft concept, script, storyboard, and model-ready prompt, wait for user confirmation, then ask whether the user wants a Storyboard preview image before video generation. Always ask any user-facing confirmation question in the same language the user has been using. If the user skips the Storyboard image, submit through `scripts/video_gen.py` directly.

For publishing requests, use `social-media-uploader` after the video file exists. Prefer `--no-publish` dry runs before the first real publish in a session.

## Core Rules

- Always use the Python scripts in `scripts/`; do not call the TopView API directly.
- For video generation, do not generate immediately from a short request. First collect the production brief, then write a script/storyboard/prompt draft, then wait for explicit user confirmation before generating.
- For video generation, ask for the key missing inputs when they are not already provided: product or subject, core selling points, target channel, aspect ratio, style, available assets, and any required text or CTA.
- For video generation, show the user a first draft before generation. The draft should cover creative angle, shot flow, script or subtitle direction, and the generation prompt draft.
- After the script/storyboard draft is approved, ask whether to generate a Storyboard preview image with `scripts/ai_image.py --type storyboard` for visual confirmation. Make it clear this is optional and the user can skip it to generate the video directly. Phrase the question in the same language the user has been using.
- If a Storyboard preview image is used for final video generation, do not upload only the storyboard. Use `scripts/video_gen.py --type omni --storyboard-image <storyboard> --input-images <product_or_user_reference_images...> --reference-image-descriptions "<desc for Image2>" ... --prompt "<video script>"`. The script will force the final prompt into the required structure: "图一是分镜参考图，图二是xxx图片，下面是视频脚本内容...".
- For competitor or trend research, collect only public or user-authorized sources, preserve URLs and metrics, and separate observed facts from creative recommendations.
- For publishing, confirm platform, account/session readiness, title/caption, visibility, schedule, and final file before any real upload.
- Keep user-facing replies short and plain, especially for login and generation results.
- If login is needed, run `scripts/auth.py login`, extract the direct `URL: ...` link, send that link to the user, and wait for their confirmation.
- For new generation tasks, use each module's `run` command so submission and waiting are handled together.
- Before the first generated task, estimate cost when the module supports it, confirm key parameters, and tell the user the expected wait time.
- Use the default board from `scripts/board.py list --default -q` and pass `--board-id` to generation tasks when possible.
- Never publish to TikTok, Instagram, or YouTube without an explicit user confirmation; use private/only-me visibility for tests.

## Content Workflow

Follow this sequence for content tasks that involve more than a direct asset edit:

1. Research: when the user asks for market, competitor, trend, comment, creator, or source collection, use `multi-platform-content-collector` and preserve traceable sources.
2. Script: use `video-script-writer` to turn the brief or research into a creative angle, hook, script, storyboard, and model-ready prompt.
3. Storyboard preview: after the script is approved, ask whether to generate a Storyboard preview image for visual confirmation. If yes, run `scripts/ai_image.py --type storyboard`; if no, continue directly.
4. Generate: after user confirmation, estimate cost when available and run the relevant TopView video script. When a storyboard image is part of the approved flow, call `scripts/video_gen.py --type omni` with `--storyboard-image` and all product/user reference images in `--input-images`, so Image1 is the storyboard and Image2+ are the material references.
5. Organize: return output files and TopView board links when available.
6. Publish: use `social-media-uploader` only after the video file exists and the user explicitly confirms the platform settings.

Do not skip the script confirmation or publish confirmation steps unless the user explicitly says to skip review for that specific step. Storyboard preview images are optional; do not block video generation if the user chooses to skip them.

## Tool Routing

- Talking avatar from photo or script: `scripts/avatar4.py`
- Video creative strategy, scripts, storyboards, shot lists, or model prompts: `video-script-writer`
- Text-to-video, image-to-video, or reference video: `scripts/video_gen.py`
- Text-to-image, image editing, or Storyboard grid preview images: `scripts/ai_image.py`
- Background removal: `scripts/remove_bg.py`
- Product model showcase images: `scripts/product_avatar.py`
- Text-to-speech: `scripts/text2voice.py`
- Voice list, clone, or delete: `scripts/voice.py`
- Board and result browsing: `scripts/board.py`
- Credits and account usage: `scripts/user.py`
- Public web and social content collection: `multi-platform-content-collector`
- Upload finished videos to TikTok, Instagram, or YouTube: `social-media-uploader`

## References

Read the focused reference before running a module:

- Auth and login: `references/auth.md`
- Video generation: `references/video_gen.md`
- Image generation and editing: `references/ai_image.md`
- Talking avatar: `references/avatar4.md`
- Background removal: `references/remove_bg.md`
- Product avatar: `references/product_avatar.md`
- Text-to-speech: `references/text2voice.md`
- Voice tools: `references/voice.md`
- Board workflows: `references/board.md`
- Credit checks: `references/user.md`
- Error recovery: `references/error_handling.md`

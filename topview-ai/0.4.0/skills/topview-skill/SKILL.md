---
name: topview-skill
description: Use when the user wants TopView AI to generate or edit videos, write Seedance prompts, create images, avatars, product model shots, background removal, text-to-speech, voice tools, TopView boards, collect multi-platform content research, or publish generated videos to TikTok, Instagram, or YouTube from Codex.
metadata:
  tags: topview, avatar, video, image, voice, ai, api, i2v, t2v, text2image, image_edit, tts, board, research, content-collection
  requires:
    bins: [python3]
  primaryEnv: TOPVIEW_API_KEY
---

# TopView AI

Use TopView AI for generation and editing tasks that should run through TopView's Python toolkit.

For public web or social research requests, use `multi-platform-content-collector` to gather structured sources, creators, comments, prompts, trend signals, competitor content, or feedback before generating assets.

For video requests with vague creative direction, first use `seedance2-prompt-writer` to turn the idea into a structured Seedance 2.0 prompt, then submit it through `scripts/video_gen.py`.

For publishing requests, use `social-media-uploader` after the video file exists. Prefer `--no-publish` dry runs before the first real publish in a session.

## Core Rules

- Always use the Python scripts in `scripts/`; do not call the TopView API directly.
- For video generation, improve the user's idea into a Seedance-ready prompt before submitting when quality matters.
- Keep user-facing replies short and plain, especially for login and generation results.
- If login is needed, run `scripts/auth.py login`, extract the direct `URL: ...` link, send that link to the user, and wait for their confirmation.
- For new generation tasks, use each module's `run` command so submission and waiting are handled together.
- Before the first generated task, estimate cost when the module supports it, confirm key parameters, and tell the user the expected wait time.
- Use the default board from `scripts/board.py list --default -q` and pass `--board-id` to generation tasks when possible.
- Never publish to TikTok, Instagram, or YouTube without an explicit user confirmation; use private/only-me visibility for tests.

## Tool Routing

- Talking avatar from photo or script: `scripts/avatar4.py`
- Seedance 2.0 prompt, video script, or storyboard writing: `seedance2-prompt-writer`
- Text-to-video, image-to-video, or reference video: `scripts/video_gen.py`
- Text-to-image or image editing: `scripts/ai_image.py`
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

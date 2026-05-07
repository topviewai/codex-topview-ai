---
name: social-media-uploader
description: "Use when uploading videos to TikTok, Instagram, or YouTube after TopView generation."
---

# Social Media Uploader

Upload finished videos to TikTok, Instagram, and YouTube through the local `social-upload` CLI.

## Local Command

Use this executable from any working directory:

`C:\Users\chia1\.codex\tools\seo-browser-uploader\.venv\Scripts\social-upload.exe`

## Safety Rules

- Always run `--no-publish` first when testing a platform or account.
- Never publish without explicit user confirmation.
- For tests, prefer YouTube `--visibility private` and TikTok `--visibility only_me`.
- The uploader reuses a Chrome debug browser on port `9222`; the user must log in manually inside that browser.
- Never ask for or handle platform passwords.

## Platform Routing

- TikTok: `social-upload tiktok --video <file> --title <title> --description <desc>`
- YouTube: `social-upload youtube --video <file> --title <title> --description <desc>`
- Instagram: `social-upload instagram --video <file> --caption <caption>`

Add `--no-publish` for dry runs. Add `--schedule "YYYY-MM-DD HH:MM"` where the platform supports scheduling.

## Typical Flow

1. Confirm the target platform, video file, title/caption, description, visibility, and schedule.
2. Check Chrome debug port `http://127.0.0.1:9222/json/version`.
3. If Chrome is not available, launch a debug Chrome session and ask the user to log in.
4. Run the platform command with `--no-publish`.
5. If the dry run succeeds, ask for explicit confirmation before publishing.
6. If a command outputs `DIAG|`, use the repair commands from `references/full-uploader-guide.md`.

## References

- Full command guide: `references/full-uploader-guide.md`
- Examples: `examples.md`
- Troubleshooting: `troubleshooting.md`
- TikTok options: `platforms/tiktok-options.md`
- YouTube options: `platforms/youtube-options.md`
- Instagram options: `platforms/instagram-options.md`

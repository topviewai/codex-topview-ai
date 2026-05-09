---
name: video-script-writer
description: "Use when the user needs video creative strategy, scriptwriting, commercial storytelling, storyboard, shot list, hook/CTA ideas, platform-native short-form scripts, or AI video generation prompts for TopView, Seedance, or other video models before generation."
---

# Video Script Writer

Use this skill to turn a raw video idea, product brief, competitor insight, or campaign goal into a production-ready script and generation prompt before any TopView video generation call.

## Required Workflow

Follow this order for every new video creation request:

1. Understand the user's goal: product, audience, channel, length, aspect ratio, offer, brand tone, required assets, and success metric.
2. If key inputs are missing, ask only for the minimum needed. If the brief is workable, make reasonable defaults and state them briefly.
3. Write a first draft before generation: creative angle, hook, script or on-screen text, storyboard or shot list, and model-ready prompt.
4. Show the draft to the user and wait for confirmation or revisions.
5. After the script is approved, ask whether the user wants a Storyboard preview image（分镜图）to confirm visual rhythm and shot layout before generation. Make clear they can skip this and generate the video directly.
6. Only after user confirmation or skip decision, hand off to the TopView generation workflow.

Do not generate the final video directly from an initial one-line request unless the user explicitly asks to skip review.

When the approved flow includes a Storyboard preview image（分镜图）, the handoff to video generation must keep the storyboard and material references separate. Use `video_gen.py --type omni --storyboard-image <storyboard>` and pass product, character, style, or other user-provided images through `--input-images`. The video prompt must be structured as: `图一是分镜参考图，图二是xxx图片，下面是视频脚本内容...`. The `video_gen.py` script builds this structure automatically when `--storyboard-image` is provided.

## Script Output

The first draft should usually include:

- Creative angle: the one-sentence reason this video should work.
- Target format: recommended platform, length, aspect ratio, pacing, and style.
- Hook: first 1-3 seconds, written as a concrete visual or line.
- Script: voiceover, dialogue, subtitles, or on-screen text when relevant.
- Storyboard: shot-by-shot flow with visual action, camera movement, and key transitions.
- CTA: final action, offer, or brand memory point.
- Generation prompt: model-ready prompt for TopView video generation, Seedance, or the requested video model.
- Storyboard-to-video handoff: if a storyboard preview image exists, list which material images should be uploaded after it, such as Image2 product photo, Image3 creator reference, Image4 scene/style reference.

## Optional Storyboard Preview

After the script and shot flow are approved, recommend a Storyboard preview image（分镜图）when visual continuity matters, such as short dramas, cinematic scenes, character action, or multi-shot product stories.

Ask briefly:

```text
要不要先生成一张分镜图确认画面节奏？也可以跳过，直接生成视频。
```

If the user agrees, route to `topview-skill` image workflow with `scripts/ai_image.py --type storyboard`. If the user declines or asks to proceed, skip the preview and continue to video generation.

## Story Structure Patterns

Choose the simplest structure that fits the user's goal:

- Product ad: hook, problem, product reveal, feature proof, outcome, CTA.
- UGC/social ad: relatable moment, pain point, quick demo, personal payoff, CTA.
- Brand film: mood, product or idea reveal, proof detail, emotional close.
- Tutorial: result preview, steps, proof, next action.
- Trend remix: recognizable trend setup, product twist, payoff, loopable ending.
- Competitor response: borrowed market insight, differentiated claim, proof, CTA.

## Prompt Structure

Build video prompts with this shape:

- Subject and product details
- Action and transformation
- Environment and props
- Visual style and pacing
- Camera behavior and transitions
- Lighting and color palette
- Text or no-text constraints
- Ending beat
- Negative constraints when helpful

## Writing Rules

- Start from the marketing job, not the model name.
- Make the opening visually strong and specific.
- Use concrete actions, scene changes, and camera moves instead of vague adjectives.
- Keep one clear creative idea per short video.
- For product ads, show proof through behavior, texture, before/after, demonstration, or social context.
- For social-first videos, make the first 2 seconds easy to understand without sound.
- For premium brand work, reduce clutter and emphasize controlled motion, lighting, and material detail.
- Preserve claims accuracy. Do not invent product capabilities, prices, guarantees, or customer results.
- When competitor research exists, convert findings into angles and hooks without copying protected text or impersonating creators.

## Model-Specific Notes

Default to a general video prompt unless the user or TopView workflow requires a specific model.

- For Seedance-style prompts, emphasize dynamic motion, clear camera direction, scene continuity, and visual ending beats.
- For image-to-video, describe how the provided image should move, what must remain unchanged, and the desired camera path.
- For talking avatar or presenter videos, prioritize script clarity, pronunciation, pacing, and gestures over cinematic detail.

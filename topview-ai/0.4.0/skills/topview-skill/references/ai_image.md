# AI Image Module

Generate images from text prompts, edit existing images, or create storyboard grid preview images for short drama planning.

## Supported Task Types

| Type | Description | Required Params |
|------|-------------|-----------------|
| `text2image` | **Text-to-Image** — generate images from a text prompt | `--model`, `--prompt`, `--aspect-ratio` |
| `image_edit` | **Image Edit** — edit images with prompt + reference images | `--model`, `--prompt`, `--aspect-ratio`, `--input-images` |
| `storyboard` | **Storyboard** — generate a 16:9 grid storyboard preview for short drama beats | `--prompt`, optional `--cell-aspect-ratio`, `--shot-count`, `--target-duration-seconds`, `--reference-images` |

## Subcommands

| Subcommand | When to use | Polls? |
|------------|-------------|--------|
| `run` | **Default.** New request, start to finish | Yes — waits until done |
| `submit` | Batch: fire multiple tasks without waiting | No — exits immediately |
| `query` | Recovery: resume polling a known `taskId` | Yes — waits until done |
| `list-models` | Check models, constraints, and supported ratios | No |
| `estimate-cost` | Estimate credit cost before running | No |

## Usage

```bash
python {baseDir}/scripts/ai_image.py <subcommand> --type <text2image|image_edit|storyboard> [options]
```

## Examples

### List Models

```bash
python {baseDir}/scripts/ai_image.py list-models --type text2image
python {baseDir}/scripts/ai_image.py list-models --type image_edit --json
```

### Text-to-Image

```bash
python {baseDir}/scripts/ai_image.py run \
  --type text2image \
  --model "Nano Banana 2" \
  --prompt "A futuristic city skyline at dusk, neon lights reflected on wet streets" \
  --aspect-ratio "16:9" \
  --resolution "2K" \
  --count 2
```

Fixed-price model (no resolution):

```bash
python {baseDir}/scripts/ai_image.py run \
  --type text2image \
  --model "GPT Image 1.5" \
  --prompt "A watercolor painting of a cat" \
  --aspect-ratio "1:1"
```

GPT Image 2:

```bash
python {baseDir}/scripts/ai_image.py run \
  --type text2image \
  --model "GPT Image 2" \
  --prompt "A clean launch poster for a new AI image product with crisp readable text" \
  --aspect-ratio "16:9" \
  --resolution "2K"
```

### Image Edit

```bash
python {baseDir}/scripts/ai_image.py run \
  --type image_edit \
  --model "Nano Banana 2" \
  --prompt "Change the background to a snowy mountain landscape" \
  --aspect-ratio "auto" \
  --resolution "2K" \
  --input-images photo.jpg
```

Multi-image reference:

```bash
python {baseDir}/scripts/ai_image.py run \
  --type image_edit \
  --model "Nano Banana 2" \
  --prompt "Blend the style of both images" \
  --aspect-ratio "1:1" \
  --resolution "2K" \
  --input-images style.jpg content.jpg \
  --count 2
```

### Storyboard

Use this for a single image that previews a short-drama beat as multiple storyboard cells. The built-in `finalPrompt` template must stay complete and close to the product reference prompt: overall 16:9 layout, locked per-cell aspect ratio, grid count rule, blank/black margin allowance, chronological reading order, thin black separators, one key frame per cell, storyboard duration design, visual consistency requirements, reference-material mapping, and plot. For the current numbered-preview mode, each cell has only a small top-left sequence number, with no captions, subtitles, dialogue text, shot descriptions, title, watermark, UI labels, or bottom text bars. Backend parameters are fixed: `type="storyboardToVideo"`, `model="GPT Image 2"`, `aspectRatio="16:9"`, `resolution="2K"`, and `generateCount=1`. Do not ask the user for an image model, whole-image aspect ratio, resolution, or count for this mode.

Parameter mapping:

| CLI parameter | Injected into final prompt as |
|---|---|
| `--prompt` | `[Plot to Represent]` |
| `--cell-aspect-ratio` | hard cell ratio constraint, default `"9:16"` |
| `--shot-count N` | `fixed count: exactly N storyboard cells` |
| no `--shot-count` | automatic count, usually 4-9 cells and up to 16 for complex plots |
| `--target-duration-seconds N` | total duration rule requiring all shot durations to sum to `N`s with +/-1s tolerance |
| no `--target-duration-seconds` | generic duration rule; model designs 1s-15s per shot |
| `--reference-images` | uploaded as ordered references corresponding to `@Image 1`, `@Image 2`, ... |

Visible text rule: only numeric cell labels (`1`, `2`, `3`, ...) are allowed. Do not generate bottom metadata bars or descriptive text inside cells.

Automatic storyboard count:

```bash
python {baseDir}/scripts/ai_image.py run \
  --type storyboard \
  --prompt "女主深夜回家，发现门口有一封匿名信。她打开信后脸色骤变，镜头切到楼道尽头的黑影。" \
  --cell-aspect-ratio "9:16" \
  --target-duration-seconds 12
```

Fixed storyboard count with reference images:

```bash
python {baseDir}/scripts/ai_image.py run \
  --type storyboard \
  --prompt "@Image 1 是女主参考，@Image 2 是公寓走廊参考。女主推门进入，发现桌上出现陌生人的照片。" \
  --cell-aspect-ratio "9:16" \
  --shot-count 6 \
  --reference-images heroine.jpg hallway.jpg
```

### Cost Estimation

```bash
python {baseDir}/scripts/ai_image.py estimate-cost \
  --type text2image --model "Nano Banana 2" --resolution "2K" --count 2
```

### Download Results

```bash
python {baseDir}/scripts/ai_image.py run \
  --type text2image --model "Nano Banana 2" \
  --prompt "Northern lights" --aspect-ratio "16:9" --resolution "2K" \
  --output-dir ./results
```

## Options

| Option | Description |
|--------|-------------|
| `--type` | `text2image` or `image_edit` (required) |
| `--model` | Model **display name** (required) |
| `--prompt` | Text prompt (required) |
| `--aspect-ratio` | Aspect ratio (required), e.g. `"16:9"`, `"1:1"`, `"auto"` |
| `--resolution` | `"512p"`, `"1K"`, `"2K"`, `"4K"` — model-dependent |
| `--count` | Number of images (1-4, default: 1) |
| `--board-id` | Board ID |
| `--input-images` | Reference image fileIds/local paths (image_edit only) |
| `--cell-aspect-ratio` | Storyboard cell ratio injected into the English final prompt, default `"9:16"` |
| `--shot-count` | Fixed number of storyboard cells; omit for automatic count |
| `--target-duration-seconds` | Target total beat duration injected into the duration rule |
| `--reference-images` | Storyboard reference images, mapped to `@Image 1`, `@Image 2`, ... |
| `--timeout` | Max polling time (default: 300) |
| `--interval` | Polling interval (default: 3) |
| `--output-dir` | Download results to directory |
| `--json` | Full JSON response |
| `-q, --quiet` | Suppress status messages |

## Model Recommendation

> **Nano Banana 2 is the top recommendation for all image tasks.**
> Best overall quality, 14 aspect ratios, up to 4K, 14 reference images for editing.

| Use Case | Recommended Models | Why |
|----------|--------------------|-----|
| **Best overall (default)** | **Nano Banana 2** | Strongest all-round model |
| **Budget** | Seedream 4.0 (0.15/img), Grok Image (0.15/img) | Lowest cost |
| **No-resolution simplicity** | GPT Image 1.5, Kontext-Pro | No resolution param needed |
| **GPT Image 2** | GPT Image 2 | TopView display-name model with 13 ratios and 1K/2K/4K |
| **Auto aspect ratio** | Seedream 5.0, Seedream 4.5 | `auto` ratio |

**Defaults:**
- text2image → `Nano Banana 2`
- image_edit → `Nano Banana 2`

## Key Notes

- `aspectRatio` is always required; image_edit models additionally support `"auto"`
- `resolution` is required for some models, forbidden for others — check via `list-models`
- `GPT Image 2` must be called exactly by TopView display name `"GPT Image 2"`; do not pass a provider code name or alias
- `GPT Image 2` supports aspect ratios `9:16`, `3:4`, `1:1`, `4:3`, `16:9`, `2:3`, `3:2`, `5:4`, `4:5`, `21:9`, `9:21`, `1:2`, and `2:1`
- `GPT Image 2` requires `--resolution "1K"`, `"2K"`, or `"4K"`
- `GPT Image 2` image editing accepts up to 16 input images
- **Imagen 4** is only available for text2image, not image_edit
- `storyboard` is a fixed image feature: it always sends `prompt=<final storyboard prompt>`, `aspectRatio="16:9"`, `type="storyboardToVideo"`, `model="GPT Image 2"`, `resolution="2K"`, and `generateCount=1`

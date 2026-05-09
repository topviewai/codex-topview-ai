# Video Generation Module

Generate videos from images, text prompts, or reference materials.

## Supported Task Types

| Type | Description | Required Params |
|------|-------------|-----------------|
| `i2v` | **Image-to-Video V2** — generate video from first/end frame images | `--first-frame` or `--ref-images` |
| `t2v` | **Text-to-Video** — generate video purely from a text prompt | `--model`, `--prompt` |
| `omni` | **Omni Reference** — generate video from reference images/videos + prompt | `--model`, `--prompt` |

## Subcommands

| Subcommand | When to use | Polls? |
|------------|-------------|--------|
| `run` | **Default.** New request, start to finish | Yes — waits until done |
| `submit` | Batch: fire multiple tasks without waiting | No — exits immediately |
| `query` | Recovery: resume polling a known `taskId` | Yes — waits until done |
| `list-models` | Check models, constraints, and audio support | No |
| `estimate-cost` | Estimate credit cost before running | No |

## Usage

```bash
python {baseDir}/scripts/video_gen.py <subcommand> --type <i2v|t2v|omni> [options]
```

## Examples

### List Models

```bash
python {baseDir}/scripts/video_gen.py list-models --type t2v
python {baseDir}/scripts/video_gen.py list-models --type i2v --json
```

### Image-to-Video (i2v)

```bash
python {baseDir}/scripts/video_gen.py run \
  --type i2v \
  --first-frame <fileId_or_local_path> \
  --prompt "A product slowly rotating on a clean white background" \
  --model "Seedance 1.5 Pro" \
  --resolution 1080 \
  --duration 5
```

With first + end frame:

```bash
python {baseDir}/scripts/video_gen.py run \
  --type i2v \
  --first-frame <fileId> \
  --end-frame <fileId> \
  --prompt "Smooth transition between scenes" \
  --resolution 1080
```

### Text-to-Video (t2v)

```bash
python {baseDir}/scripts/video_gen.py run \
  --type t2v \
  --model "Seedance 1.5 Pro" \
  --prompt "A futuristic city at night with neon lights reflecting on wet streets" \
  --aspect-ratio "16:9" \
  --resolution 1080 \
  --duration 5 \
  --sound on
```

### Omni Reference

Recommended cross-platform form:

```bash
python {baseDir}/scripts/video_gen.py run \
  --type omni \
  --model "Standard" \
  --prompt "Apply the style from <<<Image1>>> to the motion in <<<Video1>>>" \
  --input-images Image1=style.png \
  --input-videos Video1=motion.mp4 \
  --aspect-ratio "9:16" \
  --resolution 720
```

Storyboard-led final video:

Use this when a storyboard preview image（分镜图）has already been approved and the final video also needs product, character, style, or other user-provided image references. The storyboard is always uploaded as `Image1`; the other images become `Image2`, `Image3`, and so on. The script automatically rewrites the prompt into the required structure: "图一是分镜参考图，图二是xxx图片，下面是视频脚本内容...".

```bash
python {baseDir}/scripts/video_gen.py run \
  --type omni \
  --model "Standard" \
  --storyboard-image storyboard.png \
  --input-images product.png creator.jpg \
  --reference-image-descriptions "商品图" "达人/人物参考图" \
  --prompt "15s UGC product video script: hook, demo, proof, CTA..." \
  --aspect-ratio "9:16" \
  --resolution 720 \
  --duration 15
```

Bare paths/fileIds are auto-named in order:

```bash
python {baseDir}/scripts/video_gen.py run \
  --type omni \
  --model "Standard" \
  --prompt "Combine <<<Image1>>> and <<<Image2>>> into a product video" \
  --input-images product.png background.png
```

Legacy JSON form:

```bash
python {baseDir}/scripts/video_gen.py run \
  --type omni \
  --model "Standard" \
  --prompt "Apply the style from <<<Image1>>> to the motion in <<<Video1>>>" \
  --input-images '[{"fileId":"file_style","name":"Image1"}]' \
  --input-videos '[{"fileId":"file_motion","name":"Video1"}]'
```

### Cost Estimation

```bash
python {baseDir}/scripts/video_gen.py estimate-cost \
  --model "Seedance 1.5 Pro" --resolution 1080 --duration 5 --sound on --count 2
```

### Recovery / Batch

```bash
TASK_ID=$(python {baseDir}/scripts/video_gen.py submit \
  --type t2v --model "Seedance 1.5 Pro" --prompt "Sunset over ocean" -q)

python {baseDir}/scripts/video_gen.py query \
  --type t2v --task-id <taskId> --timeout 1200
```

## Common Options

| Option | Description |
|--------|-------------|
| `--type` | Task type: `i2v`, `t2v`, `omni` (required) |
| `--model` | Model **display name** (required for t2v/omni) |
| `--prompt` | Text prompt (required for t2v/omni) |
| `--aspect-ratio` | Aspect ratio, e.g. `"16:9"` |
| `--resolution` | `480`, `540`, `720`, `768`, `1080`, or `2160` |
| `--duration` | Video duration in seconds |
| `--sound` | Native audio: `"on"` / `"off"` |
| `--count` | Number of videos (1-4) |
| `--board-id` | Board ID |
| `--timeout` | Max polling time (default: 600) |
| `--interval` | Polling interval (default: 5) |
| `--output-dir` | Download result videos to directory |
| `--json` | Output full JSON response |
| `-q, --quiet` | Suppress status messages |

### i2v only

| Option | Description |
|--------|-------------|
| `--first-frame` | First frame image fileId or local path |
| `--end-frame` | End frame image fileId or local path |
| `--ref-images` | Reference image fileIds/paths (multi-ref, >=2) |

### omni only

| Option | Description |
|--------|-------------|
| `--input-images` | Recommended: `Image1=product.png` or bare refs `product.png another.png`; legacy JSON array still supported |
| `--storyboard-image` | Storyboard reference image for final video generation. When set, the script makes this `Image1`, makes `--input-images` become `Image2...`, and rebuilds the prompt as storyboard + material references + script. Requires `--input-images`. |
| `--reference-image-descriptions` | Ordered descriptions for images after `--storyboard-image`, e.g. `"商品图"` `"达人参考图"` `"场景风格图"` |
| `--input-videos` | Recommended: `Video1=demo.mp4`; legacy JSON array still supported |
| `--internet-search` | Enable internet search (Standard/Fast only) |

## Native Audio (`--sound`)

- Only models with `nativeAudio=True` support this — check via `list-models`
- Sound may increase cost depending on model

## Omni Prompt Syntax

Use `<<<ImageN>>>` or `<<<VideoN>>>` to reference inputs:

```
"Apply the color style from <<<Image1>>> to <<<Video1>>>"
```

Input parsing:

- `Name=value` keeps the explicit name, e.g. `Image1=product.png`.
- Bare values are auto-named in order, e.g. `product.png another.png` becomes `Image1`, `Image2`.
- Local paths are uploaded automatically; existing fileIds are passed through.
- If a single value starts with `[` or `{`, it is parsed as legacy JSON for backward compatibility.

## Model Recommendation

> **Note:** `Standard` and `Fast` are top-tier models with industry-leading visual quality, native audio, and up to 15s duration, delivered Seedance 2.0-level capabilities. Available for all three task types (i2v, t2v, omni). Use `Standard` for best quality; use `Fast` for quicker turnaround at similar quality.

**By priority:**

| Priority | Recommended Models | Why |
|----------|--------------------|-----|
| **Best quality** | Standard, Kling O3, Veo 3.1, Sora 2 Pro | Top-tier visual fidelity |
| **Fast turnaround** | Fast, Seedance 1.0 Pro Fast, Veo 3.1 Fast | Quicker, lower cost |
| **Long clips (10s+)** | Standard/Fast (15s), Kling V3/O3 (15s), Vidu Q3 Pro (16s) | Extended duration |
| **4K** | Veo 3.1, Veo 3.1 Fast | Only models with 2160p |
| **Budget** | Topview Lite (0.1/s), Topview Pro (0.2/s) | Lowest cost |
| **Native audio** | Standard/Fast, Kling O3/V3, Veo 3.1, Vidu Q3 Pro | Ambient sound |

**By channel:**

| Channel | Aspect Ratio | Good Models |
|---------|-------------|-------------|
| TikTok / Reels | 9:16 | Standard, Kling V3 |
| YouTube | 16:9 | Standard, Kling O3, Veo 3.1 |
| Instagram | 3:4 or 1:1 | Standard, Seedance 1.5 Pro |

**Defaults** (when user has no preference):
- t2v → `Standard`
- i2v → `Standard` or `Kling V3`
- omni → `Standard`

## Prompt Tips

**Structure:** Subject + Action + Environment + Style + Camera

**Camera keywords:** "static shot", "slow pan left", "dolly forward", "tracking shot", "orbit around", "zoom in", "crane shot rising", "shallow depth of field"

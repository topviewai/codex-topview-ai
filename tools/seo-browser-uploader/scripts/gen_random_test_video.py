"""Generate a short random test video for upload sanity-checks.

Outputs an MP4 using imageio + the bundled ffmpeg binary (no system ffmpeg).
Intended for one-off testing; the file is plain colored frames + overlay text.
"""

from __future__ import annotations

import random
import string
import sys
from datetime import datetime
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _pick_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def make_video(out_path: Path, *, seconds: int = 6, fps: int = 24, size: tuple[int, int] = (720, 1280)) -> Path:
    width, height = size
    rng = random.Random()
    short_id = "".join(rng.choices(string.ascii_uppercase + string.digits, k=6))
    title_line = f"TEST {short_id}"
    sub_line = datetime.now().strftime("%Y-%m-%d %H:%M")

    title_font = _pick_font(96)
    sub_font = _pick_font(40)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(
        str(out_path),
        fps=fps,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
        macro_block_size=8,
    )
    try:
        total = seconds * fps
        for i in range(total):
            t = i / total
            r = int(60 + 120 * (0.5 + 0.5 * np.sin(2 * np.pi * t)))
            g = int(60 + 120 * (0.5 + 0.5 * np.sin(2 * np.pi * t + 2.094)))
            b = int(60 + 120 * (0.5 + 0.5 * np.sin(2 * np.pi * t + 4.188)))
            img = Image.new("RGB", (width, height), (r, g, b))
            draw = ImageDraw.Draw(img)

            tw, th = draw.textbbox((0, 0), title_line, font=title_font)[2:]
            draw.text(((width - tw) // 2, (height - th) // 2 - 60), title_line, fill=(255, 255, 255), font=title_font)
            sw, sh = draw.textbbox((0, 0), sub_line, font=sub_font)[2:]
            draw.text(((width - sw) // 2, (height - th) // 2 + 50), sub_line, fill=(230, 230, 230), font=sub_font)

            counter = f"{i+1}/{total}"
            cw, ch = draw.textbbox((0, 0), counter, font=sub_font)[2:]
            draw.text((width - cw - 20, height - ch - 20), counter, fill=(255, 255, 255), font=sub_font)

            writer.append_data(np.asarray(img))
    finally:
        writer.close()

    return out_path


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Desktop" / "test_upload.mp4"
    final = make_video(target)
    print(f"OK {final} {final.stat().st_size} bytes")

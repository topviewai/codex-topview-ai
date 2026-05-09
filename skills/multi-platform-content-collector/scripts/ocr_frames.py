#!/usr/bin/env python3
"""
OCR text extraction from video frames.
Extracts text from all frame images in a directory, filters for prompt-like content.

Usage:
    python3 ocr_frames.py /tmp/vid/

Prerequisites:
    brew install tesseract tesseract-lang
    pip install pytesseract Pillow
"""
import sys, os, re

try:
    import pytesseract
    from PIL import Image
except ImportError:
    print("Missing dependencies. Run:")
    print("  brew install tesseract tesseract-lang")
    print("  pip install pytesseract Pillow")
    sys.exit(1)

PROMPT_KEYWORDS = [
    "prompt", "提示词", "cinematic", "scene", "camera", "shot",
    "style", "subject", "environment", "lighting", "action",
    "format", "timeline", "negative", "动作", "镜头", "风格",
]

def is_prompt_text(text):
    """Check if extracted text looks like a prompt."""
    lower = text.lower()
    matches = sum(1 for kw in PROMPT_KEYWORDS if kw.lower() in lower)
    return matches >= 2 and len(text) > 50

def extract_text_from_frames(frames_dir):
    """Extract text from all image files in directory."""
    results = []
    files = sorted(f for f in os.listdir(frames_dir) if f.endswith(('.jpg', '.png', '.jpeg')))

    if not files:
        print(f"No image files found in {frames_dir}")
        return results

    print(f"Processing {len(files)} frames...")

    for fname in files:
        path = os.path.join(frames_dir, fname)
        try:
            img = Image.open(path)
            text = pytesseract.image_to_string(img, lang='eng+chi_sim')
            text = text.strip()
            if text and is_prompt_text(text):
                results.append({"frame": fname, "text": text})
                print(f"  [PROMPT FOUND] {fname}: {text[:80]}...")
        except Exception as e:
            print(f"  [ERROR] {fname}: {e}")

    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ocr_frames.py <frames_directory>")
        sys.exit(1)

    frames_dir = sys.argv[1]
    results = extract_text_from_frames(frames_dir)

    if results:
        print(f"\n=== Found {len(results)} frames with prompt text ===")
        for r in results:
            print(f"\n--- {r['frame']} ---")
            print(r['text'])
    else:
        print("\nNo prompt text found in frames. Try AI vision model instead.")

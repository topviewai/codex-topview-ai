#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 was not found. Install Python 3.9+ first."
  echo "macOS example: brew install python"
  exit 1
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 9):
    raise SystemExit(f"Python 3.9+ is required; current version is {sys.version.split()[0]}")
PY

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

".venv/bin/python" -m pip install --upgrade pip setuptools wheel
".venv/bin/python" -m pip install -e .

echo ""
echo "social-upload installed:"
".venv/bin/social-upload" --help | head -n 20
echo ""
echo "Next:"
echo "  bash scripts/start_chrome_debug.sh"
echo "  .venv/bin/social-upload tiktok --video \"video.mp4\" --title \"Title\" --description \"Desc\" --visibility only_me --no-publish"

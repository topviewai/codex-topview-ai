#!/usr/bin/env python3
"""
social_uploader 代码修改后自动化验证脚本。

用法：.venv/bin/python scripts/verify_code.py

检查分两档：
  P0（必须通过）：import 验证、JSON 语法、CLI 可用性
  P1（建议通过）：grep 模式匹配，检测旧写法和常见错误
"""

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src" / "social_uploader"

results = []


def record(level, name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append((level, name, passed, detail))
    icon = "✅" if passed else "❌"
    print(f"  {icon} [{level}] {name}" + (f" — {detail}" if detail and not passed else ""))


# ──────────────── P0：必须通过 ────────────────

print("\n🔍 P0 检查（必须通过）\n")

# P0-1: 全量 import
try:
    import importlib
    modules = [
        "social_uploader.command_entry",
        "social_uploader.repair_engine",
        "social_uploader.error_classifier",
        "social_uploader.tools.element_finder",
        "social_uploader.tools.browser_manager",
        "social_uploader.tools.upload_profile",
        "social_uploader.uploaders",
        "social_uploader.uploaders.tiktok",
        "social_uploader.uploaders.instagram",
        "social_uploader.uploaders.youtube",
        "social_uploader.uploaders.video_check",
    ]
    failed_imports = []
    for mod in modules:
        try:
            importlib.import_module(mod)
        except Exception as e:
            failed_imports.append(f"{mod}: {e}")
    if failed_imports:
        record("P0", "全量 import", False, "; ".join(failed_imports))
    else:
        record("P0", "全量 import", True)
except Exception as e:
    record("P0", "全量 import", False, str(e))

# P0-2: button_config.json 语法
btn_cfg = SRC_DIR / "button_config.json"
try:
    data = json.loads(btn_cfg.read_text(encoding="utf-8"))
    is_valid = isinstance(data, dict) and all(
        isinstance(v, dict) and all(isinstance(sels, list) for sels in v.values())
        for v in data.values()
    )
    if is_valid:
        record("P0", "button_config.json 语法", True)
    else:
        record("P0", "button_config.json 语法", False, "结构不符合 平台→按钮名→列表 格式")
except Exception as e:
    record("P0", "button_config.json 语法", False, str(e))

# P0-3: default.json 语法
default_json = SRC_DIR / "profiles" / "default.json"
try:
    json.loads(default_json.read_text(encoding="utf-8"))
    record("P0", "default.json 语法", True)
except Exception as e:
    record("P0", "default.json 语法", False, str(e))

# P0-4: CLI 可用性
try:
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "social-upload"
    if not venv_python.exists():
        venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "social-upload"
    result = subprocess.run(
        [str(venv_python), "--help"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        record("P0", "CLI --help", True)
    else:
        record("P0", "CLI --help", False, result.stderr[:200])
except FileNotFoundError:
    record("P0", "CLI --help", False, "social-upload 命令未找到，可能未安装（pip install -e .）")
except Exception as e:
    record("P0", "CLI --help", False, str(e)[:200])

# ──────────────── P1：建议通过 ────────────────

print("\n🔍 P1 检查（建议通过）\n")

uploaders_dir = SRC_DIR / "uploaders"
uploader_files = list(uploaders_dir.glob("*.py"))
all_py_files = list(SRC_DIR.rglob("*.py"))

# P1-1: 无旧版 _should_skip 调用
old_skip_hits = []
for f in uploader_files:
    if f.name == "__init__.py":
        continue
    content = f.read_text(encoding="utf-8")
    for i, line in enumerate(content.splitlines(), 1):
        if "_should_skip(" in line and not line.strip().startswith("#") and not line.strip().startswith('"') and not line.strip().startswith("'"):
            old_skip_hits.append(f"{f.name}:{i}")
if old_skip_hits:
    record("P1", "无旧版 _should_skip 调用", False, f"发现于: {', '.join(old_skip_hits)}")
else:
    record("P1", "无旧版 _should_skip 调用", True)

# P1-2: should_skip 调用传了 3 个参数（step, resume_from, STEPS）
bad_skip_calls = []
for f in uploader_files:
    if f.name == "__init__.py":
        continue
    content = f.read_text(encoding="utf-8")
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"') or stripped.startswith("'"):
            continue
        match = re.search(r'should_skip\(([^)]+)\)', line)
        if match:
            args = [a.strip() for a in match.group(1).split(",")]
            if len(args) != 3:
                bad_skip_calls.append(f"{f.name}:{i} (参数数={len(args)})")
if bad_skip_calls:
    record("P1", "should_skip 传 3 参数", False, f"不正确: {', '.join(bad_skip_calls)}")
else:
    record("P1", "should_skip 传 3 参数", True)

# P1-3: connect_browser 解包为 4 值
bad_connect = []
for f in all_py_files:
    content = f.read_text(encoding="utf-8")
    for i, line in enumerate(content.splitlines(), 1):
        if "connect_browser(" in line and "=" in line and "def " not in line and "import " not in line:
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            lhs = line.split("=")[0].strip()
            comma_count = lhs.count(",")
            if comma_count < 3 and "connect_browser" not in lhs:
                bad_connect.append(f"{f.relative_to(SRC_DIR)}:{i}")
if bad_connect:
    record("P1", "connect_browser 解包为 4 值", False, f"不正确: {', '.join(bad_connect)}")
else:
    record("P1", "connect_browser 解包为 4 值", True)

# P1-4: dismiss_interfering_overlays 传 3 参数
bad_dismiss = []
for f in all_py_files:
    content = f.read_text(encoding="utf-8")
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#") or "def dismiss" in line or "import " in line:
            continue
        match = re.search(r'dismiss_interfering_overlays\(([^)]+)\)', line)
        if match:
            args = [a.strip() for a in match.group(1).split(",")]
            if len(args) != 3:
                bad_dismiss.append(f"{f.relative_to(SRC_DIR)}:{i} (参数数={len(args)})")
if bad_dismiss:
    record("P1", "dismiss_interfering_overlays 传 3 参数", False, f"不正确: {', '.join(bad_dismiss)}")
else:
    record("P1", "dismiss_interfering_overlays 传 3 参数", True)

# ──────────────── 汇总 ────────────────

print("\n" + "=" * 50)
p0_pass = all(r[2] for r in results if r[0] == "P0")
p1_pass = all(r[2] for r in results if r[0] == "P1")
total_pass = sum(1 for r in results if r[2])
total = len(results)

if p0_pass and p1_pass:
    print(f"🎉 全部通过 ({total_pass}/{total})")
    sys.exit(0)
elif p0_pass:
    failed_p1 = [r[1] for r in results if r[0] == "P1" and not r[2]]
    print(f"⚠️ P0 全部通过，P1 有 {len(failed_p1)} 项未通过: {', '.join(failed_p1)}")
    sys.exit(1)
else:
    failed_p0 = [r[1] for r in results if r[0] == "P0" and not r[2]]
    print(f"❌ P0 有 {len(failed_p0)} 项未通过（必须修复）: {', '.join(failed_p0)}")
    sys.exit(2)

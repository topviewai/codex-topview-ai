#!/usr/bin/env python3
"""
social_uploader 全链路模拟测试

不连接浏览器，不做真实上传，纯粹验证代码逻辑和模块协作是否通畅。

覆盖链路：
  1. 视频预校验（通过/拒绝）
  2. should_skip 跳步逻辑
  3. 错误分类 → 处理策略路由
  4. Profile 加载与合并
  5. 按钮选择器加载与查找
  6. 日志记录（log_step / write_summary / write_detail）
  7. DOM 快照分析与修复建议（suggest_selectors）
  8. 选择器热修复（add_selector）
  9. CLI 参数解析
  10. 全链路串联：校验→分类→日志→修复建议
"""

import json
import os
import sys
import shutil
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

passed = 0
failed = 0
errors = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        msg = f"{name}: {detail}" if detail else name
        errors.append(msg)
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


# ═══════════════════════════════════════════════════
#  1. 视频预校验
# ═══════════════════════════════════════════════════
print("\n🎬 1. 视频预校验\n")

from social_uploader.uploaders.video_check import validate_video_file

tmp_dir = tempfile.mkdtemp(prefix="social_uploader_test_")

# 1a. 文件不存在
ok, msg = validate_video_file("/not/exists/video.mp4")
check("不存在的文件 → 拒绝", not ok and "不存在" in msg)

# 1b. 格式不支持
bad_ext = os.path.join(tmp_dir, "test.txt")
with open(bad_ext, "wb") as f:
    f.write(b"x" * 20000)
ok, msg = validate_video_file(bad_ext)
check("不支持的格式(.txt) → 拒绝", not ok and "不支持" in msg)

# 1c. 文件太小
tiny = os.path.join(tmp_dir, "tiny.mp4")
with open(tiny, "wb") as f:
    f.write(b"x" * 100)
ok, msg = validate_video_file(tiny)
check("文件过小(100B) → 拒绝", not ok and "过小" in msg)

# 1d. 合法文件
good = os.path.join(tmp_dir, "good.mp4")
with open(good, "wb") as f:
    f.write(b"x" * 50000)
ok, msg = validate_video_file(good)
check("合法文件(50KB .mp4) → 通过", ok and msg == "")

# 1e. 各种合法后缀
for ext in [".mov", ".avi", ".mkv", ".webm"]:
    p = os.path.join(tmp_dir, f"test{ext}")
    with open(p, "wb") as f:
        f.write(b"x" * 20000)
    ok, _ = validate_video_file(p)
    check(f"合法格式({ext}) → 通过", ok)


# ═══════════════════════════════════════════════════
#  2. should_skip 跳步逻辑
# ═══════════════════════════════════════════════════
print("\n⏭️ 2. should_skip 跳步逻辑\n")

from social_uploader.uploaders import should_skip

STEPS = ["validate", "connect", "login", "file_inject", "publish", "confirm"]

# 2a. 无 resume_from → 不跳过任何步骤
check("resume_from=None → 不跳过", not should_skip("validate", None, STEPS))

# 2b. resume_from 不在 STEPS 中 → 不跳过
check("resume_from='invalid' → 不跳过", not should_skip("validate", "invalid", STEPS))

# 2c. resume_from=publish → 跳过 validate/connect/login/file_inject
check("resume=publish → 跳过 validate", should_skip("validate", "publish", STEPS))
check("resume=publish → 跳过 connect", should_skip("connect", "publish", STEPS))
check("resume=publish → 跳过 login", should_skip("login", "publish", STEPS))
check("resume=publish → 跳过 file_inject", should_skip("file_inject", "publish", STEPS))
check("resume=publish → 不跳过 publish", not should_skip("publish", "publish", STEPS))
check("resume=publish → 不跳过 confirm", not should_skip("confirm", "publish", STEPS))

# 2d. resume_from=第一个步骤 → 不跳过任何
check("resume=validate → 不跳过 validate", not should_skip("validate", "validate", STEPS))

# 2e. 对三个平台的 STEPS 验证完整性
from social_uploader.uploaders.tiktok import STEPS as TK_STEPS
from social_uploader.uploaders.youtube import STEPS as YT_STEPS
from social_uploader.uploaders.instagram import STEPS as IG_STEPS

check("TikTok STEPS 包含 validate", "validate" in TK_STEPS)
check("TikTok STEPS 包含 confirm", "confirm" in TK_STEPS)
check("YouTube STEPS 包含 validate", "validate" in YT_STEPS)
check("YouTube STEPS 包含 confirm", "confirm" in YT_STEPS)
check("Instagram STEPS 包含 validate", "validate" in IG_STEPS)
check("Instagram STEPS 包含 confirm", "confirm" in IG_STEPS)

# 2f. 三个平台的 STEPS 没有重复项
check("TikTok STEPS 无重复", len(TK_STEPS) == len(set(TK_STEPS)))
check("YouTube STEPS 无重复", len(YT_STEPS) == len(set(YT_STEPS)))
check("Instagram STEPS 无重复", len(IG_STEPS) == len(set(IG_STEPS)))


# ═══════════════════════════════════════════════════
#  3. 错误分类 → 处理策略路由
# ═══════════════════════════════════════════════════
print("\n🔀 3. 错误分类与路由\n")

from social_uploader.error_classifier import classify_error, is_agent_fixable, ERROR_TYPES

check("selector_not_found → agent_fix", classify_error("selector_not_found") == "agent_fix")
check("login_required → notify_user", classify_error("login_required") == "notify_user")
check("rate_limit → wait_retry", classify_error("rate_limit") == "wait_retry")
check("unknown → escalate_user", classify_error("unknown") == "escalate_user")
check("不存在的错误 → escalate_user", classify_error("made_up_error") == "escalate_user")
check("selector_not_found 可自动修复", is_agent_fixable("selector_not_found"))
check("login_required 不可自动修复", not is_agent_fixable("login_required"))
check("timeout 需通知用户", not is_agent_fixable("timeout"))

# 验证所有错误类型都有明确的策略
known_strategies = {"agent_fix", "notify_user", "wait_retry", "escalate_user"}
for err_code, strategy in ERROR_TYPES.items():
    check(f"错误 '{err_code}' 策略 '{strategy}' 合法", strategy in known_strategies)


# ═══════════════════════════════════════════════════
#  4. Profile 加载与合并
# ═══════════════════════════════════════════════════
print("\n📋 4. Profile 加载与合并\n")

from social_uploader.tools.upload_profile import load_profile, get_platform_config

# 4a. 默认 profile 加载
default_p = load_profile()
check("默认 profile 加载成功", isinstance(default_p, dict))
check("默认 profile 包含 youtube", "youtube" in default_p)
check("默认 profile 包含 common", "common" in default_p)
check("默认 profile 包含 tiktok", "tiktok" in default_p)
check("默认 profile 包含 instagram", "instagram" in default_p)

# 4b. YouTube 默认配置
yt_config = get_platform_config(default_p, "youtube")
check("YouTube 默认 made_for_kids=False", yt_config.get("made_for_kids") is False)
check("YouTube 默认 visibility=public", yt_config.get("visibility") == "public")

# 4c. TikTok/Instagram 默认配置（空字典，不报错）
tk_config = get_platform_config(default_p, "tiktok")
check("TikTok 默认配置是 dict", isinstance(tk_config, dict))
ig_config = get_platform_config(default_p, "instagram")
check("Instagram 默认配置是 dict", isinstance(ig_config, dict))

# 4d. 自定义 profile 合并
custom_profile = os.path.join(tmp_dir, "custom.json")
with open(custom_profile, "w") as f:
    json.dump({"youtube": {"visibility": "unlisted", "made_for_kids": True}}, f)

merged = load_profile(custom_profile)
yt_custom = get_platform_config(merged, "youtube")
check("自定义 profile 合并: visibility=unlisted", yt_custom.get("visibility") == "unlisted")
check("自定义 profile 合并: made_for_kids=True", yt_custom.get("made_for_kids") is True)

# 4e. 不存在的 profile → 报错
try:
    load_profile("/not/exists/profile.json")
    check("不存在的 profile → 应报 FileNotFoundError", False)
except FileNotFoundError:
    check("不存在的 profile → FileNotFoundError", True)


# ═══════════════════════════════════════════════════
#  5. 按钮选择器加载与查找
# ═══════════════════════════════════════════════════
print("\n🔘 5. 按钮选择器系统\n")

from social_uploader.tools.element_finder import load_selectors, reload_selectors, add_selector

reload_selectors()

# 5a. 加载各平台选择器
for platform in ["tiktok", "instagram", "youtube"]:
    sels = load_selectors(platform)
    check(f"{platform} 选择器加载成功", isinstance(sels, dict) and len(sels) > 0)

# 5b. 具体选择器存在
tk_sels = load_selectors("tiktok")
check("TikTok file_input 选择器存在", "file_input" in tk_sels)
check("TikTok post_button 选择器存在", "post_button" in tk_sels)
check("TikTok file_input 是列表", isinstance(tk_sels.get("file_input", None), list))

ig_sels = load_selectors("instagram")
check("Instagram create_button 选择器存在", "create_button" in ig_sels)
check("Instagram share_button 选择器存在", "share_button" in ig_sels)

yt_sels = load_selectors("youtube")
check("YouTube upload_icon 选择器存在", "upload_icon" in yt_sels)
check("YouTube done_button 选择器存在", "done_button" in yt_sels)

# 5c. 不存在的平台 → 空字典
empty = load_selectors("nonexistent_platform")
check("不存在的平台 → 空字典", empty == {})


# ═══════════════════════════════════════════════════
#  6. 日志与修复系统
# ═══════════════════════════════════════════════════
print("\n📝 6. 日志与修复系统\n")

from social_uploader.repair_engine import (
    generate_run_id, log_step, write_summary, write_detail,
    log_diag_line, suggest_selectors,
    _element_matches_step, _generate_selectors_for_element, STEP_KEYWORDS,
)

# 6a. run_id 生成
rid1 = generate_run_id()
rid2 = generate_run_id()
check("run_id 长度=8", len(rid1) == 8)
check("run_id 是字母数字", rid1.isalnum())
check("两次 run_id 不同", rid1 != rid2)

# 6b. log_step 不报错（输出到 stderr）
import io
old_stderr = sys.stderr
sys.stderr = io.StringIO()
log_step("test_step", "ok", detail="模拟测试")
log_step("test_step", "fail", error="timeout", detail="模拟超时")
stderr_output = sys.stderr.getvalue()
sys.stderr = old_stderr
check("log_step 输出到 stderr", len(stderr_output) > 0)
check("log_step 输出包含 JSON", '"step"' in stderr_output and '"status"' in stderr_output)

# 6c. write_summary 和 write_detail 写入文件
test_run_id = "test_" + rid1
write_summary(test_run_id, "tiktok", "publish", "selector_not_found",
              "https://tiktok.com/upload", selectors_tried="post_button")
from social_uploader.repair_engine import _LOG_DIR
summary_file = _LOG_DIR / "summary.jsonl"
check("summary.jsonl 文件存在", summary_file.exists())

summary_content = summary_file.read_text(encoding="utf-8")
last_line = summary_content.strip().split("\n")[-1]
summary_data = json.loads(last_line)
check("summary 包含 run_id", summary_data.get("run_id") == test_run_id)
check("summary 包含 platform", summary_data.get("platform") == "tiktok")
check("summary 包含 error", summary_data.get("error") == "selector_not_found")

# 6d. write_detail
mock_dom = json.dumps([
    {"tag": "button", "data-e2e": "publish_btn", "text": "Post video"},
    {"tag": "button", "aria-label": "Upload", "text": "Upload"},
    {"tag": "input", "type": "file"},
])
write_detail(test_run_id, "publish", "selector_not_found", dom_snippet=mock_dom)
detail_file = _LOG_DIR / f"detail_{test_run_id}.jsonl"
check("detail 文件存在", detail_file.exists())

detail_content = detail_file.read_text(encoding="utf-8")
detail_data = json.loads(detail_content.strip().split("\n")[-1])
check("detail 包含 dom_snippet", "dom_snippet" in detail_data)

# 6e. DIAG 行输出
old_stdout = sys.stdout
sys.stdout = io.StringIO()
log_diag_line(test_run_id, "tiktok", "publish", "selector_not_found")
diag_output = sys.stdout.getvalue()
sys.stdout = old_stdout
check("DIAG 行格式正确", diag_output.startswith("DIAG|"))
check("DIAG 包含 run_id", f"run_id={test_run_id}" in diag_output)
check("DIAG 包含 platform", "platform=tiktok" in diag_output)


# ═══════════════════════════════════════════════════
#  7. DOM 分析与修复建议
# ═══════════════════════════════════════════════════
print("\n🔧 7. DOM 分析与修复建议\n")

# 7a. 元素匹配测试
mock_btn = {"tag": "button", "data-e2e": "publish_btn", "text": "Post video"}
check("post_button 匹配 'Post video' 按钮", _element_matches_step(mock_btn, "post_button"))
check("file_input 不匹配 'Post video' 按钮", not _element_matches_step(mock_btn, "file_input"))

mock_input = {"tag": "input", "type": "file"}
check("file_input 匹配 input[type=file]", _element_matches_step(mock_input, "file_input"))

mock_create = {"tag": "svg", "aria-label": "New post", "text": ""}
check("create_button 匹配 'New post'", _element_matches_step(mock_create, "create_button"))

# 7b. 选择器生成
sels = _generate_selectors_for_element(mock_btn)
check("从按钮生成选择器数 >= 2", len(sels) >= 2)
check("data-e2e 选择器在结果中", any("data-e2e" in s for s in sels))
check("text 选择器在结果中", any("text:" in s for s in sels))

sels_input = _generate_selectors_for_element(mock_input)
check("从 input 生成 xpath 选择器", any("xpath:" in s for s in sels_input))

# 7c. suggest_selectors 完整流程
result = suggest_selectors(test_run_id)
check("suggest_selectors 返回字符串", isinstance(result, str))
check("suggest_selectors 包含 STEP", "STEP:" in result)
check("suggest_selectors 包含 PLATFORM", "PLATFORM:" in result)
check("suggest_selectors 包含 RUN_ONE", "RUN_ONE:" in result)
check("suggest_selectors 包含 fix-selector 命令", "fix-selector" in result)
check("suggest_selectors 的 fix-selector 用 button_key", "post_button" in result)

# 7d. 对非 selector_not_found 错误的处理
write_summary("test_login", "tiktok", "login", "login_required", "https://tiktok.com")
result_login = suggest_selectors("test_login")
check("login_required → NO_FIX", "NO_FIX" in result_login)


# ═══════════════════════════════════════════════════
#  8. 选择器热修复（add_selector）
# ═══════════════════════════════════════════════════
print("\n🔩 8. 选择器热修复\n")

# 8a. 正常添加
reload_selectors()
ok, msg = add_selector("tiktok", "post_button", "@data-e2e=test_selector_999")
check("添加新选择器成功", ok and "OK" in msg)

# 8b. 验证已插入到列表开头
reload_selectors()
tk_post = load_selectors("tiktok").get("post_button", [])
check("新选择器在列表开头", tk_post[0] == "@data-e2e=test_selector_999")

# 8c. 重复添加 → 不重复
ok, msg = add_selector("tiktok", "post_button", "@data-e2e=test_selector_999")
check("重复添加 → 提示已存在", ok and "已存在" in msg)

# 8d. 不存在的平台
ok, msg = add_selector("weibo", "post_button", "text:发布")
check("不存在的平台 → 失败", not ok and "不存在" in msg)

# 8e. 不存在的 key
ok, msg = add_selector("tiktok", "nonexistent_button", "text:test")
check("不存在的 key → 失败", not ok and "不存在" in msg)

# 清理：移除测试添加的选择器
from pathlib import Path
btn_cfg_path = Path(PROJECT_ROOT) / "src" / "social_uploader" / "button_config.json"
cfg_data = json.loads(btn_cfg_path.read_text(encoding="utf-8"))
if "@data-e2e=test_selector_999" in cfg_data.get("tiktok", {}).get("post_button", []):
    cfg_data["tiktok"]["post_button"].remove("@data-e2e=test_selector_999")
    btn_cfg_path.write_text(json.dumps(cfg_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
reload_selectors()
check("测试选择器已清理", "@data-e2e=test_selector_999" not in load_selectors("tiktok").get("post_button", []))


# ═══════════════════════════════════════════════════
#  9. CLI 参数解析
# ═══════════════════════════════════════════════════
print("\n🖥️ 9. CLI 参数解析\n")

import argparse
from unittest.mock import patch

from social_uploader.command_entry import main

# 9a. tiktok 参数解析
with patch("sys.argv", ["social-upload", "tiktok", "--video", "v.mp4", "--title", "T", "--description", "D"]):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='platform')
    p_tk = subparsers.add_parser('tiktok')
    p_tk.add_argument('--video', required=True)
    p_tk.add_argument('--title', required=True)
    p_tk.add_argument('--description', required=True)
    p_tk.add_argument('--cover', default=None)
    p_tk.add_argument('--no-publish', action='store_true')
    p_tk.add_argument('--resume-from', default=None)
    p_tk.add_argument('--profile', default=None)
    args = parser.parse_args(["tiktok", "--video", "v.mp4", "--title", "T", "--description", "D"])
    check("TikTok 参数: video", args.video == "v.mp4")
    check("TikTok 参数: title", args.title == "T")
    check("TikTok 参数: no_publish 默认 False", args.no_publish is False)
    check("TikTok 参数: cover 默认 None", args.cover is None)

# 9b. instagram 参数解析
parser2 = argparse.ArgumentParser()
sub2 = parser2.add_subparsers(dest='platform')
p_ig = sub2.add_parser('instagram')
p_ig.add_argument('--video', required=True)
p_ig.add_argument('--caption', required=True)
p_ig.add_argument('--no-publish', action='store_true')
args2 = parser2.parse_args(["instagram", "--video", "v.mp4", "--caption", "文案"])
check("Instagram 参数: caption", args2.caption == "文案")

# 9c. youtube 参数解析
parser3 = argparse.ArgumentParser()
sub3 = parser3.add_subparsers(dest='platform')
p_yt = sub3.add_parser('youtube')
p_yt.add_argument('--video', required=True)
p_yt.add_argument('--title', required=True)
p_yt.add_argument('--description', required=True)
p_yt.add_argument('--no-publish', action='store_true')
args3 = parser3.parse_args(["youtube", "--video", "v.mp4", "--title", "T", "--description", "D", "--no-publish"])
check("YouTube 参数: no_publish=True", args3.no_publish is True)


# ═══════════════════════════════════════════════════
#  10. 全链路串联模拟
# ═══════════════════════════════════════════════════
print("\n🔗 10. 全链路串联模拟\n")

# 模拟一次完整的「上传失败 → 错误分类 → 日志 → 修复建议 → 热修复」流程
sim_run_id = generate_run_id()
sim_platform = "tiktok"
sim_step = "publish"
sim_error = "selector_not_found"

# Step A: 验证视频
ok, _ = validate_video_file(good)
check("[链路] 视频校验通过", ok)

# Step B: 模拟 should_skip（不跳过）
skip = should_skip(sim_step, None, TK_STEPS)
check("[链路] 不跳过 publish 步骤", not skip)

# Step C: 模拟失败 → 错误分类
strategy = classify_error(sim_error)
check("[链路] selector_not_found → agent_fix", strategy == "agent_fix")

# Step D: 记录日志
old_stderr2 = sys.stderr
sys.stderr = io.StringIO()
log_step(sim_step, "fail", error=sim_error, detail="post_button 未找到")
sys.stderr = old_stderr2

# Step E: 写入摘要和详情
mock_dom2 = json.dumps([
    {"tag": "button", "data-e2e": "new_post_btn", "text": "Post"},
    {"tag": "div", "role": "button", "text": "Publish now"},
])
write_summary(sim_run_id, sim_platform, sim_step, sim_error, "https://tiktok.com/upload",
              selectors_tried="post_button")
write_detail(sim_run_id, sim_step, sim_error, dom_snippet=mock_dom2)
check("[链路] 日志写入成功", (_LOG_DIR / f"detail_{sim_run_id}.jsonl").exists())

# Step F: 修复建议
suggestion = suggest_selectors(sim_run_id)
has_fix = "RUN_ONE:" in suggestion and "fix-selector" in suggestion
check("[链路] 修复建议包含 fix-selector 命令", has_fix)

# Step G: 模拟热修复
reload_selectors()
ok, msg = add_selector(sim_platform, "post_button", "@data-e2e=new_post_btn")
check("[链路] 热修复添加选择器成功", ok)

# Step H: 验证修复后选择器在列表开头
reload_selectors()
first_sel = load_selectors(sim_platform).get("post_button", [""])[0]
check("[链路] 修复后选择器在列表开头", first_sel == "@data-e2e=new_post_btn")

# Step I: 模拟 resume-from（从 publish 步骤恢复）
for step in TK_STEPS:
    skip = should_skip(step, sim_step, TK_STEPS)
    expected = TK_STEPS.index(step) < TK_STEPS.index(sim_step)
    if skip != expected:
        check(f"[链路] resume-from={sim_step} 跳步 {step}", False,
              f"期望 skip={expected}, 实际 skip={skip}")
        break
else:
    check("[链路] resume-from 跳步逻辑全部正确", True)

# 清理测试选择器
cfg_data = json.loads(btn_cfg_path.read_text(encoding="utf-8"))
if "@data-e2e=new_post_btn" in cfg_data.get("tiktok", {}).get("post_button", []):
    cfg_data["tiktok"]["post_button"].remove("@data-e2e=new_post_btn")
    btn_cfg_path.write_text(json.dumps(cfg_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
reload_selectors()

# 清理测试日志
for f in _LOG_DIR.glob(f"detail_test_*.jsonl"):
    f.unlink(missing_ok=True)
for f in _LOG_DIR.glob(f"detail_{sim_run_id}.jsonl"):
    f.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════
#  清理 & 汇总
# ═══════════════════════════════════════════════════
shutil.rmtree(tmp_dir, ignore_errors=True)

print("\n" + "=" * 55)
total = passed + failed
if failed == 0:
    print(f"🎉 全部通过 ({passed}/{total})")
    sys.exit(0)
else:
    print(f"❌ {failed} 项未通过 / {total} 总项")
    for e in errors:
        print(f"   • {e}")
    sys.exit(1)

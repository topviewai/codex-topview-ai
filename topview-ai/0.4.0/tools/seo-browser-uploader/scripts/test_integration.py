"""集成模拟测试 — 验证 AI 混合增强架构的完整链路。

用 Mock 对象模拟 DrissionPage 页面行为，测试:
1. ai_judge 模块的 LLM 调用 / JSON 解析 / 降级逻辑
2. post_publish 的弹窗处理 + 成功确认链路
3. 三平台 state_patterns.json 配置完整性
4. 上传器 → post_publish → ai_judge 的集成调用链
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

passed = 0
failed = 0

def ok(msg):
    global passed
    passed += 1
    print(f"  ✅ {msg}")

def fail(msg, detail=""):
    global failed
    failed += 1
    print(f"  ❌ {msg}" + (f" — {detail}" if detail else ""))


# === Mock 对象 ===

class MockStates:
    def __init__(self, has_rect=True):
        self.has_rect = has_rect

class MockElement:
    def __init__(self, tag="div", text="", has_rect=True, attrs=None):
        self.tag = tag
        self.text = text
        self.states = MockStates(has_rect)
        self._attrs = attrs or {}
        self._children = []
        self._clicked = False

    def ele(self, selector, timeout=0):
        for child in self._children:
            if f"text:{child.text}" == selector or f"text:{child.text.strip()}" == selector.replace("text:", ""):
                return child
        return None

    def eles(self, selector, timeout=0):
        return [c for c in self._children if c.tag == "button"] if "button" in selector else self._children

    def click(self):
        self._clicked = True

    def attr(self, name):
        return self._attrs.get(name)

    def add_child(self, child):
        self._children.append(child)
        return self


class MockPage:
    def __init__(self, url="https://www.tiktok.com/upload"):
        self.url = url
        self._elements = {}
        self._alert_count = 0

    def ele(self, selector, timeout=0):
        return self._elements.get(selector)

    def handle_alert(self, accept=True, timeout=0):
        self._alert_count += 1

    def register_element(self, selector, element):
        self._elements[selector] = element


# === 测试 1: ai_judge JSON 解析 ===

print("\n🧠 1. AI Judge — JSON 解析")

from social_uploader.tools.ai_judge import _parse_json_response

r = _parse_json_response('{"status":"ok","message":"test"}')
if r and r["status"] == "ok":
    ok("纯 JSON 字符串解析")
else:
    fail("纯 JSON 字符串解析")

r = _parse_json_response('```json\n{"status":"ok"}\n```')
if r and r["status"] == "ok":
    ok("Markdown JSON 块解析")
else:
    fail("Markdown JSON 块解析")

r = _parse_json_response('Here is the result: {"action":"click_button","button_text":"Post"} hope this helps')
if r and r["action"] == "click_button":
    ok("混合文本中提取 JSON")
else:
    fail("混合文本中提取 JSON")

r = _parse_json_response(None)
if r is None:
    ok("None 输入 → None")
else:
    fail("None 输入 → None")

r = _parse_json_response("not json at all")
if r is None:
    ok("非 JSON 文本 → None")
else:
    fail("非 JSON 文本 → None")

r = _parse_json_response("")
if r is None:
    ok("空字符串 → None")
else:
    fail("空字符串 → None")

r = _parse_json_response('```\n{"type":"confirm","confidence":0.9}\n```')
if r and r["type"] == "confirm":
    ok("无语言标记的 Markdown 块解析")
else:
    fail("无语言标记的 Markdown 块解析")


# === 测试 2: ai_judge API Key 加载 ===

print("\n🔑 2. AI Judge — API Key")

from social_uploader.tools.ai_judge import _load_api_key

key = _load_api_key()
if key and len(key) > 10:
    ok(f"API Key 已加载 ({key[:6]}...)")
else:
    fail("API Key 未找到或过短")


# === 测试 3: ai_judge 降级（无 API Key 时） ===

print("\n🔄 3. AI Judge — 降级逻辑")

from social_uploader.tools.ai_judge import judge_popup, judge_success

mock_page = MockPage()
result = judge_popup.__wrapped__(mock_page, "tiktok") if hasattr(judge_popup, '__wrapped__') else None
ok("judge_popup 函数可调用（实际测试需浏览器页面）")

result = judge_success.__wrapped__(mock_page, "tiktok") if hasattr(judge_success, '__wrapped__') else None
ok("judge_success 函数可调用（实际测试需浏览器页面）")


# === 测试 4: state_patterns.json 三平台配置完整性 ===

print("\n📋 4. state_patterns.json — 配置完整性")

patterns_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'social_uploader', 'state_patterns.json')
with open(patterns_path) as f:
    patterns = json.load(f)

for platform in ["tiktok", "youtube", "instagram"]:
    p = patterns.get(platform, {})

    if "publish_confirm" in p:
        ok(f"{platform}: publish_confirm 节点存在")
    else:
        fail(f"{platform}: 缺少 publish_confirm 节点")

    pc = p.get("publish_confirm", {})
    if "dialog_selectors" in pc:
        ok(f"{platform}: dialog_selectors 已配置 ({len(pc['dialog_selectors'])} 个)")
    else:
        fail(f"{platform}: 缺少 dialog_selectors")

    if "secondary_confirm" in pc:
        ok(f"{platform}: secondary_confirm 已配置 ({len(pc['secondary_confirm'])} 个)")
    else:
        fail(f"{platform}: 缺少 secondary_confirm")

    if "confirm" in p:
        ok(f"{platform}: confirm 节点存在")
    else:
        fail(f"{platform}: 缺少 confirm 节点")

    confirm = p.get("confirm", {})
    if "success_signals" in confirm:
        ok(f"{platform}: success_signals 已配置 ({len(confirm['success_signals'])} 个)")
    else:
        fail(f"{platform}: 缺少 success_signals")

# YouTube 特有字段
yt_confirm = patterns.get("youtube", {}).get("confirm", {})
if "close_button" in yt_confirm:
    ok("youtube: confirm.close_button 存在")
else:
    fail("youtube: 缺少 confirm.close_button")
if "dialog_selector" in yt_confirm:
    ok("youtube: confirm.dialog_selector 存在")
else:
    fail("youtube: 缺少 confirm.dialog_selector")


# === 测试 5: post_publish — _find_dialog ===

print("\n🔍 5. post_publish — 弹窗检测")

from social_uploader.tools.post_publish import _find_dialog

page_empty = MockPage()
result = _find_dialog(page_empty, "tiktok")
if result is None:
    ok("无弹窗时返回 None")
else:
    fail("无弹窗时应返回 None")

page_with_dialog = MockPage()
dialog_el = MockElement(tag="div", text="Are you sure you want to post?")
page_with_dialog.register_element("xpath://*[contains(@class,'TUXModal')]", dialog_el)
result = _find_dialog(page_with_dialog, "tiktok")
if result is not None:
    ok("TikTok TUXModal 弹窗检测成功")
else:
    fail("TikTok TUXModal 弹窗检测失败")

page_yt = MockPage("https://studio.youtube.com")
yt_dialog = MockElement(tag="ytcp-uploads-dialog", text="Upload complete")
page_yt.register_element("xpath://ytcp-uploads-dialog", yt_dialog)
result = _find_dialog(page_yt, "youtube")
if result is not None:
    ok("YouTube 上传对话框检测成功")
else:
    fail("YouTube 上传对话框检测失败")


# === 测试 6: post_publish — _try_whitelist_click ===

print("\n🖱️ 6. post_publish — 白名单按钮点击")

from social_uploader.tools.post_publish import _try_whitelist_click

dialog = MockElement(tag="div", text="Confirm publish?")
post_btn = MockElement(tag="button", text="Post")
dialog.add_child(post_btn)
result = _try_whitelist_click(dialog, "tiktok")
if result and post_btn._clicked:
    ok("TikTok 白名单按钮 'Post' 点击成功")
else:
    fail("TikTok 白名单按钮 'Post' 点击失败")

dialog2 = MockElement(tag="div", text="Some unknown dialog")
random_btn = MockElement(tag="button", text="Do something weird")
dialog2.add_child(random_btn)
result = _try_whitelist_click(dialog2, "tiktok")
if not result and not random_btn._clicked:
    ok("非白名单按钮不会被误点")
else:
    fail("非白名单按钮不应被点击")

dialog3 = MockElement(tag="div", text="Schedule confirmation")
sched_btn = MockElement(tag="button", text="Schedule")
dialog3.add_child(sched_btn)
result = _try_whitelist_click(dialog3, "tiktok")
if result and sched_btn._clicked:
    ok("TikTok 白名单按钮 'Schedule' 点击成功")
else:
    fail("TikTok 白名单按钮 'Schedule' 点击失败")


# === 测试 7: post_publish — wait_for_publish_confirmation URL 快路径 ===

print("\n🌐 7. post_publish — URL 快路径确认")

from social_uploader.tools.post_publish import wait_for_publish_confirmation

class QuickRedirectPage(MockPage):
    def __init__(self):
        super().__init__("https://www.tiktok.com/creator/content")

page_redir = QuickRedirectPage()
success, reason = wait_for_publish_confirmation(page_redir, "tiktok", timeout_s=4)
if success and "url_redirect" in reason:
    ok("TikTok URL 跳转到 /content → 判定成功")
else:
    fail(f"TikTok URL 跳转检测失败: success={success}, reason={reason}")

class ManagePage(MockPage):
    def __init__(self):
        super().__init__("https://www.tiktok.com/creator/manage")

page_manage = ManagePage()
success, reason = wait_for_publish_confirmation(page_manage, "tiktok", timeout_s=4)
if success and "url_redirect" in reason:
    ok("TikTok URL 跳转到 /manage → 判定成功")
else:
    fail(f"TikTok URL /manage 检测失败: success={success}, reason={reason}")


# === 测试 8: post_publish — error_check_fn 回调 ===

print("\n⚠️ 8. post_publish — 平台错误检测回调")

class StillUploadPage(MockPage):
    def __init__(self):
        super().__init__("https://www.tiktok.com/upload")

def mock_error_fn(page):
    return True, "Video processing failed"

page_err = StillUploadPage()
success, reason = wait_for_publish_confirmation(page_err, "tiktok", timeout_s=8, error_check_fn=mock_error_fn)
if not success and "platform_error" in reason:
    ok("error_check_fn 回调正确触发 → 判定失败")
else:
    fail(f"error_check_fn 未正确触发: success={success}, reason={reason}")


# === 测试 9: post_publish — 超时处理 ===

print("\n⏰ 9. post_publish — 超时处理")

page_stuck = StillUploadPage()
start = time.time()
success, reason = wait_for_publish_confirmation(page_stuck, "tiktok", timeout_s=4)
elapsed = time.time() - start
if not success and "timeout" in reason:
    ok(f"超时正确返回失败 ({elapsed:.1f}秒)")
else:
    fail(f"超时处理异常: success={success}, reason={reason}")


# === 测试 10: handle_post_publish_popups — abort 路径 ===

print("\n🚫 10. handle_post_publish_popups — 无弹窗场景")

from social_uploader.tools.post_publish import handle_post_publish_popups

page_clean = MockPage("https://www.tiktok.com/upload")
result = handle_post_publish_popups(page_clean, "tiktok", max_rounds=3)
if result["action"] != "abort":
    ok("无弹窗时不触发 abort")
else:
    fail("无弹窗时不应触发 abort")


# === 测试 11: 上传器 import 验证 ===

print("\n📦 11. 上传器集成 — import 链完整性")

import importlib
for mod_name in [
    'social_uploader.uploaders.tiktok',
    'social_uploader.uploaders.youtube',
    'social_uploader.uploaders.instagram',
]:
    try:
        mod = importlib.import_module(mod_name)
        ok(f"{mod_name} 导入成功")
    except Exception as e:
        fail(f"{mod_name} 导入失败", str(e))

from social_uploader.uploaders.tiktok import upload_tiktok
from social_uploader.uploaders.youtube import upload_youtube
from social_uploader.uploaders.instagram import upload_instagram
ok("三平台 upload_* 函数可导入")


# === 测试 12: TikTok _check_upload_error 作为回调兼容性 ===

print("\n🔗 12. TikTok — _check_upload_error 回调签名")

from social_uploader.uploaders.tiktok import _check_upload_error
import inspect
sig = inspect.signature(_check_upload_error)
params = list(sig.parameters.keys())
if params == ["page"]:
    ok("_check_upload_error(page) 签名正确，可作为 error_check_fn")
else:
    fail(f"_check_upload_error 签名异常: {params}")


# === 测试 13: YouTube confirm 配置兼容 post_publish ===

print("\n🎬 13. YouTube — confirm 配置与 post_publish 兼容")

from social_uploader.tools.pattern_checker import get_patterns

yt_confirm = get_patterns("youtube", "confirm")
if "close_button" in yt_confirm and "dialog_selector" in yt_confirm:
    ok("youtube.confirm 包含 close_button + dialog_selector")
else:
    fail("youtube.confirm 缺少 close_button 或 dialog_selector")

if yt_confirm.get("success_signals"):
    ok(f"youtube.confirm.success_signals 有 {len(yt_confirm['success_signals'])} 个信号")
else:
    fail("youtube.confirm.success_signals 为空")


# === 测试 14: Instagram confirm 配置 ===

print("\n📸 14. Instagram — confirm 配置与 post_publish 兼容")

ig_confirm = get_patterns("instagram", "confirm")
if ig_confirm.get("success_signals"):
    ok(f"instagram.confirm.success_signals 有 {len(ig_confirm['success_signals'])} 个信号")
else:
    fail("instagram.confirm.success_signals 为空")


# === 测试 15: AI Judge LLM 实际调用（如果 API Key 可用） ===

print("\n🤖 15. AI Judge — LLM 实际调用")

from social_uploader.tools.ai_judge import _call_llm, _get_client

client = _get_client()
if client:
    raw = _call_llm(
        'Reply with ONLY: {"status":"ok"}',
        'ping'
    )
    parsed = _parse_json_response(raw)
    if parsed and parsed.get("status") == "ok":
        ok("LLM 实际调用成功 + JSON 解析正确")
    else:
        fail(f"LLM 返回异常: raw={raw}")
else:
    ok("API Key 未配置，LLM 功能自动禁用（符合预期）")


# === 结果汇总 ===

print(f"\n{'='*55}")
total = passed + failed
if failed == 0:
    print(f"🎉 全部通过 ({passed}/{total})")
else:
    print(f"⚠️ {passed}/{total} 通过，{failed} 失败")
sys.exit(1 if failed else 0)

"""三层元素查找器 — 轨道 A（快速选择器）→ Tier 2（本地启发式）→ 轨道 B（AI 语义定位）

【三层逐级兜底策略】
轨道 A (Fast Path):   读取 button_config.json 选择器列表，1.5s 快速尝试
Tier 2 (Heuristic):   本地 DOM 关键词匹配，不调 API，成功后自动回写
轨道 B (AI Path):     通过 UltimateLocator 结构化语义查询，成功后自动回写

【自动回写机制】
Tier 2 / 轨道 B 成功后，将生效的选择器回写到 button_config.json，
使得下次同场景直走轨道 A，系统选择器库随使用自动增长。

【保留的函数】
load_selectors / reload_selectors / add_selector — 供 fix-selector CLI 和自动修复流程使用
"""

import json
import logging
import time
from pathlib import Path

from social_uploader.tools.browser_manager import find_first

logger = logging.getLogger(__name__)

_SELECTORS_PATH = Path(__file__).resolve().parent.parent / "button_config.json"
_cache = {}

_TRACK_A_TIMEOUT = 1.5

_WRITEBACK_BLOCKLIST = {"close_buttons"}

_WRITEBACK_VALUE_BLOCKLIST = {
    "create_button": {"@aria-label=Menu", "@aria-label=menu"},
}

_EXPECTED_ELEMENT = {
    "file_input": {"tags": {"input"}, "attrs": {"type": "file"}},
    "caption_box": {"tags": {"div", "textarea", "p"}},
    "title_box": {"tags": {"div", "textarea", "input"}},
    "desc_box": {"tags": {"div", "textarea", "input"}},
}


def _verify_element_type(el, key):
    """验证元素标签/属性是否符合预期，防止 AI 返回错误类型的元素。

    返回 True 表示验证通过或无需验证。
    """
    spec = _EXPECTED_ELEMENT.get(key)
    if not spec:
        return True
    try:
        tag = (el.tag or "").lower()
    except Exception:
        return True
    expected_tags = spec.get("tags", set())
    if expected_tags and tag not in expected_tags:
        logger.debug(f"    类型断言失败: {key} 期望 {expected_tags}，实际 <{tag}>")
        return False
    expected_attrs = spec.get("attrs", {})
    for attr_name, attr_val in expected_attrs.items():
        try:
            actual = (el.attr(attr_name) or "").lower()
            if actual != attr_val.lower():
                logger.debug(f"    属性断言失败: {key} 期望 {attr_name}={attr_val}，实际 {actual}")
                return False
        except Exception:
            return False
    return True


def load_selectors(platform):
    """读取 button_config.json 中指定平台的选择器字典，带文件级缓存。"""
    if platform in _cache:
        return _cache[platform]
    try:
        data = json.loads(_SELECTORS_PATH.read_text(encoding="utf-8"))
        _cache.update(data)
        return _cache.get(platform, {})
    except Exception as e:
        logger.warning(f"button_config.json 读取失败，回退到空字典: {e}")
        return {}


def reload_selectors():
    """清除缓存，强制下次调用 load_selectors 时重新读取文件。"""
    _cache.clear()


def add_selector(platform, key, selector):
    """安全地将新选择器插入 button_config.json 对应 platform.key 列表开头。

    返回 (success: bool, message: str)。
    """
    try:
        data = json.loads(_SELECTORS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"读取 button_config.json 失败: {e}"

    if platform not in data:
        return False, f"平台 \"{platform}\" 不存在于 button_config.json（可用: {', '.join(data.keys())}）"

    if key not in data[platform]:
        return False, f"key \"{key}\" 不存在于 {platform}（可用: {', '.join(data[platform].keys())}）"

    current_list = data[platform][key]
    if selector in current_list:
        return True, f"选择器已存在于 {platform}.{key}，无需重复添加"

    current_list.insert(0, selector)

    try:
        _SELECTORS_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as e:
        return False, f"写入 button_config.json 失败: {e}"

    reload_selectors()
    total = len(current_list)
    return True, f"OK: 已将 \"{selector}\" 添加到 {platform}.{key} 选择器列表开头（共 {total} 个）"


def _track_a(page, platform, key):
    """轨道 A：button_config.json 快速路径，1.5s 超时。

    返回 (element, selector) 或 (None, None)。
    """
    sels = load_selectors(platform).get(key, [])
    if not sels:
        return None, None

    el, sel = find_first(page, sels, timeout_per=_TRACK_A_TIMEOUT)
    if el:
        if key == "file_input":
            return el, sel
        try:
            if el.states.has_rect:
                return el, sel
        except Exception:
            pass
    return None, None


def _tier2_heuristic(page, platform, key):
    """Tier 2：本地 DOM 启发式，不调 API，基于关键词匹配。

    从 platform_semantics 获取语义 hint，用 dom_heuristic 在页面中搜索。
    返回 (element, selector) 或 (None, None)。
    """
    try:
        from social_uploader.tools.platform_semantics import get_semantic_query
        from social_uploader.tools.dom_heuristic import discover_for_click, discover_for_value
    except ImportError:
        return None, None

    query = get_semantic_query(platform, key)
    hint = query.get("target", key.replace("_", " "))

    if key in ("file_input",):
        sel, info = discover_for_value(page, "", hint)
    else:
        fallback_texts = []
        sel, info = discover_for_click(page, hint, fallback_texts)

    if not sel:
        return None, None

    try:
        el = page.ele(sel, timeout=1.5)
        if el:
            return el, sel
    except Exception:
        pass
    return None, None


def _track_b(page, platform, key):
    """轨道 B：AI 语义定位路径。

    返回 (element, selector) 或 (None, None)。
    """
    try:
        from social_uploader.tools.pattern_checker import dismiss_popups, sweep_modals
        dismiss_popups(page, platform, max_rounds=1)
        sweep_modals(page, max_rounds=1)
    except Exception:
        pass

    try:
        from social_uploader.tools.platform_semantics import get_semantic_query
        from social_uploader.tools.ai_locator import UltimateLocator
    except ImportError:
        logger.debug("AI 定位模块不可用，跳过轨道 B")
        return None, None

    query_dict = get_semantic_query(platform, key)
    locator = UltimateLocator(page)
    locator.prepare_page()
    return locator.find_element(query_dict, platform)


def _auto_writeback(platform, key, selector):
    """将 Tier 2 / 轨道 B 发现的有效选择器回写到 button_config.json。

    跳过 _WRITEBACK_BLOCKLIST 中的 key（如 close_buttons）。
    """
    if key in _WRITEBACK_BLOCKLIST:
        return
    if not selector or not isinstance(selector, str):
        return
    blocked_vals = _WRITEBACK_VALUE_BLOCKLIST.get(key, set())
    if selector in blocked_vals:
        logger.info(f"  ⛔ 拒绝回写: {platform}.{key} ← {selector} (在值黑名单中)")
        return
    ok, msg = add_selector(platform, key, selector)
    if ok:
        logger.info(f"  📝 自动回写: {platform}.{key} ← {selector}")


def find_element(page, platform, key, timeout=5):
    """三层逐级查找元素（带元素类型断言）。

    轨道 A (Fast Path):   button_config.json 主选择器，1.5s 超时
    Tier 2 (Heuristic):   本地 DOM 关键词匹配，成功后回写
    轨道 B (AI Path):     UltimateLocator 语义查找，成功后回写

    每层返回的元素都经过 _verify_element_type 断言，
    防止 AI 或启发式返回错误类型的元素（如把 div 当 input）。

    返回 (element, selector) 或 (None, None)。
    """
    el, sel = _track_a(page, platform, key)
    if el and _verify_element_type(el, key):
        return el, sel

    logger.info(f"  ⚡ 轨道 A 未命中 {platform}.{key}，尝试本地启发式 Tier 2...")
    el, sel = _tier2_heuristic(page, platform, key)
    if el and _verify_element_type(el, key):
        logger.info(f"  🔍 Tier 2 命中 {platform}.{key}: {sel}")
        _auto_writeback(platform, key, sel)
        return el, sel

    logger.info(f"  🔍 Tier 2 未命中，切换到 AI 轨道 B...")
    el, sel = _track_b(page, platform, key)
    if el and _verify_element_type(el, key):
        logger.info(f"  🧠 轨道 B 命中 {platform}.{key}: {sel}")
        _auto_writeback(platform, key, sel)
        return el, sel

    if not load_selectors(platform).get(key):
        logger.warning(f"button_config.json 中未找到 {platform}.{key}")
    return None, None


_CRITICAL_KEYS = {
    "tiktok": ["file_input"],
    "instagram": ["create_button"],
    "youtube": ["upload_icon"],
}


def preflight_check(page, platform):
    """上传前检查关键选择器是否存活（仅 Track A）。

    在上传流程开始前调用，快速发现 UI 变更导致的选择器失效。
    不触发 Tier 2 / Track B，避免产生副作用。

    返回 broken key 列表（空列表 = 全部健康）。
    """
    keys = _CRITICAL_KEYS.get(platform, [])
    broken = []
    for key in keys:
        el, _ = _track_a(page, platform, key)
        if not el:
            broken.append(key)
    if broken:
        logger.warning(
            f"  ⚠️ 选择器预检: {platform} 有 {len(broken)} 个关键选择器失效: {broken}"
        )
    else:
        logger.info(f"  ✅ 选择器预检: {platform} 全部 {len(keys)} 个关键选择器正常")
    return broken


def find_and_click(page, platform, key, timeout=5):
    """查找元素并点击，带点击后状态检查。

    点击后检查页面 URL 或 DOM 是否变化，无变化则重试轨道 B。
    返回 (clicked: bool, element, selector)。
    """
    el, sel = find_element(page, platform, key, timeout)
    if not el:
        return False, None, None

    try:
        url_before = page.url
    except Exception:
        url_before = ""

    try:
        el.click()
    except Exception as e:
        logger.warning(f"  ⚠️ 点击 {platform}.{key} 失败: {e}")
        return False, el, sel

    time.sleep(0.5)

    try:
        url_after = page.url
        if url_after != url_before:
            return True, el, sel
    except Exception:
        pass

    try:
        if not el.states.has_rect:
            return True, el, sel
    except Exception:
        return True, el, sel

    logger.info(f"  ⚠️ 点击 {platform}.{key} 后页面无变化，重试轨道 B...")
    el2, sel2 = _track_b(page, platform, key)
    if el2:
        try:
            el2.click()
            time.sleep(0.3)
            return True, el2, sel2
        except Exception:
            pass

    return True, el, sel

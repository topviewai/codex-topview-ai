"""Tier 2 启发式 DOM 发现器 — 当 recipe 中的选择器过期时，自动在页面中搜索替代元素。

不调用 AI API，通过语义关键词 + 元素特征（标签、值格式、位置关系）在 DOM 中定位目标。
"""

import json
import logging
import re

logger = logging.getLogger(__name__)

# ⚠️ DrissionPage.run_js 会把脚本包成 `function(){<代码>}` 执行，
#    所以必须用顶层 return；严禁外层再裹 (function(){...})() IIFE，
#    否则外层函数不 return，结果在 Python 端永远是 None（实测验证）。
#    参数通过 %s 模板硬编码到 JS 字面量（与 _DOM_EXTRACT_JS 写法一致）。
_DISCOVER_JS = """
var contextSel = %s;
var root = document;
if (contextSel) {
    var ctx = document.querySelector(contextSel);
    if (ctx) root = ctx;
}
var tags = 'button,input,select,textarea,label,span,div,[role="button"],[role="radio"],'
         + '[role="option"],[role="listbox"],[contenteditable],[data-e2e]';
var els = root.querySelectorAll(tags);
var keep = ['id','class','name','type','role','aria-label','data-e2e',
            'placeholder','value','aria-checked','aria-expanded','for'];
var result = [];
for (var i = 0; i < els.length && result.length < 200; i++) {
    var el = els[i];
    var rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) continue;
    var obj = {tag: el.tagName.toLowerCase(), x: Math.round(rect.x), y: Math.round(rect.y)};
    for (var k = 0; k < keep.length; k++) {
        var v = el.getAttribute(keep[k]);
        if (v) {
            if (keep[k] === 'class') v = v.split(/\\s+/).slice(0, 4).join(' ');
            if (keep[k] === 'value') v = v.substring(0, 30);
            obj[keep[k]] = v;
        }
    }
    var txt = '';
    for (var c = el.firstChild; c; c = c.nextSibling) {
        if (c.nodeType === 3) txt += c.textContent;
    }
    txt = txt.trim();
    if (txt && txt.length > 0) obj.text = txt.substring(0, 40);
    result.push(obj);
}
return JSON.stringify(result);
"""


def _scan_dom(page, context_selector=None):
    """提取当前页面（或指定区域）的可交互元素列表。"""
    ctx_arg = f'"{context_selector}"' if context_selector else "null"
    js = _DISCOVER_JS % ctx_arg
    try:
        raw = page.run_js(js)
        if not raw:
            return []
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception as e:
        logger.warning(f"DOM 扫描失败: {e}")
        return []


def _build_selector(el):
    """根据元素属性生成一个 CSS 选择器字符串。"""
    tag = el.get("tag", "*")
    if el.get("id"):
        return f'{tag}#{el["id"]}'
    if el.get("name"):
        return f'{tag}[name="{el["name"]}"]'
    if el.get("data-e2e"):
        return f'{tag}[data-e2e="{el["data-e2e"]}"]'
    if el.get("class"):
        first_cls = el["class"].split()[0]
        return f'{tag}.{first_cls}'
    if el.get("role"):
        return f'{tag}[role="{el["role"]}"]'
    if el.get("type") and tag == "input":
        return f'input[type="{el["type"]}"]'
    if el.get("aria-label"):
        return f'{tag}[aria-label="{el["aria-label"]}"]'
    return None


def _matches_hint(el, hint_keywords):
    """判断元素是否语义匹配关键词列表中的任一关键词。"""
    searchable = " ".join([
        el.get("text", ""), el.get("aria-label", ""),
        el.get("name", ""), el.get("id", ""),
        el.get("placeholder", ""), el.get("class", ""),
        el.get("data-e2e", ""),
    ]).lower()
    return any(kw.lower() in searchable for kw in hint_keywords)


def _matches_value_pattern(el, pattern):
    """判断元素的 value 属性是否匹配给定正则。"""
    val = el.get("value", "")
    if not val or not pattern:
        return False
    try:
        return bool(re.match(pattern, val))
    except re.error:
        return False


def discover_for_click(page, semantic_hint, fallback_texts=None, context_selector=None):
    """发现可点击元素（用于 click / pick_option 动作）。

    策略：
    1. 按 semantic_hint 中的关键词匹配元素的文本/属性
    2. 如果有 fallback_texts，按精确文本匹配
    返回 (css_selector, element_info) 或 (None, None)。
    """
    elements = _scan_dom(page, context_selector)
    if not elements:
        return None, None

    hint_keywords = [w for w in re.split(r'[,，\s]+', semantic_hint) if len(w) >= 2]

    for el in elements:
        if _matches_hint(el, hint_keywords):
            sel = _build_selector(el)
            if sel:
                return sel, el

    if fallback_texts:
        for el in elements:
            el_text = el.get("text", "").strip()
            if el_text and el_text in fallback_texts:
                sel = _build_selector(el)
                if sel:
                    return sel, el

    return None, None


def discover_for_value(page, value_pattern, semantic_hint="", context_selector=None):
    """发现可设值的 input 元素（用于 set_value 动作）。

    策略：
    1. 找所有 input/textarea/select
    2. 按 value_pattern 匹配当前值格式
    3. 如果有 semantic_hint，用作辅助筛选
    返回 (css_selector, element_info) 或 (None, None)。
    """
    elements = _scan_dom(page, context_selector)
    if not elements:
        return None, None

    input_els = [e for e in elements if e.get("tag") in ("input", "textarea", "select")]

    for el in input_els:
        if _matches_value_pattern(el, value_pattern):
            sel = _build_selector(el)
            if sel:
                return sel, el

    hint_keywords = [w for w in re.split(r'[,，\s]+', semantic_hint) if len(w) >= 2]
    if hint_keywords:
        for el in input_els:
            if _matches_hint(el, hint_keywords):
                sel = _build_selector(el)
                if sel:
                    return sel, el

    return None, None


def discover_for_pick(page, semantic_hint, container_hint="", context_selector=None):
    """发现选项列表中的可选元素（用于 pick_option 动作）。

    策略：
    1. 找 role=option / role=listitem / li / 带点击属性的元素
    2. 在语义相关容器中搜索
    返回 (container_selector, item_selector, element_info) 或 (None, None, None)。
    """
    elements = _scan_dom(page, context_selector)
    if not elements:
        return None, None, None

    hint_keywords = [w for w in re.split(r'[,，\s]+', semantic_hint) if len(w) >= 2]
    option_tags = ("li", "div", "span", "button")
    option_roles = ("option", "listitem", "menuitem")

    for el in elements:
        is_option = (el.get("tag") in option_tags and el.get("role") in option_roles)
        if not is_option:
            continue
        if hint_keywords and _matches_hint(el, hint_keywords):
            sel = _build_selector(el)
            if sel:
                return None, sel, el

    for el in elements:
        if el.get("role") in option_roles:
            sel = _build_selector(el)
            if sel:
                return None, sel, el

    return None, None, None

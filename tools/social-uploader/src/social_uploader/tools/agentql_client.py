"""AgentQL 智能元素发现 — Tier 2b 兜底层。

采用两阶段发现策略：
  阶段 1（AgentQL 语义识别）：将页面 HTML 发送到 AgentQL REST API，
          用自然语言描述目标元素，获取粗定位属性（aria-label、id、class、css_selector）。
  阶段 2（DrissionPage 属性精提）：用粗定位属性在页面上找到元素，
          通过 JS 提取全部 HTML 属性（包括 data-e2e 等 AgentQL 看不到的自定义属性），
          从中选出最稳定的选择器写回配置。

API Key 未设置时静默降级，不影响现有 Tier 1 / 2a / 3 流程。
"""

import json
import logging
import os
import re

logger = logging.getLogger(__name__)

def _load_api_key():
    key = os.environ.get("AGENTQL_API_KEY", "")
    if key:
        return key
    key_file = os.path.expanduser("~/.social_uploader/agentql.key")
    try:
        with open(key_file) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

_API_KEY = _load_api_key()
_API_URL = "https://api.agentql.com/v1/query-data"
_API_TIMEOUT = 15

DANGEROUS_KEYWORDS = [
    "delete", "删除", "discard", "丢弃", "remove", "移除",
    "cancel", "取消", "logout", "退出",
]

_QUERY_TEMPLATE = """{{
    target_element({description}) {{
        text_content
        aria_label
        id
        class_name
        css_selector
    }}
}}"""

_EXTRACT_ATTRS_JS = """
(function(el) {
    var result = {};
    for (var i = 0; i < el.attributes.length; i++) {
        var attr = el.attributes[i];
        result[attr.name] = attr.value;
    }
    result.__tag = el.tagName.toLowerCase();
    result.__text = (el.textContent || "").trim().substring(0, 60);
    return JSON.stringify(result);
})(arguments[0])
"""


# ---------------------------------------------------------------------------
# HTML 优化层
# ---------------------------------------------------------------------------

def _clean_html(html):
    """移除 script/style/svg/noscript 等无关标签，减小 API payload。"""
    for tag in ("script", "style", "svg", "noscript", "link"):
        html = re.sub(
            rf"<{tag}[^>]*>.*?</{tag}>",
            "", html, flags=re.DOTALL | re.IGNORECASE,
        )
        html = re.sub(
            rf"<{tag}[^>]*/>",
            "", html, flags=re.IGNORECASE,
        )
    return html


def _extract_relevant_html(page, context_hint=""):
    """从 DrissionPage page 对象提取适当大小的 HTML 片段（目标 <300KB）。

    优先取小范围（dialog/form），再逐步扩大。
    """
    candidates = ["@role=dialog", "tag:form", "tag:main", "tag:body"]
    if context_hint:
        candidates.insert(0, context_hint)

    for selector in candidates:
        try:
            el = page.ele(selector, timeout=1)
            if not el:
                continue
            raw = el.html
            if not raw:
                continue
            if len(raw) < 300_000:
                return _clean_html(raw)
            cleaned = _clean_html(raw)
            if len(cleaned) < 500_000:
                return cleaned
        except Exception:
            continue

    try:
        fallback = page.html or ""
        return _clean_html(fallback[:300_000])
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# API 调用层
# ---------------------------------------------------------------------------

def _call_agentql(html, query):
    """调用 AgentQL REST API（query 语法），返回 data 字典或 None。"""
    try:
        import requests
    except ImportError:
        logger.debug("requests 未安装，跳过 AgentQL 调用")
        return None

    if not html or not query:
        return None

    headers = {
        "X-API-Key": _API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "html": html,
        "params": {"mode": "fast"},
    }

    try:
        resp = requests.post(
            _API_URL, json=payload, headers=headers, timeout=_API_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning(f"AgentQL API 返回 {resp.status_code}: {resp.text[:200]}")
            return None
        result = resp.json()
        return result.get("data")
    except Exception as e:
        logger.warning(f"AgentQL API 调用失败: {e}")
        return None


# ---------------------------------------------------------------------------
# 阶段 1：AgentQL 语义识别 → 候选选择器列表
# ---------------------------------------------------------------------------

def _attrs_to_selectors(attrs):
    """将 AgentQL 返回的元素属性转换为 DrissionPage 选择器候选列表。

    按稳定性降序排列。跳过 None 和空字符串。
    """
    if not attrs or not isinstance(attrs, dict):
        return []

    selectors = []

    id_val = attrs.get("id")
    if id_val:
        selectors.append(f"@id={id_val}")

    aria = attrs.get("aria_label")
    if aria:
        selectors.append(f"@aria-label={aria}")

    cls = attrs.get("class_name")
    if cls:
        first_cls = cls.split()[0] if " " in cls else cls
        selectors.append(f".{first_cls}")

    css_sel = attrs.get("css_selector")
    if css_sel:
        selectors.append(f"css:{css_sel}")

    text = attrs.get("text_content") or attrs.get("text") or attrs.get("visible_text")
    if text and len(text) < 30:
        selectors.append(f"text:{text}")

    return selectors


def _agentql_identify(html, description, platform=""):
    """阶段 1：调用 AgentQL API 获取候选选择器列表。"""
    platform_hint = f" on {platform}" if platform else ""
    query = _QUERY_TEMPLATE.format(
        description=f"{description}{platform_hint}",
    )

    data = _call_agentql(html, query)
    if not data:
        return []

    target = data.get("target_element")
    if not target:
        first_key = next(iter(data), None)
        target = data.get(first_key) if first_key else None

    if isinstance(target, str):
        return [f"text:{target}"] if len(target) < 30 else []

    return _attrs_to_selectors(target)


# ---------------------------------------------------------------------------
# 阶段 2：DrissionPage 属性精提 → 最优选择器
# ---------------------------------------------------------------------------

_SELECTOR_PRIORITY = [
    ("data-e2e", "@data-e2e={}"),
    ("data-testid", "@data-testid={}"),
    ("id", "@id={}"),
    ("aria-label", "@aria-label={}"),
    ("name", "@name={}"),
]


def _extract_best_selector(page, element):
    """从已找到的元素中提取全部属性，选出最稳定的 DrissionPage 选择器。"""
    try:
        from social_uploader.tools.js_runner import run_iife
        raw = run_iife(page, _EXTRACT_ATTRS_JS, element)
        if not raw:
            return None
        attrs = json.loads(raw) if isinstance(raw, str) else raw
    except Exception as e:
        logger.debug(f"属性精提失败: {e}")
        return None

    for attr_name, template in _SELECTOR_PRIORITY:
        val = attrs.get(attr_name)
        if val:
            return template.format(val)

    text = attrs.get("__text", "")
    if text and len(text) < 30:
        return f"text:{text}"

    return None


# ---------------------------------------------------------------------------
# 安全校验
# ---------------------------------------------------------------------------

def _is_safe_element(element, expected_description):
    """防止 AI 定位到危险按钮（如把"删除"当成"发布"）。"""
    try:
        el_text = (element.text or "").strip().lower()
    except Exception:
        return True

    desc_lower = expected_description.lower()
    for kw in DANGEROUS_KEYWORDS:
        if kw in el_text and kw not in desc_lower:
            logger.warning(
                f"AgentQL 安全拦截：元素文本 '{el_text}' 含危险词 '{kw}'，"
                f"但目标描述 '{expected_description}' 中不含该词"
            )
            return False
    return True


# ---------------------------------------------------------------------------
# 对外接口
# ---------------------------------------------------------------------------

def find_element_with_ai(page, description, platform=""):
    """两阶段发现：AgentQL 语义识别 → DrissionPage 属性精提。

    返回 (element, best_selector) 或 (None, None)。
    """
    if not _API_KEY:
        logger.debug("AGENTQL_API_KEY 未设置，跳过 AI 发现")
        return None, None

    html = _extract_relevant_html(page)
    if not html:
        logger.debug("无法提取页面 HTML，跳过 AI 发现")
        return None, None

    logger.info(f"  🧠 AgentQL Tier 2b: 正在识别 '{description}' (HTML {len(html)//1024}KB)...")
    candidates = _agentql_identify(html, description, platform)
    if not candidates:
        logger.info(f"  🧠 AgentQL 未返回有效属性")
        return None, None

    logger.info(f"  🧠 AgentQL 返回 {len(candidates)} 个候选选择器: {candidates}")

    for sel in candidates:
        try:
            el = page.ele(sel, timeout=2)
            if not el:
                continue
            if not _is_safe_element(el, description):
                continue

            best = _extract_best_selector(page, el)
            if best:
                logger.info(f"  🧠 两阶段精提最优选择器: {best}")
                return el, best
            else:
                return el, sel
        except Exception:
            continue

    return None, None


def discover_with_ai(page, semantic_hint, action="click", context_selector=None):
    """供 recipe_runner 调用的简化接口，返回选择器字符串或 None。"""
    if not _API_KEY:
        return None

    el, sel = find_element_with_ai(page, semantic_hint)
    if el and sel:
        return sel
    return None

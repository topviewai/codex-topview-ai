"""页面感知层 — 为 AI 提供结构化 DOM 快照和截图能力。

等效于 MCP 的 get_dom_tree / take_screenshot，但直接通过
DrissionPage 的 CDP 能力实现，无需单独部署 MCP Server。
"""

import base64
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_SNAPSHOT_DIR = Path.home() / ".social_uploader" / "snapshots"


def get_simplified_dom(page, root_selector: str | None = None, max_depth: int = 6, max_nodes: int = 200) -> str:
    """获取简化版 DOM 树，类似 MCP 的 browser_snapshot (Accessibility Tree)。

    只保留对 AI 决策有用的信息：标签、角色、文本、可见性、可交互性。
    """
    js = """
    (function(rootSel, maxDepth, maxNodes) {
        let count = 0;
        function walk(el, depth) {
            if (!el || count >= maxNodes || depth > maxDepth) return null;
            const tag = el.tagName ? el.tagName.toLowerCase() : '';
            const ignoreTags = new Set(['script','style','noscript','svg','path','link','meta']);
            if (ignoreTags.has(tag)) return null;
            const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
            const visible = rect && rect.width > 0 && rect.height > 0;
            if (!visible && !['input','select','textarea'].includes(tag)) {
                if (depth > 2) return null;
            }
            count++;
            const node = {t: tag};
            const role = el.getAttribute && el.getAttribute('role');
            if (role) node.r = role;
            const ariaLabel = el.getAttribute && el.getAttribute('aria-label');
            if (ariaLabel) node.al = ariaLabel.substring(0, 60);
            const type = el.getAttribute && el.getAttribute('type');
            if (type && ['file','text','submit','button','checkbox','radio'].includes(type)) node.tp = type;
            const disabled = el.disabled || (el.getAttribute && el.getAttribute('aria-disabled') === 'true');
            if (disabled) node.dis = true;
            if (!visible) node.hid = true;
            const directText = [];
            for (const child of (el.childNodes || [])) {
                if (child.nodeType === 3) {
                    const t = child.textContent.trim();
                    if (t && t.length < 200) directText.push(t);
                }
            }
            if (directText.length) node.tx = directText.join(' ').substring(0, 150);
            const cls = el.className;
            if (cls && typeof cls === 'string') {
                const important = cls.split(/\\s+/).filter(c =>
                    /modal|dialog|popup|overlay|alert|toast|banner|error|success|warning|upload|publish|post|schedule/i.test(c)
                );
                if (important.length) node.cls = important.join(' ').substring(0, 80);
            }
            const children = [];
            for (const child of (el.children || [])) {
                const c = walk(child, depth + 1);
                if (c) children.push(c);
            }
            if (children.length) node.ch = children;
            return node;
        }
        const root = rootSel ? document.querySelector(rootSel) : document.body;
        return JSON.stringify(walk(root, 0));
    })(arguments[0], arguments[1], arguments[2])
    """
    try:
        from social_uploader.tools.js_runner import run_iife
        raw = run_iife(page, js, root_selector, max_depth, max_nodes)
        if raw:
            return raw
    except Exception as e:
        logger.debug(f"DOM 快照获取失败: {e}")
    return "{}"


def get_interactive_elements(page) -> str:
    """获取页面所有可交互元素的摘要（按钮、输入框、链接）。"""
    js = """
    (function() {
        const items = [];
        const selectors = 'button, [role="button"], a[href], input, select, textarea, [onclick], [tabindex]';
        document.querySelectorAll(selectors).forEach((el, idx) => {
            if (idx > 50) return;
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 && rect.height === 0) return;
            const tag = el.tagName.toLowerCase();
            const text = (el.textContent || '').trim().substring(0, 60);
            const role = el.getAttribute('role') || '';
            const ariaLabel = el.getAttribute('aria-label') || '';
            const type = el.getAttribute('type') || '';
            const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';
            items.push({
                idx: idx,
                tag: tag,
                text: text || ariaLabel || type || '[empty]',
                role: role,
                type: type,
                disabled: disabled,
                rect: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)}
            });
        });
        return JSON.stringify(items);
    })()
    """
    try:
        from social_uploader.tools.js_runner import run_iife
        raw = run_iife(page, js)
        if raw:
            return raw
    except Exception as e:
        logger.debug(f"交互元素获取失败: {e}")
    return "[]"


def take_screenshot_base64(page, full_page: bool = False) -> str | None:
    """获取页面截图的 base64 编码（可供多模态 LLM 使用）。"""
    path = None
    try:
        _SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = _SNAPSHOT_DIR / f"snap_{int(time.time())}.png"
        if full_page:
            page.get_screenshot(path=str(path), full_page=True)
        else:
            page.get_screenshot(path=str(path))
        if path.exists() and path.stat().st_size > 0:
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            path.unlink(missing_ok=True)
            return data
    except Exception as e:
        logger.debug(f"截图获取失败: {e}")
    finally:
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
    return None


def diagnose_page_state(page) -> dict:
    """综合诊断当前页面状态，返回结构化信息供 AI 决策。"""
    try:
        page_url = page.url
    except Exception:
        page_url = "page_disconnected"
    result = {
        "url": page_url,
        "title": "",
        "has_dialog": False,
        "dialog_text": "",
        "visible_buttons": [],
        "error_indicators": [],
        "success_indicators": [],
    }
    try:
        result["title"] = page.title or ""
    except Exception:
        pass

    for sel in [
        "xpath://*[@role='dialog' or @role='alertdialog']",
        "xpath://*[contains(@class,'TUXModal')]",
        "xpath://*[contains(@class,'modal') and not(contains(@class,'modal-root'))]",
        "xpath://ytcp-uploads-dialog",
    ]:
        try:
            dlg = page.ele(sel, timeout=0.3)
            if dlg and dlg.states.has_rect:
                result["has_dialog"] = True
                result["dialog_text"] = (dlg.text or "")[:500]
                try:
                    btns = dlg.eles("tag:button", timeout=0.3)
                    result["visible_buttons"] = [
                        {"text": (b.text or "").strip()[:40], "disabled": b.attr("disabled") is not None}
                        for b in (btns or []) if b.states.has_rect
                    ]
                except Exception:
                    pass
                break
        except Exception:
            pass

    error_keywords = ["error", "failed", "failure", "错误", "失败", "rejected", "违反", "restricted"]
    success_keywords = ["success", "published", "scheduled", "已发布", "已安排", "发布成功", "shared", "已分享"]

    try:
        body_text = (page.ele("tag:body", timeout=0.5).text or "")[:5000].lower()
        for kw in error_keywords:
            if kw in body_text:
                result["error_indicators"].append(kw)
        for kw in success_keywords:
            if kw in body_text:
                result["success_indicators"].append(kw)
    except Exception:
        pass

    return result

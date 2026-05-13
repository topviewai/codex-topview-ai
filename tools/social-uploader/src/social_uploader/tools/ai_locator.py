"""AI 导航器 — 基于 AgentQL 的高稳定性语义定位类。

通过结构化语义查询（container + target）定位页面元素，
包含页面预热、坐标校准、视觉校验等增强机制。

AgentQL API Key 未配置时静默降级，返回 (None, None)。
"""

import logging
import time

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2


class UltimateLocator:
    """高稳定性 AI 元素定位器。

    工作流程：
    1. prepare_page() — 预热页面，激活懒加载，清理弹窗
    2. find_element(query_dict, platform) — 结构化语义查询
    3. _verify_clickable(element) — 视觉校验 + 坐标校准
    """

    def __init__(self, page):
        self.page = page

    def prepare_page(self):
        """预热页面：滚动激活懒加载 + 等待 DOM 稳定 + 清理弹窗。"""
        try:
            self.page.scroll.to_location(0, 500)
            time.sleep(0.3)
            self.page.scroll.to_location(0, 0)
            time.sleep(0.2)
        except Exception:
            pass

        try:
            self.page.wait.doc_loaded(timeout=5)
        except Exception:
            pass

        time.sleep(0.5)

        try:
            from social_uploader.tools.pattern_checker import sweep_modals
            sweep_modals(self.page, max_rounds=1)
        except Exception:
            pass

    def _get_dpr(self):
        """获取 window.devicePixelRatio，用于坐标校准。每次实时获取，不缓存。"""
        try:
            dpr = self.page.run_js("return window.devicePixelRatio || 1;")
            return float(dpr) if dpr else 1.0
        except Exception:
            return 1.0

    def find_element(self, query_dict, platform=""):
        """结构化语义查询入口。

        Args:
            query_dict: {"container": "...", "target": "..."}
            platform: 平台名（tiktok/instagram/youtube）

        Returns:
            (element, selector) 或 (None, None)
        """
        try:
            from social_uploader.tools.agentql_client import (
                _extract_relevant_html,
                _agentql_identify,
                _extract_best_selector,
                _is_safe_element,
                _API_KEY,
            )
        except ImportError:
            logger.debug("agentql_client 不可用，跳过 AI 定位")
            return None, None

        if not _API_KEY:
            logger.debug("AGENTQL_API_KEY 未设置，跳过 AI 定位")
            return None, None

        container = query_dict.get("container", "page")
        target = query_dict.get("target", "")
        if not target:
            return None, None

        description = f"{target} inside {container}"

        for attempt in range(_MAX_RETRIES):
            if attempt > 0:
                logger.info(f"  🔄 AI 定位重试 ({attempt + 1}/{_MAX_RETRIES})...")
                self.prepare_page()

            context_hint = ""
            if container and container != "page":
                context_hint = f"@role=dialog"

            html = _extract_relevant_html(self.page, context_hint)
            if not html:
                logger.debug("无法提取页面 HTML")
                continue

            logger.info(
                f"  🧠 AI 语义定位: '{target}' in '{container}' "
                f"(HTML {len(html) // 1024}KB)"
            )
            candidates = _agentql_identify(html, description, platform)
            if not candidates:
                logger.info("  🧠 AgentQL 未返回有效候选")
                continue

            logger.info(f"  🧠 获得 {len(candidates)} 个候选: {candidates}")

            for sel in candidates:
                try:
                    el = self.page.ele(sel, timeout=2)
                    if not el:
                        continue
                    if not _is_safe_element(el, target):
                        continue
                    if not self._verify_clickable(el):
                        logger.debug(f"    候选 {sel} 不可点击，跳过")
                        continue

                    best = _extract_best_selector(self.page, el)
                    final_sel = best if best else sel
                    logger.info(f"  🧠 AI 定位成功: {final_sel}")
                    return el, final_sel
                except Exception:
                    continue

        logger.info("  🧠 AI 定位未找到可用元素")
        return None, None

    def _verify_clickable(self, element):
        """视觉校验：检查元素可见性 + 鼠标移动验证。"""
        try:
            if not element.states.has_rect:
                return False
        except Exception:
            return False

        try:
            rect = element.rect.location
            if not rect:
                return False
            x, y = rect
            dpr = self._get_dpr()
            phys_x = int(x * dpr)
            phys_y = int(y * dpr)

            self.page.actions.move_to(phys_x, phys_y)
            time.sleep(0.2)
        except Exception:
            pass

        try:
            is_enabled = element.states.is_enabled
            if is_enabled is False:
                return False
        except Exception:
            pass

        return True

"""步骤级智能重试引擎 — 在步骤失败时利用 AI 诊断并智能恢复。

设计原则:
1. 每个步骤最多重试 max_retries 次
2. 每次重试前用 AI 诊断失败原因，根据建议执行恢复动作
3. 不可逆步骤（如 publish）有特殊幂等性保护
4. AI 不可用时降级为简单延时重试
"""

import logging
import time
from typing import Callable, Any

logger = logging.getLogger(__name__)

_NON_RETRYABLE_RECOVERIES = {"abort"}
_NEEDS_DISMISS = {"dismiss_and_retry"}
_NEEDS_WAIT = {"wait_and_retry"}
_NEEDS_SCROLL = {"scroll_and_retry"}
_NEEDS_REFRESH = {"refresh_and_retry"}
_NEEDS_NAV_BACK = {"navigate_back"}


class StepResult:
    """步骤执行结果。"""
    def __init__(self, success: bool, value: Any = None, error: str = ""):
        self.success = success
        self.value = value
        self.error = error

    def __bool__(self):
        return self.success


def retry_step(
    page,
    platform: str,
    step_name: str,
    step_fn: Callable,
    max_retries: int = 3,
    is_irreversible: bool = False,
    pre_retry_check: Callable | None = None,
) -> StepResult:
    """执行步骤，失败时智能重试。

    Args:
        page: DrissionPage 页面对象
        platform: 平台名
        step_name: 步骤名（用于日志和 AI 诊断）
        step_fn: 步骤执行函数，签名 () -> StepResult
        max_retries: 最大重试次数
        is_irreversible: 是否为不可逆步骤（如 publish），如果是则重试前先做幂等检查
        pre_retry_check: 重试前的幂等检查函数，签名 () -> bool (True=已完成无需重试)

    Returns:
        StepResult
    """
    last_error = ""

    for attempt in range(1 + max_retries):
        if attempt > 0:
            logger.info(f"  🔄 重试 {step_name} (第 {attempt}/{max_retries} 次)")

            if is_irreversible and pre_retry_check:
                try:
                    already_done = pre_retry_check()
                    if already_done:
                        logger.info(f"  ✅ 幂等检查: {step_name} 已完成，无需重试")
                        return StepResult(True, error="idempotent_skip")
                except Exception as e:
                    logger.debug(f"  幂等检查异常: {e}")

            recovery = _get_recovery_advice(page, platform, step_name, last_error)
            if recovery:
                action = recovery.get("recovery", "retry_same")
                if action in _NON_RETRYABLE_RECOVERIES:
                    logger.warning(f"  AI 建议放弃: {recovery.get('diagnosis', '')}")
                    return StepResult(False, error=f"ai_abort: {recovery.get('diagnosis', '')}")

                _execute_recovery(page, action, recovery)
            else:
                time.sleep(min(2 * attempt, 8))

        try:
            result = step_fn()
            if result.success:
                if attempt > 0:
                    logger.info(f"  ✅ {step_name} 在第 {attempt+1} 次尝试后成功")
                return result
            last_error = result.error or "step returned failure"
        except Exception as e:
            err_name = type(e).__name__
            last_error = f"{err_name}: {str(e)[:200]}"
            if "Disconnected" in err_name or "disconnected" in str(e).lower():
                logger.warning(f"  ⚠️ {step_name} 页面连接断开，无法继续重试")
                return StepResult(False, error=last_error)
            logger.warning(f"  ⚠️ {step_name} 异常: {last_error}")

    logger.error(f"  ❌ {step_name} 在 {1+max_retries} 次尝试后仍然失败: {last_error}")
    return StepResult(False, error=f"exhausted_{max_retries}_retries: {last_error}")


def _get_recovery_advice(page, platform: str, step_name: str, error_msg: str) -> dict | None:
    """调用 AI 诊断失败原因。AI 不可用时返回 None（降级为简单重试）。"""
    try:
        from social_uploader.tools.ai_judge import diagnose_failure
        return diagnose_failure(page, platform, step_name, error_msg)
    except Exception as e:
        logger.debug(f"  AI 诊断不可用: {e}")
        return None


def _execute_recovery(page, action: str, advice: dict):
    """根据 AI 建议执行恢复动作。"""
    logger.info(f"  🔧 执行恢复: {action}")

    if action in _NEEDS_DISMISS:
        sel = advice.get("dismiss_selector")
        if sel:
            try:
                btn = page.ele(sel, timeout=1)
                if btn and btn.states.has_rect:
                    btn.click()
                    logger.info(f"  已关闭遮挡元素: {sel}")
                    time.sleep(1)
                    return
            except Exception:
                pass
        try:
            page.handle_alert(accept=True, timeout=0.5)
        except Exception:
            pass
        for fallback_sel in ["[aria-label='Close']", "[aria-label='关闭']", "text:OK", "text:Cancel"]:
            try:
                el = page.ele(fallback_sel, timeout=0.3)
                if el and el.states.has_rect:
                    el.click()
                    time.sleep(0.5)
                    break
            except Exception:
                pass
        time.sleep(1)

    elif action in _NEEDS_WAIT:
        wait_s = advice.get("wait_seconds", 5)
        wait_s = max(2, min(wait_s, 15))
        logger.info(f"  等待 {wait_s} 秒...")
        time.sleep(wait_s)

    elif action in _NEEDS_SCROLL:
        try:
            page.scroll.to_bottom()
            time.sleep(1)
        except Exception:
            pass

    elif action in _NEEDS_REFRESH:
        try:
            page.refresh()
            time.sleep(3)
        except Exception:
            pass

    elif action in _NEEDS_NAV_BACK:
        try:
            page.back()
            time.sleep(2)
        except Exception:
            pass

    elif action == "skip":
        logger.info("  AI 建议跳过此步骤")

    else:
        time.sleep(2)

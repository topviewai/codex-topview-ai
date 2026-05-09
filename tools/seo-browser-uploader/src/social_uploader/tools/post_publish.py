"""公共发布后处理 — 弹窗处理 + 成功判定，三平台共用。

快路径（白名单按钮 / URL 跳转 / 选择器信号）优先执行，零成本。
AI 判断仅在快路径失败时兜底，带节流控制（每 3 轮调一次，最多 5 次）。
"""

import json
import logging
import time
from typing import Callable

from social_uploader.tools.pattern_checker import (
    check_signals,
    get_patterns,
    get_signal_list,
)

logger = logging.getLogger(__name__)

_DEFAULT_DIALOG_SELECTORS = [
    "xpath://*[@role='dialog' or @role='alertdialog']",
]

# 即使白名单匹配上，按钮文本（lower+strip）若**包含**以下任意子串也禁止点击。
# 防止 TikTok 内容警告/版权弹窗里的「关闭/取消/编辑/丢弃」等被误点。
_DENY_BUTTON_SUBSTRINGS = [
    # 取消/关闭类
    "cancel", "取消", "close", "关闭", "back", "返回", "dismiss",
    # 编辑/修改类（点了会回到编辑态而不是发布）
    "edit", "编辑", "modify", "修改",
    # 丢弃/删除类（极度危险，会丢掉视频）
    "discard", "丢弃", "放弃", "delete", "删除", "remove", "移除",
    # 替换/重传类
    "replace", "替换", "re-upload", "reupload", "重新上传",
    # 草稿
    "save as draft", "save draft", "保存草稿", "存为草稿", "存草稿",
    # 单按钮"我知道了"类（弹窗仅用来提示，关闭后视频不会发布）
    "got it", "知道了", "i understand", "我知道了", "了解",
]


def _is_denied_button(text: str) -> bool:
    """按钮文本命中黑名单则返回 True。空文本视为未命中。"""
    t = (text or "").strip().lower()
    if not t:
        return False
    return any(sub in t for sub in _DENY_BUTTON_SUBSTRINGS)


def _list_dialog_buttons(dialog_el) -> list[dict]:
    """探测弹窗内所有可见 button 的文本与禁用状态，用于调试日志。"""
    out = []
    try:
        btns = dialog_el.eles("xpath:.//button", timeout=0.5) or []
        for b in btns[:20]:
            try:
                if not b.states.has_rect:
                    continue
                txt = (b.text or "").strip()[:60]
                out.append({
                    "text": txt,
                    "aria_disabled": b.attr("aria-disabled"),
                    "data_type": b.attr("data-type"),
                    "denied": _is_denied_button(txt),
                })
            except Exception:
                continue
    except Exception:
        pass
    return out


def _dbg_log_popup(loc, msg, data):
    """临时调试日志（与 tiktok.py 共用 .cursor/debug-66b267.log）。"""
    try:
        rec = {
            "sessionId": "66b267", "runId": "popup",
            "timestamp": int(time.time() * 1000),
            "location": loc, "message": msg, "data": data,
        }
        with open(
            "/Users/shenyajing/Desktop/seo 浏览器操控插件 2/.cursor/debug-66b267.log",
            "a", encoding="utf-8",
        ) as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _find_dialog(page, platform: str):
    """从 state_patterns.json 读取弹窗容器选择器，依次尝试定位。"""
    patterns = get_patterns(platform, "publish_confirm")
    selectors = patterns.get("dialog_selectors", _DEFAULT_DIALOG_SELECTORS)
    for sel in selectors:
        try:
            el = page.ele(sel, timeout=0.8)
            if el and el.states.has_rect:
                return el
        except Exception:
            pass
    return None


def _resolve_button_selector(sel: str) -> tuple[str, str | None]:
    """把 'text:xxx' 转换成精确定位 <button> 的 xpath。

    返回 (selector_to_use, original_text_to_match)
    - 'text:Post now' → ('xpath:.//button[contains(normalize-space(.), "Post now")]', "Post now")
    - 其他选择器原样返回，text_to_match=None
    """
    if sel.startswith("text:"):
        text = sel[5:].strip()
        # 转义 xpath 字符串里的双引号
        if '"' in text:
            # 用 concat 拼接处理含双引号的情况（极少见）
            parts = text.split('"')
            xp_str = "concat(" + ", '\"', ".join(f'"{p}"' for p in parts) + ")"
            xpath_expr = f'xpath:.//button[contains(normalize-space(.), {xp_str})]'
        else:
            xpath_expr = f'xpath:.//button[contains(normalize-space(.), "{text}")]'
        return xpath_expr, text
    return sel, None


def _try_whitelist_click(dialog_el, platform: str) -> bool:
    """尝试在弹窗内点击白名单按钮。返回是否成功点击。

    安全机制：
    1. 进入时探测弹窗内所有可见 button，写调试日志（_DENY_BUTTON_SUBSTRINGS 标记危险按钮）
    2. text:xxx 选择器转换成 xpath 直接定位 <button>（绕开 DrissionPage 返回内层 span/div 的问题）
    3. 即使白名单 selector 匹配上，按钮文本若命中 deny list 也跳过（防止误点取消/关闭/丢弃类按钮）
    """
    confirm_texts = get_signal_list(platform, "publish_confirm", "secondary_confirm")

    # 先记录弹窗内所有按钮（无论是否点击都写一条），便于失败时复盘
    all_btns = _list_dialog_buttons(dialog_el)
    _dbg_log_popup(
        "post_publish.py:_try_whitelist_click:enter",
        f"{platform} 二次确认弹窗内所有可见按钮",
        {"platform": platform, "buttons": all_btns, "whitelist_size": len(confirm_texts)},
    )

    if not confirm_texts:
        return False

    for item in confirm_texts:
        sel = item if isinstance(item, str) else item.get("selector", "")
        if not sel:
            continue

        resolved_sel, _expected_text = _resolve_button_selector(sel)
        try:
            el = dialog_el.ele(resolved_sel, timeout=0.3)
            if not el:
                continue

            # 兜底：如果 selector 仍返回非 button（例如非 text: 选择器写法），向上爬到 <button>
            btn = el
            if btn.tag != "button":
                try:
                    ancestor = btn.ele("xpath:./ancestor::button[1]", timeout=0.3)
                    if ancestor:
                        btn = ancestor
                except Exception:
                    pass

            if btn.tag != "button" or not btn.states.has_rect:
                _dbg_log_popup(
                    "post_publish.py:_try_whitelist_click:non_button",
                    "selector 匹配到非 <button> 元素，跳过",
                    {"platform": platform, "selector": sel, "resolved": resolved_sel,
                     "matched_tag": el.tag, "matched_text": (el.text or "")[:60]},
                )
                continue

            btn_text = (btn.text or "").strip()

            # 安全闸门：命中 deny list 直接跳过（即使白名单选择器匹配上）
            if _is_denied_button(btn_text):
                logger.warning(
                    f"  [快路径] selector [{sel}] 匹配到按钮 [{btn_text[:30]}]，"
                    f"但命中 deny list，跳过以防误操作"
                )
                _dbg_log_popup(
                    "post_publish.py:_try_whitelist_click:denied",
                    f"白名单匹配但被 deny list 拦截",
                    {"platform": platform, "selector": sel, "button_text": btn_text[:60]},
                )
                continue

            btn.click()
            logger.info(f"  [快路径] 已点击弹窗按钮 [{btn_text[:30]}] (selector={sel})")
            _dbg_log_popup(
                "post_publish.py:_try_whitelist_click:clicked",
                f"已点击弹窗按钮",
                {"platform": platform, "selector": sel, "resolved": resolved_sel,
                 "button_text": btn_text[:60]},
            )
            return True
        except Exception as e:
            _dbg_log_popup(
                "post_publish.py:_try_whitelist_click:exception",
                "selector 处理异常",
                {"platform": platform, "selector": sel, "resolved": resolved_sel,
                 "err": str(e)[:120]},
            )
    return False


def handle_post_publish_popups(page, platform: str, max_rounds: int = 8, content_warning: bool = False) -> dict:
    """发布后弹窗处理（白名单快路径 + AI 兜底）。

    Args:
        content_warning: 发布前 content_check 阶段是否检测到内容限制警告。
            为 True 时，若弹窗再次出现内容限制关键词，直接 abort 不走 AI。

    返回:
        {"handled": bool, "action": str, "description": str}
        action 为 "abort" 时调用方应终止发布。
    """
    try:
        page.handle_alert(accept=True, timeout=0.5)
    except Exception:
        pass

    # 短延迟即可：调用方（tiktok.py）已经用 _handle_continue_to_post_dialog 紧贴 click 处理过弹窗，
    # 进到这里时大概率页面已稳定。原来的 2s 等待属于历史包袱，缩到 0.5s 可省 1.5s。
    time.sleep(0.5)

    result = {"handled": False, "action": "none", "description": ""}
    ai_called = False

    for rnd in range(max_rounds):
        try:
            page.handle_alert(accept=True, timeout=0.3)
        except Exception:
            pass

        dialog = _find_dialog(page, platform)
        if not dialog:
            if rnd >= 3:
                break
            time.sleep(1.5)
            continue

        dialog_text = (dialog.text or "")[:200]
        dialog_lower = dialog_text.lower()
        logger.info(f"  检测到弹窗 (轮次 {rnd}): {dialog_text[:60]}...")

        progress_keywords = ["sharing", "uploading", "processing", "正在分享", "正在上传", "处理中"]
        if any(kw in dialog_lower for kw in progress_keywords):
            logger.info(f"  ↳ 进度提示，跳过处理")
            time.sleep(1.5)
            continue

        _restrict_keywords = ["restrict", "限制", "violation", "违规", "not recommend"]
        if content_warning and any(kw in dialog_lower for kw in _restrict_keywords):
            logger.warning("  ⚠️ 内容限制弹窗（发布前已检测到 content_warning），终止发布")
            result["action"] = "abort"
            result["description"] = "视频内容被平台标记为可能受限，建议检查视频内容后重新上传。"
            return result

        if _try_whitelist_click(dialog, platform):
            result["handled"] = True
            time.sleep(1)
            still_dialog = _find_dialog(page, platform)
            if not still_dialog:
                break
            continue

        if not ai_called:
            ai_called = True
            try:
                from social_uploader.tools.ai_judge import judge_popup
                ai_result = judge_popup(page, platform, dialog_el=dialog)
                if ai_result:
                    action = ai_result.get("action", "ignore")
                    result["description"] = ai_result.get("description", "")

                    if action == "abort":
                        result["action"] = "abort"
                        logger.warning(f"  AI 建议终止: {result['description']}")
                        return result

                    if action == "click_button":
                        btn_text = ai_result.get("button_text", "")
                        if btn_text:
                            # 内容相关的危险按钮（replace/delete/discard）→ 终止发布
                            _ABORT_BUTTONS = [
                                "replace video", "replace", "替换视频", "替换",
                                "重新上传", "re-upload", "reupload",
                                "delete", "删除", "discard", "丢弃", "放弃",
                            ]
                            if btn_text.strip().lower() in _ABORT_BUTTONS:
                                logger.warning(
                                    f"  [AI] 建议点击危险按钮 [{btn_text}]，已拦截。"
                                    f" 视为内容问题，终止发布并通知用户。"
                                )
                                _dbg_log_popup(
                                    "post_publish.py:ai_judge:abort_button",
                                    "AI 推荐内容危险按钮，已拦截并终止",
                                    {"platform": platform, "button_text": btn_text},
                                )
                                result["action"] = "abort"
                                result["description"] = (
                                    f"平台弹出内容限制警告，AI 建议点击 [{btn_text}]（已拦截）。"
                                    f"请检查视频内容是否符合平台规范后重新上传。"
                                )
                                return result
                            # 关闭/取消/编辑类按钮 → 仅跳过本次点击，等待真正的发布按钮出现
                            if _is_denied_button(btn_text):
                                logger.warning(
                                    f"  [AI] 建议点击 [{btn_text}]，但命中 deny list（关闭/取消/编辑类），"
                                    f"跳过本次点击，等待真正的发布按钮"
                                )
                                _dbg_log_popup(
                                    "post_publish.py:ai_judge:denied",
                                    "AI 推荐被 deny list 拦截",
                                    {"platform": platform, "button_text": btn_text},
                                )
                                if rnd >= 5:
                                    break
                                time.sleep(1.5)
                                continue
                            btn = dialog.ele(f"text:{btn_text}", timeout=0.5)
                            if btn and btn.states.has_rect:
                                btn.click()
                                logger.info(f"  [AI] 已点击弹窗按钮 [{btn_text}]")
                                _dbg_log_popup(
                                    "post_publish.py:ai_judge:clicked",
                                    "AI 推荐按钮被点击",
                                    {"platform": platform, "button_text": btn_text},
                                )
                                result["handled"] = True
                                time.sleep(1)
                                still = _find_dialog(page, platform)
                                if not still:
                                    break
                                continue

                    if action == "dismiss":
                        close_btn = dialog.ele("[aria-label='Close']", timeout=0.3)
                        if close_btn and close_btn.states.has_rect:
                            close_btn.click()
                            result["handled"] = True
                            time.sleep(0.5)
                            break
            except Exception as e:
                logger.debug(f"  AI 弹窗判断异常: {e}")

        if rnd >= 5:
            break
        time.sleep(1.5)

    try:
        page.handle_alert(accept=True, timeout=0.3)
    except Exception:
        pass

    if result["handled"]:
        logger.info("  已处理发布确认弹窗")
    return result


def wait_for_publish_confirmation(
    page,
    platform: str,
    timeout_s: int = 30,
    error_check_fn: Callable | None = None,
) -> tuple[bool, str]:
    """等待发布成功确认（URL 快路径 + 信号 + YouTube dialog 消失 + AI 兜底）。

    Args:
        page: DrissionPage 页面对象
        platform: "tiktok" | "youtube" | "instagram"
        timeout_s: 最大等待秒数
        error_check_fn: 平台级错误检测回调，签名 (page) -> (bool, str)

    Returns:
        (is_success, reason)
    """
    logger.info("  等待发布成功确认...")

    url_pattern = get_patterns(platform, "confirm").get("success_url_pattern", {})
    url_not_contains = url_pattern.get("not_contains", [])
    url_or_contains = url_pattern.get("or_contains", [])

    confirm_patterns = get_patterns(platform, "confirm")
    yt_close_sels = confirm_patterns.get("close_button", [])
    yt_dialog_sels = confirm_patterns.get("dialog_selector", [])

    try:
        initial_url = page.url.lower()
    except Exception:
        initial_url = ""
    already_on_content = url_or_contains and any(kw in initial_url for kw in url_or_contains)

    deadline = time.time() + timeout_s
    ai_calls = 0
    max_ai_calls = 3
    poll_interval = 2
    i = 0

    while time.time() < deadline:
        elapsed = int(time.time() + timeout_s - deadline)
        try:
            page.handle_alert(accept=True, timeout=0.3)
        except Exception:
            pass

        try:
            current_url = page.url.lower()
        except Exception:
            logger.warning(f"  ⚠️ 页面连接断开 — 无法确认发布状态，请手动检查 (耗时约 {elapsed} 秒)")
            return False, "page_disconnected_unverified"

        # 0. 兜底：每 3 轮（约 6s）检测一次延迟出现的二次确认弹窗（白名单模式）
        # 防止弹窗在 handle_post_publish_popups 退出后才出现，导致死等
        # 不每轮检测：成功路径下完全是空轮询，浪费 CPU + 拖慢正常流程
        if i % 3 == 0:
            try:
                late_dialog = _find_dialog(page, platform)
                if late_dialog:
                    dlg_text = (late_dialog.text or "").strip().lower()
                    if not any(kw in dlg_text for kw in [
                        "sharing", "uploading", "processing", "正在分享", "正在上传", "处理中",
                    ]):
                        if _try_whitelist_click(late_dialog, platform):
                            logger.info(f"  ✅ wait 阶段处理了延迟出现的弹窗 (耗时约 {elapsed} 秒)")
                            time.sleep(1)
                            continue
            except Exception:
                pass

        # 1. URL 快路径（排除脚本自身导航到 content 页的情况）
        if url_or_contains and not already_on_content and any(kw in current_url for kw in url_or_contains):
            logger.info(f"  页面已跳转到管理页，发布成功 (耗时约 {elapsed} 秒)")
            return True, "url_redirect"

        # 2. error_signals 检查
        err_matched, err_sel = check_signals(page, platform, "confirm", "error_signals", timeout=0.3)
        if err_matched:
            logger.error(f"  检测到发布失败信号: {err_sel}")
            return False, f"error_signal: {err_sel}"

        # 3. 平台级错误检测（如 TikTok 异步上传错误）
        if error_check_fn and elapsed >= 4:
            try:
                has_err, err_desc = error_check_fn(page)
                if has_err:
                    logger.error(f"  平台错误检测: {err_desc}")
                    return False, f"platform_error: {err_desc}"
            except Exception:
                pass

        # 4. success_signals 快路径
        success_matched, matched_sel = check_signals(page, platform, "confirm", "success_signals", timeout=0.5)
        if success_matched:
            logger.info(f"  检测到发布成功提示 (耗时约 {elapsed} 秒)")
            return True, f"success_signal: {matched_sel}"

        # 5. YouTube 特有: close_button 可见 + (success_signals 再检 OR dialog 消失)
        if yt_close_sels:
            close_btn = None
            for sel in yt_close_sels:
                try:
                    close_btn = page.ele(sel, timeout=0.3)
                    if close_btn and close_btn.states.has_rect:
                        break
                    close_btn = None
                except Exception:
                    close_btn = None
            if close_btn:
                recheck, _ = check_signals(page, platform, "confirm", "success_signals", timeout=0.3)
                if recheck:
                    logger.info(f"  发布完成（关闭按钮+信号确认, 耗时约 {elapsed} 秒）")
                    return True, "close_button_with_signal"
                dialog_gone = True
                for sel in yt_dialog_sels:
                    try:
                        dlg = page.ele(sel, timeout=0.3)
                        if dlg and dlg.states.has_rect:
                            dialog_gone = False
                            break
                    except Exception:
                        pass
                if dialog_gone:
                    logger.info(f"  发布完成（对话框已关闭, 耗时约 {elapsed} 秒）")
                    return True, "dialog_closed"

        # 6. AI 兜底（wall-clock 控制：仅在 6 秒后、每 8 秒最多调一次，且不超过剩余时间的一半）
        remaining = deadline - time.time()
        if elapsed >= 6 and i % 4 == 3 and ai_calls < max_ai_calls and remaining > 10:
            ai_calls += 1
            try:
                from social_uploader.tools.ai_judge import judge_success
                ai_result = judge_success(page, platform)
                if ai_result:
                    status = ai_result.get("status", "pending")
                    reason = ai_result.get("reason", "")
                    confidence = ai_result.get("confidence", 0)
                    if status == "success" and confidence >= 0.7:
                        logger.info(f"  [AI] 判断发布成功: {reason} (耗时约 {elapsed} 秒)")
                        return True, f"ai_judge: {reason}"
                    # —— 定时发布场景：AI 返回 pending 但 reason 含调度关键字时视为成功
                    # 因为「scheduled」意味着视频已成功送达平台调度队列，发布动作已完成，
                    # 只是平台尚未到达发布时间点。继续等待"已发布"是无意义的（最长可能等几天）。
                    # 关键字覆盖中英文：scheduled / 已排定 / 已计划 / 排定时间 / will be published
                    _SCHEDULED_KEYWORDS = (
                        "scheduled", "schedule for", "set to publish", "will be published",
                        "已排定", "已计划", "已安排", "排定时间", "定时发布", "计划于",
                    )
                    reason_lc = reason.lower()
                    if status == "pending" and confidence >= 0.6 and any(
                        kw in reason_lc or kw in reason for kw in _SCHEDULED_KEYWORDS
                    ):
                        logger.info(f"  [AI] 判断为定时发布已生效: {reason} (耗时约 {elapsed} 秒)")
                        return True, f"ai_judge_scheduled: {reason}"
                    if status == "failed" and confidence >= 0.8:
                        logger.error(f"  [AI] 判断发布失败: {reason}")
                        return False, f"ai_judge: {reason}"
            except Exception as e:
                logger.debug(f"  AI 成功判断异常: {e}")

        if i % 5 == 4:
            logger.info(f"   等待中... ({elapsed}秒)")
        time.sleep(poll_interval)
        i += 1

    logger.warning(f"  等待发布确认超时({timeout_s}秒)")
    return False, f"timeout_{timeout_s}s"

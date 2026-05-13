import time
import os
import logging

from social_uploader.uploaders import should_skip
from social_uploader.uploaders.video_check import validate_video_file, log_login_error, quick_login_check
from social_uploader.tools.browser_manager import connect_browser, dismiss_interfering_overlays, find_platform_tab, check_page_error, inject_popup_guard, cleanup_tabs
from social_uploader.tools.element_finder import find_element, preflight_check
from social_uploader.repair_engine import log_step, report_failure, generate_run_id, write_success, safe_page_url
from social_uploader.tools.upload_profile import load_profile, get_platform_config, validate_platform_config
from social_uploader.tools.pattern_checker import dismiss_popups as _dismiss_popups_cfg, check_signals, get_signal_list

logger = logging.getLogger(__name__)

"""
代码地图（AI 修改时先看这里定位代码位置）：

步骤名          | 做什么                     | 代码位置
----------------|----------------------------|---------------------------
validate        | 校验视频文件               | upload_instagram() 开头
connect         | 连接浏览器                 | upload_instagram() 中段
login           | 打开首页 + 检测登录        | _do_upload_instagram() → "阶段 1"
create_btn      | 点击"新帖"按钮             | _do_upload_instagram() → "阶段 2"
file_inject     | 注入视频文件               | _do_upload_instagram() → "阶段 3"
crop_wait       | 等待裁剪界面就绪           | _do_upload_instagram() → "阶段 4"
ratio           | 选择原始比例               | _do_upload_instagram() → "阶段 5"
next1           | 第一次下一步（裁剪→滤镜）  | _do_upload_instagram() → "阶段 6"
next2           | 第二次下一步（滤镜→信息）  | _do_upload_instagram() → "阶段 7"
caption         | 填写发布文案               | _do_upload_instagram() → "阶段 8"
share           | 点击分享按钮               | _do_upload_instagram() → "阶段 9"
confirm         | 等待发布完成               | _do_upload_instagram() → "阶段 10"

辅助函数：
  _handle_popups()     — 关闭各种干扰弹窗
  _find_text_button()  — 按文本查找可点击元素（Instagram 专用）
  _click_next()        — 查找并点击「下一步/Next」
  should_skip()       — resume-from 跳步判断（来自 uploaders.__init__）

已实现的 profile 配置项（profile.instagram.*）：
  share_to_feed  — 同步到动态流（默认 true）
"""

INSTAGRAM_URL_PREFIX = "https://www.instagram.com"
STEPS = [
    "validate", "connect", "login", "page_check", "create_btn", "file_inject",
    "crop_wait", "ratio", "next1", "next2", "caption", "share", "confirm",
]


def _handle_popups(page, max_rounds=3):
    """从 state_patterns.json 读取 Instagram 弹窗关闭选择器。"""
    _dismiss_popups_cfg(page, "instagram", max_rounds=max_rounds)


def _find_text_button(page, keywords, scope='dialog'):
    """
    通用文本按钮查找：在对话框或全页面中按文本内容匹配可点击元素。
    Instagram 不用 <a>/<button>/role="button"，而是纯 <div> 包裹文本。
    只返回可见（has_rect）的元素，避免 NoRectError。
    """
    target = page
    if scope == 'dialog':
        dialog = page.ele('xpath://div[@role="dialog"]', timeout=3)
        if dialog:
            target = dialog

    for kw in keywords:
        for el in target.eles(f'text={kw}', timeout=1):
            try:
                if el.states.has_rect:
                    return el
            except Exception:
                pass

    for kw in keywords:
        for tag in ['div', 'span', 'button', 'a']:
            el = target.ele(f'xpath:.//{tag}[text()="{kw}"]', timeout=0.5)
            if el:
                try:
                    if el.states.has_rect:
                        return el
                except Exception:
                    pass

    if scope == 'dialog':
        dialogs = page.eles('xpath://div[@role="dialog" or @role="presentation"]', timeout=2)
        for dlg in dialogs:
            for kw in keywords:
                for el in dlg.eles(f'text={kw}', timeout=0.5):
                    try:
                        if el.states.has_rect:
                            return el
                    except Exception:
                        pass

    return None


def _click_next(page):
    """查找并点击「下一步/Next」，从 state_patterns.json 读取关键词。"""
    next_kws = get_signal_list("instagram", "navigation", "next_keywords")
    if not next_kws:
        next_kws = ['Next', '下一步']
    btn = _find_text_button(page, next_kws, scope='dialog')
    if btn:
        btn.click()
        text = (btn.text or '').strip()[:20]
        logger.info(f"  ✅ 已点击下一步 (text='{text}')")
        return True
    logger.warning("  ⚠️ 未找到【下一步】按钮")
    return False


def upload_instagram(video_path, caption, no_publish=False, run_id=None, resume_from=None, profile=None, account=None):
    if run_id is None:
        run_id = generate_run_id()
    if profile is None:
        profile = load_profile()
    config = get_platform_config(profile, "instagram")
    config, constraint_warnings = validate_platform_config("instagram", config)
    for w in constraint_warnings:
        logger.warning(f"  ⚠️ {w}")

    ok, err_msg = validate_video_file(video_path, platform="instagram")
    if not ok:
        logger.error(f"❌ 视频预校验失败: {err_msg}")
        log_step("validate", "fail", error="file_rejected", detail=err_msg)
        return False
    file_size = os.path.getsize(video_path)
    logger.info(f"✅ 视频预校验通过 ({os.path.basename(video_path)}, {file_size/1024:.0f}KB)")
    log_step("validate", "ok", file=os.path.basename(video_path), size_kb=round(file_size / 1024))

    data_dir = None
    if account is not None:
        from social_uploader.account_manager import get_data_dir
        data_dir = get_data_dir(account)
        logger.info(f"👤 使用账号: {account}")

    try:
        if resume_from:
            ctrl, work, baseline_tab_ids, _ = connect_browser(new_window=False, data_dir=data_dir)
            platform_tab = find_platform_tab(ctrl, INSTAGRAM_URL_PREFIX)
            if platform_tab:
                work = platform_tab
                logger.info(f"🔄 找到 Instagram 页面标签，将从 {resume_from} 步骤恢复")
            else:
                logger.warning("⚠️ 未找到 Instagram 页面标签，将从头执行")
                work = ctrl.new_tab(url="about:blank")
                work.set.auto_handle_alert(accept=True)
                resume_from = None
        else:
            ctrl, work, baseline_tab_ids, _ = connect_browser(data_dir=data_dir)
        log_step("connect", "ok", port=9222)
    except Exception as e:
        logger.error(f"❌ 连接浏览器失败，请确保运行了 start_chrome_debug.sh\n   {e}")
        log_step("connect", "fail", error="unknown", detail=str(e)[:200])
        return False

    success = False
    _t0 = time.time()
    try:
        success = _do_upload_instagram(work, ctrl, baseline_tab_ids, video_path, caption, no_publish, run_id, resume_from, config)
        return success
    finally:
        if success:
            write_success(run_id, "instagram", elapsed_s=round(time.time() - _t0))
            cleanup_tabs(ctrl, baseline_tab_ids)
        else:
            logger.info("💡 任务窗口已保留，可用 --resume-from 从断点恢复")


def _do_upload_instagram(work, ctrl, baseline_tab_ids, video_path, caption, no_publish, run_id, resume_from, config):
    platform = "instagram"
    page = work

    # resume-from 页面状态校验
    if resume_from:
        current_url = page.url or ""
        if INSTAGRAM_URL_PREFIX not in current_url:
            logger.warning(f"⚠️ 页面已离开 Instagram ({current_url[:60]}...)，忽略 resume-from，从头执行")
            log_step("resume_check", "fail", reason="page_url_changed", url=current_url[:100])
            resume_from = None
        else:
            log_step("resume_check", "ok", resume_from=resume_from)

    # === 阶段 1：打开 Instagram ===
    if not should_skip("login", resume_from, STEPS):
        logger.info("🌐 正在访问 Instagram...")
        page.get('https://www.instagram.com/')
        page.wait.doc_loaded(timeout=15)
        inject_popup_guard(page)

        logged_in, detail = quick_login_check(page, platform)
        if not logged_in:
            log_login_error('Instagram')
            log_step("login", "fail", error="login_required", page_url=page.url)
            report_failure(page, run_id, platform, "login", "login_required", safe_page_url(page))
            return False

        if 'accounts/login' in page.url:
            log_login_error('Instagram')
            log_step("login", "fail", error="login_required", page_url=page.url)
            report_failure(page, run_id, platform, "login", "login_required", safe_page_url(page))
            return False
        log_step("login", "ok")

    # === 页面状态检测 ===
    if not should_skip("page_check", resume_from, STEPS):
        has_page_error, page_error_desc = check_page_error(page, platform)
        if has_page_error:
            logger.error(f"❌ Instagram 平台异常: {page_error_desc}")
            log_step("page_check", "fail", error="platform_unavailable", detail=page_error_desc)
            report_failure(page, run_id, platform, "page_check", "platform_unavailable", safe_page_url(page),
                           detail=page_error_desc)
            return False
        log_step("page_check", "ok")

        preflight_check(page, platform)

    # === 阶段 2：等待「新帖」SVG 出现并点击 ===
    if not should_skip("create_btn", resume_from, STEPS):
        dismiss_interfering_overlays(ctrl, work, baseline_tab_ids)

        logger.info("➕ 等待【新帖】按钮出现并点击...")

        create_btn = None
        matched = ''

        start = time.time()
        while time.time() - start < 15:
            _handle_popups(page, max_rounds=1)
            create_btn, matched_sel = find_element(page, platform, "create_button", timeout=0.5)
            if create_btn:
                matched = matched_sel or 'create_button'
                break
            time.sleep(0.5)

        if not create_btn:
            logger.error("❌ 15秒内未找到【新帖】按钮，请检查页面。")
            log_step("create_btn", "fail", error="selector_not_found", detail="create_button 未找到")
            report_failure(page, run_id, platform, "create_btn", "selector_not_found", safe_page_url(page),
                           selectors_tried="create_button")
            return False

        elapsed = round(time.time() - start, 1)
        logger.info(f"  ✅ 找到创建按钮 ({matched}) [{elapsed}s]")

        create_btn.click()
        time.sleep(1)

        log_step("create_btn", "ok", matched=str(matched)[:50], elapsed_s=elapsed)

    # === 阶段 3：注入视频文件 ===
    if not should_skip("file_inject", resume_from, STEPS):
        logger.info("📂 注入视频文件...")

        # 等待创建帖子对话框出现（不在此阶段调用 dismiss_interfering_overlays / _handle_popups，
        # 因为 sweep_modals JS 和 OVERLAY_CLEANUP_JS 可能误关 Instagram 的上传弹窗）
        dlg = None
        for _w in range(15):
            dlg = page.ele('xpath://div[@role="dialog"]', timeout=1)
            if dlg:
                logger.info(f"  ✅ 对话框已出现 [{_w}s]")
                break
            time.sleep(1)

        if not dlg:
            logger.warning("  ⚠️ 对话框未出现，尝试重新点击创建按钮...")
            create_btn2, _ = find_element(page, platform, "create_button", timeout=3)
            if create_btn2:
                create_btn2.click()
                time.sleep(3)
                dlg = page.ele('xpath://div[@role="dialog"]', timeout=5)

        # 直接在页面中查找 file input（不经过 find_element 的 has_rect 检查）
        file_input = page.ele('xpath://input[@type="file"]', timeout=5)
        if not file_input and dlg:
            file_input = dlg.ele('xpath:.//input[@type="file"]', timeout=3)

        if not file_input:
            # 尝试点击"从电脑选择"按钮
            select_btn = None
            for txt in ['Select from computer', '从电脑选择', '从电脑中选择', '从设备中选择']:
                select_btn = page.ele(f'text:{txt}', timeout=1)
                if select_btn:
                    break
            if select_btn:
                logger.info(f"  📎 点击「{(select_btn.text or '').strip()[:30]}」...")
                select_btn.click()
                time.sleep(2)
                file_input = page.ele('xpath://input[@type="file"]', timeout=5)

        if not file_input:
            logger.error("❌ 未找到文件上传入口。")
            log_step("file_inject", "fail", error="selector_not_found", detail="file_input 未找到")
            report_failure(page, run_id, platform, "file_inject", "selector_not_found", safe_page_url(page),
                           selectors_tried="file_input, select_from_computer")
            return False

        try:
            file_input.input(video_path)
        except Exception as e:
            logger.error(f"  ❌ 文件注入失败: {e}")
            log_step("file_inject", "fail", error="inject_exception", detail=str(e)[:200])
            report_failure(page, run_id, platform, "file_inject", "inject_exception", safe_page_url(page),
                           detail=str(e)[:200])
            return False

        logger.info(f"  ✅ 已注入: {os.path.basename(video_path)}")
        log_step("file_inject", "ok", file=os.path.basename(video_path))

    # === 阶段 4：等待裁剪界面就绪 ===
    if not should_skip("crop_wait", resume_from, STEPS):
        logger.info("⏳ 等待裁剪界面...")
        _handle_popups(page, max_rounds=2)

        confirm_selectors = get_signal_list(platform, "crop_wait", "confirm_dismiss")
        for sel in confirm_selectors:
            for btn in page.eles(sel, timeout=0.5):
                try:
                    if btn.states.has_rect:
                        btn.click()
                        logger.info("  ✅ 已确认弹窗")
                        break
                except Exception:
                    pass

        ready_sels = get_signal_list(platform, "crop_wait", "ready_signals")
        for i in range(20):
            dialog = page.ele('xpath://div[@role="dialog"]', timeout=1)
            if dialog:
                found_next = False
                for sel in ready_sels:
                    nxt = dialog.ele(sel, timeout=0.5)
                    if nxt:
                        found_next = True
                        break
                if found_next:
                    logger.info(f"  ✅ 裁剪界面就绪 [{i}s]")
                    break
            time.sleep(1)
        else:
            logger.warning("  ⚠️ 等待裁剪界面超时，尝试继续...")
        log_step("crop_wait", "ok")

    # === 阶段 5：选择比例（原始）===
    if not should_skip("ratio", resume_from, STEPS):
        logger.info("📐 选择尺寸比例（原始）...")
        dialog = page.ele('xpath://div[@role="dialog"]', timeout=2)
        if dialog:
            crop_labels = get_signal_list(platform, "ratio", "crop_labels")
            ratio_btn = None
            for label in crop_labels:
                ratio_btn = dialog.ele(f'xpath:.//*[local-name()="svg" and @aria-label="{label}"]', timeout=0.5)
                if ratio_btn:
                    break
            if ratio_btn:
                ratio_btn.click()
                time.sleep(0.5)
                ratio_options = get_signal_list(platform, "ratio", "ratio_options")
                orig = None
                for sel in ratio_options:
                    orig = page.ele(sel, timeout=0.5)
                    if orig:
                        break
                if orig:
                    orig.click()
                    logger.info("  ✅ 已选择原始比例")
                time.sleep(0.3)
            else:
                logger.warning("  ⚠️ 未找到比例按钮，保持默认")
        log_step("ratio", "ok")

    # === 阶段 6：第一次「下一步」===
    if not should_skip("next1", resume_from, STEPS):
        dismiss_interfering_overlays(ctrl, work, baseline_tab_ids)
        logger.info("⏭️ 下一步 (裁剪 → 滤镜)...")
        if not _click_next(page):
            logger.error("❌ 无法点击【下一步】，流程中止。")
            log_step("next1", "fail", error="selector_not_found", detail="next_button 未找到")
            report_failure(page, run_id, platform, "next1", "selector_not_found", safe_page_url(page),
                           selectors_tried="next_button (text=Next/下一步)")
            return False
        time.sleep(1)
        log_step("next1", "ok")

    # === 阶段 7：第二次「下一步」===
    if not should_skip("next2", resume_from, STEPS):
        dismiss_interfering_overlays(ctrl, work, baseline_tab_ids)
        logger.info("⏭️ 下一步 (滤镜 → 信息填写)...")
        if not _click_next(page):
            logger.error("❌ 无法点击【下一步】，流程中止。")
            log_step("next2", "fail", error="selector_not_found", detail="next_button 未找到")
            report_failure(page, run_id, platform, "next2", "selector_not_found", safe_page_url(page),
                           selectors_tried="next_button (text=Next/下一步)")
            return False
        time.sleep(1)
        log_step("next2", "ok")

    # === 阶段 8：填写文案 ===
    if not should_skip("caption", resume_from, STEPS):
        dismiss_interfering_overlays(ctrl, work, baseline_tab_ids)
        logger.info("📝 填写发布文案...")
        safe_caption = (caption or "")[:2200]

        caption_box, _ = find_element(page, platform, "caption_box", timeout=1)
        if caption_box:
            caption_box.click()
            time.sleep(0.3)
            caption_box.input(safe_caption)
            logger.info("  ✅ 文案已填写")
        else:
            logger.warning("  ⚠️ 未找到文案输入框，跳过。")
        log_step("caption", "ok", filled=bool(caption_box))

    # === 阶段 8.5：设置 share_to_feed ===
    share_to_feed = config.get("share_to_feed", True)
    if not share_to_feed:
        logger.info("⚙️ 关闭「同步到动态流」...")
        result = page.run_js("""
            var switches = document.querySelectorAll('input[type="checkbox"], [role="switch"], [role="checkbox"]');
            for (var sw of switches) {
                var row = sw;
                for (var i = 0; i < 8; i++) {
                    row = row.parentElement;
                    if (!row) break;
                    if (row.textContent.includes('Also share to feed') || row.textContent.includes('同步到动态')) {
                        var isOn = sw.checked || sw.getAttribute('aria-checked') === 'true';
                        if (isOn) { sw.click(); return 'toggled'; }
                        return 'ok';
                    }
                }
            }
            return 'not_found';
        """)
        if result in ('toggled', 'ok'):
            logger.info(f"  ✅ share_to_feed: 关闭 ({'已切换' if result == 'toggled' else '无需改动'})")
        else:
            logger.warning("  ⚠️ 未找到 share_to_feed 开关，视频可能会同步到动态流")
            log_step("share_to_feed", "fail", error="switch_not_found",
                     detail="share_to_feed 开关未找到，视频将以默认设置（同步到动态流）发布")

    # === no_publish 检查 ===
    if no_publish:
        logger.info("⏸️ --no-publish 模式：表单已填好，跳过分享步骤。请在浏览器中手动检查并分享。")
        log_step("complete", "ok", mode="no_publish")
        return True

    # === 阶段 9：点击「分享 / Share」===
    if not should_skip("share", resume_from, STEPS):
        dismiss_interfering_overlays(ctrl, work, baseline_tab_ids)
        logger.info("🚀 点击【分享】...")
        share_kws = get_signal_list(platform, "navigation", "share_keywords")
        if not share_kws:
            share_kws = ['Share', '分享']
        share_btn = _find_text_button(page, share_kws)
        if share_btn:
            share_btn.click()
            logger.info("  ✅ 已点击【分享】")
            log_step("share", "ok")
        else:
            logger.warning("  ⚠️ 未找到【分享】按钮，请手动检查。")
            log_step("share", "fail", error="selector_not_found", detail="share_button 未找到")
            report_failure(page, run_id, platform, "share", "selector_not_found", safe_page_url(page),
                           selectors_tried="share_button (text=Share/分享)")
            return False

    # === 阶段 10：等待发布完成（带智能重试） ===
    if not should_skip("confirm", resume_from, STEPS):
        from social_uploader.tools.post_publish import handle_post_publish_popups, wait_for_publish_confirmation
        from social_uploader.tools.retry_engine import retry_step, StepResult

        popup_result = handle_post_publish_popups(page, platform, max_rounds=3)
        if popup_result.get("action") == "abort":
            logger.error(f"❌ 发布被阻止: {popup_result.get('description', '')}")
            log_step("confirm", "fail", error="popup_abort",
                     detail=popup_result.get("description", "")[:200])
            report_failure(page, run_id, platform, "confirm", "popup_abort",
                           page.url, detail=popup_result.get("description", "")[:200])
            return False

        def _ig_idempotent_check():
            matched, _ = check_signals(page, platform, "confirm", "success_signals", timeout=0.5)
            return matched

        def _do_confirm():
            ok, reason = wait_for_publish_confirmation(page, platform, timeout_s=120)
            return StepResult(ok, value=reason, error="" if ok else reason)

        confirm_result = retry_step(
            page, platform, "confirm",
            step_fn=_do_confirm,
            max_retries=2,
            is_irreversible=True,
            pre_retry_check=_ig_idempotent_check,
        )

        if confirm_result.success:
            reason = confirm_result.value or "retry_success"
            logger.info(f"🎉 Instagram 上传流程结束。({reason})")
            log_step("confirm", "ok", detail=str(reason)[:200])
            return True
        else:
            reason = confirm_result.error or "unknown"
            logger.warning(f"  ⚠️ 发布确认失败: {reason}")
            logger.info("❌ Instagram 上传流程结束（未确认成功）。")
            log_step("confirm", "fail", error="state_mismatch", detail=str(reason)[:200])
            report_failure(page, run_id, platform, "confirm", "state_mismatch",
                           page.url, detail=str(reason)[:200])
            return False

import time
import os
import json
import logging


# region agent log — Debug session 66b267 (TK confirm 调试)
def _dbg_log_tk(loc, msg, data, hyp, run_id="initial"):
    """临时 NDJSON 调试日志（tiktok confirm），写到 debug-social-upload.log。"""
    try:
        rec = {
            "sessionId": "66b267", "runId": run_id, "hypothesisId": hyp,
            "timestamp": int(time.time() * 1000),
            "location": loc, "message": msg, "data": data,
        }
        with open("debug-social-upload.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


_DBG_TK_PROBE_JS = r"""
var __r = {url: location.href, title: document.title};
try {
    var modals = document.querySelectorAll('[class*="TUXModal"], [role="dialog"], [class*="modal"]');
    var visModals = [];
    modals.forEach(function(m){
        if (m.offsetParent === null) return;
        var t = (m.innerText || '').trim().slice(0, 200);
        visModals.push({tag: m.tagName, cls: (m.className||'').toString().slice(0,100), text: t});
    });
    __r.visible_modals = visModals;
} catch(e) { __r.modal_err = String(e); }
try {
    var pb = document.querySelector('[data-e2e="post_video_button"]') ||
             document.querySelector('button[aria-label*="发布"]') ||
             document.querySelector('button[aria-label*="Post"]');
    if (pb) {
        __r.post_btn = {
            visible: pb.offsetParent !== null,
            aria_disabled: pb.getAttribute('aria-disabled'),
            data_disabled: pb.getAttribute('data-disabled'),
            disabled_attr: pb.disabled,
            text: (pb.textContent||'').trim().slice(0,40),
        };
    } else {
        __r.post_btn = null;
    }
} catch(e) { __r.btn_err = String(e); }
try {
    var toasts = document.querySelectorAll('[class*="toast"], [class*="Toast"], [role="status"], [role="alert"]');
    var visToasts = [];
    toasts.forEach(function(t){
        if (t.offsetParent === null) return;
        var txt = (t.innerText || '').trim().slice(0,200);
        if (txt) visToasts.push(txt);
    });
    __r.visible_toasts = visToasts;
} catch(e) {}
try {
    var cards = document.querySelectorAll('[class*="video"], [class*="card"], [class*="item"]');
    var seen = {};
    var keywords = ['Debug', '已发布', '已计划', '已安排', '审核', 'Scheduled', 'Processing', '处理中', 'Public', '公开', '草稿', 'Draft', '待发布'];
    var rowHits = [];
    cards.forEach(function(c){
        if (c.offsetParent === null) return;
        var t = (c.innerText || '').trim();
        if (t.length < 5 || t.length > 400) return;
        var kwHit = keywords.some(function(kw){ return t.indexOf(kw) >= 0; });
        if (!kwHit) return;
        var sample = t.slice(0,160).replace(/\s+/g,' ');
        if (seen[sample]) return;
        seen[sample] = true;
        rowHits.push(sample);
        if (rowHits.length >= 8) return;
    });
    __r.video_card_hits = rowHits;
} catch(e) { __r.card_err = String(e); }
return JSON.stringify(__r);
"""


def _dbg_tk_probe(page):
    try:
        wrapped = "var __dp_iife_r = (function(){" + _DBG_TK_PROBE_JS + "})(); return __dp_iife_r;"
        raw = page.run_js(wrapped)
        return json.loads(raw) if raw else {}
    except Exception as e:
        return {"probe_err": str(e)}
# endregion

from social_uploader.uploaders import should_skip
from social_uploader.uploaders.video_check import validate_video_file, log_login_error, quick_login_check
from social_uploader.uploaders.tiktok_helpers import (
    _set_toggle,
    _set_checkbox,
    _set_tiktok_visibility,
    _set_tiktok_schedule,
    _set_tiktok_options,
)
from social_uploader.tools.browser_manager import connect_browser, dismiss_interfering_overlays, find_platform_tab, check_page_error, inject_popup_guard, cleanup_tabs
from social_uploader.tools.element_finder import find_element, preflight_check
from social_uploader.repair_engine import log_step, report_failure, generate_run_id, write_success, safe_page_url
from social_uploader.tools.upload_profile import load_profile, get_platform_config, validate_platform_config
from social_uploader.tools.pattern_checker import check_signals, check_error_signals, dismiss_popups, dismiss_error_popup, get_signal_list, get_patterns

logger = logging.getLogger(__name__)

"""
代码地图（AI 修改时先看这里定位代码位置）：

步骤名          | 做什么                     | 代码位置
----------------|----------------------------|---------------------------
validate        | 校验视频文件               | upload_tiktok() 开头
connect         | 连接浏览器                 | upload_tiktok() 中段
login           | 打开上传页 + 检测登录      | _do_upload_tiktok() → "阶段 1"
file_inject     | 注入视频文件               | _do_upload_tiktok() → "阶段 3"
wait_upload     | 等待 Post 按钮 enabled     | _do_upload_tiktok() → "等待上传就绪"
form_fill       | 填写标题和描述             | _do_upload_tiktok() → "阶段 4"
cover           | 上传自定义封面             | _upload_cover_image() 独立函数
scroll          | 滚动到底部                 | _do_upload_tiktok() → "阶段 5"
options         | 设置平台选项               | _set_tiktok_options() → "阶段 5.5"
copyright       | 等待版权检查完成           | _do_upload_tiktok() → "阶段 6"
publish         | 点击发布按钮               | _do_upload_tiktok() → "阶段 7"
confirm         | 等待发布成功确认           | _do_upload_tiktok() → "阶段 9"

本文件内的辅助函数（仅 TikTok 步骤编排相关）：
  _check_upload_error()  — 检测上传错误弹窗
  _dismiss_error_popup() — 关闭上传错误弹窗
  _handle_popups()       — 关闭各种干扰弹窗
  should_skip()          — resume-from 跳步判断（来自 uploaders.__init__）

TikTok 平台专属辅助（位于 uploaders/tiktok_helpers.py，禁止其他平台 import）：
  _set_toggle()              — 通过标签文本设置 toggle 开关
  _set_checkbox()            — 通过标签文本设置自定义 checkbox
  _set_tiktok_visibility()   — 设置可见性下拉（recipe 配方 + 三层兜底）
  _set_tiktok_schedule()     — 设置定时发布（recipe 配方 + 三层兜底）
  _set_tiktok_options()      — 统一入口，按 config 设置所有选项

已实现的 profile 配置项（profile.tiktok.*）：
  visibility       — 可见性: everyone/friends/only_me（默认 everyone）
  schedule         — 定时发布: null=立即, "YYYY-MM-DD HH:MM"=定时
  allow_comments   — 允许评论（默认 true）
  allow_reuse      — 允许二创（默认 true）
  disclose_content — 内容披露（默认 false）
  ai_generated     — AI 生成标记（默认 false）
  high_quality     — 高画质上传（默认 true）
"""

TIKTOK_UPLOAD_URL_PREFIX = "https://www.tiktok.com"
STEPS = [
    "validate", "connect", "login", "page_check", "file_inject", "wait_upload",
    "form_fill", "cover", "scroll", "options", "copyright", "publish", "confirm",
]


def _check_upload_error(page):
    """检测 TikTok 上传错误弹窗，从 state_patterns.json 读取信号。"""
    return check_error_signals(page, "tiktok", "wait_upload")


def _dismiss_error_popup(page):
    """关闭上传错误弹窗，从 state_patterns.json 读取关闭选择器。"""
    dismiss_error_popup(page, "tiktok", "wait_upload")


def _handle_popups(page):
    """从 state_patterns.json 读取弹窗关闭选择器。"""
    dismiss_popups(page, "tiktok", max_rounds=1)


def _handle_continue_to_post_dialog(page, total_wait_s: int = 8) -> bool:
    """专用快速处理：TikTok「Continue to post?」审核弹窗 → 点 Post now。

    弹窗文案：
        Continue to post?
        We're still checking your video for potential issues.
        Do you want to continue posting before the check is complete?
    按钮：[Cancel] [Post now]

    这个弹窗只在视频审核未完成就点 Post 时出现，几乎一定在点击后 0-3 秒内弹出。
    必须主动点 Post now 才能继续发布。

    策略：紧贴点击的"快速试探"轮询（300ms 间隔，默认 8s）
    - URL 跳转 / 视频已发布 toast / Post 按钮消失 → 立即退出（已发布，不需要本函数）
    - 弹窗出现 → 立即点击 Post now
    - 8s 内都没弹窗也没成功信号 → 放手交给后续 wait_for_publish_confirmation 兜底

    为什么 8s 而不是 30s？
    - 极端延迟弹窗（>8s）由 wait_for_publish_confirmation 的逐轮 _find_dialog
      + _try_whitelist_click 兜底（state_patterns.json 白名单含 "Post now"）
    - 顺畅发布路径下不再傻等 30 秒，整体流程缩短 20+ 秒

    返回：True = 检测到弹窗并成功点击 Post now；False = 没出现弹窗（已发布或超时）

    注意：必须紧贴 post_btn.click() 调用，中间不能插任何 sleep，否则可能错过弹窗。
    """
    dialog_xpath = (
        "xpath://*[contains(@class,'TUXModal') or @role='dialog' or @role='alertdialog']"
        "[.//button[@data-type='primary'] or .//button[2]]"
    )
    post_now_selectors = [
        "xpath:.//button[normalize-space(.)='????']",
        "xpath:.//button[normalize-space(.)='Post now']",
        "xpath:.//button[normalize-space(.)='Publish now']",
        "xpath:.//button[@data-type='primary']",
        "xpath:.//button[not(@aria-disabled='true')][last()]",
        "xpath:.//button[last()]",
    ]
    main_post_xpath = "xpath://button[@data-e2e='post_video_button']"

    POLL_INTERVAL = 0.3
    deadline = time.time() + total_wait_s
    started_at = time.time()
    log_first = True
    while time.time() < deadline:
        elapsed = time.time() - started_at

        # 1) URL 已跳转 → 已发布
        try:
            cur_url = (page.url or "").lower()
        except Exception:
            cur_url = ""
        if "/content" in cur_url or "/manage" in cur_url:
            if elapsed > 0.5:
                logger.info(f"  ✅ URL 已跳转 ({cur_url[:60]})，无需 Continue-to-post 处理 (耗时 {elapsed:.1f}s)")
            return False

        # 2) 检测「Video published」toast → 已发布
        try:
            toast = page.ele("text:Video published", timeout=0.1)
            if toast and toast.states.has_rect:
                logger.info(f"  ✅ 已检测到「Video published」toast，无需 Continue-to-post 处理 (耗时 {elapsed:.1f}s)")
                return False
        except Exception:
            pass

        # 3) 主 Post 按钮消失了 → 表单切到 sharing/processing 状态，发布流程已推进
        # 这是新加的早期退出信号：1.5s 后才检查（给点击留反应时间），避免误判
        if elapsed >= 1.5:
            try:
                main_post = page.ele(main_post_xpath, timeout=0.1)
            except Exception:
                main_post = None
            if not main_post or (main_post and not main_post.states.has_rect):
                logger.info(f"  ✅ 主 Post 按钮已消失（页面状态推进），无 Continue-to-post 弹窗 (耗时 {elapsed:.1f}s)")
                return False

        # 4) 检测目标弹窗
        try:
            dialog = page.ele(dialog_xpath, timeout=0.1)
        except Exception:
            dialog = None

        if not dialog:
            if log_first:
                logger.info(f"  ⏳ 快速试探「Continue to post?」审核弹窗（{POLL_INTERVAL}s 轮询，最长 {total_wait_s}s）")
                log_first = False
            time.sleep(POLL_INTERVAL)
            continue

        # 找到弹窗 → 立即点击
        try:
            dialog_text = (dialog.text or "").strip()[:200]
        except Exception:
            dialog_text = ""
        logger.info(f"  🔔 检测到「Continue to post?」审核弹窗 (出现于点击后 {elapsed:.1f}s)")
        logger.info(f"     弹窗内容: {dialog_text[:100]}")

        btn = None
        for post_now_xpath in post_now_selectors:
            try:
                btn = dialog.ele(post_now_xpath, timeout=0.2)
            except Exception:
                btn = None
            if btn and btn.states.has_rect:
                break
        if not btn:
            logger.warning("  ?? ?????????????????????")
            return False

        try:
            btn.click()
            logger.info(f"  ✅ 立即点击 [Post now]（响应延迟 {elapsed:.1f}s）")
        except Exception as e:
            logger.warning(f"  ⚠️ 点击 [Post now] 失败: {e}，{POLL_INTERVAL}s 后重试")
            time.sleep(POLL_INTERVAL)
            continue

        # 等弹窗消失，最多 5 秒
        for _ in range(25):
            time.sleep(0.2)
            try:
                still = page.ele(dialog_xpath, timeout=0.1)
            except Exception:
                still = None
            if not still:
                logger.info("  ✅ 弹窗已关闭，发布提交成功")
                return True
        logger.info("  ⏳ 弹窗未消失，继续轮询尝试")

    logger.info(f"  ℹ️ {total_wait_s}s 快速试探未发现 Continue-to-post 弹窗，交给后续兜底")
    return False


def _upload_cover_image(page, target, cover_path):
    """上传自定义封面图到 TikTok"""
    if not cover_path:
        return
    if not os.path.exists(cover_path):
        logger.warning(f"⚠️ 封面图文件不存在: {cover_path}，跳过封面设置")
        return
    ext = os.path.splitext(cover_path)[1].lower()
    if ext not in {'.jpg', '.jpeg', '.png', '.webp'}:
        logger.warning(f"⚠️ 封面图格式不支持 '{ext}'，仅支持 jpg/png/webp，跳过封面设置")
        return

    logger.info(f"🖼️ 正在设置自定义封面图: {os.path.basename(cover_path)}")

    cover_selectors = [
        'text:Edit cover', 'text:编辑封面',
        'text:Change cover', 'text:更换封面',
        'text:Select cover', 'text:选择封面',
        '@data-e2e=edit_cover',
    ]
    cover_btn = None
    for sel in cover_selectors:
        cover_btn = target.ele(sel, timeout=2)
        if cover_btn:
            break

    if not cover_btn:
        cover_btn = target.ele('xpath://*[contains(@class, "cover") or contains(@class, "thumbnail")]', timeout=3)

    if cover_btn:
        try:
            cover_btn.click()
            time.sleep(1)
            logger.info("  ✅ 已点击封面编辑区域")
        except Exception as e:
            logger.warning(f"  ⚠️ 点击封面编辑失败: {e}")
            return
    else:
        logger.warning("  ⚠️ 未找到封面编辑入口，跳过封面设置")
        return

    cover_input = page.ele(
        'xpath://input[@type="file" and (@accept="image/*" or contains(@accept, "image/"))]',
        timeout=3,
    )

    if not cover_input:
        upload_selectors = [
            'text:Upload cover', 'text:上传封面',
            'text:From device', 'text:从设备选择',
        ]
        for sel in upload_selectors:
            upload_btn = page.ele(sel, timeout=2)
            if upload_btn:
                try:
                    upload_btn.click()
                    time.sleep(1)
                except Exception:
                    pass
                break

        cover_input = page.ele(
            'xpath://input[@type="file" and (@accept="image/*" or contains(@accept, "image/"))]',
            timeout=3,
        )

    if cover_input:
        accept_attr = cover_input.attr('accept') or ''
        if 'video' in accept_attr and 'image' not in accept_attr:
            logger.warning("  ⚠️ 找到的文件输入是视频类型而非图片类型，跳过封面上传以避免误操作")
            return

        cover_input.input(cover_path)
        logger.info("  ✅ 封面图已上传")
        time.sleep(2)

        confirm_selectors = ['text:Done', 'text:完成', 'text:Save', 'text:保存', 'text:Confirm', 'text:确认']
        for sel in confirm_selectors:
            btn = page.ele(sel, timeout=2)
            if btn:
                try:
                    if btn.states.has_rect:
                        btn.click()
                        logger.info("  ✅ 已确认封面设置")
                        time.sleep(1)
                        break
                except Exception:
                    pass
    else:
        logger.warning("  ⚠️ 未找到图片上传入口（TikTok 封面可能仅支持从视频帧选择），跳过封面上传")


def upload_tiktok(video_path, title, description, no_publish=False, cover_path=None, run_id=None, resume_from=None, profile=None, account=None):
    if run_id is None:
        run_id = generate_run_id()
    if profile is None:
        profile = load_profile()
    config = get_platform_config(profile, "tiktok")
    config, constraint_warnings = validate_platform_config("tiktok", config)
    for w in constraint_warnings:
        logger.warning(f"  ⚠️ {w}")

    ok, err_msg = validate_video_file(video_path, platform="tiktok")
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
            platform_tab = find_platform_tab(ctrl, TIKTOK_UPLOAD_URL_PREFIX)
            if platform_tab:
                work = platform_tab
                logger.info(f"🔄 找到 TikTok 页面标签，将从 {resume_from} 步骤恢复")
            else:
                logger.warning("⚠️ 未找到 TikTok 页面标签，将从头执行")
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
        success = _do_upload_tiktok(work, ctrl, baseline_tab_ids, video_path, title, description, no_publish, cover_path, run_id, resume_from, config)
        return success
    finally:
        if success:
            write_success(run_id, "tiktok", elapsed_s=round(time.time() - _t0))
            cleanup_tabs(ctrl, baseline_tab_ids)
        else:
            logger.info("💡 任务窗口已保留，可用 --resume-from 从断点恢复")


def _do_upload_tiktok(work, ctrl, baseline_tab_ids, video_path, title, description, no_publish, cover_path, run_id, resume_from, config):
    platform = "tiktok"
    page = work

    # resume-from 页面状态校验
    if resume_from:
        current_url = page.url or ""
        if TIKTOK_UPLOAD_URL_PREFIX not in current_url:
            logger.warning(f"⚠️ 页面已离开 TikTok ({current_url[:60]}...)，忽略 resume-from，从头执行")
            log_step("resume_check", "fail", reason="page_url_changed", url=current_url[:100])
            resume_from = None
        else:
            log_step("resume_check", "ok", resume_from=resume_from)

    # === 阶段 1：打开 TikTok 上传页 ===
    if not should_skip("login", resume_from, STEPS):
        logger.info("🌐 正在访问 TikTok 上传页...")
        _target_url = 'https://www.tiktok.com/tiktokstudio/upload?from=upload'
        for _nav_attempt in range(3):
            try:
                page.get(_target_url)
                break
            except Exception as _nav_err:
                _err_name = type(_nav_err).__name__
                if _nav_attempt < 2:
                    logger.warning(f"  ⚠️ 页面导航失败 ({_err_name})，重连中... (尝试 {_nav_attempt+2}/3)")
                    time.sleep(2)
                    try:
                        reconnected_tab = find_platform_tab(ctrl, "tiktok.com")
                        if reconnected_tab:
                            page = reconnected_tab
                            work = reconnected_tab
                            logger.info("  🔄 已重连到 TikTok 标签")
                        else:
                            page = ctrl.new_tab(url=_target_url)
                            work = page
                            logger.info("  🔄 已打开新标签")
                            break
                    except Exception:
                        page = ctrl.new_tab(url=_target_url)
                        work = page
                        logger.info("  🔄 重连失败，已打开新标签")
                        break
                else:
                    logger.error(f"  ❌ 页面导航 3 次均失败: {_err_name}")
                    log_step("login", "fail", error="page_disconnected", detail=str(_nav_err)[:200])
                    report_failure(page, run_id, platform, "login", "page_disconnected", "", detail=str(_nav_err)[:200])
                    return False
        page.wait.doc_loaded(timeout=10)
        time.sleep(1)
        inject_popup_guard(page)

        logged_in, detail = quick_login_check(page, platform)
        if not logged_in:
            log_login_error('TikTok')
            log_step("login", "fail", error="login_required", page_url=page.url)
            report_failure(page, run_id, platform, "login", "login_required", safe_page_url(page))
            return False

        if 'login' in page.url.lower() or page.ele('text:Log in', timeout=2) or page.ele('text:登录', timeout=1):
            log_login_error('TikTok')
            log_step("login", "fail", error="login_required", page_url=page.url)
            report_failure(page, run_id, platform, "login", "login_required", safe_page_url(page))
            return False
        log_step("login", "ok")

        _handle_popups(page)
        dismiss_interfering_overlays(ctrl, work, baseline_tab_ids)

    # === 阶段 2：页面状态检测 ===
    if not should_skip("page_check", resume_from, STEPS):
        has_page_error, page_error_desc = check_page_error(page, platform)
        if has_page_error:
            logger.error(f"❌ TikTok 平台异常: {page_error_desc}")
            log_step("page_check", "fail", error="platform_unavailable", detail=page_error_desc)
            report_failure(page, run_id, platform, "page_check", "platform_unavailable", safe_page_url(page),
                           detail=page_error_desc)
            return False
        log_step("page_check", "ok")

        preflight_check(page, platform)

    # === 阶段 3：注入视频文件 ===
    if not should_skip("file_inject", resume_from, STEPS):
        _handle_popups(page)
        logger.info("📁 正在注入视频文件...")
        iframe = page.get_frame('@src^https://www.tiktok.com/creator#/upload')
        target = iframe if iframe else page

        # 残留检测：上次上传的视频卡片若还在，<input type="file"> 会被销毁，导致 file_input 怎么找都找不到
        # 表现为：页面有 data-e2e="upload_status_container" 卡片或 [Replace] 按钮
        # 解决：刷新当前 upload 页 → 回到空白状态 → 再找 file_input
        try:
            stale_card = target.ele('@data-e2e=upload_status_container', timeout=0.5)
        except Exception:
            stale_card = None
        try:
            replace_btn = target.ele('@aria-label=Replace', timeout=0.3) if not stale_card else None
        except Exception:
            replace_btn = None
        if stale_card or replace_btn:
            logger.warning("  ⚠️ 检测到 upload 页面残留上次的视频卡片，刷新页面以清理状态")
            try:
                _clean_url = "https://www.tiktok.com/tiktokstudio/upload?from=upload"
                page.get(_clean_url)
                page.wait.doc_loaded(timeout=15)
                time.sleep(2)
                _handle_popups(page)
                iframe = page.get_frame('@src^https://www.tiktok.com/creator#/upload')
                target = iframe if iframe else page
                logger.info("  ✅ upload 页面已重置")
            except Exception as _e:
                logger.warning(f"  ⚠️ 刷新 upload 页失败: {_e}，继续按原策略尝试")

        file_input, sel = find_element(target, platform, "file_input", timeout=15)
        if not file_input:
            logger.error("❌ 未找到文件上传入口，可能页面结构已变化。")
            log_step("file_inject", "fail", error="selector_not_found", detail="file_input 未找到")
            report_failure(page, run_id, platform, "file_inject", "selector_not_found", safe_page_url(page),
                           selectors_tried="file_input")
            return False

        # --- 确保拿到的是真正的 <input type="file">，而非包装容器 ---
        try:
            _fi_tag = file_input.tag
            _fi_type = file_input.attr('type')
        except Exception:
            _fi_tag = _fi_type = None

        if _fi_tag != "input" or _fi_type != "file":
            logger.info(f"  ⚠️ 定位到的元素不是 <input type='file'> (tag={_fi_tag}, type={_fi_type})，在其内部/页面中查找真正的 file input...")
            real_fi = None
            # 先在定位到的元素内部找
            try:
                real_fi = file_input.ele("xpath:.//input[@type='file']", timeout=2)
            except Exception:
                pass
            # 再在 target 范围内找
            if not real_fi:
                try:
                    real_fi = target.ele("xpath://input[@type='file']", timeout=3)
                except Exception:
                    pass
            # 最后在 page 范围内找
            if not real_fi:
                try:
                    real_fi = page.ele("xpath://input[@type='file']", timeout=3)
                except Exception:
                    pass

            if real_fi:
                logger.info(f"  ✅ 找到真正的 file input (tag={real_fi.tag}, type={real_fi.attr('type')})")
                file_input = real_fi
            else:
                logger.warning("  ⚠️ 未找到真正的 <input type='file'>，尝试用原始元素注入...")

        logger.info(f"   注入文件: {video_path}")
        try:
            file_input.input(video_path)
        except Exception as e:
            logger.error(f"  ❌ 文件注入失败: {e}")
            log_step("file_inject", "fail", error="inject_exception", detail=str(e)[:200])
            report_failure(page, run_id, platform, "file_inject", "inject_exception", safe_page_url(page),
                           detail=str(e)[:200])
            return False
        log_step("file_inject", "ok", file=os.path.basename(video_path))
    else:
        iframe = page.get_frame('@src^https://www.tiktok.com/creator#/upload')
        target = iframe if iframe else page

    # === 等待上传就绪（通过 Post 按钮 enabled 状态判断）===
    if not should_skip("wait_upload", resume_from, STEPS):
        logger.info("⏳ 等待视频上传处理...")
        upload_ready = False
        for i in range(120):
            time.sleep(1)

            has_error, error_desc = _check_upload_error(page)
            if has_error:
                logger.error(f"❌ TikTok 上传错误: {error_desc}")
                _dismiss_error_popup(page)
                logger.info("   已关闭错误弹窗。此视频无法上传，请检查视频文件是否完整、格式是否正确。")
                log_step("wait_upload", "fail", error="file_rejected", detail=error_desc)
                report_failure(page, run_id, platform, "wait_upload", "file_rejected", safe_page_url(page), detail=error_desc)
                return False

            editor_ready, _ = check_signals(target, platform, "wait_upload", "editor_ready", timeout=1)
            if not editor_ready:
                if i % 5 == 4:
                    logger.info(f"   等待编辑器出现... ({i+1}秒)")
                continue

            post_btn, _ = find_element(page, platform, "post_button", timeout=1)
            if post_btn and post_btn.attr('aria-disabled') != 'true' and post_btn.attr('data-disabled') != 'true':
                upload_ready = True
                logger.info(f"   ✅ Post 按钮已就绪，视频处理完成 (耗时约 {i+1} 秒)")
                break

            if i % 10 == 9:
                logger.info(f"   视频处理中... ({i+1}秒)")

        if not upload_ready:
            has_error, error_desc = _check_upload_error(page)
            if has_error:
                logger.error(f"❌ TikTok 上传错误: {error_desc}")
                _dismiss_error_popup(page)
                log_step("wait_upload", "fail", error="file_rejected", detail=error_desc)
                report_failure(page, run_id, platform, "wait_upload", "file_rejected", safe_page_url(page), detail=error_desc)
                return False
            logger.warning("   ⚠️ 等待超时(120秒)，继续尝试...")
        log_step("wait_upload", "ok" if upload_ready else "warn_timeout")
        _handle_popups(page)
        dismiss_interfering_overlays(ctrl, work, baseline_tab_ids)

    # === 阶段 4：填写标题和描述 ===
    if not should_skip("form_fill", resume_from, STEPS):
        _handle_popups(page)
        dismiss_interfering_overlays(ctrl, work, baseline_tab_ids)
        logger.info("📝 正在填写标题和描述...")
        full_text = f"{title or ''}\n\n{description or ''}".strip()[:3900]

        caption_box, _ = find_element(target, platform, "caption_box", timeout=15)

        if caption_box:
            try:
                caption_box.clear()
                caption_box.input(full_text)
                logger.info("✅ 标题和描述已填写")
            except Exception as e:
                logger.warning(f"⚠️ 填写失败: {e}")
        else:
            logger.warning("⚠️ 未找到描述输入框，跳过。")
            log_step("form_fill", "fail", error="selector_not_found", detail="caption_box 未找到")
            report_failure(page, run_id, platform, "form_fill", "selector_not_found", safe_page_url(page),
                           selectors_tried="caption_box")
            return False
        log_step("form_fill", "ok")

    # === 阶段 4.5：上传自定义封面图 ===
    if not should_skip("cover", resume_from, STEPS):
        if cover_path:
            _upload_cover_image(page, target, cover_path)
        log_step("cover", "ok", has_cover=bool(cover_path))

    # === 阶段 5：滚动到底部 ===
    if not should_skip("scroll", resume_from, STEPS):
        logger.info("📜 滚动页面到底部...")
        try:
            target.scroll.to_bottom()
            time.sleep(1)
        except Exception as e:
            logger.warning(f"⚠️ 滚动失败: {e}")
        _handle_popups(page)
        dismiss_interfering_overlays(ctrl, work, baseline_tab_ids)
        log_step("scroll", "ok")

    # === 阶段 5.5：设置平台选项 ===
    if not should_skip("options", resume_from, STEPS):
        _handle_popups(page)
        dismiss_interfering_overlays(ctrl, work, baseline_tab_ids)
        logger.info("⚙️ 正在设置上传选项...")
        changed, recipe_diag = _set_tiktok_options(page, config)
        if changed:
            logger.info(f"  📋 已设置: {', '.join(changed)}")
        else:
            logger.info("  ℹ️ 所有选项保持默认值")

        requested_schedule = config.get("schedule")
        schedule_set = any(c.startswith("schedule=") for c in changed)
        if requested_schedule and not schedule_set:
            logger.error(f"  ❌ 定时发布设置失败（目标: {requested_schedule}），为防止视频被立即发布，已中止。")
            log_step("options", "fail", error="recipe_step_failed",
                     detail=f"定时发布 {requested_schedule} 设置失败，中止发布以防立即公开")
            schedule_diag = recipe_diag.get("schedule") or {}
            report_failure(page, run_id, platform, "options", "recipe_step_failed", safe_page_url(page),
                           detail=f"定时发布 {requested_schedule} 设置失败",
                           recipe_key=schedule_diag.get("recipe_key", "schedule_recipe"),
                           failed_step=schedule_diag.get("failed_step", ""),
                           semantic_hint=schedule_diag.get("semantic_hint", ""),
                           selectors_tried="schedule_recipe")
            return False

        requested_visibility = config.get("visibility", "everyone")
        visibility_set = any(c.startswith("visibility=") for c in changed)
        if requested_visibility != "everyone" and not visibility_set:
            logger.error(f"  ❌ 可见性设置失败（目标: {requested_visibility}），为防止视频公开发布，已中止。")
            log_step("options", "fail", error="visibility_failed",
                     detail=f"可见性 {requested_visibility} 设置失败，中止发布以防公开")
            visibility_diag = recipe_diag.get("visibility") or {}
            report_failure(page, run_id, platform, "options", "visibility_failed", safe_page_url(page),
                           detail=f"可见性 {requested_visibility} 设置失败",
                           recipe_key=visibility_diag.get("recipe_key", "visibility_recipe"),
                           failed_step=visibility_diag.get("failed_step", ""),
                           semantic_hint=visibility_diag.get("semantic_hint", ""),
                           selectors_tried="visibility_recipe")
            return False

        log_step("options", "ok", changed=changed)
        time.sleep(0.5)

    # === 阶段 6：等待版权检查完成 ===
    if not should_skip("copyright", resume_from, STEPS):
        _handle_popups(page)
        logger.info("🔍 等待版权检查完成...")
        required_checks = 1  # 默认只需 1 项通过，动态检测实际数量
        time.sleep(1)
        toggle_on_sels = get_signal_list(platform, "copyright", "toggle_selector")
        toggle_off_sels = get_signal_list(platform, "copyright", "toggle_off_selector")
        try:
            enabled_count = 0
            for sel in toggle_on_sels:
                toggles_on = page.eles(sel, timeout=3)
                enabled_count += len(toggles_on) if toggles_on else 0
            if enabled_count > 0:
                required_checks = enabled_count
                logger.info(f"   检测到 {required_checks} 个检查项已开启")
            else:
                off_count = 0
                for sel in toggle_off_sels:
                    toggles_off = page.eles(sel, timeout=1)
                    off_count += len(toggles_off) if toggles_off else 0
                if off_count > 0:
                    required_checks = max(1, 2 - off_count)
                    logger.info(f"   检测到 {off_count} 个检查项已关闭，需等待 {required_checks} 项通过")
                else:
                    logger.info(f"   未检测到开关状态，默认等待 {required_checks} 项通过")
        except Exception:
            logger.info(f"   开关检测异常，默认等待 {required_checks} 项通过")

        passed_sels = get_signal_list(platform, "copyright", "passed_signals")
        check_passed = False
        for i in range(15):
            total_passed = 0
            for sel in passed_sels:
                items = page.eles(sel, timeout=0.5)
                total_passed += len(items) if items else 0
            if total_passed >= required_checks:
                logger.info(f"   ✅ 版权检查全部通过 ({total_passed}/{required_checks} 项，耗时约 {i*2} 秒)")
                check_passed = True
                break
            if i % 5 == 4:
                logger.info(f"   检查进行中... 已通过 {total_passed}/{required_checks} 项 ({i*2}秒)")
            time.sleep(2)

        if not check_passed:
            logger.warning("   ⚠️ 版权检查等待超时(30秒)，尝试继续发布...")
        log_step("copyright", "ok" if check_passed else "fail",
                 error="" if check_passed else "timeout",
                 detail="" if check_passed else "版权检查等待超时")

    # === 阶段 6.5：发布前内容限制扫描 ===
    _has_content_warning = False
    _content_check_warnings = [
        'text:Content may be restricted',
        'text:内容可能会受到限制',
        'text:content check',
    ]
    for _cw_sel in _content_check_warnings:
        _cw_el = page.ele(_cw_sel, timeout=1)
        if _cw_el and _cw_el.states.has_rect:
            _has_content_warning = True
            _cw_text = (_cw_el.text or "").strip()[:150]
            logger.warning(f"  ⚠️ 发布前检测到内容限制警告: {_cw_text}")
            logger.warning("  ⚠️ TikTok 提示该视频内容可能受限，可见度可能降低，但仍可发布")
            log_step("content_check", "ok", detail=f"content_warning: {_cw_text[:80]}")
            break

    # === 阶段 7：点击发布 ===
    if no_publish:
        logger.info("⏸️ --no-publish 模式：表单已填好，跳过发布步骤。请在浏览器中手动检查并发布。")
        log_step("complete", "ok", mode="no_publish")
        return True

    if not should_skip("publish", resume_from, STEPS):
        dismiss_interfering_overlays(ctrl, work, baseline_tab_ids)

        # 发布前重新检查上传是否出错（视频处理可能异步失败）
        has_error, error_desc = _check_upload_error(page)
        if has_error:
            logger.warning(f"  ⚠️ 发布前检测到上传错误: {error_desc}，尝试点击 Retry...")
            retry_btn = page.ele('text:Retry', timeout=2) or page.ele('text:重试', timeout=1)
            if retry_btn:
                try:
                    retry_btn.click()
                    logger.info("  🔄 已点击 Retry，等待重新上传...")
                    time.sleep(3)
                    for _rw in range(60):
                        time.sleep(2)
                        still_error, _ = _check_upload_error(page)
                        if still_error:
                            if _rw % 10 == 9:
                                logger.info(f"   重新上传中... ({_rw*2}秒)")
                            continue
                        post_btn_check, _ = find_element(page, platform, "post_button", timeout=1)
                        if post_btn_check and post_btn_check.attr('aria-disabled') != 'true':
                            logger.info(f"  ✅ 重新上传成功 (耗时约 {_rw*2} 秒)")
                            break
                    else:
                        logger.error("  ❌ 重新上传超时(120秒)，中止发布。")
                        log_step("publish", "fail", error="file_rejected", detail=f"重试后仍失败: {error_desc}")
                        report_failure(page, run_id, platform, "publish", "file_rejected", safe_page_url(page), detail=error_desc)
                        return False
                except Exception as e:
                    logger.error(f"  ❌ 点击 Retry 失败: {e}")
                    log_step("publish", "fail", error="file_rejected", detail=error_desc)
                    report_failure(page, run_id, platform, "publish", "file_rejected", safe_page_url(page), detail=error_desc)
                    return False
            else:
                logger.error(f"  ❌ 上传错误且无 Retry 按钮: {error_desc}")
                log_step("publish", "fail", error="file_rejected", detail=error_desc)
                report_failure(page, run_id, platform, "publish", "file_rejected", safe_page_url(page), detail=error_desc)
                return False

        logger.info("🚀 正在查找【发布】按钮...")
        post_btn, _ = find_element(page, platform, "post_button", timeout=10)

        if not post_btn:
            logger.warning("⚠️ 未找到发布按钮，请手动检查浏览器。")
            log_step("publish", "fail", error="selector_not_found", detail="post_button 未找到")
            report_failure(page, run_id, platform, "publish", "selector_not_found", safe_page_url(page),
                           selectors_tried="post_button")
            return False

        for i in range(15):
            if post_btn.attr('aria-disabled') == 'true' or post_btn.attr('data-disabled') == 'true':
                logger.info(f"   按钮未就绪，等待... ({i+1}/15)")
                time.sleep(2)
            else:
                break

        if post_btn.attr('aria-disabled') == 'true' or post_btn.attr('data-disabled') == 'true':
            has_error_final, error_desc_final = _check_upload_error(page)
            if has_error_final:
                logger.error(f"❌ 发布按钮持续禁用，检测到错误: {error_desc_final}")
                log_step("publish", "fail", error="file_rejected", detail=error_desc_final)
                report_failure(page, run_id, platform, "publish", "file_rejected", safe_page_url(page), detail=error_desc_final)
                return False
            logger.warning("⚠️ 发布按钮仍为禁用状态(30秒)，强制尝试点击...")

        # region agent log — TL1: publish click 之前 (T-A: 强制点击是否合法)
        _dbg_log_tk(
            "tiktok.py:publish:before_click",
            "publish click 之前页面状态（post 按钮 disabled / 顶层 modal）",
            {"run_id": run_id, **_dbg_tk_probe(page)},
            "T-A+T-B",
        )
        # endregion

        try:
            post_btn.click()
            logger.info("✅ 已点击发布按钮")
            # 立即开始监听「Continue to post?」审核弹窗（与点击紧贴，不能中间插 sleep）
            # 弹窗通常在点击后 0-3 秒内出现，错过窗口期就会被后续流程当成"已发布"误判
            ctp_handled = _handle_continue_to_post_dialog(page)
        except Exception as e:
            logger.warning(f"⚠️ 点击发布按钮失败: {e}")
            log_step("publish", "fail", error="unknown", detail=str(e)[:200])
            report_failure(page, run_id, platform, "publish", "unknown", safe_page_url(page), detail=str(e)[:200])
            return False
        log_step("publish", "ok")
        if ctp_handled:
            logger.info("  ℹ️ Continue-to-post 弹窗已处理，等待平台跳转/发布完成")

    # === 阶段 8：处理可能的二次确认弹窗 ===
    from social_uploader.tools.post_publish import handle_post_publish_popups, wait_for_publish_confirmation
    from social_uploader.tools.retry_engine import retry_step, StepResult

    popup_result = handle_post_publish_popups(page, platform, content_warning=_has_content_warning)
    if popup_result.get("action") == "abort":
        logger.error(f"❌ 发布被阻止: {popup_result.get('description', '')}")
        log_step("publish_confirm", "fail", error="platform_unavailable",
                 detail=popup_result.get("description", "")[:200])
        report_failure(page, run_id, platform, "publish_confirm", "platform_unavailable",
                       page.url, detail=popup_result.get("description", "")[:200])
        return False

    # === 阶段 9：等待发布成功确认（带智能重试） ===
    if not should_skip("confirm", resume_from, STEPS):

        def _idempotent_check():
            """幂等检查：视频是否已经在作品列表中。
            仅 URL 不足以判定成功（可能是脚本自己导航过去的），
            必须同时检测到 success_signals 或视频标题。
            """
            try:
                cur = page.url.lower()
            except Exception:
                return False
            matched, _ = check_signals(page, platform, "confirm", "success_signals", timeout=0.5)
            if matched:
                return True
            url_or = get_patterns(platform, "confirm").get("success_url_pattern", {}).get("or_contains", [])
            on_content_page = url_or and any(kw in cur for kw in url_or)
            if on_content_page and title:
                short_title = title[:20]
                title_el = page.ele(f'text:{short_title}', timeout=2)
                if title_el:
                    return True
            return False

        def _do_confirm():
            try:
                ok, reason = wait_for_publish_confirmation(
                    page, platform, timeout_s=30,
                    error_check_fn=_check_upload_error,
                )
                if ok:
                    return StepResult(True, value=reason)

                try:
                    cur = page.url.lower()
                except Exception:
                    logger.warning("  ⚠️ 页面连接断开，无法确认发布状态，请手动检查")
                    return StepResult(False, error="page_disconnected_unverified")

                if "upload" in cur:
                    logger.info("  页面仍在上传页，主动检查内容管理页...")
                    page.get("https://www.tiktok.com/tiktokstudio/content")
                    page.wait.doc_loaded(timeout=10)
                    time.sleep(2)
                    # region agent log — TL3: 跳到内容页后探针 (T-C, T-D, T-E)
                    _dbg_log_tk(
                        "tiktok.py:confirm:on_content_page",
                        "跳转到 tiktokstudio/content 后页面状态（视频卡片 / success_signals）",
                        {"run_id": run_id, "title_short_for_search": (title[:20] if title else None), **_dbg_tk_probe(page)},
                        "T-C+T-D+T-E",
                    )
                    # endregion
                    matched, sel = check_signals(page, platform, "confirm", "success_signals", timeout=1)
                    if matched:
                        logger.info(f"  ✅ 内容页检测到成功信号: {sel}")
                        return StepResult(True, value=f"manual_nav_signal: {sel}")
                    if title:
                        short_title = title[:20]
                        title_el = page.ele(f'text:{short_title}', timeout=3)
                        if title_el:
                            logger.info(f"  ✅ 内容页找到视频标题「{short_title}」，视为发布成功")
                            return StepResult(True, value="manual_nav_title_verified")
                    logger.warning("  ⚠️ 内容页未找到发布成功证据，判定为失败")
                    # region agent log — TL4: 判定失败前最终探针 (T-C, T-D)
                    _dbg_log_tk(
                        "tiktok.py:confirm:before_fail",
                        "内容页未找到证据，判定失败前最终页面状态",
                        {"run_id": run_id, **_dbg_tk_probe(page)},
                        "T-C+T-D",
                    )
                    # endregion
                    try:
                        page.get("https://www.tiktok.com/tiktokstudio/upload?from=upload")
                        page.wait.doc_loaded(timeout=5)
                    except Exception:
                        pass

                return StepResult(False, error=reason)
            except Exception as e:
                err_name = type(e).__name__
                if "Disconnected" in err_name or "disconnected" in str(e).lower():
                    logger.warning("  ⚠️ 页面连接断开，无法确认发布状态，请手动检查")
                    return StepResult(False, error="page_disconnected_unverified")
                raise

        confirm_result = retry_step(
            page, platform, "confirm",
            step_fn=_do_confirm,
            max_retries=2,
            is_irreversible=True,
            pre_retry_check=_idempotent_check,
        )

        if confirm_result.success:
            reason = confirm_result.value or "retry_success"
            logger.info(f"🎉 TikTok 上传流程结束。({reason})")
            log_step("confirm", "ok", detail=str(reason)[:200])
            return True
        else:
            reason = confirm_result.error or "unknown"
            logger.warning(f"  ⚠️ 发布确认失败: {reason}")
            logger.info("❌ TikTok 上传流程结束（未确认成功）。")
            log_step("confirm", "fail", error="state_mismatch", detail=str(reason)[:200])
            try:
                current_url = page.url
            except Exception:
                current_url = "page_disconnected"
            report_failure(page, run_id, platform, "confirm", "state_mismatch",
                           current_url, detail=str(reason)[:200])
            return False

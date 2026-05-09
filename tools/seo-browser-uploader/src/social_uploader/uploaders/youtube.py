import time
import os
import logging

from social_uploader.uploaders import should_skip
from social_uploader.uploaders.video_check import validate_video_file, log_login_error, quick_login_check
from social_uploader.uploaders.youtube_helpers import (
    ensure_upload_dialog_open,
    find_file_input_deep,
    _writeback_from_fallback,
    _set_youtube_schedule,
)
from social_uploader.tools.browser_manager import connect_browser, dismiss_interfering_overlays, find_platform_tab, check_page_error, inject_popup_guard, cleanup_tabs
from social_uploader.tools.element_finder import find_element, preflight_check
from social_uploader.repair_engine import log_step, report_failure, generate_run_id, write_success, safe_page_url
from social_uploader.tools.upload_profile import load_profile, get_platform_config, validate_platform_config
from social_uploader.tools.pattern_checker import check_signals, get_signal_list, get_patterns, dismiss_popups

logger = logging.getLogger(__name__)

"""
代码地图（AI 修改时先看这里定位代码位置）：

步骤名          | 做什么                     | 代码位置
----------------|----------------------------|---------------------------
validate        | 校验视频文件               | upload_youtube() 开头
connect         | 连接浏览器                 | upload_youtube() 中段
login           | 打开 Studio + 检测登录     | _do_upload_youtube() → 步骤 1
cleanup         | 关闭残留弹窗               | _do_upload_youtube() → 步骤 2
upload_dialog   | 唤出上传弹窗               | _do_upload_youtube() → 步骤 3
file_inject     | 注入视频文件               | _do_upload_youtube() → 步骤 4
form_fill       | 填写标题和描述             | _do_upload_youtube() → 步骤 5
kids            | 设置不面向儿童             | _do_upload_youtube() → 步骤 6
next_steps      | 循环点击下一步             | _do_upload_youtube() → 步骤 7
visibility      | 设置为公开                 | _do_upload_youtube() → 步骤 8
publish         | 点击发布按钮               | _do_upload_youtube() → 步骤 9
confirm         | 等待发布成功确认           | _do_upload_youtube() → 步骤 10

辅助函数：
  should_skip() — resume-from 跳步判断（来自 uploaders.__init__）

YouTube 平台专属辅助（位于 uploaders/youtube_helpers.py，禁止其他平台 import）：
  find_file_input_deep()      — 穿透 Shadow DOM 查找 file input（YouTube Studio 必需）
  _set_youtube_schedule()     — 定时发布（格式: YYYY-MM-DD HH:MM）+ CDP 时间字段聚焦
  _writeback_from_fallback()  — 索引模式找到的元素回写 button_config.json

已实现的 profile 配置项（profile.youtube.*）：
  made_for_kids  — 是否面向儿童（默认 false）
  visibility     — 可见性：public / unlisted / private（默认 public）
  tags           — 标签，逗号分隔字符串（默认 null）
  category       — 分类名（默认 null）
  schedule       — 定时发布时间：'YYYY-MM-DD HH:MM'（默认 null = 立即发布）
"""

YOUTUBE_UPLOAD_URL_PREFIX = "https://studio.youtube.com"
STEPS = [
    "validate", "connect", "login", "page_check", "cleanup", "upload_dialog",
    "file_inject", "form_fill", "kids", "next_steps", "visibility",
    "publish", "confirm",
]


def upload_youtube(video_path, title, description, no_publish=False, run_id=None, resume_from=None, profile=None, account=None):
    if run_id is None:
        run_id = generate_run_id()
    if profile is None:
        profile = load_profile()
    config = get_platform_config(profile, "youtube")
    config, constraint_warnings = validate_platform_config("youtube", config)
    for w in constraint_warnings:
        logger.warning(f"  ⚠️ {w}")

    ok, err_msg = validate_video_file(video_path, platform="youtube")
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
            platform_tab = find_platform_tab(ctrl, YOUTUBE_UPLOAD_URL_PREFIX)
            if platform_tab:
                work = platform_tab
                logger.info(f"🔄 找到 YouTube Studio 页面标签，将从 {resume_from} 步骤恢复")
            else:
                logger.warning("⚠️ 未找到 YouTube Studio 页面标签，将从头执行")
                work = ctrl.new_tab(url="about:blank")
                work.set.auto_handle_alert(accept=True)
                resume_from = None
        else:
            ctrl, work, baseline_tab_ids, _ = connect_browser(data_dir=data_dir)
        log_step("connect", "ok", port=9222)
    except Exception as e:
        logger.error(f"❌ 连接浏览器失败，请确保运行了 start_chrome_debug.sh。错误详情: {e}")
        log_step("connect", "fail", error="unknown", detail=str(e)[:200])
        return False

    success = False
    _t0 = time.time()
    try:
        success = _do_upload_youtube(work, ctrl, baseline_tab_ids, video_path, title, description, no_publish, run_id, resume_from, config)
        return success
    finally:
        if success:
            write_success(run_id, "youtube", elapsed_s=round(time.time() - _t0))
            cleanup_tabs(ctrl, baseline_tab_ids)
        else:
            logger.info("💡 任务窗口已保留，可用 --resume-from 从断点恢复")


def _do_upload_youtube(work, ctrl, baseline_tab_ids, video_path, title, description, no_publish, run_id, resume_from, config):
    platform = "youtube"
    page = work

    # resume-from 页面状态校验
    if resume_from:
        current_url = page.url or ""
        if YOUTUBE_UPLOAD_URL_PREFIX not in current_url:
            logger.warning(f"⚠️ 页面已离开 YouTube Studio ({current_url[:60]}...)，忽略 resume-from，从头执行")
            log_step("resume_check", "fail", reason="page_url_changed", url=current_url[:100])
            resume_from = None
        else:
            log_step("resume_check", "ok", resume_from=resume_from)

    # 1. 登录状态检测
    if not should_skip("login", resume_from, STEPS):
        logger.info("🌐 正在检查 YouTube 登录状态...")
        page.get('https://studio.youtube.com/')
        page.wait.doc_loaded(timeout=10)
        inject_popup_guard(page)

        logged_in, detail = quick_login_check(page, platform)
        if not logged_in:
            log_login_error('YouTube')
            log_step("login", "fail", error="login_required", page_url=page.url)
            report_failure(page, run_id, platform, "login", "login_required", safe_page_url(page))
            return False

        if 'accounts.google.com' in page.url or 'signin' in page.url.lower():
            log_login_error('YouTube')
            log_step("login", "fail", error="login_required", page_url=page.url)
            report_failure(page, run_id, platform, "login", "login_required", safe_page_url(page))
            return False
        log_step("login", "ok")

    # 页面状态检测
    if not should_skip("page_check", resume_from, STEPS):
        has_page_error, page_error_desc = check_page_error(page, platform)
        if has_page_error:
            logger.error(f"❌ YouTube 平台异常: {page_error_desc}")
            log_step("page_check", "fail", error="platform_unavailable", detail=page_error_desc)
            report_failure(page, run_id, platform, "page_check", "platform_unavailable", safe_page_url(page),
                           detail=page_error_desc)
            return False
        log_step("page_check", "ok")

        preflight_check(page, platform)

    # 2. 关闭残留弹窗
    if not should_skip("cleanup", resume_from, STEPS):
        logger.info("🧹 正在扫描并清理可能存在的弹窗...")
        dismiss_popups(page, platform, max_rounds=1)
        cleanup_patterns = get_patterns(platform, "cleanup")
        dialog_js = cleanup_patterns.get("dialog_js", "")
        if dialog_js:
            try:
                page.run_js(dialog_js)
                time.sleep(1)
            except Exception as e:
                logger.debug(f"  清理弹窗 JS 执行失败: {e}")
        log_step("cleanup", "ok")

    # 3. 唤出上传弹窗
    # 实测最稳路径：URL 直跳 `studio.youtube.com/channel/<id>/videos/upload?d=ud`
    # 比点 #upload-icon 更可靠（图标点击有时静默无效，对话框不弹）
    if not should_skip("upload_dialog", resume_from, STEPS):
        dismiss_interfering_overlays(ctrl, work, baseline_tab_ids)
        logger.info("📤 正在唤出上传弹窗...")

        dialog_open = ensure_upload_dialog_open(page, timeout=15)

        # 兜底：URL 直跳失败时退回原 #upload-icon 路径
        if not dialog_open:
            logger.info("  ↩️ URL 直跳未弹出对话框，降级到 #upload-icon 点击...")
            try:
                upload_icon, _ = find_element(page, platform, "upload_icon", timeout=3)
                if upload_icon:
                    upload_icon.click()
                    time.sleep(2)
                    dialog_open = ensure_upload_dialog_open(page, timeout=5)
                else:
                    create_btn, _ = find_element(page, platform, "create_button", timeout=2)
                    if create_btn:
                        create_btn.click()
                        time.sleep(1)
                        upload_menu_item, _ = find_element(page, platform, "upload_menu_item", timeout=2)
                        if upload_menu_item:
                            upload_menu_item.click()
                            time.sleep(2)
                            dialog_open = ensure_upload_dialog_open(page, timeout=5)
            except Exception as e:
                logger.warning(f"  ⚠️ 降级路径异常: {e}")

        if not dialog_open:
            logger.error("❌ 上传对话框打开失败（URL 直跳 + #upload-icon + #create-icon 均失败）")
            log_step("upload_dialog", "fail", error="dialog_not_open",
                     detail="ytcp-uploads-dialog 在 15s 内未出现")
            report_failure(page, run_id, platform, "upload_dialog", "dialog_not_open", safe_page_url(page),
                           selectors_tried="ensure_upload_dialog_open + upload_icon + create_button")
            return False

        log_step("upload_dialog", "ok")

    # 4. 等待并上传文件
    if not should_skip("file_inject", resume_from, STEPS):
        logger.info("⏳ 等待上传组件加载...")
        # 三层兜底（轨道A → Tier2 启发式 → 轨道B AI）
        file_input, _ = find_element(page, platform, "file_input", timeout=15)
        # 第 4 层兜底：YouTube Studio 把 file input 包在 web component 的 shadowRoot 内,
        # 标准 querySelector / page.ele 无法穿透 closed shadow root,
        # 用 JS 递归遍历所有 shadowRoot 兜底。
        if not file_input:
            logger.info("  🌑 三层选择器未命中，尝试 Shadow DOM 深度查找...")
            file_input = find_file_input_deep(page, timeout=15)
            if file_input:
                logger.info("  ✅ Shadow DOM 深度查找命中 file input")
        if not file_input:
            logger.error("❌ 30秒内未找到上传按钮，可能是网络太慢或页面结构突变。")
            log_step("file_inject", "fail", error="selector_not_found",
                     detail="file input 未找到（三层选择器 + Shadow DOM 深度查找均失败）")
            report_failure(page, run_id, platform, "file_inject", "selector_not_found", safe_page_url(page),
                           selectors_tried="file_input + shadow_dom_deep")
            return False

        logger.info(f"📁 正在静默注入视频文件: {video_path}")
        try:
            file_input.input(video_path)
        except Exception as e:
            logger.error(f"  ❌ 文件注入失败: {e}")
            log_step("file_inject", "fail", error="inject_exception", detail=str(e)[:200])
            report_failure(page, run_id, platform, "file_inject", "inject_exception", safe_page_url(page),
                           detail=str(e)[:200])
            return False
        log_step("file_inject", "ok", file=os.path.basename(video_path))

    # 5. 填写表单
    if not should_skip("form_fill", resume_from, STEPS):
        dismiss_interfering_overlays(ctrl, work, baseline_tab_ids)
        logger.info("📝 正在填写视频信息...")
        safe_title = (title or "")[:95]
        safe_desc = (description or "")[:4900]

        title_box = None
        desc_box = None

        title_box, _ = find_element(page, platform, "title_box", timeout=5)
        desc_box, _ = find_element(page, platform, "desc_box", timeout=5)

        if not title_box or not desc_box:
            logger.info("  按语义选择器未全部找到，降级为索引模式...")
            fallback_sels = get_signal_list(platform, "form_fill", "textbox_fallback")
            fallback_sel = fallback_sels[0] if fallback_sels else '#textbox'
            textboxes = page.eles(fallback_sel, timeout=20)
            if len(textboxes) >= 2:
                if not title_box:
                    title_box = textboxes[0]
                    _writeback_from_fallback(title_box, platform, "title_box")
                if not desc_box:
                    desc_box = textboxes[1]
                    _writeback_from_fallback(desc_box, platform, "desc_box")

        if title_box:
            title_box.clear()
            title_box.input(safe_title)
            logger.info("  ✅ 标题已填写")
        else:
            logger.warning("  ⚠️ 未找到标题输入框，跳过")

        if desc_box:
            desc_box.clear()
            desc_box.input(safe_desc)
            logger.info("  ✅ 描述已填写")
        else:
            logger.warning("  ⚠️ 未找到描述输入框，跳过")

        tags = config.get("tags")
        if tags:
            logger.info("🏷️ 正在填写标签...")
            show_more = page.ele('text:Show more', timeout=2) or page.ele('text:展开', timeout=1)
            if show_more:
                try:
                    show_more.click()
                    time.sleep(1)
                except Exception:
                    pass
            tags_input = page.ele('xpath://input[contains(@aria-label,"Tag") or contains(@placeholder,"Tag")]', timeout=3)
            if not tags_input:
                tags_input = page.ele('xpath://input[contains(@aria-label,"标签") or contains(@placeholder,"标签")]', timeout=2)
            if tags_input:
                tag_list = [t.strip() for t in tags.split(',') if t.strip()]
                tags_text = ','.join(tag_list)
                tags_input.clear()
                tags_input.input(tags_text)
                time.sleep(0.3)
                logger.info(f"  ✅ 已填写 {len(tag_list)} 个标签")
            else:
                logger.warning("  ⚠️ 未找到标签输入框")

        category = config.get("category")
        if category:
            safe_cat = category.replace("'", "\\'")
            logger.info(f"🗂️ 正在设置分类: {category}...")
            cat_info = page.run_js(f"""
                var safe = '{safe_cat}';
                var selects = document.querySelectorAll('select, [role="listbox"]');
                for (var sel of selects) {{
                    var row = sel;
                    for (var i=0;i<5;i++) {{ row=row.parentElement; if(!row)break; }}
                    if (row && (row.textContent.includes('Category') || row.textContent.includes('分类'))) {{
                        if (sel.tagName === 'SELECT') {{
                            for (var idx=0; idx < sel.options.length; idx++) {{
                                if (sel.options[idx].textContent.includes(safe)) {{
                                    var rect = sel.getBoundingClientRect();
                                    return {{type: 'select', x: rect.x + rect.width/2, y: rect.y + rect.height/2, delta: idx - sel.selectedIndex}};
                                }}
                            }}
                        }} else {{
                            sel.click();
                            return {{type: 'opened'}};
                        }}
                    }}
                }}
                return null;
            """)
            cat_result = 'not_found'
            if cat_info:
                if cat_info.get('type') == 'select':
                    delta = cat_info.get('delta', 0)
                    if delta == 0:
                        cat_result = 'ok_select'
                    else:
                        cdp_click_at(page, cat_info['x'], cat_info['y'])
                        time.sleep(0.3)
                        arrow = 'ArrowDown' if delta > 0 else 'ArrowUp'
                        for _ in range(abs(delta)):
                            cdp_press_key(page, arrow, arrow)
                            time.sleep(0.05)
                        cdp_press_key(page, 'Enter', 'Enter', 13)
                        cat_result = 'ok_select'
                elif cat_info.get('type') == 'opened':
                    cat_result = 'opened'
            if cat_result == 'ok_select':
                logger.info(f"  ✅ 分类: {category}")
            elif cat_result == 'opened':
                time.sleep(0.5)
                opt = page.ele(f'text:{category}', timeout=3)
                if opt:
                    try:
                        opt.click()
                        logger.info(f"  ✅ 分类: {category} (自定义下拉)")
                    except Exception:
                        logger.warning(f"  ⚠️ 点击分类选项失败")
                else:
                    logger.warning(f"  ⚠️ 未找到分类选项: {category}")
            else:
                logger.warning(f"  ⚠️ 设置分类失败: {cat_result}")

        log_step("form_fill", "ok", title_filled=bool(title_box), desc_filled=bool(desc_box),
                 tags=bool(tags), category=bool(category))

    # 6. 设置面向儿童选项（根据 config.made_for_kids）
    if not should_skip("kids", resume_from, STEPS):
        dismiss_interfering_overlays(ctrl, work, baseline_tab_ids)
        made_for_kids = config.get("made_for_kids", False)
        kids_label = "面向儿童" if made_for_kids else "不面向儿童"
        logger.info(f"👶 正在设置观众限制（{kids_label}）...")

        try:
            page.run_js("""
                var sc = document.querySelector('#scrollable-content');
                if (sc) sc.scrollTop = sc.scrollHeight;
            """)
            time.sleep(1.5)
        except Exception:
            pass

        kids_radio_name = "VIDEO_MADE_FOR_KIDS_MFK" if made_for_kids else "VIDEO_MADE_FOR_KIDS_NOT_MFK"

        def verify_kids_selected():
            try:
                result = page.run_js(f"""
                    var radio = document.querySelector('tp-yt-paper-radio-button[name="{kids_radio_name}"]');
                    if (!radio) return 'not_found';
                    if (radio.getAttribute('aria-checked') === 'true' || radio.hasAttribute('checked') || radio.checked) return 'checked';
                    var inner = radio.querySelector('#radioContainer iron-icon, #radioContainer .checked');
                    if (inner) return 'checked';
                    return 'unchecked';
                """)
                return str(result) == 'checked'
            except Exception:
                return False

        kids_clicked = False
        MAX_KIDS_ATTEMPTS = 3

        for attempt in range(MAX_KIDS_ATTEMPTS):
            if attempt > 0:
                logger.info(f"  🔄 第 {attempt+1} 次尝试选择「不面向儿童」...")
                time.sleep(1)
                try:
                    page.run_js("""
                        var sc = document.querySelector('#scrollable-content');
                        if (sc) sc.scrollTop = sc.scrollHeight;
                    """)
                    time.sleep(1)
                except Exception:
                    pass

            try:
                rect = page.run_js(f"""
                    var radio = document.querySelector('tp-yt-paper-radio-button[name="{kids_radio_name}"]');
                    if (!radio) return null;
                    radio.scrollIntoView({{block: 'center'}});
                    var r = radio.getBoundingClientRect();
                    return {{x: r.x + r.width/2, y: r.y + r.height/2}};
                """)
                if rect:
                    cdp_click_at(page, rect['x'], rect['y'])
                    time.sleep(0.5)
                    if verify_kids_selected():
                        kids_clicked = True
                        logger.info(f"  ✅ 已选择（CDP 点击，第 {attempt+1} 次）")
                        break
                    else:
                        logger.info("  ⚠️ CDP 点击已执行，但验证未通过")
            except Exception:
                pass

            if not kids_clicked:
                kids_radio = page.ele(f'@name={kids_radio_name}', timeout=3)
                if kids_radio:
                    try:
                        kids_radio.click(by_js=False)
                        time.sleep(0.5)
                        if verify_kids_selected():
                            kids_clicked = True
                            logger.info(f"  ✅ 已选择（原生坐标点击，第 {attempt+1} 次）")
                            break
                    except Exception:
                        pass

            if not kids_clicked:
                labels = page.eles('#radioLabel', timeout=2)
                for label in labels:
                    text = (label.text or '').strip()
                    text_lower = text.lower()
                    is_match = False
                    if made_for_kids:
                        if ('面向儿童' in text or 'made for kids' in text_lower) and '不' not in text and 'not' not in text_lower:
                            is_match = True
                    else:
                        if '不' in text or 'not' in text_lower:
                            is_match = True
                    if not is_match:
                        continue
                    try:
                        label.click(by_js=False)
                        time.sleep(0.5)
                        if verify_kids_selected():
                            kids_clicked = True
                            logger.info(f"  ✅ 已选择（radioLabel 点击: {text[:20]}，第 {attempt+1} 次）")
                            break
                    except Exception:
                        pass
                if kids_clicked:
                    break

            if not kids_clicked:
                try:
                    result = page.run_js(f"""
                        var radio = document.querySelector('tp-yt-paper-radio-button[name="{kids_radio_name}"]');
                        if (!radio) return 'not_found';
                        var container = radio.querySelector('#radioContainer') || radio.querySelector('.radioContainer');
                        if (container) {{
                            container.scrollIntoView({{block: 'center'}});
                            container.click();
                            return 'ok_container';
                        }}
                        var inp = radio.querySelector('input[type="radio"]');
                        if (inp) {{ inp.click(); return 'ok_input'; }}
                        return 'no_inner';
                    """)
                    if result and str(result).startswith('ok'):
                        time.sleep(0.5)
                        if verify_kids_selected():
                            kids_clicked = True
                            logger.info(f"  ✅ 已选择（内部容器点击: {result}，第 {attempt+1} 次）")
                            break
                except Exception:
                    pass

            if not kids_clicked:
                signal_key = "made_for_kids_text" if made_for_kids else "not_made_for_kids_text"
                kids_text_selectors = get_signal_list(platform, "kids", signal_key)
                if not kids_text_selectors:
                    if made_for_kids:
                        kids_text_selectors = [
                            'text:是，内容面向儿童', "text:Yes, it's Made for Kids",
                        ]
                    else:
                        kids_text_selectors = [
                            'text:不，内容不是面向儿童的', "text:No, it's not Made for Kids",
                        ]
                for sel in kids_text_selectors:
                    el = page.ele(sel, timeout=1)
                    if el:
                        try:
                            el.click(by_js=False)
                            time.sleep(0.5)
                            if verify_kids_selected():
                                kids_clicked = True
                                logger.info(f"  ✅ 已选择（文本选择器，第 {attempt+1} 次）")
                                break
                        except Exception:
                            pass
                if kids_clicked:
                    break

        if kids_clicked:
            logger.info(f"  ✅ 观众限制设置完成：{kids_label}（已验证选中状态）")
        else:
            logger.error(f"  ❌ 无法自动选择「{kids_label}」，中止发布以防合规问题")
            log_step("kids", "fail", error="kids_setting_failed",
                     detail="多策略尝试均未通过验证")
            report_failure(page, run_id, platform, "kids", "kids_setting_failed", safe_page_url(page),
                           detail="儿童选项设置失败")
            return False

        log_step("kids", "ok")
        time.sleep(1)

    # 7. 循环点击下一步
    if not should_skip("next_steps", resume_from, STEPS):
        logger.info("⏭️ 正在跳过中间步骤（视频元素 / 检查）...")
        step_names = ['视频元素', '检查', '可见性']
        for i in range(3):
            step_label = step_names[i] if i < len(step_names) else f'步骤{i+1}'

            next_btn_sels = get_signal_list(platform, "next_steps", "next_button")
            if not next_btn_sels:
                next_btn_sels = ['#next-button']
            next_btn = None
            for wait in range(15):
                for sel in next_btn_sels:
                    try:
                        candidate = page.ele(sel, timeout=1)
                        if candidate and candidate.states.has_rect:
                            aria_disabled = candidate.attr('aria-disabled')
                            if aria_disabled != 'true':
                                next_btn = candidate
                                break
                    except Exception:
                        continue
                if next_btn:
                    break
                try:
                    _ = page.url
                except Exception:
                    try:
                        ctrl, work, baseline_tab_ids, _ = connect_browser(new_window=False)
                        page = work
                        logger.info("  🔄 已重新连接浏览器")
                    except Exception:
                        pass
                time.sleep(1)

            if next_btn:
                try:
                    next_btn.click()
                    logger.info(f"  ✅ 已跳过【{step_label}】")
                except Exception:
                    try:
                        page.run_js(f'document.querySelector("{next_btn_sels[0]}").click()')
                        logger.info(f"  ✅ 已跳过【{step_label}】(JS)")
                    except Exception:
                        logger.warning(f"  ⚠️ 跳过【{step_label}】失败")
            else:
                logger.warning(f"  ⚠️ 未找到下一步按钮（{step_label}），尝试继续...")

            time.sleep(1)
        log_step("next_steps", "ok")

    # === no_publish 检查 ===
    if no_publish:
        logger.info("⏸️ --no-publish 模式：表单已填好，跳过发布步骤。请在浏览器中手动选择可见性并发布。")
        log_step("complete", "ok", mode="no_publish")
        return True

    # 8. 设置可见性（根据 config.visibility）
    if not should_skip("visibility", resume_from, STEPS):
        visibility = (config.get("visibility") or "public").upper()
        visibility_labels = {
            "PUBLIC": ("公开", "Public"),
            "UNLISTED": ("不公开列出", "Unlisted"),
            "PRIVATE": ("私享", "Private"),
        }
        vis_cn, vis_en = visibility_labels.get(visibility, ("公开", "Public"))
        logger.info(f"🌍 正在设置视频为【{vis_cn} ({vis_en})】...")
        visibility_clicked = False
        for attempt in range(3):
            try:
                info = page.run_js(f"""
                    var selectors = [
                        'tp-yt-paper-radio-button[name="{visibility}"]',
                        '[name="{visibility}"]'
                    ];
                    for (var s of selectors) {{
                        var r = document.querySelector(s);
                        if (r) {{
                            r.scrollIntoView({{block: 'center'}});
                            var rect = r.getBoundingClientRect();
                            return {{type: 'ok_event', x: rect.x + rect.width/2, y: rect.y + rect.height/2}};
                        }}
                    }}
                    var labels = document.querySelectorAll('#radioLabel');
                    for (var l of labels) {{
                        if (l.textContent.includes('{vis_cn}') || l.textContent.includes('{vis_en}')) {{
                            var btn = l.closest('tp-yt-paper-radio-button') || l.parentElement;
                            if (btn) {{
                                btn.scrollIntoView({{block: 'center'}});
                                var rect = btn.getBoundingClientRect();
                                return {{type: 'ok_label', x: rect.x + rect.width/2, y: rect.y + rect.height/2}};
                            }}
                        }}
                    }}
                    return null;
                """)
                if info:
                    cdp_click_at(page, info['x'], info['y'])
                    visibility_clicked = True
                    logger.info(f"  ✅ 已设置为{vis_cn}（CDP 点击: {info['type']}）")
                    break
            except Exception:
                pass

            vis_radio = page.ele(f'@name={visibility}', timeout=3)
            if vis_radio:
                try:
                    vis_radio.click(by_js=False)
                    visibility_clicked = True
                    logger.info(f"  ✅ 已设置为{vis_cn}（原生点击）")
                    break
                except Exception:
                    pass
            time.sleep(1)

        if not visibility_clicked:
            if visibility != "PUBLIC":
                logger.error(f"  ❌ 可见性设置失败（目标: {vis_cn}），为防止视频以错误可见性发布，已中止。")
                log_step("visibility", "fail", error="visibility_failed",
                         detail=f"可见性 {vis_cn} 设置失败，中止发布以防泄露")
                report_failure(page, run_id, platform, "visibility", "visibility_failed", safe_page_url(page),
                               detail=f"可见性 {vis_cn} 设置失败")
                return False
            else:
                logger.warning(f"  ⚠️ 无法确认{vis_cn}已选中，但公开为默认值，继续发布...")
        log_step("visibility", "ok" if visibility_clicked else "fail",
                 error="" if visibility_clicked else "unknown",
                 detail="" if visibility_clicked else f"{vis_cn}设置未成功")

        # 8.5 定时发布（仅在 visibility 步骤内，需要先设好 PUBLIC）
        schedule_str = config.get("schedule")
        if schedule_str:
            logger.info(f"📅 检测到定时发布配置: {schedule_str}")
            schedule_ok, schedule_diag = _set_youtube_schedule(page, schedule_str)
            if schedule_ok:
                logger.info(f"✅ YouTube 定时发布已设置: {schedule_str}")
                log_step("schedule", "ok", schedule=schedule_str)
            else:
                logger.error(f"❌ YouTube 定时发布设置失败: {schedule_str}")
                logger.error("🚨 安全门控：定时设置失败，中止发布防止视频立即公开")
                log_step("schedule", "fail", error="recipe_step_failed", detail=schedule_str)
                diag = schedule_diag or {}
                report_failure(page, run_id, platform, "schedule", "recipe_step_failed", safe_page_url(page),
                               detail=f"定时发布 {schedule_str} 设置失败",
                               recipe_key=diag.get("recipe_key", "schedule_recipe"),
                               failed_step=diag.get("failed_step", ""),
                               semantic_hint=diag.get("semantic_hint", ""),
                               selectors_tried="schedule_recipe")
                return False

    # 9. 点击发布按钮
    if not should_skip("publish", resume_from, STEPS):
        logger.info("⏳ 等待发布按钮就绪...")
        time.sleep(1.5)

        max_publish_attempts = 20
        clicked = False
        for attempt in range(max_publish_attempts):
            try:
                result = page.run_js("""
                    var btn = document.querySelector('#done-button');
                    if (!btn) return 'not_found';
                    if (btn.disabled || btn.getAttribute('aria-disabled') === 'true'
                        || btn.classList.contains('disabled') || btn.hasAttribute('disabled'))
                        return 'disabled';
                    btn.click();
                    return 'ok';
                """)
                if result == 'ok':
                    logger.info("✅ 视频发布指令已发送！")
                    clicked = True
                    break
                elif result == 'disabled':
                    if attempt % 5 == 4:
                        logger.info(f"  发布按钮仍未就绪，等待中... ({attempt+1}/{max_publish_attempts})")
                    time.sleep(1.5)
                    continue
            except Exception:
                pass

            done_btn, _ = find_element(page, platform, "done_button", timeout=3)
            if done_btn:
                try:
                    aria_disabled = done_btn.attr('aria-disabled')
                    if aria_disabled == 'true':
                        time.sleep(1.5)
                        continue
                    if done_btn.states.has_rect:
                        done_btn.click()
                        logger.info("✅ 视频发布指令已发送！")
                        clicked = True
                        break
                except Exception:
                    pass
            logger.warning(f"  ⚠️ 发布按钮点击失败，重试中... ({attempt+1}/{max_publish_attempts})")
            time.sleep(1.5)

        if not clicked:
            logger.warning("⚠️ 多次尝试后仍无法点击发布按钮，请手动检查。")
            log_step("publish", "fail", error="selector_not_found", detail="done_button 不可点击")
            report_failure(page, run_id, platform, "publish", "selector_not_found", safe_page_url(page),
                           selectors_tried="done_button")
            return False
        log_step("publish", "ok")

    # 10. 等待发布成功确认（带智能重试）
    if not should_skip("confirm", resume_from, STEPS):
        from social_uploader.tools.post_publish import wait_for_publish_confirmation
        from social_uploader.tools.retry_engine import retry_step, StepResult

        def _yt_idempotent_check():
            matched, _ = check_signals(page, platform, "confirm", "success_signals", timeout=0.5)
            return matched

        def _do_confirm():
            ok, reason = wait_for_publish_confirmation(page, platform, timeout_s=60)
            return StepResult(ok, value=reason, error="" if ok else reason)

        confirm_result = retry_step(
            page, platform, "confirm",
            step_fn=_do_confirm,
            max_retries=2,
            is_irreversible=True,
            pre_retry_check=_yt_idempotent_check,
        )

        if confirm_result.success:
            reason = confirm_result.value or "retry_success"
            logger.info(f"🎉 YouTube 自动化上传流程结束。({reason})")
            log_step("confirm", "ok", detail=str(reason)[:200])
            return True
        else:
            reason = confirm_result.error or "unknown"
            logger.warning(f"  ⚠️ 发布确认失败: {reason}")
            logger.info("❌ YouTube 上传流程结束（未确认成功）。")
            log_step("confirm", "fail", error="state_mismatch", detail=str(reason)[:200])
            report_failure(page, run_id, platform, "confirm", "state_mismatch",
                           page.url, detail=str(reason)[:200])
            return False

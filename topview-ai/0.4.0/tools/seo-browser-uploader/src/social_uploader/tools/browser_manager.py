import os
import time
import logging
import subprocess
import signal
import platform as _platform
from DrissionPage import ChromiumOptions, ChromiumPage

logger = logging.getLogger(__name__)


_PROJECT_PROFILE_MARKER = ".social_uploader/chrome_profiles"


def _is_project_chrome_process(pid: int) -> tuple[bool, str]:
    """判断给定 PID 的进程是否为本项目启动的调试 Chrome。

    判定依据：进程命令行中必须同时包含
    - "Google Chrome"   （排除其他 Electron 应用）
    - "--user-data-dir=" 且路径含 ".social_uploader/chrome_profiles"
      （排除日常 Chrome 与其他第三方调试 Chrome）

    返回 (is_project_chrome: bool, command_line: str)
    """
    try:
        result = subprocess.run(
            ["ps", "-o", "command=", "-p", str(pid)],
            capture_output=True, text=True, timeout=3,
        )
        cmd = (result.stdout or "").strip()
    except Exception as e:
        logger.debug(f"  无法读取 PID {pid} 命令行: {e}")
        return False, ""

    if not cmd:
        return False, ""
    if "Google Chrome" not in cmd:
        return False, cmd
    if _PROJECT_PROFILE_MARKER not in cmd:
        return False, cmd
    return True, cmd


def kill_browser(port=9222, force=False):
    """终止占用指定调试端口的"本项目调试 Chrome"，用于账号切换后重新连接。

    安全护栏（强制启用，除非 force=True）：
      - 仅终止命令行包含 ".social_uploader/chrome_profiles" 的 Chrome 进程
      - 跳过所有"日常 Chrome"（用户自己启动的）
      - 这样即使 lsof 返回了多个 PID，也绝不会误杀其他 Chrome 实例

    Args:
        port: 调试端口，默认 9222
        force: 紧急情况下绕过安全检查（**强烈不推荐**），默认 False

    返回 (killed: bool, message: str)。
    """
    try:
        result = subprocess.run(
            ["lsof", "-nP", "-iTCP:" + str(port), "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=5,
        )
        pids_raw = result.stdout.strip()
        if not pids_raw:
            return False, f"端口 {port} 上没有运行中的 Chrome 进程"

        pids = list(set(int(p.strip()) for p in pids_raw.splitlines() if p.strip()))
        killed = []
        skipped_safe = []

        for pid in pids:
            if not force:
                is_ours, cmd = _is_project_chrome_process(pid)
                if not is_ours:
                    skipped_safe.append((pid, cmd[:80]))
                    logger.warning(
                        f"  🛡️ 拒绝终止 PID {pid}：不属于本项目调试 Chrome（user-data-dir 不匹配）"
                    )
                    continue

            try:
                os.kill(pid, signal.SIGTERM)
                killed.append(pid)
            except ProcessLookupError:
                pass
            except PermissionError:
                logger.warning(f"  ⚠️ 无权终止进程 {pid}，请手动关闭 Chrome")

        if killed:
            time.sleep(1)
            msg = f"已终止 {len(killed)} 个本项目调试 Chrome 进程 (PID: {', '.join(str(p) for p in killed)})"
            if skipped_safe:
                msg += f"；安全跳过 {len(skipped_safe)} 个非本项目 Chrome"
            return True, msg

        if skipped_safe:
            return False, (
                f"端口 {port} 上检测到 {len(skipped_safe)} 个 Chrome 进程，"
                f"但均不属于本项目调试 Chrome（user-data-dir 不匹配），已安全跳过。"
                f"如需强制终止请显式调用 kill_browser(force=True)。"
            )
        return False, "未能终止任何进程"

    except FileNotFoundError:
        try:
            result = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True, timeout=5,
            )
            target_pids = set()
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        try:
                            target_pids.add(int(parts[-1]))
                        except ValueError:
                            pass
            if target_pids:
                killed_win = []
                for pid in target_pids:
                    if not force:
                        is_ours, _ = _is_project_chrome_process(pid)
                        if not is_ours:
                            logger.warning(
                                f"  🛡️ Windows: 拒绝终止 PID {pid}：不属于本项目调试 Chrome"
                            )
                            continue
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                   capture_output=True, timeout=5)
                    killed_win.append(pid)
                if killed_win:
                    time.sleep(1)
                    return True, f"已终止端口 {port} 上的 {len(killed_win)} 个本项目 Chrome 进程"
                return False, f"端口 {port} 上的进程均不属于本项目调试 Chrome，已安全跳过"
            return False, f"端口 {port} 上没有运行中的进程"
        except FileNotFoundError:
            return False, "无法检测端口占用（lsof/netstat 均不可用）"
    except Exception as e:
        return False, f"终止浏览器时出错: {e}"


_POPUP_GUARD_JS = """
(function() {
    if (window.__popupGuard) return 'already_active';

    var exactP1 = ['ok','got it','skip','dismiss','not now','maybe later',
                   'i understand','understood','later',
                   '知道了','确定','了解','跳过','以后再说','明白','好的','好'];
    var exactP2 = ['allow','accept','enable','agree','confirm','yes','sure',
                   'turn on',
                   '允许','开启','接受','同意','确认','是','打开'];
    var exactP3 = ['cancel','close','deny','reject','decline','no','no thanks',
                   'not interested','decline all','ignore',
                   '取消','关闭','拒绝','不用了','否','忽略','不感兴趣','全部拒绝'];

    var dangerWords = ['delete','remove','upload','post','publish','submit','send',
                       'save','download','share','pay','purchase','buy','sign',
                       'install','visit','learn more','get started',
                       'accept all',
                       '删除','移除','上传','发布','提交','发送','保存',
                       '下载','分享','付款','购买','签署',
                       '安装','访问','了解详情','了解更多','开始使用','立即体验',
                       '全部接受'];

    var safeIgnoreTags = ['ytcp-uploads-dialog'];
    var safeIgnoreSelectors = [
        '[class*="upload"]', '[class*="Upload"]',
        '[class*="creator"]', '[class*="Creator"]',
        '[class*="post-dialog"]', '[class*="PostDialog"]'
    ];

    function exactMatch(text, list) {
        var t = text.toLowerCase().trim();
        if (t.length === 0 || t.length > 20) return false;
        for (var kw of list) {
            if (t === kw) return true;
        }
        return false;
    }

    function isDangerous(text) {
        var t = text.toLowerCase().trim();
        for (var dw of dangerWords) {
            if (t.indexOf(dw) >= 0) return true;
        }
        return false;
    }

    function isUploadRelated(dlg) {
        for (var si of safeIgnoreTags) {
            if (dlg.tagName.toLowerCase() === si || dlg.closest(si)) return true;
        }
        for (var sel of safeIgnoreSelectors) {
            try { if (dlg.matches(sel) || dlg.querySelector(sel)) return true; } catch(e) {}
        }
        if (dlg.querySelector('input[type="file"]')) return true;
        var navKw = ['next','back','share','post','publish','下一步','返回','分享','发布'];
        var btns = dlg.querySelectorAll('button,[role="button"]');
        for (var b of btns) {
            var bt = (b.textContent || '').trim().toLowerCase();
            for (var nk of navKw) { if (bt === nk) return true; }
        }
        var text = (dlg.textContent || '').slice(0, 300).toLowerCase();
        if (text.indexOf('upload') >= 0 && text.indexOf('file') >= 0) return true;
        if (text.indexOf('上传') >= 0 && text.indexOf('文件') >= 0) return true;
        if (text.indexOf('select from computer') >= 0) return true;
        if (text.indexOf('从电脑中选择') >= 0 || text.indexOf('从电脑选择') >= 0) return true;
        if (text.indexOf('drag') >= 0 && text.indexOf('drop') >= 0) return true;
        if (text.indexOf('拖放') >= 0 || text.indexOf('拖拽') >= 0) return true;
        return false;
    }

    function isProtectedPublishDialog(dlg) {
        var text = (dlg.textContent || '').toLowerCase();
        if (text.indexOf('continue to post') >= 0) return true;
        if (text.indexOf('继续发布') >= 0) return true;
        if (text.indexOf('检查尚未完成') >= 0) return true;
        var btns = dlg.querySelectorAll('button,[role="button"]');
        var hasCancel = false;
        var hasConfirm = false;
        for (var btn of btns) {
            var bt = (btn.textContent || '').trim().toLowerCase();
            if (bt === 'cancel' || bt === '取消') hasCancel = true;
            if (bt === 'post now' || bt === 'publish now' || bt === '立即发布' || bt === '继续发布') hasConfirm = true;
        }
        return hasCancel && hasConfirm;
    }

    function handleDialog(dlg) {
        try {
            var rect = dlg.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return;
            if (rect.width > window.innerWidth * 0.85 && rect.height > window.innerHeight * 0.85) return;
            if (isUploadRelated(dlg)) return;
            if (isProtectedPublishDialog(dlg)) return;

            var btns = dlg.querySelectorAll('button,[role="button"]');
            if (btns.length === 0) return;

            var groups = [exactP1, exactP2, exactP3];
            for (var grp of groups) {
                for (var btn of btns) {
                    var t = btn.textContent.trim();
                    if (exactMatch(t, grp) && !isDangerous(t) && btn.getBoundingClientRect().width > 0) {
                        btn.click();
                        return;
                    }
                }
            }

            var closeBtn = dlg.querySelector('[aria-label="Close"],[aria-label="close"],[aria-label="关闭"]');
            if (closeBtn) {
                var target = closeBtn.closest('button') || closeBtn;
                if (target.getBoundingClientRect().width > 0) { target.click(); return; }
            }
        } catch(e) {}
    }

    var obs = new MutationObserver(function(muts) {
        if (!window.__popupGuard) return;
        for (var m of muts) {
            for (var node of m.addedNodes) {
                if (node.nodeType !== 1) continue;
                var role = node.getAttribute && node.getAttribute('role');
                if (role === 'dialog' || role === 'alertdialog') {
                    setTimeout(handleDialog.bind(null, node), 600);
                }
                if (node.querySelectorAll) {
                    var inner = node.querySelectorAll('[role="dialog"],[role="alertdialog"]');
                    for (var d of inner) {
                        setTimeout(handleDialog.bind(null, d), 600);
                    }
                }
            }
        }
    });
    obs.observe(document.body, { childList: true, subtree: true });
    window.__popupGuard = true;
    return 'activated';
})();
"""


def inject_popup_guard(page):
    """注入弹窗自动守卫（MutationObserver），实时拦截并关闭随机弹窗。

    优先级策略：
      P1 中性关闭（知道了/Got it/OK）→ P2 接受权限（允许/Allow）→ P3 取消（取消/Cancel）
    安全保护：跳过 YouTube 上传对话框、跳过占满屏幕的主 UI 对话框。
    """
    try:
        # 用 run_iife 拿 IIFE 返回值（详见 tools/js_runner.py 的 ASI 解释）。
        # IIFE 本体保留不动，因为还要给 cdp.addScriptToEvaluateOnNewDocument 注入新文档时立即执行。
        from social_uploader.tools.js_runner import run_iife
        result = run_iife(page, _POPUP_GUARD_JS)
        if result == 'activated':
            logger.info("  🛡️ 弹窗自动守卫已激活")
        return result
    except Exception:
        return None


_STALE_TASK_URL_FRAGMENTS = (
    "tiktok.com/tiktokstudio",
    "studio.youtube.com",
    "instagram.com/reels/create",
    "instagram.com/creation/",
    "about:blank",
)


def connect_browser(port=9222, new_window=True, data_dir=None):
    """连接本地 Chrome 调试端口，新开标签页执行任务。

    参数:
    - port: Chrome 调试端口
    - new_window: True 时新开标签页执行任务
    - data_dir: Chrome 用户数据目录（多账号隔离用），为 None 时仅连接已有实例

    返回 (ctrl, work, baseline_tab_ids, work_tab_id)：
    - ctrl: ChromiumPage，用于多标签管理、cleanup
    - work: 实际执行操作的标签页（新标签页或当前标签）
    - baseline_tab_ids: 连接时已有的用户标签 id（任务结束后保留）
    - work_tab_id: 任务标签 id
    """
    logger.info(f"🚀 正在连接本地浏览器 (端口 {port})...")
    co = ChromiumOptions()
    co.set_local_port(port)
    if data_dir:
        co.set_user_data_path(data_dir)
    ctrl = ChromiumPage(co)
    ctrl.set.auto_handle_alert(accept=True)
    try:
        ctrl.run_cdp('Page.addScriptToEvaluateOnNewDocument',
                     source="delete Object.getPrototypeOf(navigator).webdriver")
    except Exception:
        pass
    try:
        ctrl.run_cdp('Page.addScriptToEvaluateOnNewDocument', source=_POPUP_GUARD_JS)
    except Exception:
        pass

    if new_window:
        _close_stale_task_tabs(ctrl)

    try:
        baseline_tab_ids = list(ctrl.tab_ids)
    except Exception:
        baseline_tab_ids = None

    if new_window:
        work = ctrl.new_tab(url="about:blank")
        work.set.auto_handle_alert(accept=True)
        work_tab_id = work.tab_id
        logger.info("  📑 已新开标签页执行任务")
    else:
        work = ctrl
        work_tab_id = ctrl.tab_id

    return ctrl, work, baseline_tab_ids, work_tab_id


def _close_stale_task_tabs(ctrl):
    """关闭上次运行遗留的任务标签页，防止标签堆积。

    仅在 new_window=True（全新上传）时调用。
    始终保留 all_ids[0]，且清理后确保至少剩 1 个标签。
    """
    try:
        all_ids = list(ctrl.tab_ids)
    except Exception:
        return
    if len(all_ids) <= 1:
        return

    closed = 0
    for tid in all_ids[1:]:
        try:
            remaining = len(all_ids) - closed
            if remaining <= 1:
                break
            tab = ctrl.get_tab(tid)
            url = (tab.url or "").lower()
            if any(frag in url for frag in _STALE_TASK_URL_FRAGMENTS):
                tab.close()
                closed += 1
        except Exception:
            pass
    if closed:
        logger.info(f"  🧹 已清理 {closed} 个上次遗留的任务标签页")


_OVERLAY_CLEANUP_JS = """
(function() {
    var r = 0;
    document.querySelectorAll('iframe').forEach(function(f) {
        var s = f.src || '';
        if (s.startsWith('chrome-extension://') || s.startsWith('moz-extension://')) {
            f.remove(); r++;
        }
    });
    document.querySelectorAll('body > div, body > section, body > aside').forEach(function(el) {
        if (el.shadowRoot) { el.remove(); r++; return; }
        if (el.querySelector('[role="dialog"],[role="alertdialog"],input[type="file"]')) return;
        if (el.matches('[role="dialog"],[role="alertdialog"]')) return;
        var st = window.getComputedStyle(el);
        var z = parseInt(st.zIndex) || 0;
        if (z > 99999 && (st.position === 'fixed' || st.position === 'absolute')) {
            var rect = el.getBoundingClientRect();
            if (rect.width > 60 && rect.height > 60) { el.remove(); r++; }
        }
    });
    return r;
})();
"""


_JUNK_URL_PREFIXES = (
    "about:blank",
    "chrome-extension://",
    "moz-extension://",
    "chrome://",
    "edge://",
    "data:",
)


def dismiss_interfering_overlays(ctrl, work, baseline_tab_ids=None):
    """清理干扰元素：只关闭明确的垃圾标签（空白页/扩展页），保留用户标签和平台标签。"""
    closed_any = False

    if baseline_tab_ids is not None and ctrl is not None:
        try:
            protected = set(baseline_tab_ids) | {work.tab_id}
            for tid in ctrl.tab_ids:
                if tid not in protected:
                    try:
                        tab = ctrl.get_tab(tid)
                        tab_url = (tab.url or "").strip()
                        if not tab_url or any(tab_url.startswith(p) for p in _JUNK_URL_PREFIXES):
                            tab.close()
                            closed_any = True
                    except Exception:
                        pass
            if closed_any:
                logger.info("  🧹 已关闭垃圾标签页（空白页/扩展页）")
        except Exception:
            pass

    try:
        # 用 run_iife 拿 IIFE 返回值（详见 tools/js_runner.py 的 ASI 解释）。
        from social_uploader.tools.js_runner import run_iife
        removed = run_iife(work, _OVERLAY_CLEANUP_JS)
        if removed and int(removed) > 0:
            logger.info(f"  🧹 已清理 {removed} 个扩展/插件干扰元素")
            closed_any = True
    except Exception:
        pass

    return closed_any


def find_first(page_or_el, selectors, timeout_per=1):
    """在给定的页面/元素中尝试多个选择器，返回第一个命中的 (element, selector)"""
    for selector in selectors:
        el = page_or_el.ele(selector, timeout=timeout_per)
        if el:
            return el, selector
    return None, None


def find_platform_tab(ctrl, url_prefix):
    """在已有标签中查找 URL 包含 url_prefix 的标签页，用于 resume-from 连接上次失败的窗口。"""
    try:
        for tid in ctrl.tab_ids:
            tab = ctrl.get_tab(tid)
            if url_prefix in (tab.url or ""):
                return tab
    except Exception:
        pass
    return None


def _select_all_modifier():
    """macOS 用 Cmd (4)，其他系统用 Ctrl (2)。"""
    return 4 if _platform.system() == 'Darwin' else 2


def cdp_click_at(page, x, y):
    """通过 CDP 在指定坐标发送真实鼠标点击（isTrusted=true）。"""
    page.run_cdp('Input.dispatchMouseEvent',
                 type='mousePressed', x=int(x), y=int(y),
                 button='left', clickCount=1)
    page.run_cdp('Input.dispatchMouseEvent',
                 type='mouseReleased', x=int(x), y=int(y),
                 button='left', clickCount=1)


def cdp_click_element(page, js_selector):
    """通过 CDP 点击 JS 选择器定位的元素（isTrusted=true）。

    返回 True 成功，False 元素不存在。
    """
    rect = page.run_js(
        'var el = document.querySelector(arguments[0]);'
        'if (!el) return null;'
        'el.scrollIntoView({block: "center"});'
        'var r = el.getBoundingClientRect();'
        'return {x: r.x + r.width/2, y: r.y + r.height/2};',
        js_selector,
    )
    if not rect:
        return False
    cdp_click_at(page, rect['x'], rect['y'])
    return True


def cdp_press_key(page, key, code, key_code=0):
    """通过 CDP 发送真实键盘按键（isTrusted=true）。"""
    page.run_cdp('Input.dispatchKeyEvent',
                 type='keyDown', key=key, code=code,
                 windowsVirtualKeyCode=key_code)
    page.run_cdp('Input.dispatchKeyEvent',
                 type='keyUp', key=key, code=code,
                 windowsVirtualKeyCode=key_code)


def cdp_select_all(page):
    """通过 CDP 发送全选快捷键（macOS: Cmd+A, 其他: Ctrl+A, isTrusted=true）。"""
    mod = _select_all_modifier()
    page.run_cdp('Input.dispatchKeyEvent',
                 type='keyDown', key='a', code='KeyA',
                 windowsVirtualKeyCode=65, modifiers=mod)
    page.run_cdp('Input.dispatchKeyEvent',
                 type='keyUp', key='a', code='KeyA',
                 windowsVirtualKeyCode=65, modifiers=mod)


def cdp_type_text(page, text):
    """通过 CDP 输入文本（isTrusted=true）。"""
    page.run_cdp('Input.insertText', text=text)


_PAGE_ERROR_PATTERNS = {
    "tiktok": {
        "url_contains": ["/unavailable"],
        "texts": ["Feature unavailable", "功能不可用", "Something went wrong", "出错了",
                  "Page not available", "页面不可用"],
    },
    "instagram": {
        "url_contains": ["/sorry/", "/challenge/", "/suspended", "/disabled"],
        "texts": ["Sorry, this page isn't available", "此页面不可用",
                  "Something went wrong", "出错了", "Try Again",
                  "Your account has been suspended", "你的帐户已被暂停"],
    },
    "youtube": {
        "url_contains": ["/oops"],
        "texts": ["Something went wrong", "出错了", "YouTube Studio is unavailable",
                  "YouTube Studio 不可用", "This feature isn't available"],
    },
}


def check_page_error(page, platform):
    """检测页面是否处于平台错误状态（功能不可用、维护中等）。

    返回 (has_error, description)。has_error=True 时 description 描述错误原因。
    """
    patterns = _PAGE_ERROR_PATTERNS.get(platform, {})
    current_url = (page.url or "").lower()

    for fragment in patterns.get("url_contains", []):
        if fragment.lower() in current_url:
            return True, f"URL contains '{fragment}'"

    for text in patterns.get("texts", []):
        el = page.ele(f'text:{text}', timeout=1)
        if el:
            try:
                if el.states.has_rect:
                    return True, text
            except Exception:
                pass

    return False, ""


def cleanup_tabs(ctrl, baseline_tab_ids):
    """关闭本次任务新开的标签页，保留连接前已存在的标签。"""
    if baseline_tab_ids is None or ctrl is None:
        return
    try:
        current_tabs = list(ctrl.tab_ids)
        for tid in current_tabs:
            if tid not in baseline_tab_ids:
                try:
                    ctrl.get_tab(tid).close()
                except Exception:
                    pass
        if baseline_tab_ids:
            try:
                ctrl.get_tab(baseline_tab_ids[0])
            except Exception:
                pass
    except Exception:
        pass

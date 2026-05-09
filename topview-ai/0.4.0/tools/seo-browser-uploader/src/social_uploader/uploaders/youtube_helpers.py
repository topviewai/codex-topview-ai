"""YouTube 平台专属辅助函数（不含步骤编排）。

【架构约定】
- `tools/` = 全平台通用基础设施
- `uploaders/youtube_helpers.py` = YouTube 专属辅助（仅 youtube.py 可 import）
- `uploaders/youtube.py` = 步骤编排器（不写底层逻辑）

禁止跨平台 import：tiktok.py / instagram.py 不得 import 本模块。

【本模块包含】
- `ensure_upload_dialog_open`    URL 直跳 + polling 等待 ytcp-uploads-dialog（最稳路径）
- `find_file_input_deep`         穿透 Shadow DOM 查找 video file input（带 accept 过滤）
- `_set_youtube_schedule`        定时发布配方执行 + CDP 时间字段聚焦
- `_writeback_from_fallback`     索引模式找到的元素回写 button_config.json
"""

import re
import time
import logging

from social_uploader.tools.browser_manager import cdp_click_at, cdp_press_key
from social_uploader.tools.element_finder import add_selector
from social_uploader.tools.recipe_runner import run_recipe

logger = logging.getLogger(__name__)


# 深度查找视频专用 file input 的 JS。
# 现实情况:
#   - 真正的 YouTube Studio file input 在普通 DOM 内, accept 为空、name="Filedata"。
#   - 浏览器扩展 (Glarity / 翻译插件等) 会注入 accept="application/pdf" 等噪音 input。
#   - 实测 YouTube 当前没有 closed shadow DOM 包装, 但深度遍历仍可作为兜底。
# 过滤规则:
#   - accept 为空 / null → 接受 (YouTube 当前形态)
#   - accept 含 "video" / "mp4" / "*" → 接受
#   - 其它 (pdf / image / audio 等) → 拒绝, 防止误命中扩展
#
# ⚠️ DrissionPage 的 run_js 会自动把代码包成 `function(){<代码>}` 执行,
#    所以必须用顶层 return 语句, 严禁用 (function(){...})() IIFE — 那样返回值会丢失变成 None。
_DEEP_VIDEO_FILE_INPUT_JS = r"""
function isVideoInput(inp) {
  var acc = (inp.getAttribute('accept') || '').toLowerCase().trim();
  if (!acc) return true;
  if (acc === '*' || acc === '*/*') return true;
  if (acc.indexOf('video') !== -1) return true;
  if (acc.indexOf('mp4') !== -1) return true;
  return false;
}
function deep(root) {
  if (!root) return null;
  var inputs = root.querySelectorAll ? root.querySelectorAll('input[type="file"]') : [];
  for (var i = 0; i < inputs.length; i++) {
    if (isVideoInput(inputs[i])) return inputs[i];
  }
  var nodes = root.querySelectorAll ? root.querySelectorAll('*') : [];
  for (var j = 0; j < nodes.length; j++) {
    if (nodes[j].shadowRoot) {
      var f = deep(nodes[j].shadowRoot);
      if (f) return f;
    }
  }
  return null;
}
return deep(document);
"""


# 上传对话框就绪探测 JS。
# 实测: ytcp-uploads-dialog 本身高度为 0 (内部用 tp-yt-paper-dialog 走 position:fixed),
# 用 offsetParent / getBoundingClientRect 判断都不可靠。
# 真正可靠的"对话框就绪"标志是: ytcp-uploads-file-picker 已挂载 + 顶层 file input 已存在。
#
# ⚠️ 同上, 严禁用 IIFE, 必须用顶层 return。
_DIALOG_PROBE_JS = r"""
var picker = document.querySelector('ytcp-uploads-file-picker');
if (!picker) return false;
var input = document.querySelector('input[type="file"][name="Filedata"]') ||
            picker.querySelector('input[type="file"]');
return !!input;
"""


def _extract_channel_id(url):
    """从 studio.youtube.com URL 中提取 channel_id (UCxxxxxxxx)。"""
    if not url:
        return None
    m = re.search(r'/channel/([^/?#]+)', url)
    return m.group(1) if m else None


def ensure_upload_dialog_open(page, timeout=15):
    """确保 YouTube Studio 的视频上传对话框已打开。

    实测最稳定的策略 (优于点击 #upload-icon, 因为图标点击有时不弹对话框):
      1. 强制进 studio 主页拿 channel_id (即使当前已在 studio 域名也要重进, 防止陈旧 SPA 状态)
      2. URL 直跳 `studio.youtube.com/channel/<id>/videos/upload?d=ud`
      3. SPA 挂载等待 + polling 探测 <ytcp-uploads-dialog>

    返回 True / False。
    """
    # popup_guard (browser_manager._POPUP_GUARD_JS) 的 MutationObserver 会监听新加的 [role="dialog"]。
    # 它在 callback 首行检查 `if (!window.__popupGuard) return;`,
    # 所以设为 false 即可让它停止干预。
    # SPA 路由切换 (page.get) 可能不会刷新 JS 上下文, 必须显式停用。
    try:
        page.run_js("window.__popupGuard = false;")
    except Exception:
        pass

    try:
        # 必须先进 channel 主页, 即使当前已经在 studio.youtube.com 也要刷新一次,
        # 因为 login/page_check/cleanup 步骤之后页面状态可能残留 (popup_guard JS / 残留 dialog)
        # 重新 get 一次能让 channel_id 提取拿到最新值, 也能丢弃旧 SPA 状态。
        logger.info("  🔄 重置到 studio 主页...")
        page.get('https://studio.youtube.com/')
        page.wait.doc_loaded(timeout=15)
        time.sleep(0.8)  # SPA 路由完成

        channel_id = _extract_channel_id(page.url)
        if channel_id:
            upload_url = f'https://studio.youtube.com/channel/{channel_id}/videos/upload?d=ud'
        else:
            upload_url = 'https://studio.youtube.com/?d=ud'
            logger.info(f"  ⚠️ 未从 {page.url} 解析到 channel_id, 用兜底 URL")

        logger.info(f"  🎯 直跳上传 URL: {upload_url}")
        page.get(upload_url)
        page.wait.doc_loaded(timeout=15)
        time.sleep(1.5)  # 给 ytcp-uploads-dialog 挂载时间
    except Exception as e:
        logger.warning(f"  ⚠️ URL 直跳异常: {e}")

    deadline = time.time() + timeout
    last_url_log = 0.0
    while time.time() < deadline:
        try:
            if page.run_js(_DIALOG_PROBE_JS):
                logger.info("  ✅ 上传对话框已打开 (ytcp-uploads-dialog)")
                return True
            now = time.time()
            if now - last_url_log >= 3.0:
                cur_url = ""
                try:
                    cur_url = page.url or ""
                except Exception:
                    pass
                logger.info(f"  ⏳ 等待对话框... (当前 url: {cur_url[:90]})")
                last_url_log = now
        except Exception as e:
            logger.debug(f"  探测异常: {e}")
        time.sleep(0.5)

    logger.warning(f"  ⚠️ {timeout}s 内对话框未出现")
    return False


def find_file_input_deep(page, timeout=15):
    """穿透所有 Shadow DOM 查找 YouTube 视频上传专用的 <input type="file">。

    带 accept 过滤: 排除浏览器扩展 (Glarity PDF / 翻译插件) 注入的非视频 file input,
    防止注入文件时被错误目标接收导致失败。

    返回 ChromiumElement 或 None。
    """
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            el = page.run_js(_DEEP_VIDEO_FILE_INPUT_JS)
            if el:
                return el
        except Exception as e:
            last_err = e
        time.sleep(0.5)
    if last_err is not None:
        logger.debug(f"  Shadow DOM 深度查找异常: {last_err}")
    return None


def _writeback_from_fallback(el, platform, key):
    """当上传器自身的 fallback 逻辑找到元素后，将有效选择器回写到 button_config.json。

    目前只在 YouTube 的 form_fill 索引模式下使用，迁出共享区是为了平台代码各自独立。
    若未来其他平台也需要，再抽到 tools/。
    """
    try:
        tag = (el.tag or "").lower()
        el_id = el.attr("id") or ""
        aria = el.attr("aria-label") or ""
    except Exception:
        return
    sel = None
    if el_id:
        sel = f"#{el_id}" if "." not in el_id and " " not in el_id else f'@id={el_id}'
    elif aria:
        sel = f'@aria-label={aria}'
    if sel:
        ok, msg = add_selector(platform, key, sel)
        if ok and "已将" in msg:
            logger.info(f"  📝 fallback 回写: {platform}.{key} ← {sel}")


def _set_youtube_schedule(page, schedule_str):
    """设置 YouTube 定时发布（格式: 'YYYY-MM-DD HH:MM'）。

    使用 recipe 配方系统（三层兜底）：
    - Tier 1: 按 state_patterns.json → youtube.schedule_recipe 执行
    - Tier 2: 选择器失败时启发式发现替代元素，成功后自动写回配方
    - Tier 3: 全部失败时输出增强 DIAG，交给 Agent 介入

    返回 (success: bool, diag: dict|None)。
    diag 含 failed_step / semantic_hint / recipe_key，供 report_failure 透传。
    """
    def _format_diag(reason):
        return {
            "failed_step": "format_check",
            "semantic_hint": reason,
            "recipe_key": "schedule_recipe",
        }

    parts = schedule_str.strip().split(' ')
    if len(parts) != 2:
        logger.warning(f"  ⚠️ 定时格式错误（需要 'YYYY-MM-DD HH:MM'）: {schedule_str}")
        return False, _format_diag(f"schedule_str 格式错误: {schedule_str}")
    date_str, time_str = parts
    date_parts = date_str.split('-')
    if len(date_parts) != 3:
        logger.warning(f"  ⚠️ 日期格式错误（需要 'YYYY-MM-DD'）: {date_str}")
        return False, _format_diag(f"date_str 格式错误: {date_str}")

    try:
        target_day = str(int(date_parts[2]))
    except ValueError:
        logger.warning(f"  ⚠️ 日期中的日无法解析为数字: {date_str}")
        return False, _format_diag(f"date_str 日字段非数字: {date_str}")

    time_parts = time_str.split(':')
    if len(time_parts) != 2:
        logger.warning(f"  ⚠️ 时间格式错误（需要 'HH:MM'）: {time_str}")
        return False, _format_diag(f"time_str 格式错误: {time_str}")
    try:
        int(time_parts[0])
        int(time_parts[1])
    except ValueError:
        logger.warning(f"  ⚠️ 时间中包含非数字字符: {time_str}")
        return False, _format_diag(f"time_str 含非数字: {time_str}")

    variables = {
        "date": date_str,
        "time": time_str,
        "day": target_day,
    }

    success, failed_step, hint = run_recipe(page, "youtube", "schedule_recipe", variables)

    if success:
        # 通过 CDP 逐个聚焦 + Tab 让 YouTube Polymer 组件完成时间验证（所有事件 isTrusted=true）
        input_rects = page.run_js("""
            var inputs = document.querySelectorAll('#second-container input, #time-of-day-container input');
            var rects = [];
            for (var inp of inputs) {
                var r = inp.getBoundingClientRect();
                if (r.width > 0) rects.push({x: r.x + r.width/2, y: r.y + r.height/2});
            }
            return rects;
        """)
        if input_rects:
            for rect in input_rects:
                cdp_click_at(page, rect['x'], rect['y'])
                time.sleep(0.15)
                cdp_press_key(page, 'Tab', 'Tab', 9)
                time.sleep(0.15)
        time.sleep(1)
        logger.info(f"  ✅ YouTube 定时发布: {schedule_str}")
        return True, None
    logger.warning(f"  ⚠️ YouTube 定时发布失败 (step={failed_step}, hint={hint})")
    return False, {
        "failed_step": failed_step or "",
        "semantic_hint": hint or "",
        "recipe_key": "schedule_recipe",
    }

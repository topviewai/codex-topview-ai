"""TikTok 平台专属辅助函数（不含步骤编排）。

【架构约定】
- `tools/` = 全平台通用基础设施
- `uploaders/tiktok_helpers.py` = TikTok 专属辅助（仅 tiktok.py 可 import）
- `uploaders/tiktok.py` = 步骤编排器（不写底层逻辑）

禁止跨平台 import：youtube.py / instagram.py 不得 import 本模块。

【本模块包含】
- `_set_toggle`             基于标签文本设置 button[role="switch"] 的开关状态
- `_set_checkbox`           基于标签文本设置 [role="checkbox"] / input[type="checkbox"] 状态
- `_set_tiktok_visibility`  设置可见性下拉（everyone/friends/only_me），走 visibility_recipe
- `_set_tiktok_schedule`    设置定时发布，走 schedule_recipe
- `_set_tiktok_options`     聚合上述选项设置，返回 (changed, recipe_diag)
"""

import logging

from social_uploader.tools.recipe_runner import run_recipe

logger = logging.getLogger(__name__)


def _set_toggle(page, label_keywords, desired_state):
    """通过标签文本找到 TikTok toggle 开关并设置到目标状态。"""
    for kw in label_keywords:
        safe_kw = kw.replace("\\", "\\\\").replace("'", "\\'")
        result = page.run_js(f"""
            var kw = '{safe_kw}';
            var switches = document.querySelectorAll('button[role="switch"]');
            for (var sw of switches) {{
                var row = sw;
                for (var i = 0; i < 8; i++) {{
                    row = row.parentElement;
                    if (!row) break;
                    if (row.textContent.includes(kw)) {{
                        var isOn = sw.getAttribute('aria-checked') === 'true';
                        var want = {'true' if desired_state else 'false'};
                        if (isOn !== want) {{ sw.click(); return 'toggled'; }}
                        return 'ok';
                    }}
                }}
            }}
            return 'not_found';
        """)
        if result in ('toggled', 'ok'):
            action = '开启' if desired_state else '关闭'
            status = '已切换' if result == 'toggled' else '无需改动'
            logger.info(f"  ✅ {kw}: {action} ({status})")
            return True
    return False


def _set_checkbox(page, label_keywords, desired_state):
    """通过标签文本找到 TikTok 自定义 checkbox 并设置到目标状态。"""
    for kw in label_keywords:
        safe_kw = kw.replace("\\", "\\\\").replace("'", "\\'")
        result = page.run_js(f"""
            var kw = '{safe_kw}';
            var targets = document.querySelectorAll(
                '[role="checkbox"], input[type="checkbox"], [role="switch"]'
            );
            for (var el of targets) {{
                var row = el;
                for (var i = 0; i < 8; i++) {{
                    row = row.parentElement;
                    if (!row) break;
                    if (row.textContent.includes(kw)) {{
                        var isChecked = el.checked
                            || el.getAttribute('aria-checked') === 'true'
                            || el.classList.contains('checked');
                        var want = {'true' if desired_state else 'false'};
                        if (isChecked !== want) {{ el.click(); return 'toggled'; }}
                        return 'ok';
                    }}
                }}
            }}
            return 'not_found';
        """)
        if result in ('toggled', 'ok'):
            action = '勾选' if desired_state else '取消勾选'
            status = '已切换' if result == 'toggled' else '无需改动'
            logger.info(f"  ✅ {kw}: {action} ({status})")
            return True
    return False


def _set_tiktok_visibility(page, visibility):
    """设置 TikTok 可见性下拉（everyone/friends/only_me）。

    使用 recipe 配方系统（三层兜底）：
    - Tier 1: 按 state_patterns.json → tiktok.visibility_recipe 执行
    - Tier 2: 选择器失败时启发式发现替代元素，成功后自动写回配方
    - Tier 3: 全部失败时输出增强 DIAG，交给 Agent 介入

    返回 (success: bool, diag: dict|None)。
    """
    visibility_map = {
        "everyone": ["Everyone", "所有人"],
        "friends": ["Friends", "好友"],
        "only_me": ["Only you", "Only me", "仅自己", "Only Me"],
    }
    option_texts = visibility_map.get(visibility, ["Everyone", "所有人"])

    variables = {
        "option_text": "|".join(option_texts),
        "option_hint": option_texts[0],
    }

    success, failed_step, hint = run_recipe(
        page, "tiktok", "visibility_recipe", variables,
    )

    if success:
        logger.info(f"  ✅ 可见性: {visibility}")
        return True, None
    logger.warning(
        f"  ⚠️ 可见性设置失败 (step={failed_step}, hint={hint})"
    )
    return False, {
        "failed_step": failed_step or "",
        "semantic_hint": hint or "",
        "recipe_key": "visibility_recipe",
    }


def _set_tiktok_schedule(page, schedule_str):
    """设置 TikTok 定时发布（格式: 'YYYY-MM-DD HH:MM'）。

    使用 recipe 配方系统（三层兜底）：
    - Tier 1: 按 state_patterns.json → tiktok.schedule_recipe 执行
    - Tier 2: 选择器失败时启发式发现替代元素，成功后自动写回配方
    - Tier 3: 全部失败时输出增强 DIAG，交给 Agent 介入

    返回 (success: bool, diag: dict|None)。
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

    time_parts = time_str.split(':')
    if len(time_parts) != 2:
        logger.warning(f"  ⚠️ 时间格式错误（需要 'HH:MM'）: {time_str}")
        return False, _format_diag(f"time_str 格式错误: {time_str}")
    try:
        hour_int = int(time_parts[0])
        minute_int = int(time_parts[1])
    except ValueError:
        logger.warning(f"  ⚠️ 时间中包含非数字字符: {time_str}")
        return False, _format_diag(f"time_str 含非数字: {time_str}")
    target_hour = str(hour_int).zfill(2)
    target_minute = str(minute_int - (minute_int % 5)).zfill(2)

    date_parts = date_str.split('-')
    if len(date_parts) != 3:
        logger.warning(f"  ⚠️ 日期格式错误（需要 'YYYY-MM-DD'）: {date_str}")
        return False, _format_diag(f"date_str 格式错误: {date_str}")
    try:
        day = str(int(date_parts[2]))
    except ValueError:
        logger.warning(f"  ⚠️ 日期中的日无法解析为数字: {date_str}")
        return False, _format_diag(f"date_str 日字段非数字: {date_str}")

    variables = {
        "date": date_str,
        "time": f"{target_hour}:{target_minute}",
        "hour": target_hour,
        "minute": target_minute,
        "day": day,
    }

    success, failed_step, hint = run_recipe(page, "tiktok", "schedule_recipe", variables)

    if success:
        logger.info(f"  ✅ 定时发布: {date_str} {target_hour}:{target_minute}")
        return True, None
    logger.warning(f"  ⚠️ 定时发布设置失败 (step={failed_step}, hint={hint})")
    return False, {
        "failed_step": failed_step or "",
        "semantic_hint": hint or "",
        "recipe_key": "schedule_recipe",
    }


def _set_tiktok_options(page, config):
    """根据 profile 配置设置 TikTok 上传页面的所有选项。

    返回 (changed, recipe_diag)：
      changed     — 已成功改动的选项列表
      recipe_diag — {"visibility": diag|None, "schedule": diag|None}，
                    用于上层在失败时把 failed_step / semantic_hint / recipe_key
                    透传给 report_failure，方便事后诊断。
    """
    changed = []
    recipe_diag = {"visibility": None, "schedule": None}

    ai_generated = config.get("ai_generated", False)
    if ai_generated:
        if _set_toggle(page, ["AI-generated content", "AI 生成内容", "AI-generated"], True):
            changed.append("ai_generated")

    disclose = config.get("disclose_content", False)
    if disclose:
        if _set_toggle(page, ["Disclose post content", "披露帖子内容", "Disclose"], True):
            changed.append("disclose_content")

    high_quality = config.get("high_quality", True)
    if not high_quality:
        if _set_toggle(page, ["High-quality uploads", "高画质上传", "High-quality"], False):
            changed.append("high_quality=off")

    allow_comments = config.get("allow_comments", True)
    if not allow_comments:
        if _set_checkbox(page, ["Comment", "评论"], False):
            changed.append("comments=off")

    allow_reuse = config.get("allow_reuse", True)
    if not allow_reuse:
        if _set_checkbox(page, ["Reuse of content", "允许引用", "Reuse"], False):
            changed.append("reuse=off")

    visibility = config.get("visibility", "everyone")
    if visibility != "everyone":
        ok, diag = _set_tiktok_visibility(page, visibility)
        if ok:
            changed.append(f"visibility={visibility}")
        else:
            recipe_diag["visibility"] = diag

    schedule = config.get("schedule")
    if schedule:
        if visibility == "only_me":
            logger.warning("  ⚠️ TikTok 平台限制：仅自己可见的视频无法定时发布，已自动跳过定时设置，视频将立即发布。")
            changed.append("schedule=skipped(private)")
        else:
            ok, diag = _set_tiktok_schedule(page, schedule)
            if ok:
                changed.append(f"schedule={schedule}")
            else:
                recipe_diag["schedule"] = diag

    return changed, recipe_diag

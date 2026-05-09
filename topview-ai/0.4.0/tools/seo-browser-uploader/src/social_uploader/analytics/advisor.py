"""创作建议生成 — 纯规则引擎，基于分析结果输出可执行建议。

设计原则：
- 不依赖任何外部 LLM 服务（无网络、无 API Key、无超时风险）
- 输出字段保持与历史 LLM 版本一致，确保 reporter.py 模板兼容
- 建议必须基于真实数据数值，避免空泛口号
"""

import logging

logger = logging.getLogger(__name__)

_DEFAULT_PERIOD_DAYS = 28

_PLATFORM_DISPLAY = {
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "douyin": "抖音",
}

_PLATFORM_FORMAT_TIPS = {
    "youtube": "横屏 16:9 长视频（5-15 分钟）+ Shorts 竖屏（< 60 秒）双轨并行，长视频留住订阅，Shorts 拉新",
    "tiktok": "竖屏 9:16，时长 15-60 秒，前 3 秒必须有强 hook（反差/悬念/视觉冲击）",
    "instagram": "Reels 优先（竖屏 9:16，15-30 秒），封面统一风格，主题集中便于建立账号识别度",
    "douyin": "竖屏 9:16，15-60 秒，开头 3 秒强冲突或反转，配合热门 BGM 提升完播",
}

_PLATFORM_TITLE_HOOKS = {
    "youtube": [
        "How to ___ in ___ (data: ___)",
        "I tried ___ for 7 days — here's what happened",
        "___ you should NEVER do (and why)",
    ],
    "tiktok": [
        "POV: ___",
        "Watch till the end 👀",
        "Wait for it…",
    ],
    "instagram": [
        "Save this for later 📌",
        "3 things I wish I knew about ___",
        "The truth about ___",
    ],
    "douyin": [
        "千万别这样做___",
        "原来___还可以这样",
        "看完不许哭",
    ],
}


def generate_advice(analysis_result: dict) -> dict:
    """根据分析结果生成创作建议（纯规则，无 LLM 依赖）。"""
    advice = {
        "recommended_topics": [],
        "content_format": "",
        "title_hooks": [],
        "publish_schedule": "",
        "improvements": [],
        "summary": "",
        "source": "rules",
    }

    platforms = analysis_result.get("platforms", {}) or {}
    period_days = analysis_result.get("period_days", _DEFAULT_PERIOD_DAYS)

    if not platforms:
        advice["summary"] = "未采集到任何平台数据，请先确认浏览器已登录目标平台再重试。"
        return advice

    engagement_rates = []
    has_hits = False
    has_flops = False
    total_videos = 0
    platform_breakdowns = []

    for platform, data in platforms.items():
        plat_label = _PLATFORM_DISPLAY.get(platform, platform.upper())
        metrics = data.get("metrics", {}) or {}
        videos = data.get("videos", {}) or {}
        trend = data.get("trend", {}) or {}

        er = data.get("engagement_rate")
        if er is not None:
            engagement_rates.append((platform, plat_label, er))

        hits = videos.get("hits", []) or []
        flops = videos.get("flops", []) or []
        if hits:
            has_hits = True
        if flops:
            has_flops = True

        video_count = len(videos.get("all", []) or []) or len(hits) + len(flops)
        total_videos += video_count

        platform_breakdowns.append({
            "platform": platform,
            "label": plat_label,
            "metrics": metrics,
            "engagement_rate": er,
            "trend": trend,
            "hits": hits,
            "flops": flops,
            "video_count": video_count,
        })

        _append_platform_format_tip(advice, platform, hits, flops, metrics)
        _append_platform_title_hooks(advice, platform, hits)

        for tip in _build_per_platform_topics(platform, plat_label, hits, flops, metrics):
            if tip not in advice["recommended_topics"]:
                advice["recommended_topics"].append(tip)

        for tip in _build_trend_improvements(plat_label, trend):
            if tip not in advice["improvements"]:
                advice["improvements"].append(tip)

        for tip in _build_metrics_improvements(plat_label, metrics, video_count):
            if tip not in advice["improvements"]:
                advice["improvements"].append(tip)

    advice["publish_schedule"] = _build_publish_schedule(
        analysis_result.get("publish_cadence", {}) or {},
        period_days,
    )

    if engagement_rates:
        engagement_rates.sort(key=lambda x: x[2], reverse=True)
        best = engagement_rates[0]
        worst = engagement_rates[-1]
        advice["improvements"].insert(
            0,
            f"{best[1]} 互动率最高（{best[2]}%），建议优先投入精力做系列化内容",
        )
        if len(engagement_rates) > 1 and worst[2] < best[2] * 0.5:
            advice["improvements"].append(
                f"{worst[1]} 互动率仅 {worst[2]}%，落后 {best[1]} 较多，"
                "可考虑暂停投入或参考 {best_label} 的内容形式".format(best_label=best[1])
            )

    if has_hits and not advice["recommended_topics"]:
        advice["recommended_topics"].append("从已有爆款视频提炼共性主题，做 3-5 期同主题系列内容")

    if has_flops and not any("低迷" in t or "改进" in t for t in advice["improvements"]):
        advice["improvements"].append("低迷视频复盘：检查标题吸引力、封面对比度、前 3 秒留存率")

    if not advice["recommended_topics"]:
        advice["recommended_topics"].append("数据量较少，建议先稳定每周发布 2-3 条，积累 4 周后再做主题分析")

    if not advice["improvements"]:
        advice["improvements"].append("各项指标稳定，可尝试加大单期投入或测试新选题方向")

    advice["recommended_topics"] = advice["recommended_topics"][:5]
    advice["improvements"] = advice["improvements"][:6]
    advice["title_hooks"] = advice["title_hooks"][:5]

    advice["summary"] = _build_summary(
        period_days,
        platform_breakdowns,
        engagement_rates,
        total_videos,
        analysis_result.get("publish_cadence", {}) or {},
        has_hits,
        has_flops,
    )

    return advice


def _append_platform_format_tip(advice: dict, platform: str, hits: list, flops: list, metrics: dict) -> None:
    """根据平台特性追加内容形式建议（仅追加首个明显落后的平台提示）。"""
    if advice["content_format"]:
        return
    tip = _PLATFORM_FORMAT_TIPS.get(platform)
    if not tip:
        return
    if flops and len(flops) > len(hits):
        plat_label = _PLATFORM_DISPLAY.get(platform, platform.upper())
        advice["content_format"] = f"{plat_label}：{tip}"


def _append_platform_title_hooks(advice: dict, platform: str, hits: list) -> None:
    """有爆款时优先用爆款平台的标题模板。"""
    if advice["title_hooks"]:
        return
    if not hits:
        return
    hooks = _PLATFORM_TITLE_HOOKS.get(platform)
    if hooks:
        advice["title_hooks"].extend(hooks)


def _build_per_platform_topics(
    platform: str, plat_label: str, hits: list, flops: list, metrics: dict
) -> list:
    """基于单平台数据的具体主题建议。"""
    tips = []
    if hits:
        top = hits[0]
        title = (top.get("title") or "").strip()
        views = top.get("views")
        if title and views is not None:
            preview = title[:24] + ("…" if len(title) > 24 else "")
            tips.append(f"[{plat_label}] 复制爆款方向：《{preview}》（{_fmt_num(views)} 播放），做 3 期同主题")
        elif views is not None:
            tips.append(f"[{plat_label}] 围绕最高播放视频（{_fmt_num(views)}）做系列化复制")

    if platform == "youtube" and metrics.get("subscribers") is not None:
        subs = float(metrics.get("subscribers") or 0)
        if subs < 1000:
            tips.append(f"[{plat_label}] 订阅 {_fmt_num(subs)} < 1000，优先做订阅引导（结尾 CTA + Shorts 引流）")
        elif subs < 10000:
            tips.append(f"[{plat_label}] 订阅 {_fmt_num(subs)}，建议做 1-2 期长视频建立专业度，搭配 Shorts 拉量")

    if platform == "tiktok" and metrics:
        followers = metrics.get("followers")
        if followers is not None:
            try:
                fnum = float(followers)
                if fnum < 1000:
                    tips.append(f"[{plat_label}] 粉丝 {_fmt_num(fnum)} < 1000，建议每天 1-2 条蹭热点 BGM 测试爆款")
            except (TypeError, ValueError):
                pass

    return tips


def _build_trend_improvements(plat_label: str, trend: dict) -> list:
    """基于趋势变化生成改进项（聚焦显著下滑指标）。"""
    tips = []
    for metric, info in (trend or {}).items():
        if not isinstance(info, dict):
            continue
        pct = info.get("change_pct")
        if pct is None:
            continue
        try:
            pct_val = float(pct)
        except (TypeError, ValueError):
            continue
        if pct_val <= -30:
            tips.append(f"[{plat_label}] {metric} 较上次下降 {abs(pct_val):.0f}%，建议复盘最近一周内容")
        elif pct_val >= 50:
            tips.append(f"[{plat_label}] {metric} 较上次上升 {pct_val:.0f}%，可加大同类内容产出")
    return tips


def _build_metrics_improvements(plat_label: str, metrics: dict, video_count: int) -> list:
    """基于绝对值阈值的改进建议。"""
    tips = []
    views = metrics.get("views")
    if views is not None:
        try:
            v = float(views)
            if v < 100 and video_count > 0:
                tips.append(f"[{plat_label}] 周期内总播放仅 {_fmt_num(v)}，建议优化封面/标题点击率")
        except (TypeError, ValueError):
            pass

    watch_time = metrics.get("watch_time_hours")
    if watch_time is not None:
        try:
            w = float(watch_time)
            if w < 10 and video_count > 0:
                tips.append(f"[{plat_label}] 总观看时长 {w:.1f} 小时偏低，需提升完播率（开头钩子 + 节奏）")
        except (TypeError, ValueError):
            pass

    return tips


def _build_publish_schedule(cadence: dict, period_days: int) -> str:
    """根据发布节奏数据生成节奏建议。"""
    total = cadence.get("total_uploads", 0) or 0
    avg_interval = cadence.get("avg_interval_days")
    successful = cadence.get("successful_uploads", 0) or 0
    failed = cadence.get("failed_uploads", 0) or 0

    if total == 0:
        return f"周期内（{period_days} 天）无上传记录，建议立即建立每周 2-3 条的发布节奏"

    if avg_interval is None:
        return f"周期内共上传 {total} 次（成功 {successful}、失败 {failed}），建议保持稳定输出"

    try:
        interval = float(avg_interval)
    except (TypeError, ValueError):
        return f"周期内共上传 {total} 次（成功 {successful}、失败 {failed}）"

    if interval > 7:
        target = "每周 2-3 条"
        return f"当前平均 {interval:.1f} 天发一条，频率偏低，建议提高到 {target}（成功 {successful}/失败 {failed}）"
    if interval < 0.5:
        rate = 1 / interval if interval > 0 else 0
        return f"当前每天约发 {rate:.0f} 条，节奏过密，注意保证内容质量与审核通过率（成功 {successful}/失败 {failed}）"
    if interval <= 3:
        return f"当前平均 {interval:.1f} 天一条，节奏健康，建议保持（成功 {successful}/失败 {failed}）"
    return f"当前平均 {interval:.1f} 天一条，可微调到每周 2-3 条以获得更稳定的算法分发（成功 {successful}/失败 {failed}）"


def _build_summary(
    period_days: int,
    platform_breakdowns: list,
    engagement_rates: list,
    total_videos: int,
    cadence: dict,
    has_hits: bool,
    has_flops: bool,
) -> str:
    """生成 2-3 句话的总结。"""
    parts = []
    plat_count = len(platform_breakdowns)
    if plat_count:
        plat_names = "、".join(p["label"] for p in platform_breakdowns)
        parts.append(f"近 {period_days} 天分析了 {plat_names} 共 {plat_count} 个平台 {total_videos} 条视频")

    if engagement_rates:
        engagement_rates_sorted = sorted(engagement_rates, key=lambda x: x[2], reverse=True)
        best = engagement_rates_sorted[0]
        parts.append(f"{best[1]} 互动率 {best[2]}% 表现最佳")

    cadence_total = cadence.get("total_uploads", 0) or 0
    if cadence_total:
        parts.append(f"周期内上传 {cadence_total} 次")

    if has_hits and has_flops:
        parts.append("内容呈两极分化，建议系列化复制爆款 + 复盘低迷视频")
    elif has_hits:
        parts.append("已出现爆款，建议立即跟进同主题系列")
    elif has_flops:
        parts.append("整体表现偏低，建议优化标题、封面、前 3 秒")
    else:
        parts.append("数据稳定，可尝试加大投入测试新方向")

    return "；".join(parts) + "。"


def _fmt_num(value) -> str:
    """格式化数字：1234 → 1.2k，1500000 → 1.5M。"""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    if n == int(n):
        return str(int(n))
    return f"{n:.1f}"

"""报告生成 — 支持 Markdown / HTML / 终端三种输出格式。

使用 jinja2 渲染模板，模板位于 analytics/templates/ 目录。
"""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from . import store
from .analyzer import _METRIC_LABELS

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_VIDEO_METRIC_DISPLAY_ORDER = [
    "views", "watch_time_hours", "likes", "comments", "shares", "saves",
    "impressions", "ctr", "avg_view_duration", "avg_percentage_viewed",
    "unique_viewers", "returning_viewers", "new_viewers",
    "subscribers", "non_subscriber_pct",
]

_VIDEO_METRIC_LABELS = {
    "views": "播放",
    "watch_time_hours": "时长(h)",
    "likes": "赞",
    "comments": "评论",
    "shares": "分享",
    "saves": "收藏",
    "impressions": "展示",
    "ctr": "CTR%",
    "avg_view_duration": "均时长",
    "avg_percentage_viewed": "完播%",
    "unique_viewers": "独立观众",
    "returning_viewers": "回访",
    "new_viewers": "新观众",
    "subscribers": "订阅变化",
    "non_subscriber_pct": "非订阅%",
    "collects": "收藏",
    "danmaku": "弹幕",
    "new_followers": "涨粉",
    "hearts": "获赞",
    "profile_views": "主页访问",
    "estimated_reward": "预估奖励",
}


def _format_number(value) -> str:
    """将数字格式化为可读字符串。"""
    if value is None:
        return "-"
    try:
        v = float(value)
    except (ValueError, TypeError):
        return str(value)
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 10_000:
        return f"{v / 1_000:.1f}K"
    if v == int(v):
        return f"{int(v):,}"
    return f"{v:,.1f}"


def _trend_arrow(change_pct) -> str:
    """根据变化百分比返回文本箭头。"""
    if change_pct is None:
        return "-"
    pct = float(change_pct)
    if pct > 0:
        return f"↑ +{pct:.0f}%"
    elif pct < 0:
        return f"↓ {pct:.0f}%"
    return "→ 0%"


def _trend_arrow_html(change_pct) -> str:
    """根据变化百分比返回带颜色的 HTML。"""
    if change_pct is None:
        return '<span style="color:#6c757d">-</span>'
    pct = float(change_pct)
    if pct > 0:
        return f'<span class="up">↑ +{pct:.0f}%</span>'
    elif pct < 0:
        return f'<span class="down">↓ {pct:.0f}%</span>'
    return '<span>→ 0%</span>'


def _metric_label(metric_name: str) -> str:
    return _METRIC_LABELS.get(metric_name, metric_name)


def _video_metric_label(key: str) -> str:
    return _VIDEO_METRIC_LABELS.get(key, key)


def _detect_video_columns(video_metrics: list[dict]) -> list[str]:
    """从视频列表中检测所有可用的指标列（按展示优先级排序）。"""
    all_keys: set[str] = set()
    for v in video_metrics:
        all_keys.update(k for k, val in v.items() if k != "title" and val is not None)

    ordered = [k for k in _VIDEO_METRIC_DISPLAY_ORDER if k in all_keys]
    remaining = sorted(all_keys - set(ordered) - {"title"})
    return ordered + remaining


def _build_cross_platform_summary(platforms: dict) -> list[dict]:
    """生成跨平台对比摘要行。每行: {metric, values: {platform: formatted_value}}。"""
    if len(platforms) < 2:
        return []

    common_keys = ["views", "likes", "comments", "shares", "followers", "new_followers"]
    rows: list[dict] = []

    for key in common_keys:
        row_vals: dict[str, str] = {}
        for pname, pdata in platforms.items():
            val = pdata.get("metrics", {}).get(key)
            if val is not None:
                row_vals[pname] = _format_number(val)
        if len(row_vals) >= 2:
            rows.append({"metric": _metric_label(key), "values": row_vals})

    er_vals: dict[str, str] = {}
    for pname, pdata in platforms.items():
        er = pdata.get("engagement_rate")
        if er is not None:
            er_vals[pname] = f"{er}%"
    if len(er_vals) >= 2:
        rows.append({"metric": "互动率", "values": er_vals})

    return rows


def _get_jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["format_number"] = _format_number
    env.globals["trend_arrow"] = _trend_arrow
    env.globals["trend_arrow_html"] = _trend_arrow_html
    env.globals["metric_label"] = _metric_label
    env.globals["video_metric_label"] = _video_metric_label
    env.globals["detect_video_columns"] = _detect_video_columns
    env.globals["build_cross_platform_summary"] = _build_cross_platform_summary
    env.globals["hit_threshold"] = "2"
    env.globals["flop_threshold"] = "0.3"
    return env


def render_markdown(analysis_result: dict, advice: dict) -> str:
    """渲染 Markdown 报告。"""
    env = _get_jinja_env()
    template = env.get_template("report.md")
    return template.render(**analysis_result, advice=advice)


def render_html(analysis_result: dict, advice: dict) -> str:
    """渲染 HTML 报告。"""
    env = _get_jinja_env()
    template = env.get_template("report.html")
    return template.render(**analysis_result, advice=advice)


def render_terminal(analysis_result: dict, advice: dict) -> str:
    """渲染详细版终端输出（创作建议优先，数据在后）。"""
    lines = []
    lines.append("=" * 60)
    lines.append("  社交媒体数据简报")
    lines.append(f"  周期: 最近 {analysis_result.get('period_days', 28)} 天")
    lines.append("=" * 60)

    lines.append("\n── 创作建议 ──")
    summary = advice.get("summary", "")
    if summary and not summary.lstrip().startswith("{"):
        lines.append(f"  {summary}")
    if advice.get("recommended_topics"):
        lines.append("  推荐主题:")
        for t in advice["recommended_topics"][:3]:
            lines.append(f"    • {t}")
    if advice.get("publish_schedule"):
        lines.append(f"  发布节奏: {advice['publish_schedule']}")
    if advice.get("improvements"):
        lines.append("  改进方向:")
        for item in advice["improvements"][:3]:
            lines.append(f"    • {item}")
    if advice.get("content_format"):
        lines.append(f"  内容形式: {advice['content_format']}")
    if advice.get("title_hooks"):
        lines.append("  标题参考:")
        for hook in advice["title_hooks"][:3]:
            lines.append(f"    • {hook}")

    if analysis_result.get("highlights") or analysis_result.get("warnings"):
        lines.append("\n── 关键发现 ──")
        if analysis_result.get("highlights"):
            for h in analysis_result["highlights"][:5]:
                lines.append(f"  ✅ {h}")
        if analysis_result.get("warnings"):
            for w in analysis_result["warnings"][:5]:
                lines.append(f"  ⚠️ {w}")

    for platform, data in analysis_result.get("platforms", {}).items():
        lines.append(f"\n── {platform.upper()} ──")
        trend = data.get("trend", {})

        for metric, info in trend.items():
            label = _metric_label(metric)
            current = _format_number(info.get("current"))
            arrow = _trend_arrow(info.get("change_pct"))
            lines.append(f"  {label:<16} {current:>10}  {arrow}")

        er = data.get("engagement_rate")
        if er is not None:
            lines.append(f"  {'互动率':<16} {er:>9}%")

        videos = data.get("videos", {})
        ranked = videos.get("ranked", [])
        if ranked:
            cols = _detect_video_columns(ranked)
            display_cols = cols[:6]

            lines.append(f"\n  视频详情 (共 {len(ranked)} 条):")

            header_parts = [f"{'#':<3} {'标题':<30}"]
            for c in display_cols:
                header_parts.append(f"{_video_metric_label(c):>8}")
            lines.append(f"    {' '.join(header_parts)}")
            lines.append(f"    {'─' * (35 + 9 * len(display_cols))}")

            for i, v in enumerate(ranked[:10], 1):
                title = v.get("title", "?")[:28]
                is_hit = v in videos.get("hits", [])
                is_flop = v in videos.get("flops", [])
                marker = " 🔥" if is_hit else (" ⚠️" if is_flop else "")
                row_parts = [f"{i:<3} {title:<30}"]
                for c in display_cols:
                    val = v.get(c)
                    row_parts.append(f"{_format_number(val):>8}")
                lines.append(f"    {' '.join(row_parts)}{marker}")

    cross = _build_cross_platform_summary(analysis_result.get("platforms", {}))
    if cross:
        platform_names = list(analysis_result.get("platforms", {}).keys())
        lines.append(f"\n── 跨平台对比 ──")
        header = f"  {'指标':<12}"
        for p in platform_names:
            header += f" {p.upper():>12}"
        lines.append(header)
        lines.append(f"  {'─' * (14 + 13 * len(platform_names))}")
        for row in cross:
            row_str = f"  {row['metric']:<12}"
            for p in platform_names:
                row_str += f" {row['values'].get(p, '-'):>12}"
            lines.append(row_str)

    cadence = analysis_result.get("publish_cadence", {})
    if cadence.get("total_uploads", 0) > 0:
        lines.append(f"\n── 发布节奏 ──")
        lines.append(f"  周期内上传: {cadence['total_uploads']} 次"
                     f"（成功 {cadence.get('successful_uploads', 0)} / 失败 {cadence.get('failed_uploads', 0)}）")
        avg = cadence.get("avg_interval_days")
        if avg:
            lines.append(f"  平均发布间隔: {avg} 天")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def generate_report(
    analysis_result: dict,
    advice: dict,
    fmt: str = "md",
    save: bool = True,
    output_path: str | None = None,
    account: str = "default",
) -> tuple[str, str | None]:
    """生成报告并可选保存到文件。

    参数:
      fmt: "md" / "html" / "terminal"
      save: 是否保存到 reports 目录
      output_path: 自定义保存路径（覆盖默认 reports 目录）
      account: 账号名（用于隔离存储路径）

    返回 (报告内容字符串, 保存路径或 None)。
    """
    if fmt == "html":
        content = render_html(analysis_result, advice)
    elif fmt == "terminal":
        content = render_terminal(analysis_result, advice)
    else:
        content = render_markdown(analysis_result, advice)

    saved_path: str | None = None

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        saved_path = str(out)
        logger.info(f"📄 报告已保存: {saved_path}")
    elif save and fmt != "terminal":
        ext = "html" if fmt == "html" else "md"
        path = store.save_report(content, ext, account=account)
        saved_path = str(path)
        logger.info(f"📄 报告已保存: {saved_path}")

    return content, saved_path

"""数据采集层 — 通过 OpenCLI 适配器采集各平台创作者数据看板。

技术方案：
  调用 `opencli <平台> creator-stats [参数] --format json` 获取结构化数据。
  OpenCLI 负责浏览器操控、页面导航、Cookie 认证、DOM/API 数据提取。
  本模块只负责：调用命令 → 解析 JSON → 转换为统一格式。

支持的平台：
  - 有 creator-stats 适配器的平台（youtube, tiktok, instagram 等）
  - 有其他 stats 命令的平台（douyin 的 stats 命令）
  - 新平台只需在 ~/.opencli/clis/<平台>/ 下添加 JS 适配器即可
"""

import json
import logging
import re
import shutil
import subprocess

logger = logging.getLogger(__name__)

_OPENCLI_TIMEOUT = 120
_OPENCLI_TIMEOUT_YOUTUBE = 300

_COMMAND_MAP = {
    "youtube": {"command": "creator-stats", "positional": True},
    "tiktok": {"command": "creator-stats", "positional": False},
    "instagram": {"command": "creator-stats", "positional": False},
    "douyin": {"command": "stats", "positional": True},
}

_NUM_RE = re.compile(r"[\d,]+\.?\d*")


def _parse_number(text: str) -> float | None:
    """从文本中提取数字，支持 K/M/B/万/亿 后缀和逗号分隔。"""
    if not text:
        return None
    text = text.strip().replace("\n", "").replace("\u00a0", "")
    if text == "-" or text == "---":
        return None
    multiplier = 1
    lower = text.lower().rstrip("%")
    if lower.endswith("k"):
        multiplier = 1_000
        text = text[:-1]
    elif lower.endswith("m"):
        multiplier = 1_000_000
        text = text[:-1]
    elif lower.endswith("b"):
        multiplier = 1_000_000_000
        text = text[:-1]
    elif "万" in text:
        multiplier = 10_000
        text = text.replace("万", "")
    elif "亿" in text:
        multiplier = 100_000_000
        text = text.replace("亿", "")
    m = _NUM_RE.search(text)
    if m:
        try:
            return float(m.group().replace(",", "")) * multiplier
        except ValueError:
            return None
    return None


def _find_opencli() -> str | None:
    """查找 opencli 可执行文件路径。"""
    path = shutil.which("opencli")
    if path:
        return path
    for candidate in ("/usr/local/bin/opencli", "/opt/homebrew/bin/opencli"):
        if shutil.which(candidate):
            return candidate
    return None


_YT_CHANNEL_RE = re.compile(r"UC[\w-]{22}")


def _auto_detect_youtube_channel() -> str | None:
    """通过 Chrome 调试端口自动获取当前登录用户的 YouTube 频道 ID。

    检测策略（按优先级）:
      1. 扫描已打开的标签页 URL 提取 UCxxx
      2. 通过 CDP 主动导航到 studio.youtube.com，等待重定向后从 URL 提取
      3. 从 YouTube Studio 页面 DOM 提取 channel-id 属性
    """
    import urllib.request
    import urllib.error

    try:
        raw = urllib.request.urlopen("http://localhost:9222/json", timeout=5).read()
        tabs = json.loads(raw)
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        logger.debug("  YouTube 频道自动检测: 无法连接 Chrome 调试端口 9222")
        return None

    for tab in tabs:
        url = tab.get("url", "")
        if "studio.youtube.com" in url:
            m = _YT_CHANNEL_RE.search(url)
            if m:
                logger.debug(f"  从 YouTube Studio 标签页检测到频道")
                return m.group()

    for tab in tabs:
        url = tab.get("url", "")
        if "youtube.com" in url:
            m = _YT_CHANNEL_RE.search(url)
            if m:
                logger.debug(f"  从 YouTube 标签页检测到频道")
                return m.group()

    channel = _detect_youtube_channel_via_cdp(tabs)
    if channel:
        return channel

    logger.warning("  ⚠️ YouTube 频道自动检测失败: 未能从浏览器会话中获取频道 ID")
    return None


def _cdp_send(ws, method: str, params: dict | None = None, msg_id: int = 1) -> dict:
    """发送 CDP 命令并等待对应 id 的响应，跳过中间的事件推送。"""
    payload = {"id": msg_id, "method": method}
    if params:
        payload["params"] = params
    ws.send(json.dumps(payload))
    for _ in range(50):
        resp = json.loads(ws.recv())
        if resp.get("id") == msg_id:
            return resp
    return {}


def _detect_youtube_channel_via_cdp(tabs: list[dict]) -> str | None:
    """通过 CDP 新建标签页打开 YouTube Studio，等待重定向后提取频道 ID。

    YouTube Studio 在用户已登录时会重定向到 /channel/UCxxx/...，
    从重定向后的 URL 即可提取频道 ID。检测完成后自动关闭临时标签页。
    """
    import time
    import urllib.request
    import urllib.error

    try:
        import websocket
    except ImportError:
        logger.debug("  websocket-client 未安装，跳过 CDP 检测")
        return None

    tab_id = None
    ws = None
    channel_id = None

    try:
        logger.debug("  正在通过浏览器自动检测 YouTube 频道...")
        req = urllib.request.Request(
            "http://localhost:9222/json/new?https://studio.youtube.com",
            method="PUT",
        )
        raw = urllib.request.urlopen(req, timeout=10).read()
        new_tab = json.loads(raw)
        tab_id = new_tab.get("id")
        ws_url = new_tab.get("webSocketDebuggerUrl")
        if not ws_url:
            logger.debug("  新标签页缺少 webSocketDebuggerUrl")
            return None

        ws = websocket.create_connection(ws_url, timeout=15)

        for attempt in range(8):
            time.sleep(3)
            resp = _cdp_send(ws, "Runtime.evaluate",
                             {"expression": "window.location.href"}, msg_id=10 + attempt)
            url = resp.get("result", {}).get("result", {}).get("value", "")
            m = _YT_CHANNEL_RE.search(url)
            if m:
                channel_id = m.group()
                logger.debug(f"  从 YouTube Studio 重定向检测到频道")
                break

        if not channel_id:
            resp = _cdp_send(ws, "Runtime.evaluate", {
                "expression": (
                    "document.querySelector('[channel-id]')?.getAttribute('channel-id') || "
                    "document.querySelector('ytcp-entity-page-header')?.getAttribute('channel-id') || "
                    "''"
                )
            }, msg_id=20)
            val = resp.get("result", {}).get("result", {}).get("value", "")
            if val and _YT_CHANNEL_RE.match(val):
                channel_id = val
                logger.debug(f"  从 YouTube Studio DOM 检测到频道")
    except (urllib.error.URLError, OSError) as e:
        logger.debug(f"  CDP 新标签页创建失败: {e}")
    except Exception as e:
        logger.debug(f"  CDP 检测异常: {e}")
    finally:
        if ws:
            try:
                ws.close()
            except Exception:
                pass
        if tab_id:
            try:
                close_req = urllib.request.Request(
                    f"http://localhost:9222/json/close/{tab_id}", method="GET",
                )
                urllib.request.urlopen(close_req, timeout=5)
            except Exception:
                pass

    return channel_id


def _run_opencli(platform: str, account_arg: str | None) -> dict | None:
    """调用 opencli <平台> <命令> [参数] --format json 并返回解析后的 JSON。

    返回 None 表示命令失败或 opencli 不可用。
    """
    opencli = _find_opencli()
    if not opencli:
        logger.error("  ❌ 未找到 opencli 命令，请确认已安装: npm install -g @jackwener/opencli")
        return None

    spec = _COMMAND_MAP.get(platform)
    if not spec:
        spec = {"command": "creator-stats", "positional": bool(account_arg and account_arg is not True)}

    cmd = [opencli, platform, spec["command"]]
    if spec["positional"] and account_arg and account_arg is not True and str(account_arg).lower() != "true":
        cmd.append(str(account_arg))
    cmd.extend(["--format", "json"])

    timeout = _OPENCLI_TIMEOUT_YOUTUBE if platform == "youtube" else _OPENCLI_TIMEOUT
    safe_cmd = [c if not _YT_CHANNEL_RE.search(c) else "[CHANNEL_ID]" for c in cmd]
    logger.info(f"  🔧 执行: {' '.join(safe_cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 77:
            logger.error(f"  ❌ {platform}: 未登录目标网站（exit code 77）")
            return None
        if result.returncode == 69:
            logger.error(f"  ❌ {platform}: Browser Bridge 未连接（exit code 69），请运行 opencli doctor")
            return None
        if result.returncode != 0:
            stderr = result.stderr.strip()[:200] if result.stderr else ""
            logger.error(f"  ❌ {platform}: opencli 退出码 {result.returncode}  {stderr}")
            return None

        stdout = result.stdout.strip()
        if not stdout:
            logger.warning(f"  ⚠️ {platform}: opencli 返回空输出")
            return None

        return json.loads(stdout)
    except subprocess.TimeoutExpired:
        logger.error(f"  ❌ {platform}: opencli 超时 ({_OPENCLI_TIMEOUT}s)")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"  ❌ {platform}: JSON 解析失败: {e}")
        logger.debug(f"  原始输出前 500 字符: {result.stdout[:500] if result.stdout else '(空)'}")
        return None
    except Exception as e:
        logger.error(f"  ❌ {platform}: {e}")
        return None


def _normalize_opencli_output(platform: str, raw_data) -> dict:
    """将 opencli 的 JSON 输出转换为统一的内部格式。

    支持两种输出格式：
      旧格式 (flat):  [{metric, value, trend}, ...]
      新格式 (per-video): [{video, tab, metric, value}, ...]  ← YouTube 逐视频采集

    内部格式: {"account_metrics": {key: number}, "video_metrics": [...]}
    """
    rows = raw_data if isinstance(raw_data, list) else []
    if not rows:
        return {"account_metrics": {}, "video_metrics": [], "account_identity": {}, "collection_method": "opencli"}

    has_video_col = any(isinstance(r, dict) and "video" in r and "tab" in r for r in rows)
    if has_video_col:
        return _normalize_per_video_output(rows)
    return _normalize_flat_output(rows)


def _normalize_flat_output(rows: list) -> dict:
    """处理统一格式: [{metric, value, trend}, ...]

    支持分段：
      - 账号级指标（顶部，无分隔符前的行）
      - "--- Top Videos ---" / "--- 单帖数据 ---" 等分隔符后是视频/帖子级数据
      - "--- 近期内容汇总 ---" 后是汇总统计
      - "--- 分析数据 ---" 后是平台分析指标

    身份字段（用户名、账号类型等）不丢弃，存入 account_identity。
    """
    account_metrics = {}
    video_metrics = []
    account_identity = {}
    section = "account"

    _IDENTITY_METRICS = {
        "用户名 (username)": "username",
        "用户名": "username",
        "username": "username",
        "账号类型": "account_type",
        "info": "info",
    }

    _SKIP_METRICS = {"热门帖子", "人群画像", "粉丝画像", "性别分布", "年龄分布", "地区分布",
                     "粉丝性别", "粉丝年龄", "粉丝地区"}

    for row in rows:
        if not isinstance(row, dict):
            continue

        metric = row.get("metric", "")
        value = row.get("value", "")

        if "---" in str(metric):
            val_lower = str(value).lower()
            if "top video" in val_lower or "单帖" in val_lower or "top content" in val_lower:
                section = "videos"
            elif "近期内容" in val_lower or ("content" in val_lower and "top" not in val_lower):
                section = "summary"
            elif ("分析数据" in val_lower or "analytics" in val_lower
                  or "overview" in val_lower or "概览" in val_lower
                  or "viewers" in val_lower or "观众" in val_lower
                  or "followers" in val_lower or "粉丝" in val_lower):
                section = "analytics"
            else:
                section = "other"
            continue

        identity_key = _IDENTITY_METRICS.get(metric)
        if identity_key:
            account_identity[identity_key] = str(value).strip()
            continue

        if metric in _SKIP_METRICS:
            continue

        if section == "videos" and metric and value:
            entry = {"title": metric}
            kv_match = re.findall(r"(\w+)=(\d+)", str(value))
            if kv_match:
                for k, v in kv_match:
                    entry[k] = float(v)
            else:
                entry["views"] = _parse_number(str(value))
            video_metrics.append(entry)
            continue

        if metric and value:
            metric_key = _metric_to_key(metric)
            num_val = _parse_number(str(value))
            if num_val is not None:
                account_metrics[metric_key] = num_val

    return {
        "account_metrics": account_metrics,
        "video_metrics": video_metrics,
        "account_identity": account_identity,
        "collection_method": "opencli",
    }


def _normalize_per_video_output(rows: list) -> dict:
    """处理逐视频格式: [{video, tab, metric, value}, ...]

    将每个视频的 4 个标签页指标合并，同时聚合出 account_metrics（取所有视频总和/均值）。
    """
    from collections import OrderedDict

    videos_map: dict[str, dict] = OrderedDict()

    for row in rows:
        if not isinstance(row, dict):
            continue
        video_title = row.get("video", "")
        tab = row.get("tab", "")
        metric = row.get("metric", "")
        value = row.get("value", "")

        if not video_title or not metric or metric.startswith("_"):
            continue

        if video_title not in videos_map:
            videos_map[video_title] = {"title": video_title, "tabs": {}}

        vid = videos_map[video_title]
        if tab not in vid["tabs"]:
            vid["tabs"][tab] = {}

        metric_key = _metric_to_key(metric)
        num_val = _parse_number(str(value))
        if num_val is not None:
            vid["tabs"][tab][metric_key] = num_val

    video_metrics = []
    agg: dict[str, list[float]] = {}

    for title, vid in videos_map.items():
        flat = {}
        for _tab, metrics in vid["tabs"].items():
            flat.update(metrics)

        entry = {"title": title}
        entry.update(flat)
        video_metrics.append(entry)

        for k, v in flat.items():
            agg.setdefault(k, []).append(v)

    account_metrics = {}
    _SUM_KEYS = {"views", "watch_time_hours", "likes", "comments", "shares",
                 "impressions", "subscribers", "unique_viewers",
                 "returning_viewers", "new_viewers", "saves"}
    _AVG_KEYS = {"ctr", "avg_view_duration", "avg_percentage_viewed"}

    for k, vals in agg.items():
        if k in _SUM_KEYS:
            account_metrics[k] = sum(vals)
        elif k in _AVG_KEYS:
            account_metrics[k] = sum(vals) / len(vals) if vals else 0
        else:
            account_metrics[k] = sum(vals)

    account_identity = {}
    if video_metrics:
        first_title = video_metrics[0].get("title", "")
        if first_title:
            account_identity["channel_hint"] = first_title

    return {
        "account_metrics": account_metrics,
        "video_metrics": video_metrics,
        "account_identity": account_identity,
        "collection_method": "opencli",
    }


def _metric_to_key(metric_label: str) -> str:
    """将 opencli 输出的中英文指标名转为规范化的 key。"""
    mapping = {
        # ── YouTube API 拦截版 ──
        "播放量 (views)": "views",
        "观看时长-小时 (watch time hours)": "watch_time_hours",
        "观看时长 (watch time hours)": "watch_time_hours",
        "订阅变化 (subscribers)": "subscribers",
        "观看时长（小时） (watch_time_hours)": "watch_time_hours",
        "订阅人数 (subscribers)": "subscribers",
        "展示次数 (impressions)": "impressions",
        "展示点击率 (CTR)": "ctr",
        "唯一观看者 (unique viewers)": "unique_viewers",
        "平均观看时长 (avg view duration)": "avg_view_duration",
        # ── Instagram REST API 版 ──
        "粉丝数 (followers)": "followers",
        "关注数 (following)": "following",
        "帖子数 (posts)": "posts",
        "总点赞 (total likes)": "likes",
        "总评论 (total comments)": "comments",
        "总播放 (total plays)": "plays",
        "平均互动率 (engagement rate %)": "engagement_rate",
        "触达人数 (accounts reached)": "accounts_reached",
        "曝光量 (impressions)": "impressions",
        "互动 (interactions)": "interactions",
        "保存 (saves)": "saves",
        "Reels 播放 (reels plays)": "reels_plays",
        "主页访问 (profile visits)": "profile_visits",
        # ── TikTok Studio 版 ──
        "获赞总数 (hearts)": "hearts",
        "视频数 (videos)": "video_count",
        "观看次数 (views)": "views",
        "主页访问量 (profile_views)": "profile_views",
        "赞 (likes)": "likes",
        "评论 (comments)": "comments",
        "分享次数 (shares)": "shares",
        "预估奖励 (estimated_reward)": "estimated_reward",
        "新粉丝 (new_followers)": "new_followers",
        # ── TikTok Studio 4-tab 新增 ──
        "Video views (views)": "video_views",
        "Profile views (profile_views)": "profile_views",
        "Likes (likes)": "likes",
        "Comments (comments)": "comments",
        "Shares (shares)": "shares",
        "Est. rewards (estimated_reward)": "estimated_reward",
        "Total viewers (total_viewers)": "total_viewers",
        "New viewers (new_viewers)": "new_viewers",
        "Total followers (total_followers)": "total_followers",
        "Net followers (net_followers)": "net_followers",
        # ── 通用 / 旧格式 ──
        "点赞 (likes)": "likes",
        "评论 (comments)": "comments",
        "分享 (shares)": "shares",
        "收藏 (saves)": "saves",
        "视频播放量 (video views)": "video_views",
        "主页访问 (profile views)": "profile_views",
        "粉丝变化 (followers)": "followers",
        # ── YouTube 逐视频（中文 UI）──
        "观看次数": "views",
        "观看时长(小时)": "watch_time_hours",
        "订阅人数": "subscribers",
        "点赞次数": "likes",
        "评论": "comments",
        "分享次数": "shares",
        "保存到播放列表": "saves",
        "展示次数": "impressions",
        "展示点击率(%)": "ctr",
        "唯一观看者": "unique_viewers",
        "平均观看时长": "avg_view_duration",
        "平均观看百分比(%)": "avg_percentage_viewed",
        "回访观看者": "returning_viewers",
        "新观看者": "new_viewers",
        "非订阅者(%)": "non_subscriber_pct",
        # ── YouTube 逐视频（英文 UI）──
        "Views": "views",
        "Watch time (hours)": "watch_time_hours",
        "Subscribers": "subscribers",
        "Likes": "likes",
        "Comments": "comments",
        "Shares": "shares",
        "Impressions": "impressions",
        "CTR (%)": "ctr",
        "Avg view duration": "avg_view_duration",
        "Avg % viewed": "avg_percentage_viewed",
        "Unique viewers": "unique_viewers",
        "Returning viewers": "returning_viewers",
        "New viewers": "new_viewers",
    }
    normalized = mapping.get(metric_label)
    if normalized:
        return normalized
    key = metric_label.lower()
    key = re.sub(r"\s*\(.*?\)\s*", "", key)
    key = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", key)
    key = key.strip("_")
    return key or "unknown"


def collect_platform(platform: str, account_arg: str | None) -> dict:
    """采集单个平台的数据。

    YouTube 频道 ID 通过 Chrome 调试端口从 YouTube Studio 页面自动获取，
    本模块不缓存也不持久化频道 ID。

    返回统一格式 dict:
      {"account_metrics": {...}, "video_metrics": [...], "collection_method": "opencli"}
    或带 error 字段的 dict。
    """

    logger.info(f"📊 开始采集 {platform} 数据...")
    raw = _run_opencli(platform, account_arg)
    if raw is None:
        return {"error": f"opencli {platform} creator-stats 执行失败", "account_metrics": {}, "video_metrics": [], "account_identity": {}}

    result = _normalize_opencli_output(platform, raw)
    if not result["account_metrics"] and not result["video_metrics"]:
        logger.warning(f"  ⚠️ {platform}: 采集到 0 项指标，可能未登录或页面结构变化")

    return result


def run_collect(account_platforms: dict, **_kwargs) -> dict[str, dict]:
    """采集所有已配置平台的数据。供 CLI 调用。

    account_platforms 示例:
      {"youtube": "UCxxx", "tiktok": true, "instagram": true}

    YouTube 频道 ID 会自动检测（从上传历史/浏览器会话），无需用户手动提供。
    其他平台（TikTok / Instagram）仅需用户在 Chrome 中登录即可。

    返回 {"youtube": {...}, "tiktok": {...}, ...}
    """
    opencli = _find_opencli()
    if not opencli:
        logger.error("❌ 未找到 opencli，请安装: npm install -g @jackwener/opencli")
        return {}

    results = {}
    for platform, arg in account_platforms.items():
        if not arg and arg is not True:
            continue
        val_str = str(arg).strip().lower()
        if val_str in ("", "false"):
            continue

        explicit_arg = None
        if arg is not True and val_str != "true":
            explicit_arg = str(arg)

        try:
            data = collect_platform(platform, explicit_arg)
            if data.get("error"):
                logger.error(f"  ❌ {platform}: {data['error']}")
            else:
                logger.info(f"  ✅ {platform} 数据采集完成")
            results[platform] = data
        except Exception as e:
            logger.error(f"  ❌ {platform} 采集异常: {e}")
            results[platform] = {"error": str(e), "account_metrics": {}, "video_metrics": [], "account_identity": {}}

    if not results:
        logger.warning("  ⚠️ 未配置任何平台账号，无数据可采集")

    return results

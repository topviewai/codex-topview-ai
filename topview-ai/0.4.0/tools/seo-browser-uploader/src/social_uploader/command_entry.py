import argparse
import sys
import logging

from social_uploader.repair_engine import generate_run_id


def main():
    parser = argparse.ArgumentParser(
        prog='social-upload',
        description='社交媒体视频自动上传工具（TikTok / Instagram / YouTube）',
    )
    subparsers = parser.add_subparsers(dest='platform', required=True, help='目标平台')

    # --- 公共账号参数 ---
    _account_help = '使用指定账号上传（不传则用上次使用的账号）'

    # --- TikTok ---
    p_tk = subparsers.add_parser('tiktok', help='上传到 TikTok')
    p_tk.add_argument('--video', required=True, help='视频文件路径')
    p_tk.add_argument('--title', required=True, help='视频标题')
    p_tk.add_argument('--description', required=True, help='视频描述')
    p_tk.add_argument('--cover', default=None, help='封面图路径（可选，支持 jpg/png）')
    p_tk.add_argument('--no-publish', action='store_true', help='填好表单但不点发布')
    p_tk.add_argument('--resume-from', default=None, help='从指定步骤恢复执行')
    p_tk.add_argument('--profile', default=None, help='上传配置文件路径（JSON），不传则用默认配置')
    p_tk.add_argument('--schedule', default=None, help='定时发布时间（格式: "YYYY-MM-DD HH:MM"），不传则立即发布')
    p_tk.add_argument('--visibility', default=None, help='可见性: everyone / friends / only_me（默认 everyone）')
    p_tk.add_argument('--account', default=None, help=_account_help)

    # --- Instagram ---
    p_ig = subparsers.add_parser('instagram', help='上传到 Instagram')
    p_ig.add_argument('--video', required=True, help='视频文件路径')
    p_ig.add_argument('--caption', required=True, help='发布文案')
    p_ig.add_argument('--no-publish', action='store_true', help='填好表单但不点分享')
    p_ig.add_argument('--resume-from', default=None, help='从指定步骤恢复执行')
    p_ig.add_argument('--profile', default=None, help='上传配置文件路径（JSON），不传则用默认配置')
    p_ig.add_argument('--schedule', default=None, help='Instagram 不支持定时发布，传入会被自动忽略')
    p_ig.add_argument('--visibility', default=None, help='Instagram 不支持可见性设置，传入会被自动忽略')
    p_ig.add_argument('--account', default=None, help=_account_help)

    # --- YouTube ---
    p_yt = subparsers.add_parser('youtube', help='上传到 YouTube')
    p_yt.add_argument('--video', required=True, help='视频文件路径')
    p_yt.add_argument('--title', required=True, help='视频标题')
    p_yt.add_argument('--description', required=True, help='视频描述')
    p_yt.add_argument('--no-publish', action='store_true', help='填好表单但不点发布')
    p_yt.add_argument('--resume-from', default=None, help='从指定步骤恢复执行')
    p_yt.add_argument('--profile', default=None, help='上传配置文件路径（JSON），不传则用默认配置')
    p_yt.add_argument('--schedule', default=None, help='定时发布时间（格式: "YYYY-MM-DD HH:MM"），不传则立即发布')
    p_yt.add_argument('--visibility', default=None, help='可见性: public / unlisted / private（默认 public）')
    p_yt.add_argument('--account', default=None, help=_account_help)

    # --- Account 账号管理 ---
    p_acc = subparsers.add_parser('account', help='管理上传账号')
    acc_sub = p_acc.add_subparsers(dest='account_action', required=True, help='账号操作')
    acc_add = acc_sub.add_parser('add', help='添加新账号')
    acc_add.add_argument('name', help='账号名称')
    acc_add.add_argument('--login', action='store_true', help='创建后立即启动浏览器登录')
    acc_rm = acc_sub.add_parser('remove', help='删除账号')
    acc_rm.add_argument('name', help='账号名称')
    acc_rm.add_argument('--delete-data', action='store_true', help='同时删除 Chrome 数据目录')
    acc_sub.add_parser('list', help='列出所有账号')
    acc_login = acc_sub.add_parser('login', help='启动浏览器登录指定账号')
    acc_login.add_argument('name', nargs='?', default=None, help='账号名称（不传则用当前账号）')
    acc_login.add_argument('--debug', action='store_true', help='（已废弃，默认就带调试端口）')

    # --- Diag ---
    p_diag = subparsers.add_parser('diag', help='诊断：提取当前浏览器页面的精简 DOM')
    p_diag.add_argument('--area', default=None, help='目标区域 CSS 选择器（可选）')

    # --- Suggest Selectors ---
    p_suggest = subparsers.add_parser('suggest-selectors', help='从最近失败的 DOM 片段中推荐候选选择器')
    p_suggest.add_argument('--run-id', required=True, help='失败的 run_id（从 DIAG| 行获取）')

    # --- Fix Selector ---
    p_fix = subparsers.add_parser('fix-selector', help='安全地向 button_config.json 添加新选择器')
    p_fix.add_argument('--target', required=True, dest='target_platform', help='目标平台（youtube/tiktok/instagram）')
    p_fix.add_argument('--key', required=True, help='选择器 key（如 post_button）')
    p_fix.add_argument('--selector', required=True, help='新的 DrissionPage 选择器字符串')

    # --- Suggest Patterns ---
    p_sp = subparsers.add_parser('suggest-patterns', help='从最近失败的 DOM 快照中推荐候选状态信号')
    p_sp.add_argument('--run-id', required=True, help='失败的 run_id（从 DIAG| 行获取）')

    # --- Fix Pattern ---
    p_fp = subparsers.add_parser('fix-pattern', help='安全地向 state_patterns.json 添加新状态信号')
    p_fp.add_argument('--target', required=True, dest='target_platform', help='目标平台（youtube/tiktok/instagram）')
    p_fp.add_argument('--step', required=True, help='步骤名（如 confirm / wait_upload）')
    p_fp.add_argument('--signal', required=True, help='信号类型（如 success_signals / error_signals）')
    p_fp.add_argument('--value', required=True, help='新的选择器字符串（如 "text:Published"）')

    # --- Show Recipe ---
    p_sr = subparsers.add_parser('show-recipe', help='查看交互配方的当前配置')
    p_sr.add_argument('--target', required=True, dest='target_platform', help='目标平台（youtube/tiktok/instagram）')
    p_sr.add_argument('--recipe', required=True, help='配方名（如 schedule_recipe）')

    # --- Fix Recipe ---
    p_fr = subparsers.add_parser('fix-recipe', help='更新交互配方中某一步的选择器')
    p_fr.add_argument('--target', required=True, dest='target_platform', help='目标平台（youtube/tiktok/instagram）')
    p_fr.add_argument('--recipe', required=True, help='配方名（如 schedule_recipe）')
    p_fr.add_argument('--step', required=True, help='步骤 ID（如 set_date）')
    p_fr.add_argument('--selector', required=True, help='新的 CSS 选择器')

    # --- Restart Browser ---
    p_rb = subparsers.add_parser('restart-browser', help='终止调试端口上的 Chrome，用于切换账号后重新连接')
    p_rb.add_argument('--port', type=int, default=9222, help='调试端口号（默认 9222）')

    # --- Monitor 数据监控 ---
    p_mon = subparsers.add_parser('monitor', help='社交媒体数据监控与分析（通过 OpenCLI 采集）')
    mon_sub = p_mon.add_subparsers(dest='monitor_action', required=True, help='监控操作')

    mon_config = mon_sub.add_parser('config', help='配置账号的平台映射')
    mon_config.add_argument('--account', default='default', help='账号名称（默认 default）')
    mon_config.add_argument('--youtube', default=None, help='YouTube: true/false（频道 ID 由浏览器实时获取）')
    mon_config.add_argument('--tiktok', default=None, help='TikTok: true/false')
    mon_config.add_argument('--instagram', default=None, help='Instagram: true/false')
    mon_config.add_argument('--douyin', default=None, help='抖音: true/false')

    _platforms_help = (
        '只对指定平台执行（逗号分隔，可选 youtube/tiktok/instagram/douyin），'
        '不传则覆盖账号所有已配置平台。例: --platforms tiktok 或 --platforms youtube,tiktok'
    )

    mon_collect = mon_sub.add_parser('collect', help='采集各平台数据看板（通过 opencli）')
    mon_collect.add_argument('--account', default='default', help='账号名称（默认 default）')
    mon_collect.add_argument('--no-report', action='store_true', help='只采集不生成报告')
    mon_collect.add_argument('--format', default='terminal', choices=['md', 'html', 'terminal'], help='报告格式（默认 terminal）')
    mon_collect.add_argument('--period', type=int, default=28, help='分析周期天数（默认 28）')
    mon_collect.add_argument('--platforms', default=None, help=_platforms_help)

    mon_report = mon_sub.add_parser('report', help='生成数据分析报告')
    mon_report.add_argument('--format', default='md', choices=['md', 'html', 'terminal'], help='输出格式（默认 md）')
    mon_report.add_argument('--period', type=int, default=28, help='分析周期天数（默认 28）')
    mon_report.add_argument('--account', default='default', help='账号名称（默认 default）')
    mon_report.add_argument('--output', default=None, help='自定义报告保存路径')
    mon_report.add_argument('--platforms', default=None, help=_platforms_help)

    mon_run = mon_sub.add_parser('run', help='一键采集 + 生成报告')
    mon_run.add_argument('--format', default='md', choices=['md', 'html', 'terminal'], help='输出格式（默认 md）')
    mon_run.add_argument('--period', type=int, default=28, help='分析周期天数（默认 28）')
    mon_run.add_argument('--account', default='default', help='账号名称（默认 default）')
    mon_run.add_argument('--output', default=None, help='自定义报告保存路径')
    mon_run.add_argument('--platforms', default=None, help=_platforms_help)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
    )

    # --- 数据监控分支 ---
    if args.platform == 'monitor':
        _handle_monitor(args)
        sys.exit(0)

    # --- 账号管理分支 ---
    if args.platform == 'account':
        from social_uploader.account_manager import (
            add_account, remove_account, list_accounts,
            launch_chrome_for_account, launch_chrome_for_login, get_data_dir,
        )  # launch_chrome_for_login 保留以向后兼容
        if args.account_action == 'add':
            ok, msg = add_account(args.name)
            if ok:
                print(f"✅ 账号 '{args.name}' 已创建")
                print(f"   数据目录: {msg}")
                if args.login:
                    ok2, msg2 = launch_chrome_for_login(args.name)
                    print(msg2)
            else:
                print(f"❌ {msg}")
            sys.exit(0 if ok else 1)
        elif args.account_action == 'remove':
            ok, msg = remove_account(args.name, delete_data=args.delete_data)
            print(msg)
            sys.exit(0 if ok else 1)
        elif args.account_action == 'list':
            accounts = list_accounts()
            if not accounts:
                print("暂无账号，用 `social-upload account add <名称>` 创建")
            else:
                for acc in accounts:
                    marker = " ← 当前" if acc["is_last_used"] else ""
                    print(f"  {'●' if acc['is_last_used'] else '○'} {acc['name']}{marker}")
                    print(f"    创建时间: {acc['created_at']}")
            sys.exit(0)
        elif args.account_action == 'login':
            ok, msg = launch_chrome_for_account(args.name)
            print(msg)
            sys.exit(0 if ok else 1)

    run_id = generate_run_id()
    resume_from = getattr(args, 'resume_from', None)
    profile_path = getattr(args, 'profile', None)
    account = getattr(args, 'account', None)

    profile = None
    if args.platform in ('tiktok', 'instagram', 'youtube'):
        from social_uploader.tools.upload_profile import load_profile
        profile = load_profile(profile_path)

        schedule_cli = getattr(args, 'schedule', None)
        visibility_cli = getattr(args, 'visibility', None)
        if schedule_cli or visibility_cli:
            if args.platform not in profile:
                profile[args.platform] = {}
            if schedule_cli:
                profile[args.platform]["schedule"] = schedule_cli
            if visibility_cli:
                profile[args.platform]["visibility"] = visibility_cli

    if args.platform == 'tiktok':
        from social_uploader.uploaders.tiktok import upload_tiktok
        success = upload_tiktok(args.video, args.title, args.description, args.no_publish,
                                cover_path=args.cover, run_id=run_id, resume_from=resume_from,
                                profile=profile, account=account)
    elif args.platform == 'instagram':
        from social_uploader.uploaders.instagram import upload_instagram
        success = upload_instagram(args.video, args.caption, args.no_publish,
                                   run_id=run_id, resume_from=resume_from,
                                   profile=profile, account=account)
    elif args.platform == 'youtube':
        from social_uploader.uploaders.youtube import upload_youtube
        success = upload_youtube(args.video, args.title, args.description, args.no_publish,
                                 run_id=run_id, resume_from=resume_from,
                                 profile=profile, account=account)
    elif args.platform == 'diag':
        from social_uploader.tools.browser_manager import connect_browser
        from social_uploader.repair_engine import get_dom_snippet
        _, work, _, _ = connect_browser(new_window=False)
        print(get_dom_snippet(work, area_selector=args.area))
        sys.exit(0)
    elif args.platform == 'suggest-selectors':
        from social_uploader.repair_engine import suggest_selectors
        print(suggest_selectors(args.run_id))
        sys.exit(0)
    elif args.platform == 'fix-selector':
        from social_uploader.tools.element_finder import add_selector
        ok, msg = add_selector(args.target_platform, args.key, args.selector)
        print(msg)
        sys.exit(0 if ok else 1)
    elif args.platform == 'suggest-patterns':
        from social_uploader.repair_engine import suggest_patterns
        print(suggest_patterns(args.run_id))
        sys.exit(0)
    elif args.platform == 'fix-pattern':
        from social_uploader.tools.pattern_checker import add_pattern
        ok, msg = add_pattern(args.target_platform, args.step, args.signal, args.value)
        print(msg)
        sys.exit(0 if ok else 1)
    elif args.platform == 'restart-browser':
        from social_uploader.tools.browser_manager import kill_browser
        killed, msg = kill_browser(port=args.port)
        print(msg)
        if killed:
            print(f"\n✅ Chrome 已关闭。请重新启动调试浏览器：")
            if sys.platform == 'darwin':
                print(f"   bash scripts/start_chrome_debug.sh")
            elif sys.platform == 'win32':
                print(f"   scripts\\start_chrome_debug.bat")
            else:
                print(f"   google-chrome --remote-debugging-port={args.port}")
            print(f"\n   启动后在调试浏览器中登录目标平台账号，然后重新执行上传命令。")
        else:
            print(f"\n💡 如果浏览器仍在运行，请手动关闭所有 Chrome 窗口后重新启动。")
        sys.exit(0)

    elif args.platform == 'show-recipe':
        from social_uploader.tools.recipe_runner import show_recipe
        print(show_recipe(args.target_platform, args.recipe))
        sys.exit(0)
    elif args.platform == 'fix-recipe':
        from social_uploader.tools.recipe_runner import fix_recipe_step
        ok, msg = fix_recipe_step(args.target_platform, args.recipe, args.step, args.selector)
        print(msg)
        sys.exit(0 if ok else 1)
    else:
        parser.print_help()
        sys.exit(1)

    sys.exit(0 if success else 1)


def _verify_login_before_collect(platforms: dict) -> dict[str, bool]:
    """在采集前逐平台验证登录态，返回各平台登录状态。

    未登录的平台会打印醒目提示并从采集列表中排除。
    如果全部平台都未登录，直接退出并要求用户先登录。
    """
    import shutil
    import subprocess as _sp

    opencli = shutil.which("opencli")
    if not opencli:
        for candidate in ("/usr/local/bin/opencli", "/opt/homebrew/bin/opencli"):
            if shutil.which(candidate):
                opencli = candidate
                break
    if not opencli:
        print("❌ 未找到 opencli，跳过登录验证")
        return {p: True for p in platforms}

    print("🔍 正在验证各平台登录状态...")
    login_status = {}
    for platform in platforms:
        if not platforms[platform]:
            continue
        if platform == "youtube":
            import urllib.request, urllib.error, json as _json
            try:
                raw = urllib.request.urlopen("http://localhost:9222/json", timeout=3).read()
                tabs = _json.loads(raw)
                has_yt = any("youtube.com" in t.get("url", "") for t in tabs)
                login_status[platform] = has_yt
                if has_yt:
                    print(f"  ✅ {platform}: 检测到 YouTube 标签页")
                else:
                    print(f"  ⚠️ {platform}: 未检测到 YouTube 标签页，采集时将自动导航")
                    login_status[platform] = True
            except Exception:
                login_status[platform] = True
                print(f"  ⚠️ {platform}: 无法检测浏览器状态，跳过预检")
            continue
        cmd_map = {
            "tiktok": [opencli, "tiktok", "creator-stats", "-f", "json"],
            "instagram": [opencli, "instagram", "creator-stats", "-f", "json"],
        }
        cmd = cmd_map.get(platform)
        if not cmd:
            login_status[platform] = True
            continue
        try:
            result = _sp.run(cmd, capture_output=True, text=True, timeout=30)
            output = (result.stdout + result.stderr).lower()
            if result.returncode == 0 and "not logged in" not in output and "missing" not in output:
                login_status[platform] = True
                print(f"  ✅ {platform}: 已登录")
            else:
                login_status[platform] = False
                print(f"  ❌ {platform}: 未登录")
        except Exception:
            login_status[platform] = True
            print(f"  ⚠️ {platform}: 验证超时，跳过")

    logged_in = [p for p, ok in login_status.items() if ok]
    not_logged_in = [p for p, ok in login_status.items() if not ok]

    if not logged_in and not_logged_in:
        print("\n" + "=" * 50)
        print("⛔ 所有平台均未登录，无法采集数据。")
        print("请先在调试浏览器中登录各平台账号：")
        print("  1. YouTube Studio → studio.youtube.com")
        print("  2. TikTok Studio → tiktok.com/tiktokstudio")
        print("  3. Instagram → instagram.com")
        print("=" * 50)
        sys.exit(1)

    if not_logged_in:
        print(f"\n⚠️ 以下平台未登录，将跳过采集: {', '.join(not_logged_in)}")
        print(f"   继续采集已登录的平台: {', '.join(logged_in)}\n")

    return login_status


def _format_identity(platform: str, identity: dict) -> str:
    """从 account_identity 中提取可读的账号标识。"""
    username = identity.get("username", "")
    if username:
        prefix = "@" if not username.startswith("@") else ""
        return f"用户: {prefix}{username}"
    channel_hint = identity.get("channel_hint", "")
    if channel_hint and platform == "youtube":
        return f"频道首视频: {channel_hint[:30]}"
    return ""


_PLATFORM_ALIAS = {
    "yt": "youtube",
    "youtube": "youtube",
    "tk": "tiktok",
    "tiktok": "tiktok",
    "ig": "instagram",
    "insta": "instagram",
    "instagram": "instagram",
    "dy": "douyin",
    "douyin": "douyin",
    "抖音": "douyin",
}


def _parse_platforms_filter(raw: str | None) -> list[str] | None:
    """把 --platforms 的字符串解析为规范化的平台列表。

    返回值语义:
      - None             ：用户没传 --platforms，沿用账号所有已配置平台
      - []               ：用户传了但全是无法识别的别名（调用方应直接退出）
      - ["xxx", ...]     ：用户传了并解析出至少一个合法平台
    """
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    cleaned: list[str] = []
    for token in raw.replace(";", ",").split(","):
        key = token.strip().lower()
        if not key:
            continue
        norm = _PLATFORM_ALIAS.get(key)
        if not norm:
            print(f"⚠️ 忽略未知平台: {token.strip()}（支持: youtube/tiktok/instagram/douyin）")
            continue
        if norm not in cleaned:
            cleaned.append(norm)
    return cleaned


def _apply_platforms_filter(platforms: dict, only: list[str] | None) -> dict:
    """根据 --platforms 过滤 account_platforms 字典。

    only 为 None 时原样返回；否则只保留交集，并对未配置但被显式要求的平台
    临时补一个 True，让后续 collector 仍能尝试采集（适合用户登录了但还
    没跑过 monitor config 的场景）。
    """
    if not only:
        return platforms
    result: dict = {}
    for p in only:
        if p in platforms:
            val = platforms[p]
            if val:
                result[p] = val
            else:
                print(f"⚠️ 平台 '{p}' 在账号配置中已关闭，--platforms 将临时启用本次采集")
                result[p] = True
        else:
            print(f"ℹ️ 平台 '{p}' 未在账号配置中，--platforms 将临时启用本次采集")
            result[p] = True
    return result


def _handle_monitor(args):
    """处理 monitor 子命令。"""
    action = args.monitor_action

    _PLATFORM_ARGS = ['youtube', 'tiktok', 'instagram', 'douyin']

    if action == 'config':
        from social_uploader.analytics.store import get_account_platforms, set_account_platforms
        current = get_account_platforms(args.account)
        updated = dict(current)

        has_update = False
        for p in _PLATFORM_ARGS:
            val = getattr(args, p, None)
            if val is not None:
                updated[p] = val.lower() == 'true'
                has_update = True

        if not has_update:
            if current:
                print(f"📋 账号 '{args.account}' 的平台映射:")
                for k, v in current.items():
                    display = '已启用' if v else '(未配置)'
                    print(f"   {k}: {display}")
            else:
                print(f"⚠️ 账号 '{args.account}' 尚未配置平台映射")
                print(f"\n用法示例:")
                print(f"  social-upload monitor config --youtube true --tiktok true --instagram true")
            return

        set_account_platforms(args.account, updated)
        print(f"✅ 账号 '{args.account}' 的平台映射已更新:")
        for k, v in updated.items():
            display = v if isinstance(v, str) and v else ('已启用' if v else '(未配置)')
            print(f"   {k}: {display}")

    elif action == 'collect':
        from social_uploader.analytics.store import (
            get_account_platforms, save_snapshot, append_history,
            load_latest_snapshot, load_previous_snapshot,
        )
        from social_uploader.analytics.collector import run_collect

        platforms = get_account_platforms(args.account)
        only = _parse_platforms_filter(getattr(args, 'platforms', None))
        if only == []:
            print("❌ --platforms 参数中没有任何可识别的平台，已退出")
            sys.exit(1)
        if not platforms and not only:
            print(f"❌ 账号 '{args.account}' 未配置平台映射，请先运行:")
            print(f"   social-upload monitor config --youtube true --tiktok true --instagram true")
            sys.exit(1)

        platforms = _apply_platforms_filter(platforms or {}, only)
        if not platforms:
            print("❌ 经过 --platforms 过滤后没有可采集的平台，已退出")
            sys.exit(1)

        if only:
            print(f"🎯 仅采集指定平台: {', '.join(platforms.keys())}")

        login_status = _verify_login_before_collect(platforms)
        verified_platforms = {p: v for p, v in platforms.items() if login_status.get(p, True)}

        print(f"\n🔄 开始采集数据（账号: {args.account}，通过 OpenCLI）...")
        results = run_collect(verified_platforms)

        success_count = 0
        for platform, data in results.items():
            if data.get("error"):
                print(f"  ❌ {platform}: {data['error']}")
            else:
                metric_count = len(data.get("account_metrics", {}))
                video_count = len(data.get("video_metrics", []))
                save_snapshot(platform, data, account=args.account)
                append_history({
                    "action": "collect",
                    "platform": platform,
                    "metrics_count": metric_count,
                    "videos_count": video_count,
                }, account=args.account)
                identity = data.get("account_identity", {})
                identity_label = _format_identity(platform, identity)
                if identity_label:
                    print(f"  ✅ {platform}: {metric_count} 项指标, {video_count} 条视频数据 ({identity_label})")
                else:
                    print(f"  ✅ {platform}: {metric_count} 项指标, {video_count} 条视频数据")
                success_count += 1

                top_metrics = data.get("account_metrics", {})
                if top_metrics:
                    summary_parts = []
                    for key in ("views", "likes", "comments", "followers", "new_followers"):
                        val = top_metrics.get(key)
                        if val is not None:
                            from social_uploader.analytics.reporter import _format_number
                            summary_parts.append(f"{key}={_format_number(val)}")
                    if summary_parts:
                        print(f"     📈 {', '.join(summary_parts[:5])}")

        print(f"\n🎉 数据采集完成（{success_count}/{len(results)} 个平台成功）")

        collected_identities = []
        for platform, data in results.items():
            if not data.get("error"):
                identity = data.get("account_identity", {})
                label = _format_identity(platform, identity)
                collected_identities.append((platform, label or "（未检测到账号名）"))
        if collected_identities:
            print("\n" + "=" * 50)
            print("⚠️  请确认以下采集的账号是否正确：")
            print("-" * 50)
            for plat, label in collected_identities:
                print(f"  {plat}: {label}")
            print("=" * 50)
            print("如果账号不正确，请在浏览器中切换账号后重新采集。\n")

        if not getattr(args, 'no_report', False) and success_count > 0:
            from social_uploader.analytics.analyzer import analyze
            from social_uploader.analytics.advisor import generate_advice
            from social_uploader.analytics.reporter import generate_report

            current_snapshots = {}
            previous_snapshots = {}
            for platform in verified_platforms:
                snap = load_latest_snapshot(platform, account=args.account)
                if snap:
                    current_snapshots[platform] = snap
                    prev = load_previous_snapshot(platform, account=args.account)
                    if prev:
                        previous_snapshots[platform] = prev

            if current_snapshots:
                fmt = getattr(args, 'format', 'terminal')
                period = getattr(args, 'period', 28)
                print(f"\n📊 正在分析数据（周期: {period} 天）...")
                analysis = analyze(current_snapshots, previous_snapshots, period_days=period, account=args.account)

                print("📝 正在基于规则生成创作建议...")
                advice = generate_advice(analysis)

                content, saved_path = generate_report(analysis, advice, fmt=fmt, account=args.account)
                print(content)
                if saved_path:
                    print(f"\n📄 报告文件: {saved_path}")

    elif action == 'report':
        from social_uploader.analytics.store import (
            get_account_platforms, load_latest_snapshot, load_previous_snapshot,
        )
        from social_uploader.analytics.analyzer import analyze
        from social_uploader.analytics.advisor import generate_advice
        from social_uploader.analytics.reporter import generate_report

        platforms = get_account_platforms(args.account)
        only = _parse_platforms_filter(getattr(args, 'platforms', None))
        if only == []:
            print("❌ --platforms 参数中没有任何可识别的平台，已退出")
            sys.exit(1)
        all_platform_keys = list(platforms.keys()) if platforms else _PLATFORM_ARGS
        if only:
            all_platform_keys = [p for p in only if p in all_platform_keys] or list(only)
            print(f"🎯 仅基于以下平台生成报告: {', '.join(all_platform_keys)}")

        current_snapshots = {}
        previous_snapshots = {}
        for platform in all_platform_keys:
            snap = load_latest_snapshot(platform, account=args.account)
            if snap:
                current_snapshots[platform] = snap
                prev = load_previous_snapshot(platform, account=args.account)
                if prev:
                    previous_snapshots[platform] = prev

        if not current_snapshots:
            print("❌ 没有找到采集数据，请先运行:")
            print("   social-upload monitor collect")
            sys.exit(1)

        print(f"📊 正在分析数据（周期: {args.period} 天）...")
        analysis = analyze(current_snapshots, previous_snapshots, period_days=args.period, account=args.account)

        print("📝 正在基于规则生成创作建议...")
        advice = generate_advice(analysis)

        fmt = getattr(args, 'format', 'md')
        output_path = getattr(args, 'output', None)
        content, saved_path = generate_report(analysis, advice, fmt=fmt, output_path=output_path, account=args.account)

        print(content)
        if saved_path:
            print(f"\n📄 报告文件: {saved_path}")

    elif action == 'run':
        from social_uploader.analytics.store import (
            get_account_platforms, save_snapshot, append_history,
            load_latest_snapshot, load_previous_snapshot,
        )
        from social_uploader.analytics.collector import run_collect
        from social_uploader.analytics.analyzer import analyze
        from social_uploader.analytics.advisor import generate_advice
        from social_uploader.analytics.reporter import generate_report

        platforms = get_account_platforms(args.account)
        only = _parse_platforms_filter(getattr(args, 'platforms', None))
        if only == []:
            print("❌ --platforms 参数中没有任何可识别的平台，已退出")
            sys.exit(1)
        if not platforms and not only:
            print(f"❌ 账号 '{args.account}' 未配置平台映射，请先运行:")
            print(f"   social-upload monitor config --youtube true --tiktok true --instagram true")
            sys.exit(1)

        platforms = _apply_platforms_filter(platforms or {}, only)
        if not platforms:
            print("❌ 经过 --platforms 过滤后没有可采集的平台，已退出")
            sys.exit(1)

        if only:
            print(f"🎯 仅采集指定平台: {', '.join(platforms.keys())}")

        login_status = _verify_login_before_collect(platforms)
        verified_platforms = {p: v for p, v in platforms.items() if login_status.get(p, True)}

        print(f"\n🔄 开始采集数据（账号: {args.account}，通过 OpenCLI）...")
        results = run_collect(verified_platforms)

        for platform, data in results.items():
            if data.get("error"):
                print(f"  ❌ {platform}: {data['error']}")
            else:
                save_snapshot(platform, data, account=args.account)
                append_history({
                    "action": "collect",
                    "platform": platform,
                    "metrics_count": len(data.get("account_metrics", {})),
                    "videos_count": len(data.get("video_metrics", [])),
                }, account=args.account)
                identity = data.get("account_identity", {})
                identity_label = _format_identity(platform, identity)
                suffix = f" ({identity_label})" if identity_label else ""
                print(f"  ✅ {platform}: 采集完成{suffix}")

        all_platform_keys = list(verified_platforms.keys())
        current_snapshots = {}
        previous_snapshots = {}
        for platform in all_platform_keys:
            snap = load_latest_snapshot(platform, account=args.account)
            if snap:
                current_snapshots[platform] = snap
                prev = load_previous_snapshot(platform, account=args.account)
                if prev:
                    previous_snapshots[platform] = prev

        if not current_snapshots:
            print("❌ 所有平台采集失败，无法生成报告")
            sys.exit(1)

        print(f"\n📊 正在分析数据（周期: {args.period} 天）...")
        analysis = analyze(current_snapshots, previous_snapshots, period_days=args.period, account=args.account)

        print("📝 正在基于规则生成创作建议...")
        advice = generate_advice(analysis)

        fmt = getattr(args, 'format', 'md')
        output_path = getattr(args, 'output', None)
        content, saved_path = generate_report(analysis, advice, fmt=fmt, output_path=output_path, account=args.account)

        print(content)
        if saved_path:
            print(f"\n📄 报告文件: {saved_path}")
        print("\n🎉 采集 + 报告一键完成")


if __name__ == '__main__':
    main()

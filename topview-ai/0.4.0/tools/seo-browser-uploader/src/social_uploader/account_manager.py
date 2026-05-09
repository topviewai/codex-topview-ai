"""多账号管理 — 每个账号对应独立的 Chrome 用户数据目录，登录态互不干扰。

存储结构：
  ~/.social_uploader/accounts.json   — 账号注册表
  ~/.social_uploader/chrome_profiles/<name>/  — 各账号的 Chrome 数据目录

向后兼容：
  旧版唯一数据目录 ~/.chrome-social-upload 自动迁移为 "default" 账号。
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_BASE_DIR = Path.home() / ".social_uploader"
_PROFILES_DIR = _BASE_DIR / "chrome_profiles"
_REGISTRY_PATH = _BASE_DIR / "accounts.json"
_LEGACY_DATA_DIR = Path.home() / ".chrome-social-upload"

DEFAULT_ACCOUNT = "default"


def _ensure_dirs():
    _BASE_DIR.mkdir(parents=True, exist_ok=True)
    _PROFILES_DIR.mkdir(parents=True, exist_ok=True)


def _load_registry() -> dict:
    _ensure_dirs()
    if _REGISTRY_PATH.exists():
        return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    return {"accounts": {}, "last_used": None}


def _save_registry(reg: dict):
    _ensure_dirs()
    _REGISTRY_PATH.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def _migrate_legacy():
    """将旧版 ~/.chrome-social-upload 迁移为 default 账号（仅执行一次）。"""
    reg = _load_registry()
    if DEFAULT_ACCOUNT in reg["accounts"]:
        return
    target = _PROFILES_DIR / DEFAULT_ACCOUNT
    if _LEGACY_DATA_DIR.exists() and not target.exists():
        shutil.copytree(str(_LEGACY_DATA_DIR), str(target), symlinks=True)
        logger.info(f"  📦 已将旧数据目录迁移为 '{DEFAULT_ACCOUNT}' 账号")
    elif not target.exists():
        target.mkdir(parents=True, exist_ok=True)
    reg["accounts"][DEFAULT_ACCOUNT] = {
        "data_dir": str(target),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if reg["last_used"] is None:
        reg["last_used"] = DEFAULT_ACCOUNT
    _save_registry(reg)


def get_data_dir(account: str | None = None) -> str:
    """获取指定账号的 Chrome 数据目录路径。

    account=None 时使用上次使用的账号，都没有则自动迁移/创建 default。
    """
    _migrate_legacy()
    reg = _load_registry()

    if account is None:
        account = reg.get("last_used") or DEFAULT_ACCOUNT

    if account not in reg["accounts"]:
        raise ValueError(
            f"账号 '{account}' 不存在。可用账号: {', '.join(reg['accounts'].keys()) or '(无)'}\n"
            f"用 `social-upload account add {account}` 创建。"
        )

    reg["last_used"] = account
    _save_registry(reg)
    return reg["accounts"][account]["data_dir"]


def add_account(name: str) -> tuple[bool, str]:
    """注册新账号。返回 (成功, 消息)。"""
    _migrate_legacy()
    reg = _load_registry()
    if name in reg["accounts"]:
        return False, f"账号 '{name}' 已存在"

    data_dir = _PROFILES_DIR / name
    data_dir.mkdir(parents=True, exist_ok=True)
    reg["accounts"][name] = {
        "data_dir": str(data_dir),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_registry(reg)
    return True, str(data_dir)


def remove_account(name: str, delete_data: bool = False) -> tuple[bool, str]:
    """删除账号注册。delete_data=True 时同时删除 Chrome 数据目录。"""
    reg = _load_registry()
    if name not in reg["accounts"]:
        return False, f"账号 '{name}' 不存在"
    if name == DEFAULT_ACCOUNT:
        return False, "不能删除 default 账号"

    entry = reg["accounts"].pop(name)
    if reg.get("last_used") == name:
        reg["last_used"] = DEFAULT_ACCOUNT
    _save_registry(reg)

    if delete_data:
        data_dir = Path(entry["data_dir"])
        if data_dir.exists():
            shutil.rmtree(str(data_dir), ignore_errors=True)
            return True, f"已删除账号 '{name}' 及其数据目录"
    return True, f"已删除账号 '{name}'（数据目录已保留）"


def list_accounts() -> list[dict]:
    """返回所有账号信息列表。"""
    _migrate_legacy()
    reg = _load_registry()
    result = []
    for name, info in reg["accounts"].items():
        result.append({
            "name": name,
            "data_dir": info["data_dir"],
            "created_at": info.get("created_at", ""),
            "is_last_used": name == reg.get("last_used"),
        })
    return result


def _find_chrome_path() -> str:
    """定位 Chrome 可执行文件路径。"""
    if sys.platform == "darwin":
        return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    for p in [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]:
        if os.path.exists(p):
            return p
    return os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe")


def launch_chrome_for_login(account: str | None = None) -> tuple[bool, str]:
    """向后兼容入口，直接调用 launch_chrome_for_account。"""
    return launch_chrome_for_account(account)


def _is_existing_chrome_compatible(port: int, expected_data_dir: str) -> bool:
    """检测端口上已运行的 Chrome 是否就是目标账号的调试 Chrome（user-data-dir 匹配）。

    匹配则可直接复用，避免误杀已经登录好的 Chrome 实例。
    """
    try:
        result = subprocess.run(
            ["lsof", "-nP", "-iTCP:" + str(port), "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=5,
        )
        pids = [int(p.strip()) for p in (result.stdout or "").splitlines() if p.strip()]
    except Exception:
        return False

    if not pids:
        return False

    expected_marker = expected_data_dir.rstrip("/")
    for pid in pids:
        try:
            ps_out = subprocess.run(
                ["ps", "-o", "command=", "-p", str(pid)],
                capture_output=True, text=True, timeout=3,
            ).stdout or ""
            if expected_marker in ps_out:
                return True
        except Exception:
            continue
    return False


def launch_chrome_for_account(account: str | None = None, port: int = 9222) -> tuple[bool, str]:
    """为指定账号启动 Chrome 调试浏览器，供用户登录和数据采集。

    安全策略（防止误杀日常 Chrome 或已登录的调试 Chrome）：
      1. 如果 9222 端口已有 Chrome 在跑，且其 user-data-dir 与目标账号匹配
         → 直接复用，不杀不重启，登录态保留
      2. 如果 9222 端口已有 Chrome 在跑，但 user-data-dir 不匹配（说明是其他账号或日常 Chrome）
         → kill_browser 内部的安全护栏会拒绝终止；返回提示要求用户手动处理
      3. 如果 9222 端口空闲 → 正常启动新的调试 Chrome
    """
    data_dir = get_data_dir(account)
    account = account or _load_registry().get("last_used", DEFAULT_ACCOUNT)
    chrome_path = _find_chrome_path()

    if _is_existing_chrome_compatible(port, data_dir):
        logger.info(f"  ✅ 端口 {port} 上已有匹配的调试 Chrome 在运行，直接复用")
        return True, (
            f"✅ 检测到账号 '{account}' 的调试 Chrome 已在运行 (端口 {port})\n"
            f"   数据目录: {data_dir}\n"
            f"   未做任何重启操作，登录状态保留。\n"
            f"   如需切换账号，请先运行: social-upload restart-browser --port {port}"
        )

    killed, kill_msg = _kill_existing_chrome_safely(port)
    if not killed and "不属于本项目" in kill_msg:
        return False, (
            f"⚠️ 端口 {port} 已被一个**非本项目**的 Chrome 实例占用，无法自动启动\n"
            f"   {kill_msg}\n"
            f"   建议操作：\n"
            f"     1. 手动关闭那个 Chrome 实例（不影响你日常使用的 Chrome）\n"
            f"     2. 或换一个调试端口启动："
            f" social-upload account login --port 9223"
        )

    try:
        subprocess.Popen(
            [
                chrome_path,
                f"--remote-debugging-port={port}",
                f"--user-data-dir={data_dir}",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--excludeSwitches=enable-automation",
                "--remote-allow-origins=*",
                "--no-first-run",
                "--no-default-browser-check",
                "--restore-last-session",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(3)
        return True, (
            f"✅ 已为账号 '{account}' 启动 Chrome (端口 {port})\n"
            f"   数据目录: {data_dir}\n"
            f"   请在浏览器中登录 TikTok / Instagram / YouTube，登录完成后告诉我。"
        )
    except FileNotFoundError:
        return False, f"❌ 未找到 Chrome，请确认安装路径: {chrome_path}"
    except Exception as e:
        return False, f"❌ 启动 Chrome 失败: {e}"


def _kill_existing_chrome_safely(port: int) -> tuple[bool, str]:
    """带安全护栏的 Chrome 终止：只杀本项目的调试 Chrome。"""
    from social_uploader.tools.browser_manager import kill_browser
    killed, msg = kill_browser(port=port)
    if killed:
        logger.info(f"  🔄 已关闭旧的本项目调试 Chrome (端口 {port})")
        time.sleep(1)
    return killed, msg

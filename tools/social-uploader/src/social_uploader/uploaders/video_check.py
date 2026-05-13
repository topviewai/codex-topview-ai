import os
import logging
import struct

logger = logging.getLogger(__name__)

VALID_VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.3gp'}
MIN_VIDEO_SIZE_BYTES = 10_000

_H264_MARKERS = {b'avc1', b'avc3', b'avcC'}
_H265_MARKERS = {b'hev1', b'hvc1', b'hvcC'}
_MPEG4P2_MARKERS = {b'mp4v'}

_PLATFORM_CODEC_REQUIREMENTS = {
    "instagram": {"required": "H.264", "markers": _H264_MARKERS},
}


def detect_video_codec(video_path: str) -> str:
    """通过扫描 MP4 box 中的编码标记检测视频编码。

    同时扫描文件头部和尾部（各 1MB）以覆盖 moov 在文件末尾的情况。
    返回 'h264'/'h265'/'mpeg4'/'unknown'。
    """
    try:
        file_size = os.path.getsize(video_path)
        scan_size = 1024 * 1024
        with open(video_path, "rb") as f:
            head = f.read(min(file_size, scan_size))
            if file_size > scan_size:
                f.seek(max(0, file_size - scan_size))
                tail = f.read()
            else:
                tail = b""
    except Exception:
        return "unknown"

    data = head + tail
    if any(m in data for m in _H264_MARKERS):
        return "h264"
    if any(m in data for m in _H265_MARKERS):
        return "h265"
    if b'mp4v' in data:
        return "mpeg4"
    return "unknown"


def check_codec_compatibility(video_path: str, platform: str) -> tuple[bool, str]:
    """检查视频编码是否与目标平台兼容。返回 (compatible, warning_msg)。"""
    req = _PLATFORM_CODEC_REQUIREMENTS.get(platform)
    if not req:
        return True, ""

    codec = detect_video_codec(video_path)
    if codec == "unknown":
        return True, ""

    if codec == "h264":
        return True, ""

    required = req["required"]
    codec_name = {"h265": "H.265/HEVC", "mpeg4": "MPEG-4 Part 2"}.get(codec, codec)
    return False, (
        f"视频编码为 {codec_name}，{platform.title()} 要求 {required}。"
        f"该视频可能被平台静默拒绝。请使用 H.264 编码的视频。"
    )


def validate_video_file(video_path, platform=None):
    """上传前预校验视频文件，返回 (ok, error_msg)。

    platform 可选，传入时额外检查编码兼容性（不兼容仅警告不阻断）。
    """
    if not os.path.exists(video_path):
        return False, f"文件不存在: {video_path}"
    ext = os.path.splitext(video_path)[1].lower()
    if ext not in VALID_VIDEO_EXTENSIONS:
        return False, f"不支持的视频格式 '{ext}'，支持: {', '.join(sorted(VALID_VIDEO_EXTENSIONS))}"
    file_size = os.path.getsize(video_path)
    if file_size < MIN_VIDEO_SIZE_BYTES:
        return False, f"文件过小 ({file_size} bytes)，可能不是有效视频"

    if platform:
        compat, warn = check_codec_compatibility(video_path, platform)
        if not compat:
            logger.warning(f"⚠️ 编码警告: {warn}")

    return True, ""


def log_login_error(platform):
    """统一的未登录错误输出"""
    logger.error(f"\n❌ 检测到 {platform} 未登录！请在浏览器中手动完成登录后重新执行。")
    logger.warning("⚠️ 安全提示：本工具不会处理您的账号密码，请自行在浏览器中访问对应平台完成登录。")


_LOGIN_SIGNALS = {
    "tiktok": ["accounts.tiktok.com", "/login", "login-modal"],
    "instagram": ["accounts.instagram.com", "/accounts/login"],
    "youtube": ["accounts.google.com", "/signin"],
}


def quick_login_check(page, platform):
    """快速检查当前页面是否处于已登录状态。

    比各平台 login 步骤更前置——在导航到目标页之前调用，
    若检测到登录页面 URL 特征则立即终止，节省后续流程的时间。

    返回 (logged_in: bool, detail: str)。
    """
    try:
        url = (page.url or "").lower()
    except Exception:
        return True, "无法获取 URL，跳过预检"

    signals = _LOGIN_SIGNALS.get(platform, [])
    for signal in signals:
        if signal.lower() in url:
            return False, f"URL 包含登录信号 '{signal}'"
    return True, "ok"

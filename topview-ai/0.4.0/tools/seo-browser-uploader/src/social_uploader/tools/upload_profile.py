"""
上传配置文件加载器

职责：加载、验证、合并用户的上传配置（profile）。
上传脚本通过 profile 获取可配置项的值，而非写死在代码里。

配置优先级：用户 profile > 平台默认值 > common 默认值
"""

import json
import os
import logging
import copy

logger = logging.getLogger(__name__)

_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_PROFILE_PATH = os.path.join(_DIR, '..', 'profiles', 'default.json')


def _deep_merge(base, override):
    """递归合并两个字典，override 覆盖 base 的同名字段。"""
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def load_profile(profile_path=None):
    """
    加载上传配置。

    - profile_path=None → 返回默认配置（行为和改动前完全一致）
    - profile_path=路径 → 加载用户配置，与默认配置合并（用户的覆盖默认的）

    返回完整的 profile 字典。
    """
    with open(_DEFAULT_PROFILE_PATH, 'r', encoding='utf-8') as f:
        default = json.load(f)

    if profile_path is None:
        return default

    if not os.path.exists(profile_path):
        logger.error(f"配置文件不存在: {profile_path}")
        raise FileNotFoundError(f"Profile not found: {profile_path}")

    with open(profile_path, 'r', encoding='utf-8') as f:
        user_profile = json.load(f)

    merged = _deep_merge(default, user_profile)

    known_top_keys = {"common", "tiktok", "instagram", "youtube"}
    unknown = set(user_profile.keys()) - known_top_keys
    if unknown:
        logger.warning(f"⚠️ 配置文件中有未识别的顶层字段: {unknown}，已忽略")

    return merged


def get_platform_config(profile, platform):
    """
    获取某个平台的完整配置。

    合并逻辑：common 作为基础 → 平台特定配置覆盖 common 的同名字段。
    例如 common.visibility="public" 但 youtube.visibility="unlisted" → 最终 visibility="unlisted"

    返回一个扁平字典，上传脚本直接用 config["字段名"] 取值。
    """
    common = profile.get("common", {})
    platform_specific = profile.get(platform, {})
    return _deep_merge(common, platform_specific)


_PLATFORM_CONSTRAINTS = [
    {
        "platform": "instagram",
        "check": lambda c: c.get("schedule") is not None,
        "message": "Instagram 不支持定时发布，已自动移除，视频将立即发布",
        "strip_keys": ["schedule"],
    },
    {
        "platform": "instagram",
        "check": lambda c: c.get("visibility") is not None,
        "message": "Instagram 不支持可见性设置，已自动移除",
        "strip_keys": ["visibility"],
    },
    {
        "platform": "tiktok",
        "check": lambda c: c.get("visibility") == "only_me" and c.get("schedule") is not None,
        "message": "TikTok 仅自己可见的视频无法定时发布，已自动移除定时设置，视频将立即发布",
        "strip_keys": ["schedule"],
    },
]


def validate_platform_config(platform, config):
    """校验平台配置，自动移除不兼容的选项并返回警告列表。

    只拦截"危险的静默忽略"——即不拦截会导致用户实际损失的场景
    （例如用户以为视频已定时但实际立即发布）。
    不维护全量支持矩阵，避免新增配置项时被误杀。

    返回 (config, warnings)，config 已就地修正，warnings 为字符串列表。
    """
    warnings = []
    for rule in _PLATFORM_CONSTRAINTS:
        if rule["platform"] != platform:
            continue
        if rule["check"](config):
            warnings.append(rule["message"])
            for key in rule["strip_keys"]:
                config[key] = None
    return config, warnings

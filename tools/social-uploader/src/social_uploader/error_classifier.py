"""自动修复 - 错误分类：决定哪些错误 AI 能自己修，哪些要通知用户

【这个文件负责什么】
定义所有错误类型和对应的处理方式：
- agent_fix：AI 可以自己修（比如按钮名字变了）
- notify_user：需要用户介入（比如没登录）
- wait_retry：等一会儿再试（比如频率限制）
- escalate_user：搞不定，告诉用户（未知错误）

【你可能要改的地方】
- ERROR_TYPES 字典：增删错误类型或调整处理策略
"""

ERROR_TYPES = {
    "selector_not_found": "agent_fix",
    "element_stale":      "agent_fix",
    "intercepted_click":  "agent_fix",
    "timeout":            "notify_user",
    "file_rejected":      "notify_user",
    "state_mismatch":     "agent_fix",
    "recipe_step_failed": "agent_fix",
    "visibility_failed":  "agent_fix",
    "dialog_not_open":    "wait_retry",
    "login_required":     "notify_user",
    "captcha_detected":   "notify_user",
    "platform_unavailable": "wait_retry",
    "rate_limit":         "wait_retry",
    "unknown":            "escalate_user",
}


def classify_error(error_code):
    """返回错误码对应的处理策略标签。"""
    return ERROR_TYPES.get(error_code, "escalate_user")


def is_agent_fixable(error_code):
    """判断该错误类型是否可由 Agent 自主修复。"""
    return classify_error(error_code) == "agent_fix"

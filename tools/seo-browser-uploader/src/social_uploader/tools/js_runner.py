"""DrissionPage.run_js 的 IIFE 返回值 helper。

# ⚠️ 这是一个针对 DrissionPage 4.1.x 的兼容补丁。

## 背景

DrissionPage 的 `page.run_js(script)` 内部会把不识别为 js 函数的脚本包成
    function(){<code>}
然后通过 CDP `Runtime.callFunctionOn` 执行。`is_js_func()` 只在
`script.strip().startswith('function')` **且** `endswith('}')` 时才不包装。

对于 IIFE 形式的脚本：
    (function(){ ... return X; })();
两种坑：

1. **直接传** — wrap 后变成 `function(){(function(){...return X;})();}`，
   外层没 return，**Python 端拿到 None**，IIFE 的返回值丢失。

2. **手工加 `"return " + iife_js` 前缀** — 看似能解决，但当 iife_js 字符串
   开头有换行（多行常量字符串通常如此），wrap 后变成：
        function(){return
        (function(){...return X;})();}
   JavaScript 的 **ASI（Automatic Semicolon Insertion）** 规则规定：
   `return` 关键字与下一个 token 之间不能有 LineTerminator，否则自动补分号
   → 实际执行的是 `return; (function(){...})();`，IIFE 表达式被丢弃。
   **Python 端依然拿到 None**。实测验证。

## 解决

用 `var __r = IIFE; return __r;` 缓存中间结果再 return。`var` 后接换行
不受 ASI 限制（var 声明可以跨行），且无论 IIFE 字符串前后有多少空白/换行
都能稳定工作。

## 使用

    from social_uploader.tools.js_runner import run_iife
    result = run_iife(page, _SOME_IIFE_JS)
    result = run_iife(page, _IIFE_WITH_PARAM, element)  # 参数透传
"""

import logging

logger = logging.getLogger(__name__)


def run_iife(page_or_ele, iife_js: str, *args, timeout=None):
    """对 IIFE 形式 `(function(){...return X;})();` 的 JS 字符串安全取得返回值。

    Args:
        page_or_ele: DrissionPage page / element / shadow_root 对象（任何有 run_js 方法的）。
        iife_js: 完整 IIFE 表达式字符串。末尾分号和空白会被自动 strip。
        *args: 透传给 IIFE 内部的 arguments[0..n]（DrissionPage 原生支持）。
        timeout: 透传给 page.run_js 的 timeout 参数。

    Returns:
        IIFE 实际返回的值。
    """
    body = iife_js.strip().rstrip(";").rstrip()
    wrapped = f"var __dp_iife_r = {body}; return __dp_iife_r;"
    if timeout is not None:
        return page_or_ele.run_js(wrapped, *args, timeout=timeout)
    return page_or_ele.run_js(wrapped, *args)

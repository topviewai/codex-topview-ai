"""自动修复 - 核心模块：日志记录 + 页面快照 + 修复推荐

【这个文件负责什么】
1. 脚本每一步执行后记录"成功/失败"日志
2. 失败时给页面"拍快照"（提取所有按钮信息）
3. 根据快照分析哪个按钮可能是目标，推荐修复命令

【你可能要改的地方】
- STEP_KEYWORDS 字典：定义每种按钮"长什么样"（关键词匹配）
- suggest_selectors() 函数：修复推荐的输出格式
- _generate_selectors_for_element()：从按钮信息生成选择器的规则
"""

import json
import logging
import os
import sys
import time
import string
import random
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_SNIPPET_CHARS = 1500
_LOG_DIR = Path.home() / ".social_uploader"


def generate_run_id():
    """生成 8 位随机 run_id。"""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=8))


def _ensure_log_dir():
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_step(step, status, **kwargs):
    """输出一行 JSON 到 stderr（供 Agent 解析），同时保留 emoji 日志到 stdout。

    成功示例: {"step":"navigate","status":"ok","time_s":0.8}
    失败示例: {"step":"find_element","status":"fail","error":"selector_not_found",...}
    """
    record = {"step": step, "status": status, **kwargs}
    print(json.dumps(record, ensure_ascii=False), file=sys.stderr)

    if status == "ok":
        logger.info(f"  ✅ [{step}] 完成" + (f" ({kwargs.get('detail', '')})" if kwargs.get("detail") else ""))
    elif status == "fail":
        err = kwargs.get("error", "unknown")
        logger.error(f"  ❌ [{step}] 失败 — {err}")


def log_diag_line(run_id, platform, step, error, **hints):
    """输出 DIAG| 索引行到 stdout，供 Agent 检测触发修复。

    当 error=recipe_step_failed 时，额外输出 HINT| 行帮助 Agent 推理修复方案。
    """
    diag_parts = [f"DIAG|run_id={run_id}|platform={platform}|step={step}|error={error}"]
    for k, v in hints.items():
        diag_parts[0] += f"|{k}={v}"
    print(diag_parts[0])

    if error == "recipe_step_failed":
        failed_step = hints.get("failed_step", "")
        semantic_hint = hints.get("semantic_hint", "")
        recipe_key = hints.get("recipe_key", "schedule_recipe")
        if semantic_hint:
            print(f"HINT|该步骤目标：{semantic_hint}")
        if failed_step:
            print(f"HINT|修复命令模板：social-upload fix-recipe --target {platform} --recipe {recipe_key} --step {failed_step} --selector \"新选择器\"")
        print(f"HINT|DOM 快照已保存：~/.social_uploader/detail_{run_id}.jsonl")


def write_summary(run_id, platform, step, error, url, **extra):
    """追加一条到 ~/.social_uploader/summary.jsonl（< 500 字符）。"""
    _ensure_log_dir()
    record = {
        "run_id": run_id,
        "platform": platform,
        "failed_at": step,
        "error": error,
        "url": url,
        "detail_file": f"detail_{run_id}.jsonl",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        **extra,
    }
    line = json.dumps(record, ensure_ascii=False)
    with (_LOG_DIR / "summary.jsonl").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_success(run_id, platform, elapsed_s=0):
    """追加一条成功记录到 ~/.social_uploader/summary.jsonl。

    与 write_summary（失败记录）共享同一文件，通过 status 字段区分。
    使成功率统计成为可能：success_count / total_count。
    """
    _ensure_log_dir()
    record = {
        "run_id": run_id,
        "platform": platform,
        "status": "success",
        "elapsed_s": elapsed_s,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    line = json.dumps(record, ensure_ascii=False)
    with (_LOG_DIR / "summary.jsonl").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_detail(run_id, step, error, **context):
    """写入 ~/.social_uploader/detail_{run_id}.jsonl，含 DOM snippet 等上下文。"""
    _ensure_log_dir()
    record = {"step": step, "error": error, **context}
    line = json.dumps(record, ensure_ascii=False)
    with (_LOG_DIR / f"detail_{run_id}.jsonl").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# ⚠️ DrissionPage.run_js 会把脚本包成 `function(){<代码>}` 执行，
#    所以必须用顶层 return；严禁外层再裹 (function(){...})() IIFE，
#    否则外层函数不 return，结果在 Python 端永远是 None（实测验证）。
#    参数通过 %s / %d 模板硬编码到 JS 字面量。
_DOM_EXTRACT_JS = """
var areaSelector = %s;
var maxChars = %d;
var root = document;
if (areaSelector) {
    var area = document.querySelector(areaSelector);
    if (area) root = area;
}

var result = [];

var pageMeta = {_page: true, title: document.title || '', url: location.href};
var h1 = document.querySelector('h1');
if (h1) pageMeta.h1 = (h1.textContent || '').trim().substring(0, 60);
var alert = document.querySelector('[role="alert"],[role="status"]');
if (alert) pageMeta.alert = (alert.textContent || '').trim().substring(0, 80);
result.push(pageMeta);

var diagTags = 'h1,h2,h3,[role="alert"],[role="status"],[role="dialog"]';
var diagEls = root.querySelectorAll(diagTags);
for (var d = 0; d < diagEls.length && d < 5; d++) {
    var de = diagEls[d];
    var dr = de.getBoundingClientRect();
    if (dr.width === 0 && dr.height === 0) continue;
    var dObj = {tag: de.tagName.toLowerCase(), _diag: true};
    var dRole = de.getAttribute('role');
    if (dRole) dObj.role = dRole;
    var dTxt = (de.textContent || '').trim();
    if (dTxt) dObj.text = dTxt.substring(0, 60);
    result.push(dObj);
}

var tags = 'button,input,a,select,textarea,[role="button"],[contenteditable],[data-e2e],svg[aria-label]';
var els = root.querySelectorAll(tags);
var keep = ['id','class','name','type','role','aria-label','data-e2e','placeholder','aria-checked','aria-disabled','href'];
for (var i = 0; i < els.length; i++) {
    var el = els[i];
    var rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) continue;
    var obj = {tag: el.tagName.toLowerCase()};
    for (var k = 0; k < keep.length; k++) {
        var v = el.getAttribute(keep[k]);
        if (v) {
            if (keep[k] === 'class') {
                v = v.split(/\\s+/).slice(0, 3).join(' ');
            }
            obj[keep[k]] = v;
        }
    }
    var txt = (el.textContent || '').trim();
    if (txt && txt.length > 0) {
        obj.text = txt.substring(0, 15);
    }
    result.push(obj);
}
var out = JSON.stringify(result);
if (out.length > maxChars) {
    out = out.substring(0, maxChars - 14) + '...[truncated]';
}
return out;
"""


def get_dom_snippet(page, area_selector=None, max_chars=MAX_SNIPPET_CHARS):
    """提取当前页面精简 DOM，返回 JSON 字符串（硬限 max_chars）。

    第一条是页面元信息（title/url/h1/alert），随后是诊断元素（h1-h3/alert/dialog），
    最后是交互元素的关键属性 + textContent。
    """
    area_arg = f'"{area_selector}"' if area_selector else "null"
    js = _DOM_EXTRACT_JS % (area_arg, max_chars)
    try:
        raw = page.run_js(js)
        if not raw:
            return "[]"
        result = str(raw)
        if len(result) > max_chars:
            result = result[:max_chars - 14] + "...[truncated]"
        return result
    except Exception as e:
        return json.dumps({"error": str(e)[:200]}, ensure_ascii=False)


STEP_KEYWORDS = {
    "post_button":      ["post", "publish", "发布", "submit"],
    "upload_icon":      ["upload", "上传", "create", "创建"],
    "upload_dialog":    ["upload", "上传"],
    "upload_menu_item": ["upload video", "上传视频"],
    "file_input":       ["file", "input", "type"],
    "caption_box":      ["caption", "text", "write", "contenteditable", "textbox", "描述", "标题"],
    "title_box":        ["title", "标题"],
    "desc_box":         ["description", "描述", "tell viewers"],
    "create_button":    ["create", "new post", "新帖", "创建"],
    "share_button":     ["share", "分享"],
    "next_button":      ["next", "下一步"],
    "done_button":      ["done", "完成", "publish", "发布"],
    "select_from_computer": ["select", "computer", "从电脑", "从设备"],
}


def _generate_selectors_for_element(el):
    """为单个 DOM 元素生成所有可能的 DrissionPage 格式选择器，按优先级排列。"""
    candidates = []
    if el.get("data-e2e"):
        candidates.append(f'@data-e2e={el["data-e2e"]}')
    if el.get("id"):
        candidates.append(f'@id={el["id"]}')
    if el.get("aria-label"):
        candidates.append(f'@aria-label={el["aria-label"]}')
    if el.get("name"):
        candidates.append(f'@name={el["name"]}')
    if el.get("text") and len(el["text"].strip()) >= 2:
        candidates.append(f'text:{el["text"].strip()}')
    if el.get("role"):
        tag = el.get("tag", "*")
        candidates.append(f'xpath://{tag}[@role="{el["role"]}"]')
    if el.get("type") and el.get("tag") == "input":
        candidates.append(f'xpath://input[@type="{el["type"]}"]')
    if el.get("placeholder"):
        candidates.append(f'@placeholder={el["placeholder"]}')
    return candidates


def _element_matches_step(el, step):
    """判断一个 DOM 元素是否语义上匹配某个 step 的目标。"""
    keywords = STEP_KEYWORDS.get(step, [])
    if not keywords:
        return False
    searchable = " ".join([
        el.get("text", ""), el.get("aria-label", ""),
        el.get("data-e2e", ""), el.get("id", ""),
        el.get("name", ""), el.get("role", ""),
        el.get("type", ""), el.get("placeholder", ""),
    ]).lower()
    return any(kw.lower() in searchable for kw in keywords)


def suggest_selectors(run_id):
    """读取 detail 文件，从 DOM 片段中提取候选选择器，输出完整 fix-selector 命令。"""
    summary_path = _LOG_DIR / "summary.jsonl"
    if not summary_path.exists():
        return "ERROR: summary.jsonl 不存在，没有失败记录"

    last_line = summary_path.read_text(encoding="utf-8").strip().split("\n")[-1]
    try:
        summary = json.loads(last_line)
    except Exception:
        return "ERROR: summary.jsonl 最后一行解析失败"

    if summary.get("run_id") != run_id:
        return f"ERROR: run_id 不匹配 (期望 {run_id}, 实际 {summary.get('run_id')})"

    platform = summary.get("platform", "unknown")
    step = summary.get("failed_at", "unknown")
    error = summary.get("error", "unknown")
    # selectors_tried 是 report_failure 传入的按钮配置 key（如 "post_button"），
    # 与 STEP_KEYWORDS 的 key 对应；step 是上传步骤名（如 "publish"），两者不同。
    # 可能包含逗号分隔的多个 key（如 "file_input, select_from_computer"）。
    raw_keys = summary.get("selectors_tried", step)
    button_keys = [k.strip().split("(")[0].strip() for k in raw_keys.split(",")]

    if error != "selector_not_found":
        return f"STEP: {step}\nPLATFORM: {platform}\nERROR: {error}\nNO_FIX: 此错误类型不支持自动修复选择器，请通知用户处理"

    detail_path = _LOG_DIR / f"detail_{run_id}.jsonl"
    if not detail_path.exists():
        return f"STEP: {step}\nPLATFORM: {platform}\nNO_CANDIDATES: detail 文件不存在"

    last_detail = detail_path.read_text(encoding="utf-8").strip().split("\n")[-1]
    try:
        detail = json.loads(last_detail)
    except Exception:
        return f"STEP: {step}\nPLATFORM: {platform}\nNO_CANDIDATES: detail 文件解析失败"

    dom_raw = detail.get("dom_snippet", "[]")
    try:
        if isinstance(dom_raw, str):
            clean = dom_raw
            if clean.endswith("...[truncated]"):
                last_bracket = clean.rfind("]")
                if last_bracket > 0:
                    clean = clean[:last_bracket + 1]
            elements = json.loads(clean)
        else:
            elements = dom_raw
    except Exception:
        elements = []

    if not elements:
        return f"STEP: {step}\nPLATFORM: {platform}\nNO_CANDIDATES: DOM 片段为空或解析失败"

    def _matches_any_key(el):
        return any(_element_matches_step(el, bk) for bk in button_keys)

    matched = [(el, _generate_selectors_for_element(el)) for el in elements
               if _matches_any_key(el) and _generate_selectors_for_element(el)]

    if not matched:
        return f"STEP: {step}\nPLATFORM: {platform}\nNO_CANDIDATES: DOM 中未找到匹配 \"{', '.join(button_keys)}\" 语义的元素"

    primary_key = button_keys[0]
    lines = [f"STEP: {step}", f"PLATFORM: {platform}", "RUN_ONE:"]
    idx = 1
    for el, sels in matched:
        tag = el.get("tag", "?")
        text = el.get("text", "")[:15]
        label = f"<{tag}>{text}</{tag}>" if text else f"<{tag}>"
        for sel in sels[:2]:
            lines.append(f'  {idx}. social-upload fix-selector --target {platform} --key {primary_key} --selector "{sel}"    # {label}')
            idx += 1
            if idx > 8:
                break
        if idx > 8:
            break

    return "\n".join(lines)


def suggest_patterns(run_id):
    """读取 detail 文件，从 DOM 快照的 _page/_diag 条目中推荐可作为状态信号的文本。

    用于 state_mismatch 错误时，帮助 agent 找到新的状态检测文案。
    """
    summary_path = _LOG_DIR / "summary.jsonl"
    if not summary_path.exists():
        return "ERROR: summary.jsonl 不存在，没有失败记录"

    last_line = summary_path.read_text(encoding="utf-8").strip().split("\n")[-1]
    try:
        summary = json.loads(last_line)
    except Exception:
        return "ERROR: summary.jsonl 最后一行解析失败"

    if summary.get("run_id") != run_id:
        return f"ERROR: run_id 不匹配 (期望 {run_id}, 实际 {summary.get('run_id')})"

    platform = summary.get("platform", "unknown")
    step = summary.get("failed_at", "unknown")
    error = summary.get("error", "unknown")

    if error not in ("state_mismatch", "timeout"):
        return f"STEP: {step}\nPLATFORM: {platform}\nERROR: {error}\nNO_FIX: 此错误类型不适用 fix-pattern，请用 suggest-selectors 或通知用户"

    detail_path = _LOG_DIR / f"detail_{run_id}.jsonl"
    if not detail_path.exists():
        return f"STEP: {step}\nPLATFORM: {platform}\nNO_CANDIDATES: detail 文件不存在"

    last_detail = detail_path.read_text(encoding="utf-8").strip().split("\n")[-1]
    try:
        detail = json.loads(last_detail)
    except Exception:
        return f"STEP: {step}\nPLATFORM: {platform}\nNO_CANDIDATES: detail 文件解析失败"

    dom_raw = detail.get("dom_snippet", "[]")
    try:
        if isinstance(dom_raw, str):
            clean = dom_raw
            if clean.endswith("...[truncated]"):
                last_bracket = clean.rfind("]")
                if last_bracket > 0:
                    clean = clean[:last_bracket + 1]
            elements = json.loads(clean)
        else:
            elements = dom_raw
    except Exception:
        elements = []

    if not elements:
        return f"STEP: {step}\nPLATFORM: {platform}\nNO_CANDIDATES: DOM 片段为空或解析失败"

    lines = [f"STEP: {step}", f"PLATFORM: {platform}", f"ERROR: {error}", ""]

    page_meta = [e for e in elements if isinstance(e, dict) and e.get("_page")]
    diag_items = [e for e in elements if isinstance(e, dict) and e.get("_diag")]

    if page_meta:
        pm = page_meta[0]
        lines.append("PAGE_META:")
        lines.append(f"  title: {pm.get('title', '')}")
        lines.append(f"  url: {pm.get('url', '')}")
        if pm.get("h1"):
            lines.append(f"  h1: {pm['h1']}")
        if pm.get("alert"):
            lines.append(f"  alert: {pm['alert']}")
        lines.append("")

    if diag_items:
        lines.append("DIAG_ELEMENTS:")
        for d in diag_items[:5]:
            tag = d.get("tag", "?")
            text = d.get("text", "")
            role = d.get("role", "")
            desc = f"<{tag}"
            if role:
                desc += f' role="{role}"'
            desc += f">{text}</{tag}>"
            lines.append(f"  - {desc}")
        lines.append("")

    text_candidates = []
    for e in elements:
        if not isinstance(e, dict):
            continue
        if e.get("_page") or e.get("_diag"):
            text = e.get("text") or e.get("h1") or e.get("alert") or ""
        else:
            text = e.get("text", "")
        if text and len(text.strip()) >= 3:
            text_candidates.append(text.strip())

    seen = set()
    unique_texts = []
    for t in text_candidates:
        if t not in seen:
            seen.add(t)
            unique_texts.append(t)

    if unique_texts:
        lines.append("CANDIDATE_TEXTS:")
        idx = 1
        for t in unique_texts[:10]:
            lines.append(f'  {idx}. social-upload fix-pattern --target {platform} --step {step} --signal success_signals --value "text:{t}"')
            idx += 1
        lines.append("")
        lines.append("NOTE: 请根据页面语义选择合适的信号类型（success_signals / error_signals / ready_signals 等）")
    else:
        lines.append("NO_CANDIDATES: DOM 中未找到可用作状态信号的文本")

    return "\n".join(lines)


def safe_page_url(page, default="page_disconnected"):
    """安全获取 page.url，避免 PageDisconnectedError 导致调用方崩溃。"""
    try:
        return page.url or default
    except Exception:
        return default


def report_failure(page, run_id, platform, step, error, url, **extra):
    """一站式失败报告：写 summary + detail + 输出 DIAG 行。

    自动提取 DOM snippet 以便事后诊断。
    使用 error_classifier 标注该错误是否可自动修复。
    """
    from social_uploader.error_classifier import classify_error

    strategy = classify_error(error)
    if strategy == "agent_fix":
        logger.info(f"  🔧 错误类型 [{error}] 可自动修复")
    elif strategy == "notify_user":
        logger.warning(f"  👤 错误类型 [{error}] 需要用户介入")
    elif strategy == "wait_retry":
        logger.info(f"  ⏳ 错误类型 [{error}] 建议等待后重试")
    else:
        logger.warning(f"  ⚠️ 错误类型 [{error}] 需要人工判断")

    dom_snippet = None
    try:
        dom_snippet = get_dom_snippet(page)
    except Exception:
        dom_snippet = "[]"

    write_summary(
        run_id, platform, step, error, url,
        strategy=strategy,
        **{k: v for k, v in extra.items() if k != "dom_snippet"},
    )

    detail_ctx = {k: v for k, v in extra.items()}
    if dom_snippet:
        detail_ctx["dom_snippet"] = dom_snippet
    write_detail(run_id, step, error, **detail_ctx)

    diag_hints = {k: v for k, v in extra.items()
                  if k in ("failed_step", "semantic_hint", "recipe_key")}
    log_diag_line(run_id, platform, step, error, **diag_hints)

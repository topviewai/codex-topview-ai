"""配方执行器 — 读取 JSON recipe，按步骤执行浏览器交互。

三层逐级兜底：
  Tier 1: 用配方中的 selector 直接执行
  Tier 2: selector 失败时调用 dom_heuristic 启发式查找，成功后自动写回配方
  Tier 3: 全部失败时输出增强 DIAG，交给 Agent（OpenClaw）介入

支持的 action 类型：
  click         — 点击元素（CSS 选择器 / JS querySelector）
  set_value     — 用 nativeSet 设置 input 值
  click_and_set — 先点击再设值（针对自定义下拉/日历）
  pick_option   — 在选项列表中按文本选择
  wait          — 等待元素出现
"""

import json
import logging
import re
import sys
import time
from pathlib import Path

from social_uploader.tools.dom_heuristic import (
    _scan_dom,
    discover_for_click,
    discover_for_value,
)
from social_uploader.tools.browser_manager import (
    cdp_click_at,
    cdp_press_key,
    cdp_type_text,
)

logger = logging.getLogger(__name__)

_PATTERNS_PATH = Path(__file__).resolve().parent.parent / "state_patterns.json"


def _load_patterns():
    try:
        return json.loads(_PATTERNS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"state_patterns.json 读取失败: {e}")
        return {}


def _save_patterns(data):
    try:
        _PATTERNS_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"state_patterns.json 写入失败: {e}")


def load_recipe(platform, recipe_key):
    """从 state_patterns.json 加载指定配方。"""
    data = _load_patterns()
    recipe = data.get(platform, {}).get(recipe_key)
    if not recipe:
        logger.warning(f"配方 {platform}.{recipe_key} 不存在")
        return None
    return recipe


def _resolve_variables(text, variables):
    """将模板变量 ${key} 替换为实际值。"""
    if not isinstance(text, str):
        return text
    for k, v in variables.items():
        text = text.replace(f"${{{k}}}", str(v))
    return text


def _resolve_step(step, variables):
    """对 step 中的所有字符串字段做变量替换（深拷贝）。"""
    resolved = {}
    for k, v in step.items():
        if isinstance(v, str):
            resolved[k] = _resolve_variables(v, variables)
        elif isinstance(v, dict):
            inner = {}
            for sk, sv in v.items():
                if isinstance(sv, str):
                    inner[sk] = _resolve_variables(sv, variables)
                elif isinstance(sv, list):
                    inner[sk] = [_resolve_variables(item, variables) if isinstance(item, str) else item
                                 for item in sv]
                else:
                    inner[sk] = sv
            resolved[k] = inner
        elif isinstance(v, list):
            resolved[k] = [_resolve_variables(item, variables) if isinstance(item, str) else item
                           for item in v]
        else:
            resolved[k] = v
    return resolved


def _get_selectors(step):
    """从 step 的 target 中提取选择器列表（primary + fallbacks）。"""
    target = step.get("target", {})
    if isinstance(target, str):
        return [target]
    selectors = []
    primary = target.get("selector")
    if primary:
        selectors.append(primary)
    fallbacks = target.get("fallbacks", [])
    selectors.extend(fallbacks)
    return selectors


def _text_matches_verify(el, verify_list):
    """检查元素文本是否包含 verify_text 列表中的任一值。"""
    try:
        el_text = (el.text or "").strip()
    except Exception:
        el_text = ""
    for expected in verify_list:
        if expected in el_text:
            return True
    return False


def _exec_click(page, step):
    """执行 click 动作。

    使用 DrissionPage 原生 ele().click() 以确保触发 React 合成事件。
    纯 JS el.click() 无法触发 React 事件系统绑定的 onClick 回调。

    可选 verify_text：点击前验证元素文本是否包含预期值，防止 CSS 选择器
    命中错误元素导致的假成功。不匹配时跳过该选择器继续尝试下一个。
    """
    selectors = _get_selectors(step)
    fallback_texts = step.get("fallback", {}).get("text_match", []) if isinstance(step.get("fallback"), dict) else []
    verify_text = step.get("verify_text", [])

    for sel in selectors:
        try:
            el = page.ele(f'css:{sel}', timeout=2)
            if el:
                if verify_text and not _text_matches_verify(el, verify_text):
                    logger.debug(f"    verify_text 不匹配, 跳过 {sel}")
                    continue
                el.click()
                return "ok", sel
        except Exception:
            pass

    if fallback_texts:
        for text in fallback_texts:
            try:
                el = page.ele(f'text:{text}', timeout=2)
                if el:
                    el.click()
                    return "ok_text", "text_match"
            except Exception:
                pass

    return "not_found", None


def _exec_set_value(page, step):
    """执行 set_value 动作（通过 CDP Input 层设置值，所有事件 isTrusted=true）。

    支持 Shadow DOM 穿透：先用标准 querySelectorAll，失败后递归搜索 Shadow DOM。
    流程：JS 定位元素 → CDP 点击聚焦 → CDP 全选 → CDP 输入新值 → CDP Tab 触发 change。
    """
    selectors = _get_selectors(step)
    value = step.get("value", "")
    value_pattern = step.get("target", {}).get("value_pattern", "")

    js_find_rect = (
        'var sel = arguments[0]; var valPat = arguments[1];'
        'function findInputs(root, depth) {'
        '  if (depth > 10) return [];'
        '  var results = [];'
        '  try {'
        '    var els = root.querySelectorAll(sel);'
        '    for (var e of els) results.push(e);'
        '    if (results.length === 0) {'
        '      var all = root.querySelectorAll("*");'
        '      for (var c of all) {'
        '        if (c.shadowRoot) results = results.concat(findInputs(c.shadowRoot, depth + 1));'
        '      }'
        '    }'
        '  } catch(e) {}'
        '  return results;'
        '}'
        'var els = findInputs(document, 0);'
        'for (var inp of els) {'
        '  var rect = inp.getBoundingClientRect();'
        '  if (rect.width === 0) continue;'
        '  if (valPat && !(new RegExp(valPat)).test(inp.value)) continue;'
        '  inp.scrollIntoView({block: "center"});'
        '  var r = inp.getBoundingClientRect();'
        '  return {x: r.x + r.width/2, y: r.y + r.height/2};'
        '}'
        'return null;'
    )

    for sel in selectors:
        rect = page.run_js(js_find_rect, sel, value_pattern)
        if not rect:
            continue

        try:
            cdp_click_at(page, rect['x'], rect['y'])
            time.sleep(0.1)

            select_result = page.run_js(
                'var el = document.activeElement;'
                'if (!el) return "no_element";'
                'if (el.select) { el.select(); return "select_called"; }'
                'else if (el.isContentEditable) {'
                '  var r = document.createRange(); r.selectNodeContents(el);'
                '  var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);'
                '  return "range_selected";'
                '}'
                'return "no_method";'
            )
            time.sleep(0.05)

            cdp_type_text(page, value)
            time.sleep(0.1)

            actual_value = page.run_js(
                'var el = document.activeElement;'
                'if (!el) return null;'
                'return el.value;',
            )

            if actual_value != value:
                for _ in range(len(actual_value or "")):
                    cdp_press_key(page, 'Backspace', 'Backspace', 8)
                time.sleep(0.05)

                cdp_type_text(page, value)
                time.sleep(0.1)
                actual_value = page.run_js(
                    'var el = document.activeElement; return el ? el.value : null;'
                )

            verify = "ok" if actual_value == value else "set_but_unverified"

            cdp_press_key(page, 'Tab', 'Tab', 9)
            return verify or "set_but_unverified", sel
        except Exception as e:
            logger.debug(f"CDP set_value failed for {sel}: {e}")
            continue

    return "not_found", None


def _exec_pick_option(page, step):
    """执行 pick_option 动作（在选项列表中选择）。

    match_text 支持 ``|`` 分隔的多候选文本，例如 ``"Only me|仅自己|Only Me"``，
    JS 侧会依次匹配，命中任一即点击。

    会自动跳过不可见 / disabled / 跨月补位等不可点击的候选项，避免日历类
    控件因为 DOM 中存在前后月份的同名"日"被错误点击（例如 4 月日历首行的
    3 月 30 号）。可通过 step 配置 ``exclude_classes`` 增加自定义过滤类名。
    """
    container = step.get("container", "")
    item_selector = step.get("item_selector", "")
    match_text = step.get("match_text", "")
    extra_excludes = step.get("exclude_classes") or []
    if isinstance(extra_excludes, str):
        extra_excludes = [extra_excludes]

    if not item_selector or not match_text:
        return "missing_config", None

    default_exclude_classes = [
        "disabled", "is-disabled", "gray", "grey",
        "other-month", "outside", "not-current",
        "prev-month", "next-month", "muted",
    ]
    exclude_classes = list({*default_exclude_classes, *extra_excludes})

    exclude_classes_json = json.dumps(exclude_classes)

    js_locate = (
        'var containerSel = arguments[0]; var itemSel = arguments[1];'
        'var target = arguments[2]; var excludeClasses = JSON.parse(arguments[3] || "[]");'
        'var root = containerSel ? document.querySelector(containerSel) : document;'
        'if (!root) return {result: "container_not_found"};'
        'var targets = target.indexOf("|") >= 0 ? target.split("|") : [target];'
        'function isClickable(el) {'
        '  if (!el) return false;'
        '  if (el.offsetParent === null && el.getClientRects().length === 0) return false;'
        '  var rect = el.getBoundingClientRect();'
        '  if (rect.width === 0 || rect.height === 0) return false;'
        '  if (el.hasAttribute("disabled")) return false;'
        '  if (el.getAttribute("aria-disabled") === "true") return false;'
        '  if (el.getAttribute("data-disabled") === "true") return false;'
        '  for (var c of excludeClasses) { if (c && el.classList.contains(c)) return false; }'
        '  var style = window.getComputedStyle(el);'
        '  if (style.pointerEvents === "none") return false;'
        '  if (style.visibility === "hidden") return false;'
        '  return true;'
        '}'
        'var items = root.querySelectorAll(itemSel);'
        'var skippedDisabled = 0;'
        'for (var item of items) {'
        '  var txt = item.textContent.trim();'
        '  for (var t of targets) {'
        '    if (txt === t || txt.startsWith(t)) {'
        '      if (!isClickable(item)) { skippedDisabled++; continue; }'
        '      item.scrollIntoView({block:"center"});'
        '      var r = item.getBoundingClientRect();'
        '      return {result: "ok", x: r.x + r.width/2, y: r.y + r.height/2};'
        '    }'
        '  }'
        '}'
        'return {result: skippedDisabled > 0 ? "option_disabled_only" : "option_not_found"};'
    )
    located = page.run_js(js_locate, container, item_selector, match_text, exclude_classes_json)
    if not isinstance(located, dict):
        return "locate_invalid", item_selector
    status = located.get("result", "option_not_found")
    if status != "ok":
        return status, item_selector

    try:
        cdp_click_at(page, located["x"], located["y"])
    except Exception as e:
        logger.debug(f"CDP click failed for pick_option {item_selector}: {e}")
        return "click_failed", item_selector
    return "ok", item_selector


def _exec_wait(page, step):
    """执行 wait 动作（等待元素出现）。"""
    selectors = _get_selectors(step)
    max_wait = step.get("max_wait_ms", 5000)
    interval = 500
    attempts = max(1, max_wait // interval)

    for _ in range(attempts):
        for sel in selectors:
            js = (
                'var el = document.querySelector(arguments[0]);'
                'return el && el.offsetParent !== null ? "visible" : "hidden";'
            )
            result = page.run_js(js, sel)
            if result == "visible":
                return "ok", sel
        time.sleep(interval / 1000)

    return "not_found", None


_ACTION_MAP = {
    "click": _exec_click,
    "set_value": _exec_set_value,
    "pick_option": _exec_pick_option,
    "wait": _exec_wait,
}


def _try_discover(page, step, action):
    """Tier 2a（启发式） → Tier 2b（AgentQL AI）逐级发现替代选择器。"""
    hint = step.get("semantic_hint", "")
    context = step.get("context_selector")

    # Tier 2a: dom_heuristic 启发式（本地、免费、快速）
    if action in ("click", "wait"):
        fallback_texts = step.get("fallback", {}).get("text_match", []) if isinstance(step.get("fallback"), dict) else []
        sel, el_info = discover_for_click(page, hint, fallback_texts, context)
        if sel:
            logger.info(f"    🔍 Tier 2a 发现: {sel}")
            return sel
    elif action == "set_value":
        val_pat = step.get("target", {}).get("value_pattern", "")
        sel, el_info = discover_for_value(page, val_pat, hint, context)
        if sel:
            logger.info(f"    🔍 Tier 2a 发现: {sel}")
            return sel
    elif action == "pick_option":
        match_text = step.get("match_text", "")
        texts = match_text.split("|") if "|" in match_text else [match_text]
        for text in texts:
            sel, el_info = discover_for_click(page, f"{hint} {text}", [text], context)
            if sel:
                logger.info(f"    🔍 Tier 2a 发现: {sel}")
                return sel

    # Tier 2b: AgentQL AI（云端、10s 延迟、需 API Key）
    if hint:
        try:
            from social_uploader.tools.agentql_client import discover_with_ai
            sel = discover_with_ai(page, hint, action, context)
            if sel:
                logger.info(f"    🧠 Tier 2b AgentQL 发现: {sel}")
                return sel
        except ImportError:
            pass

    return None


def _update_recipe_step(platform, recipe_key, step_id, new_selector):
    """将 Tier 2 发现的新选择器写回 recipe（旧选择器降为 fallback）。"""
    data = _load_patterns()
    recipe = data.get(platform, {}).get(recipe_key)
    if not recipe:
        return

    for step in recipe.get("steps", []):
        if step.get("id") != step_id:
            continue

        target = step.get("target", {})
        if isinstance(target, str):
            step["target"] = {
                "selector": new_selector,
                "fallbacks": [target],
            }
        else:
            old = target.get("selector")
            target["selector"] = new_selector
            fallbacks = target.get("fallbacks", [])
            if old and old not in fallbacks:
                fallbacks.insert(0, old)
            target["fallbacks"] = fallbacks

        break

    recipe["version"] = recipe.get("version", 0) + 1
    _save_patterns(data)

    from social_uploader.tools.pattern_checker import reload_patterns
    reload_patterns()

    logger.info(f"  📝 配方已更新: {platform}.{recipe_key}.{step_id} → {new_selector} (v{recipe['version']})")


def _emit_failure_candidates(page, step, hint, action, context_selector=None, top_n=3):
    """Tier 1+2 都失败时，扫描 DOM 输出 top_n 候选元素到 stderr，便于事后诊断。

    输出格式（一行 JSON）：
      {"step":"recipe_candidates","step_id":...,"hint":...,"candidates":[...]}
    候选按 hint 关键词命中数排序。空 hint 时降级为输出当前 DOM 中前 top_n 个可见交互元素。
    """
    try:
        elements = _scan_dom(page, context_selector)
    except Exception as e:
        elements = []
        logger.debug(f"扫描 DOM 失败: {e}")

    if not elements:
        return

    keywords = [w.lower() for w in re.findall(r"[\w\u4e00-\u9fff]+", hint or "") if len(w) >= 2]
    if not keywords:
        return  # 没有 hint 关键词时不做无意义的输出

    def _score(el):
        searchable = " ".join([
            str(el.get("text", "")), str(el.get("aria-label", "")),
            str(el.get("data-e2e", "")), str(el.get("id", "")),
            str(el.get("name", "")), str(el.get("placeholder", "")),
            str(el.get("role", "")),
        ]).lower()
        return sum(1 for kw in keywords if kw in searchable)

    scored = [(el, _score(el)) for el in elements]
    scored = [item for item in scored if item[1] > 0]
    scored.sort(key=lambda x: -x[1])
    top = [el for el, _ in scored[:top_n]]

    if not top:
        return

    summary = []
    for el in top:
        summary.append({
            "tag": el.get("tag"),
            "text": (el.get("text") or "")[:30],
            "aria_label": el.get("aria-label"),
            "id": el.get("id"),
            "data_e2e": el.get("data-e2e"),
            "role": el.get("role"),
            "class": (el.get("class") or "")[:60],
        })

    record = {
        "step": "recipe_candidates",
        "step_id": step.get("id"),
        "action": action,
        "hint": hint,
        "candidates": summary,
    }
    print(json.dumps(record, ensure_ascii=False), file=sys.stderr)


def run_recipe(page, platform, recipe_key, variables):
    """执行交互配方，返回 (success: bool, failed_step_id: str|None, hint: str)。

    每一步先尝试 Tier 1（配方选择器），失败则 Tier 2（启发式发现），
    Tier 2 成功后自动写回配方，下次直接走 Tier 1。
    """
    recipe = load_recipe(platform, recipe_key)
    if not recipe:
        return False, None, f"配方 {platform}.{recipe_key} 不存在"

    steps = recipe.get("steps", [])
    if not steps:
        return False, None, "配方步骤为空"

    logger.info(f"  📋 执行配方: {platform}.{recipe_key} (v{recipe.get('version', 1)}, {len(steps)} 步)")

    for step in steps:
        step_id = step.get("id", "unknown")
        action = step.get("action", "")
        hint = step.get("semantic_hint", "")
        resolved = _resolve_step(step, variables)

        executor = _ACTION_MAP.get(action)
        if not executor:
            logger.warning(f"  ⚠️ [{step_id}] 未知 action: {action}")
            return False, step_id, f"未知 action 类型: {action}"

        # Tier 1: 按配方执行
        retry_count = resolved.get("retry", 1)
        wait_before = resolved.get("wait_before_ms", 0)
        if wait_before:
            time.sleep(wait_before / 1000)

        result, used_sel = "not_found", None
        for attempt in range(max(1, retry_count)):
            result, used_sel = executor(page, resolved)
            if result and result != "not_found" and result != "not_found":
                break
            if attempt < retry_count - 1:
                time.sleep(0.5)

        if result and (result.startswith("ok") or result == "set_but_unverified"):
            if result == "set_but_unverified":
                logger.info(f"  ⚠️ [{step_id}] {action} 值已写入但未通过验证，视为成功继续")
            else:
                logger.info(f"  ✅ [{step_id}] {action} 成功")
            wait_after = resolved.get("wait_after_ms", 0)
            if wait_after:
                time.sleep(wait_after / 1000)
            continue

        # Tier 2: 启发式发现
        logger.info(f"  ⚠️ [{step_id}] Tier 1 失败 ({result})，尝试 Tier 2 发现...")
        discovered = _try_discover(page, resolved, action)

        if discovered:
            tier2_step = dict(resolved)
            target = tier2_step.get("target", {})
            if isinstance(target, dict):
                tier2_step["target"] = {**target, "selector": discovered}
            else:
                tier2_step["target"] = {"selector": discovered}

            result2, _ = executor(page, tier2_step)
            if result2 and result2.startswith("ok"):
                logger.info(f"  ✅ [{step_id}] Tier 2 成功，自动更新配方")
                _update_recipe_step(platform, recipe_key, step_id, discovered)
                wait_after = resolved.get("wait_after_ms", 0)
                if wait_after:
                    time.sleep(wait_after / 1000)
                continue

        # Tier 1+2 都失败
        if resolved.get("optional"):
            logger.info(f"  ⏭️ [{step_id}] 可选步骤失败，跳过继续")
            continue
        logger.error(f"  ❌ [{step_id}] Tier 1+2 失败: {result}")
        _emit_failure_candidates(
            page, resolved, hint, action,
            context_selector=resolved.get("context_selector"),
        )
        return False, step_id, hint or f"{action} 操作失败"

    return True, None, ""


def show_recipe(platform, recipe_key):
    """以可读格式输出配方内容。"""
    recipe = load_recipe(platform, recipe_key)
    if not recipe:
        return f"配方 {platform}.{recipe_key} 不存在"

    lines = [
        f"RECIPE: {platform}.{recipe_key}",
        f"VERSION: {recipe.get('version', 1)}",
        f"STEPS: {len(recipe.get('steps', []))}",
        "",
    ]
    for i, step in enumerate(recipe.get("steps", []), 1):
        step_id = step.get("id", "?")
        action = step.get("action", "?")
        hint = step.get("semantic_hint", "")
        target = step.get("target", {})
        sel = target.get("selector", str(target)) if isinstance(target, dict) else str(target)
        fallbacks = target.get("fallbacks", []) if isinstance(target, dict) else []

        lines.append(f"  {i}. [{step_id}] {action}")
        lines.append(f"     selector: {sel}")
        if fallbacks:
            lines.append(f"     fallbacks: {fallbacks}")
        if hint:
            lines.append(f"     hint: {hint}")
        lines.append("")

    return "\n".join(lines)


def fix_recipe_step(platform, recipe_key, step_id, new_selector):
    """CLI 命令接口：手动更新配方中某一步的选择器。"""
    data = _load_patterns()
    recipe = data.get(platform, {}).get(recipe_key)
    if not recipe:
        return False, f"配方 {platform}.{recipe_key} 不存在"

    found = False
    for step in recipe.get("steps", []):
        if step.get("id") != step_id:
            continue
        found = True

        target = step.get("target", {})
        if isinstance(target, str):
            step["target"] = {"selector": new_selector, "fallbacks": [target]}
        else:
            old = target.get("selector")
            target["selector"] = new_selector
            fallbacks = target.get("fallbacks", [])
            if old and old not in fallbacks:
                fallbacks.insert(0, old)
            target["fallbacks"] = fallbacks
        break

    if not found:
        available = [s.get("id") for s in recipe.get("steps", [])]
        return False, f"步骤 {step_id} 不存在（可用: {', '.join(available)}）"

    recipe["version"] = recipe.get("version", 0) + 1
    _save_patterns(data)
    return True, f"OK: {platform}.{recipe_key}.{step_id} selector 已更新为 \"{new_selector}\" (v{recipe['version']})"

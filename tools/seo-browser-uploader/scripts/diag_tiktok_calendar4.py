"""Robust diag: handle 'continue editing' modal, inject file via existing
upload helper, wait for schedule picker, click date input, dump DOM."""

from __future__ import annotations

import json
import time

from social_uploader.tools.browser_manager import connect_browser, find_platform_tab


VIDEO = "/Users/shenyajing/Desktop/seo 浏览器操控插件 2/test_videos/test_upload_20260420_145614.mp4"


def _dump_js() -> str:
    return r"""
    function summarize(el) {
      if (!el) return null;
      var rect = el.getBoundingClientRect();
      return {
        tag: el.tagName,
        cls: el.className && el.className.toString ? el.className.toString().slice(0, 200) : '',
        id: el.id || '',
        rect: {x: Math.round(rect.x), y: Math.round(rect.y),
               w: Math.round(rect.width), h: Math.round(rect.height)},
        text: (el.textContent || '').trim().slice(0, 80)
      };
    }
    function findClassesContaining(needles) {
      var seen = {}; var out = [];
      var all = document.querySelectorAll('*');
      for (var el of all) {
        if (el.offsetParent === null) continue;
        var rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        var c = el.className && el.className.toString ? el.className.toString() : '';
        if (!c) continue;
        for (var n of needles) {
          if (c.toLowerCase().indexOf(n) >= 0) {
            var key = c + '|' + el.tagName;
            if (seen[key]) continue;
            seen[key] = 1;
            out.push(summarize(el));
            if (out.length >= 30) return out;
            break;
          }
        }
      }
      return out;
    }
    function findVisibleByText(target, limit) {
      var all = document.querySelectorAll('div, span, button, td, li, a, p');
      var out = [];
      for (var el of all) {
        if (el.offsetParent === null) continue;
        var rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        var t = '';
        if (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3) {
          t = (el.textContent || '').trim();
        }
        if (t === target) {
          var info = summarize(el);
          info.parent_cls = el.parentElement ? el.parentElement.className.toString().slice(0, 160) : '';
          var path = []; var c = el;
          for (var i = 0; i < 5 && c; i++) {
            path.push(c.tagName + (c.className ? '.' + c.className.toString().split(' ').slice(0,2).join('.') : ''));
            c = c.parentElement;
          }
          info.path = path.join(' > ');
          out.push(info);
          if (out.length >= limit) break;
        }
      }
      return out;
    }
    return {
      calendar_like: findClassesContaining(['calendar', 'datepicker', 'date-picker', 'date_picker', 'tux-date', 'tuxdate']),
      popovers: findClassesContaining(['popover', 'popper', 'dropdown', 'tuxsheet', 'tux-sheet']),
      visible_30: findVisibleByText('30', 12),
      visible_29: findVisibleByText('29', 6),
      visible_28: findVisibleByText('28', 6),
      visible_april: findVisibleByText('April', 5),
    };
    """


def main() -> None:
    ctrl, work, _, _ = connect_browser(new_window=False)
    tab = find_platform_tab(ctrl, "https://www.tiktok.com/tiktokstudio") or work
    print("Reloading to /upload...")
    tab.get("https://www.tiktok.com/tiktokstudio/upload?from=upload")
    time.sleep(5)
    print("URL:", tab.url)

    # Handle "Continue editing?" modal — pick "Discard" to start fresh
    js_dismiss_draft = (
        'var modal = document.querySelector(".TUXModal-overlay, [role=dialog]");'
        'if (!modal) return "no_modal";'
        'var btns = modal.querySelectorAll("button");'
        'for (var b of btns) {'
        '  var t = (b.textContent || "").trim().toLowerCase();'
        '  if (t.indexOf("discard") >= 0 || t.indexOf("放弃") >= 0 || t.indexOf("丢弃") >= 0) {'
        '    b.click(); return "clicked discard:" + t;'
        '  }'
        '}'
        'return "no_discard_button";'
    )
    print("draft modal:", tab.run_js(js_dismiss_draft))
    time.sleep(1.0)

    print("Injecting video via input[type=file]...")
    try:
        fi = tab.ele('xpath://input[@type="file"]', timeout=5)
        fi.input(VIDEO)
        print("file injected")
    except Exception as e:
        print("file inject failed:", e)
        return

    print("Waiting for postSchedule radio (max 60s)...")
    for i in range(60):
        time.sleep(1.0)
        if tab.run_js('return !!document.querySelector("input[name=\\"postSchedule\\"]");'):
            print(f"  schedule radio appeared after {i+1}s")
            break
    else:
        print("ABORT: postSchedule radio never appeared")
        return

    print("Activating schedule (clicking radio for value=schedule)...")
    tab.run_js(
        'var r = document.querySelector("input[name=\\"postSchedule\\"][value=\\"schedule\\"]");'
        'if (r) { r.click(); return "clicked"; } return "no_radio";'
    )
    time.sleep(2.0)

    print("Now waiting for .scheduled-picker after clicking radio...")
    for i in range(15):
        time.sleep(1.0)
        if tab.run_js('return !!document.querySelector(".scheduled-picker");'):
            print(f"  picker appeared after {i+1}s")
            break
    else:
        print("scheduled-picker still missing; continuing anyway")

    # Try to dismiss any consent modal that pops up
    tab.run_js(
        'var m = document.querySelector(".TUXModal-overlay");'
        'if (m) {'
        '  var btns = m.querySelectorAll("button");'
        '  for (var b of btns) {'
        '    var t = (b.textContent || "").trim().toLowerCase();'
        '    if (t.indexOf("allow") >= 0 || t.indexOf("agree") >= 0 || t.indexOf("ok") >= 0 || t.indexOf("继续") >= 0) {'
        '      b.click(); break;'
        '    }'
        '  }'
        '}'
    )
    time.sleep(1.0)

    print("Inspecting BEFORE opening date picker:")
    print(json.dumps(tab.run_js(_dump_js()), indent=2, ensure_ascii=False, default=str)[:1500])

    print("\nClicking date input (right side)...")
    tab.run_js(
        'var box = document.querySelector(".scheduled-picker > div:last-child .TUXInputBox");'
        'if (box) box.click();'
    )
    time.sleep(1.5)

    print("\n=== Inspecting AFTER opening date picker ===")
    result = tab.run_js(_dump_js())
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()

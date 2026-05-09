"""End-to-end diag: upload video → enable schedule → open date picker → dump DOM.

Connects to debug Chrome, uses an already-open TikTok upload tab if present
(must be on /tiktokstudio/upload). User must run a fresh upload first so the
form is in the post-upload "fill metadata" state, OR this script will inject
the file itself.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from social_uploader.tools.browser_manager import connect_browser, find_platform_tab


URL_PREFIX = "https://www.tiktok.com/tiktokstudio/upload"


def _summarize_js() -> str:
    return r"""
    function summarize(el) {
      if (!el) return null;
      var rect = el.getBoundingClientRect();
      return {
        tag: el.tagName,
        cls: el.className && el.className.toString ? el.className.toString().slice(0, 200) : '',
        id: el.id || '',
        visible: el.offsetParent !== null,
        rect: {x: Math.round(rect.x), y: Math.round(rect.y),
               w: Math.round(rect.width), h: Math.round(rect.height)},
        text: (el.textContent || '').trim().slice(0, 80)
      };
    }
    function findClassesContaining(needles) {
      var seen = {};
      var all = document.querySelectorAll('*');
      var out = [];
      for (var el of all) {
        if (el.offsetParent === null) continue;
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
      calendar_like_visible: findClassesContaining(['calendar', 'datepicker', 'date-picker', 'date_picker']),
      visible_30: findVisibleByText('30', 10),
      visible_29: findVisibleByText('29', 10),
      schedule_picker_present: !!document.querySelector('.scheduled-picker')
    };
    """


def main() -> None:
    video = "/Users/shenyajing/Desktop/seo 浏览器操控插件 2/test_videos/test_upload_20260420_145614.mp4"

    ctrl, work, baseline_tab_ids, _ = connect_browser(new_window=False)
    tab = find_platform_tab(ctrl, "https://www.tiktok.com/tiktokstudio") or work
    print("URL:", tab.url)
    if "tiktokstudio/upload" not in tab.url:
        print("Navigating to /tiktokstudio/upload ...")
        tab.get("https://www.tiktok.com/tiktokstudio/upload?from=upload")
        time.sleep(4)
        print("URL after nav:", tab.url)

    has_picker = tab.run_js('return !!document.querySelector(".scheduled-picker");')
    if not has_picker:
        print("scheduled-picker not present, injecting video first...")
        file_input_js = (
            'var inputs = document.querySelectorAll("input[type=file]");'
            'return Array.from(inputs).map(function(i){return {accept:i.accept, name:i.name};});'
        )
        print("file inputs:", tab.run_js(file_input_js))
        try:
            file_input = tab.ele('xpath://input[@type="file"]', timeout=3)
            file_input.input(video)
            print("file injected via .input()")
        except Exception as e:
            print("upload via UI failed:", e)

        for i in range(30):
            time.sleep(1.0)
            has = tab.run_js('return !!document.querySelector(".scheduled-picker");')
            if has:
                print(f"picker appeared after {i+1}s")
                break
        else:
            print("ABORT: still no scheduled-picker after 30s. Manually upload first.")
            sys.exit(1)

    print("Activating schedule radio...")
    js_activate = (
        'var radio = document.querySelector("input[name=\\"postSchedule\\"][value=\\"schedule\\"]");'
        'if (!radio) return "no_radio";'
        'radio.click();'
        'return "ok";'
    )
    print("activate result:", tab.run_js(js_activate))
    time.sleep(1.0)

    handle_modal = (
        'var modal = document.querySelector(".TUXModal-overlay");'
        'if (!modal) return "no_modal";'
        'var btns = modal.querySelectorAll("button");'
        'for (var b of btns) {'
        '  var t = (b.textContent || "").trim().toLowerCase();'
        '  if (t.indexOf("allow") >= 0 || t.indexOf("agree") >= 0 || t.indexOf("允许") >= 0 || t.indexOf("ok") >= 0 || t.indexOf("confirm") >= 0) {'
        '    b.click(); return "clicked:" + t;'
        '  }'
        '}'
        'return "no_match";'
    )
    print("consent modal:", tab.run_js(handle_modal))
    time.sleep(1.0)

    print("Clicking date input...")
    js_click_date = (
        'var box = document.querySelector(".scheduled-picker > div:last-child .TUXInputBox");'
        'if (!box) return "no_box";'
        'box.click(); return "clicked";'
    )
    print("click result:", tab.run_js(js_click_date))
    time.sleep(1.5)

    print("Inspecting calendar DOM...")
    result = tab.run_js(_summarize_js())
    out_path = Path("test_videos") / "tiktok_calendar_dump.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"Dump written to {out_path}")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str)[:6000])


if __name__ == "__main__":
    main()

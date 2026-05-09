"""Inspect any TikTok upload tab that's currently in 'fill metadata' state.

Walks all open tabs, finds one with /tiktokstudio/upload AND a visible
.scheduled-picker, then clicks the date input and dumps the calendar DOM.
"""

from __future__ import annotations

import json
import time

from social_uploader.tools.browser_manager import connect_browser


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
      var out = [];
      var all = document.querySelectorAll('*');
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
      calendar_like_visible: findClassesContaining(['calendar', 'datepicker', 'date-picker', 'date_picker', 'tux-date', 'tuxdate']),
      visible_30: findVisibleByText('30', 10),
      visible_29: findVisibleByText('29', 10),
      visible_28: findVisibleByText('28', 6),
      visible_april: findVisibleByText('April', 5),
      tux_popovers: findClassesContaining(['popover', 'popper', 'dropdown']),
    };
    """


def main() -> None:
    ctrl, work, _, _ = connect_browser(new_window=False)
    tabs = ctrl.get_tabs()
    print(f"Total tabs: {len(tabs)}")
    target_tab = None
    for t in tabs:
        try:
            url = t.url
            print(f"  - {url}")
            if "tiktokstudio/upload" in url:
                has_picker = t.run_js('return !!document.querySelector(".scheduled-picker");')
                print(f"      has_picker: {has_picker}")
                if has_picker:
                    target_tab = t
                    break
        except Exception as e:
            print(f"  - <err {e}>")

    if not target_tab:
        print("No tab with .scheduled-picker found.")
        return

    print(f"\nActivating schedule on: {target_tab.url}")
    js_activate = (
        'var radio = document.querySelector("input[name=\\"postSchedule\\"][value=\\"schedule\\"]");'
        'if (!radio) return "no_radio";'
        'if (!radio.checked) radio.click();'
        'return "ok";'
    )
    print("activate result:", target_tab.run_js(js_activate))
    time.sleep(0.8)

    # close any modal that may pop up
    js_modal = (
        'var modal = document.querySelector(".TUXModal-overlay");'
        'if (!modal) return "no_modal";'
        'var btns = modal.querySelectorAll("button");'
        'for (var b of btns) {'
        '  var t = (b.textContent || "").trim().toLowerCase();'
        '  if (t.indexOf("allow") >= 0 || t.indexOf("agree") >= 0 || t.indexOf("ok") >= 0) {'
        '    b.click(); return "clicked:" + t;'
        '  }'
        '}'
        'return "no_match";'
    )
    print("consent modal:", target_tab.run_js(js_modal))
    time.sleep(0.8)

    print("\nClicking date input...")
    js_click_date = (
        'var box = document.querySelector(".scheduled-picker > div:last-child .TUXInputBox");'
        'if (!box) return "no_box";'
        'box.click(); return "clicked";'
    )
    print("click result:", target_tab.run_js(js_click_date))
    time.sleep(1.2)

    print("\n=== Calendar DOM dump ===")
    result = target_tab.run_js(_summarize_js())
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    print("\n=== Now clicking time input for comparison ===")
    target_tab.run_js(
        'var box = document.querySelector(".scheduled-picker > div:first-child .TUXInputBox");'
        'if (box) box.click();'
    )
    time.sleep(1.0)
    print("After clicking time input — visible 30:")
    result2 = target_tab.run_js(_summarize_js())
    print(json.dumps(result2, indent=2, ensure_ascii=False, default=str)[:3000])


if __name__ == "__main__":
    main()

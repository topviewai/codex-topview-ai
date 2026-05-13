"""Open the TikTok date picker and dump the calendar DOM."""

from __future__ import annotations

import json
import time

from social_uploader.tools.browser_manager import connect_browser, find_platform_tab


URL_PREFIX = "https://www.tiktok.com/tiktokstudio/upload"


def main() -> None:
    ctrl, work, baseline_tab_ids, _ = connect_browser(new_window=False)
    tab = find_platform_tab(ctrl, URL_PREFIX) or work
    print("URL:", tab.url)

    print("Clicking date input (.scheduled-picker > div:last-child .TUXInputBox)...")
    js_click = (
        'var box = document.querySelector(".scheduled-picker > div:last-child .TUXInputBox");'
        'if (!box) return "no_box";'
        'box.click();'
        'return "clicked";'
    )
    print("click result:", tab.run_js(js_click))
    time.sleep(1.2)

    js_inspect = r"""
    function summarize(el) {
      if (!el) return null;
      var rect = el.getBoundingClientRect();
      return {
        tag: el.tagName,
        cls: el.className && el.className.toString ? el.className.toString().slice(0, 160) : '',
        id: el.id || '',
        visible: el.offsetParent !== null,
        rect: {x: Math.round(rect.x), y: Math.round(rect.y),
               w: Math.round(rect.width), h: Math.round(rect.height)},
        text: (el.textContent || '').trim().slice(0, 60)
      };
    }
    function findByText(target, limit) {
      var all = document.querySelectorAll('div, span, button, td, li, a');
      var out = [];
      for (var el of all) {
        var t = (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3)
          ? (el.textContent || '').trim() : '';
        if (t === target) {
          var info = summarize(el);
          info.parent_cls = el.parentElement ? el.parentElement.className.toString().slice(0, 120) : '';
          info.path = (function(n){
            var p = []; var c = n;
            for (var i = 0; i < 4 && c; i++) {
              p.push(c.tagName + (c.className ? '.' + c.className.toString().split(' ')[0] : ''));
              c = c.parentElement;
            }
            return p.join(' > ');
          })(el);
          out.push(info);
          if (out.length >= limit) break;
        }
      }
      return out;
    }
    function findCalendarLike() {
      var candidates = document.querySelectorAll('[class*="calendar" i], [class*="datepicker" i], [class*="date-picker" i], [class*="DatePicker" i]');
      var out = [];
      for (var el of candidates) {
        if (out.length >= 8) break;
        out.push(summarize(el));
      }
      return out;
    }
    function findVisibleDayCells() {
      var sels = ['span.day', 'td.day', '[class*="day" i]', '[role="gridcell"]', '[aria-label*="2026" i]'];
      var report = {};
      for (var s of sels) {
        var els = document.querySelectorAll(s);
        var visible = [];
        for (var el of els) {
          if (el.offsetParent !== null) {
            var info = summarize(el);
            if (info.rect.w > 0 && info.rect.h > 0) visible.push(info);
          }
          if (visible.length >= 5) break;
        }
        report[s] = {count: els.length, visible_sample: visible};
      }
      return report;
    }
    return {
      calendar_like_classes: findCalendarLike(),
      day_cells_by_selector: findVisibleDayCells(),
      visible_30: findByText('30', 8),
      visible_2026: findByText('2026-04-30', 5),
    };
    """
    result = tab.run_js(js_inspect)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()

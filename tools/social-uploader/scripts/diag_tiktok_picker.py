"""Diagnose TikTok schedule picker DOM.

Connects to Chrome debug port 9222, finds the TikTok upload tab,
and dumps the structure of .scheduled-picker / .calendar-wrapper /
the time picker so we can see what selectors actually exist now.
"""

from __future__ import annotations

import json

from social_uploader.tools.browser_manager import connect_browser, find_platform_tab


URL_PREFIX = "https://www.tiktok.com/tiktokstudio/upload"


def main() -> None:
    ctrl, work, baseline_tab_ids, _ = connect_browser(new_window=False)
    tab = find_platform_tab(ctrl, URL_PREFIX) or work
    print("URL:", tab.url)

    js = r"""
    function summarize(el) {
      if (!el) return null;
      var rect = el.getBoundingClientRect();
      return {
        tag: el.tagName,
        cls: el.className && el.className.toString ? el.className.toString().slice(0, 120) : '',
        id: el.id || '',
        visible: el.offsetParent !== null,
        rect: {x: Math.round(rect.x), y: Math.round(rect.y),
               w: Math.round(rect.width), h: Math.round(rect.height)},
        text: (el.textContent || '').trim().slice(0, 40)
      };
    }
    function dump(sel, limit) {
      var els = document.querySelectorAll(sel);
      var out = [];
      for (var i = 0; i < Math.min(els.length, limit || 10); i++) out.push(summarize(els[i]));
      return {selector: sel, count: els.length, items: out};
    }
    function children(sel) {
      var el = document.querySelector(sel);
      if (!el) return null;
      var kids = [];
      for (var c of el.children) kids.push(summarize(c));
      return {selector: sel, parent: summarize(el), kids: kids};
    }
    function findVisible30(sel) {
      var els = document.querySelectorAll(sel);
      var matches = [];
      for (var el of els) {
        var t = (el.textContent || '').trim();
        if (t === '30' || t.startsWith('30')) {
          matches.push(summarize(el));
        }
      }
      return {selector: sel, matches: matches};
    }
    return {
      scheduled_picker: children('.scheduled-picker'),
      calendar_wrapper_exists: !!document.querySelector('.calendar-wrapper'),
      calendar_wrapper: children('.calendar-wrapper'),
      span_day_30: findVisible30('span.day'),
      day_in_calendar: findVisible30('.calendar-wrapper span.day'),
      time_picker_exists: !!document.querySelector('.tiktok-timepicker-time-picker-container'),
      time_picker: dump('.tiktok-timepicker-time-picker-container', 3),
      tux_input_boxes: dump('.scheduled-picker .TUXInputBox', 5),
      visible_30s_anywhere: findVisible30('*'),
    };
    """
    result = tab.run_js(js)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Design review by measurement, on pages served by a local Hevanti with made-up data (no real lecture, no Gemini call).

    python tools/review_design.py [out.json]

For every screen, in light and dark, it measures: sideways overflow at narrow widths and at larger text sizes, click targets under
24 px (WCAG 2.2 AA, 2.5.8), controls with no accessible name, a visible keyboard focus, and text contrast (computed from the real
colours on the page). It reports what it finds and changes nothing. Needs Playwright and Edge, Chrome or HEVANTI_TEST_CHROMIUM."""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix="hev-review-")
os.environ.update(PYTHONUTF8="1", BZM_NO_BROWSER="1", BZM_DATA_DIR=os.path.join(TMP, "data"), LOCALAPPDATA=os.path.join(TMP, "local"))
os.makedirs(os.environ["LOCALAPPDATA"])
LIB = os.path.join(TMP, "data", "הקורסים שלי", "פיזיקה 1")
LECT = "2026-11-05 10-00 הרצאה"
for n, body in ((LECT, "[10:00:05 | +0:00:05] היום נדבר על תנועה בקו ישר.\n[10:03:40 | +0:03:40] [סימון: חשוב]\n[10:03:45 | +0:03:45] המהירות היא נגזרת של המקום.\n"),
                ("2026-11-12 09-00 הרצאה", "[09:00:05 | +0:00:05] ממשיכים עם תאוצה.\n[09:02:10 | +0:02:10] תאוצה היא נגזרת של המהירות.\n")):
    os.makedirs(os.path.join(LIB, n))
    with open(os.path.join(LIB, n, n + ".txt"), "w", encoding="utf-8") as f:
        f.write("# תמלול הרצאה (עברית) - התחלה 2026-11-05 10:00\n" + body)
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

MEASURE = r"""() => {
  const wide = [...document.querySelectorAll('body *')].filter(e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && s.position !== 'fixed' && !e.closest('[hidden]') && s.display !== 'none' && (r.right > window.innerWidth + 1 || r.left < -1); });
  const out = {scroll: document.documentElement.scrollWidth - document.documentElement.clientWidth, overflow: wide.length, wide: wide.slice(0, 4).map(e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (e.className ? '.' + String(e.className).split(' ')[0] : '')), small: [], noname: [], lowc: []};
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && !e.closest('[hidden]') && !e.closest('[inert]'); };
  const label = e => (e.getAttribute('aria-label') || e.textContent || e.title || e.placeholder || e.id || e.tagName).trim().replace(/\s+/g, ' ').slice(0, 40);
  const sel = 'button, a[href], input:not([type=hidden]), select, textarea, summary, [role=tab], [role=button]';
  for (const e of document.querySelectorAll(sel)) {
    if (!vis(e)) continue;
    let r = e.getBoundingClientRect();
    const isBox = e.matches('input[type=checkbox], input[type=radio], input[type=range]');
    if (isBox && e.labels && e.labels.length) { const lr = e.labels[0].getBoundingClientRect(); r = {width: Math.max(r.width, lr.width), height: Math.max(r.height, lr.height)}; }
    if (e.matches('a[href]') && e.closest('p, li, dd, small, .sub') && e.parentElement && e.parentElement.childNodes.length > 1) continue;   // a link inside a sentence is exempt (WCAG 2.5.8)
    if (r.width < 24 || r.height < 24) out.small.push([label(e), Math.round(r.width) + 'x' + Math.round(r.height), e.tagName.toLowerCase() + (e.id ? '#' + e.id : '')]);
    const named = e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || (e.labels && e.labels.length) || (e.textContent || '').trim() || e.title || (e.tagName === 'INPUT' && e.placeholder);
    if (!named) out.noname.push([e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (e.className ? '.' + String(e.className).split(' ')[0] : '')]);
  }
  // text contrast, from the real colours (alpha over the first solid background up the tree)
  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(',').map(x => parseFloat(x)); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
  const lin = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const lum = c => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
  const over = (f, b) => ({r: f.r * f.a + b.r * (1 - f.a), g: f.g * f.a + b.g * (1 - f.a), b: f.b * f.a + b.b * (1 - f.a), a: 1});
  const bgOf = e => { const stack = []; for (let n = e; n; n = n.parentElement) { const c = parse(getComputedStyle(n).backgroundColor); if (c && c.a > 0) { stack.push(c); if (c.a === 1) break; } } let b = {r: 255, g: 255, b: 255, a: 1}; for (const c of stack.reverse()) b = over(c, b); return b; };
  const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let t; (t = walker.nextNode());) {
    if (!t.textContent.trim()) continue;
    const e = t.parentElement; if (!e || !vis(e) || e.closest('script, style, svg')) continue;
    const s = getComputedStyle(e); if (parseFloat(s.opacity) < 1 && false) continue;
    const fg = parse(s.color); if (!fg) continue;
    const bg = bgOf(e), f = over(fg, bg);
    const L1 = lum(f), L2 = lum(bg), ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const px = parseFloat(s.fontSize), bold = parseInt(s.fontWeight) >= 700, large = px >= 24 || (px >= 18.66 && bold), need = large ? 3 : 4.5;
    const key = e.tagName + '.' + String(e.className).split(' ')[0] + '|' + s.color + '|' + Math.round(bg.r) + ',' + Math.round(bg.g) + ',' + Math.round(bg.b);
    if (ratio < need && !seen.has(key)) { seen.add(key); out.lowc.push([t.textContent.trim().slice(0, 36), Math.round(ratio * 100) / 100, need, px]); }
  }
  return out;
}"""

FOCUS = r"""async (n) => {
  const bad = [], seen = []; document.activeElement && document.activeElement.blur();
  for (let i = 0; i < n; i++) {
    const e = document.activeElement; if (i > 0 && e === document.body) break;
  }
  return bad;
}"""


def launch(p):
    for kw in ({"channel": "msedge"}, {"channel": "chrome"}, {}):
        try:
            return p.chromium.launch(headless=True, **kw)
        except Exception:
            continue


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(TMP, "review.json")
    srv = L.AppServer()
    assert srv.start()
    url = srv.url.rstrip("/")
    L.save_settings(consent_ok=True, math={"key": L.keep_secret("AQ.fake"), "ask": True})
    results = {}
    live_lines = [{"i": i, "t": i * 5, "c": "00:%02d:00" % i, "x": "שורה מספר %d בתמלול של ההרצאה החיה, עם עוד כמה מילים כדי שתהיה ארוכה" % i} for i in range(8)]

    with sync_playwright() as p:
        b = launch(p)

        def page(width, height, theme, zoom=1.0, tx=1.0, extra=None):
            ctx = b.new_context(viewport={"width": width, "height": height}, locale="he-IL", color_scheme=theme)
            pg = ctx.new_page()
            pg.errs = []
            pg.on("pageerror", lambda e: pg.errs.append(str(e)))
            pg.add_init_script("try{localStorage.setItem('bzm.a11y', JSON.stringify(%s));localStorage.setItem('bzm.consent','1')}catch(e){}" % json.dumps({"zoom": zoom, "tx": tx}))
            if extra:
                extra(pg)
            return pg

        def live_routes(pg, key=True):
            def app(route):
                resp = route.fetch()
                d = resp.json()
                d["session"] = {"kind": "live", "lang": "he", "title": "", "course": "פיזיקה 1", "ready": True, "done": False, "stopping": False, "started": 0, "yt": False}
                d["math"] = dict(d.get("math") or {}, has_key=key, ask=key, on=key)
                route.fulfill(response=resp, body=json.dumps(d))
            pg.route("**/api/app*", app)
            pg.route("**/api/live*", lambda r: r.fulfill(content_type="application/json", body=json.dumps(
                {"total": len(live_lines), "since": 0, "draft": "טיוטה של מה שנאמר עכשיו", "pending": 0, "lag": 0, "fast": False, "shot": None, "info": {}, "ended": False, "items": live_lines})))

        def nokey(pg):
            def app(route):
                resp = route.fetch()
                d = resp.json()
                d["math"] = dict(d.get("math") or {}, has_key=False, ask=False, on=False)
                route.fulfill(response=resp, body=json.dumps(d))
            pg.route("**/api/app*", app)

        def gpu(pg):
            def app(route):
                resp = route.fetch()
                d = resp.json()
                d["gpu"] = {"cards": 1, "libs_ok": False, "state": "idle"}
                route.fulfill(response=resp, body=json.dumps(d))
            pg.route("**/api/app*", app)

        screens = [  # (name, hash, extra, selector to wait for)
            ("home", "#", None, "#vHome"), ("home, no key", "#", nokey, "#vHome"), ("home, NVIDIA card", "#", gpu, "#vHome"),
            ("my courses", "#courses", None, "#vCourses"), ("guide", "#how", None, "#vHow"),
            ("course page", "#c=" + "%D7%A4%D7%99%D7%96%D7%99%D7%A7%D7%94%201", None, "#vCourse"),
            ("lecture page", "#t=" + "%D7%A4%D7%99%D7%96%D7%99%D7%A7%D7%94%201/" + LECT.replace(" ", "%20"), None, "#vPast"),
            ("live lecture", "#live", live_routes, "#vLive"),
        ]
        for i, tab in enumerate(["מפתח", "התאמת התשובות", "צילום וטשטוש", "נגישות", "מתקדם", "פרטיות"]):
            screens.append(("settings: " + tab, "#settings", None, "#vSettings"))
        for theme in ("light", "dark"):
            for name, h, extra, wait in screens:
                key = f"{name} | {theme}"
                try:
                    pg = page(1280, 900, theme, extra=extra)
                    pg.goto(url + "/" + h)
                    pg.wait_for_timeout(1200)
                    pg.evaluate("document.querySelectorAll('.modal').forEach(m => m.hidden = true); document.documentElement.dataset.theme = '%s'" % theme)
                    if name.startswith("settings: "):
                        t = name.split(": ", 1)[1]
                        pg.evaluate("(t) => { const b = [...document.querySelectorAll('#setTabs > *')].find(x => x.textContent.trim() === t); if (b) b.click(); }", t)
                        pg.wait_for_timeout(400)
                    res = pg.evaluate(MEASURE)
                    res["errors"] = pg.errs
                    # narrow widths and big text
                    res["overflow_at"] = {}
                    for w in (320, 360, 480, 700):
                        pg.set_viewport_size({"width": w, "height": 900})
                        pg.wait_for_timeout(250)
                        o = pg.evaluate(MEASURE)
                        if o["scroll"] > 0:   # a real sideways scroll (an element clipped by its parent is not one)
                            res["overflow_at"][w] = [o["scroll"], o["wide"]]
                    pg.set_viewport_size({"width": 1280, "height": 900})
                    for z in (1.15, 1.3, 1.5):
                        for w in (1280, 700):
                            pg.set_viewport_size({"width": w, "height": 900})
                            pg.evaluate("(z) => { document.documentElement.style.zoom = String(z); }", z)
                            pg.wait_for_timeout(250)
                            o = pg.evaluate(MEASURE)
                            if o["scroll"] > 0:
                                res["overflow_at"]["zoom%d%% at %d" % (round(z * 100), w)] = [o["scroll"], o["wide"]]
                    pg.evaluate("document.documentElement.style.zoom = ''")
                    pg.set_viewport_size({"width": 1280, "height": 900})
                    # keyboard focus: tab through the first 40 stops, look for an outline or a ring
                    nofocus = []
                    pg.evaluate("document.activeElement && document.activeElement.blur()")
                    for _ in range(40):
                        pg.keyboard.press("Tab")
                        r = pg.evaluate("""() => { const e = document.activeElement; if (!e || e === document.body) return null; const s = getComputedStyle(e);
                            const ring = (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) >= 2) || (s.boxShadow && s.boxShadow !== 'none');
                            return {l: (e.getAttribute('aria-label') || e.textContent || e.id || e.tagName).trim().slice(0, 30), ring, tag: e.tagName}; }""")
                        if r is None:
                            break
                        if not r["ring"]:
                            nofocus.append(r["l"])
                    res["no_focus_ring"] = nofocus
                    results[key] = res
                    pg.unroute_all(behavior='ignoreErrors')
                    pg.context.close()
                except Exception as e:
                    results[key] = {"error": str(e)[:200]}
                    print("ERR", key, str(e)[:150], flush=True)
        b.close()
    srv.stop()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("written", out_path)


if __name__ == "__main__":
    main()

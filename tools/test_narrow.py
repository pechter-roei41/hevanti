"""Nothing scrolls sideways at 320 px wide (DESIGN.md, Layout), on every screen, light and dark, and the focus ring of the
floating window's answer button is the 2px green one. Needs Playwright and Edge or Chrome; skips when missing.
  python3 tools/test_narrow.py"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP playwright is not installed")
    sys.exit(0)
TMP = tempfile.mkdtemp()
os.environ.update(BZM_DATA_DIR=os.path.join(TMP, "data"), LOCALAPPDATA=os.path.join(TMP, "local"), BZM_NO_BROWSER="1", PYTHONUTF8="1")
LECT = "2026-11-05 10-00 הרצאה"
os.makedirs(os.path.join(TMP, "data", "הקורסים שלי", "פיזיקה 1", LECT))
os.makedirs(os.environ["LOCALAPPDATA"])
with open(os.path.join(TMP, "data", "הקורסים שלי", "פיזיקה 1", LECT, LECT + ".txt"), "w", encoding="utf-8") as f:
    f.write("# תמלול\n[10:00:05 | +0:00:05] שורה ראשונה.\n[10:03:40 | +0:03:40] [סימון: חשוב]\n")
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)))
    if not ok:
        fails.append(name)


def launch(p):
    for kw in ({"channel": "msedge"}, {"channel": "chrome"}, {}):
        try:
            return p.chromium.launch(headless=True, **kw)
        except Exception:
            continue


srv = L.AppServer()
assert srv.start()
url = srv.url.rstrip("/")
L.save_settings(consent_ok=True, math={"key": L.keep_secret("AQ.fake"), "ask": True})
LIVE = [{"i": i, "t": i * 5, "c": "00:%02d:00" % i, "x": "שורה מספר %d בתמלול" % i} for i in range(6)]


def live_routes(pg):
    def app(route):
        resp = route.fetch()
        d = resp.json()
        d["session"] = {"kind": "live", "lang": "he", "title": "", "course": "פיזיקה 1", "ready": True, "done": False, "stopping": False, "started": 0, "yt": False}
        d["math"] = dict(d.get("math") or {}, has_key=True, ask=True, on=True)
        route.fulfill(response=resp, body=json.dumps(d))
    pg.route("**/api/app*", app)
    pg.route("**/api/live*", lambda r: r.fulfill(content_type="application/json", body=json.dumps(
        {"total": 6, "since": 0, "draft": "", "pending": 0, "lag": 0, "fast": False, "shot": None, "info": {}, "ended": False, "items": LIVE})))


SCREENS = [("home", "#", None), ("my courses", "#courses", None), ("guide", "#how", None), ("course page", "#c=%D7%A4%D7%99%D7%96%D7%99%D7%A7%D7%94%201", None),
           ("lecture page", "#t=%D7%A4%D7%99%D7%96%D7%99%D7%A7%D7%94%201/" + LECT.replace(" ", "%20"), None), ("live lecture", "#live", live_routes)]
SET_TABS = ["מפתח", "התאמת התשובות", "צילום וטשטוש", "נגישות", "מתקדם", "פרטיות"]
with sync_playwright() as p:
    b = launch(p)
    if b is None:
        print("SKIP no browser for Playwright")
        sys.exit(0)
    for theme in ("light", "dark"):
        for name, h, extra in SCREENS + [("settings: " + t, "#settings", None) for t in SET_TABS]:
            pg = b.new_context(viewport={"width": 320, "height": 800}, locale="he-IL", color_scheme=theme).new_page()
            if extra:
                extra(pg)
            pg.goto(url + "/" + h)
            pg.wait_for_timeout(900)
            pg.evaluate("document.querySelectorAll('.modal').forEach(m => m.hidden = true)")
            if name.startswith("settings: "):
                pg.evaluate("(t) => { [...document.querySelectorAll('#setTabs > *')].find(x => x.textContent.trim() === t).click(); }", name.split(": ", 1)[1])
                pg.wait_for_timeout(250)
            sw = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check(f"320px, {theme}: {name} does not scroll sideways", sw <= 0, f"{sw}px")
            pg.unroute_all(behavior="ignoreErrors")
            pg.context.close()
        mn = b.new_context(viewport={"width": 420, "height": 640}, locale="he-IL", color_scheme=theme).new_page()
        live_routes(mn)
        mn.goto(url + "/mini")
        mn.wait_for_timeout(900)
        got = None
        mn.fill("textarea", "שאלה")   # (the round send button is live only with text, so only then can the keyboard reach it)
        mn.focus("textarea")
        for _ in range(4):
            mn.keyboard.press("Tab")
            r = mn.evaluate("() => { const e = document.activeElement, s = getComputedStyle(e); return [e.getAttribute('aria-label'), s.outlineStyle, s.outlineWidth]; }")
            if r[0] == "שליחה":
                got = r
                break
        check(f"floating window, {theme}: the send button (the arrow) shows a 2px solid focus ring", got and got[1] == "solid" and got[2] == "2px", got)
        mn.focus("textarea")
        box_ring = mn.evaluate("() => { const s = getComputedStyle(document.querySelector('.inbox')); return [s.outlineStyle, s.outlineWidth]; }")
        check(f"floating window, {theme}: the writing box shows a 2px solid focus ring while one writes in it", box_ring == ["solid", "2px"], box_ring)
        # a long course name is cut with an ellipsis: the star and the menu stay in the same row as the name
        mn.evaluate("setLec('הרצאה חיה - דינמיקה של גוף קשיח - מתחילה... ועוד שם ארוך מאוד של קורס')")
        rows = mn.evaluate("() => [...document.querySelectorAll('#lec, #markImp, #menuBtn')].map(e => Math.round(e.getBoundingClientRect().top))")
        check(f"floating window, {theme}: a long course name keeps the title row in one line", max(rows) - min(rows) <= 12, rows)
        mn.unroute_all(behavior="ignoreErrors")
        mn.context.close()
    # the text size, reading spacing and contrast chosen in the app reach the small windows (audit 16.11.2026, P1 #6): they change the look and nothing runs off the side
    L.save_settings(a11y_view={"tx": 2.0, "read": True, "contrast": True})
    for theme in ("light", "dark"):
        for name, path in (("floating window", "/mini"), ("quick-start window", "/quick")):
            for width in (320, 380):
                sm = b.new_context(viewport={"width": width, "height": 700}, locale="he-IL", color_scheme=theme).new_page()
                live_routes(sm)
                sm.goto(url + path)
                sm.wait_for_timeout(1300)
                got = sm.evaluate("() => { const r = document.documentElement; return [r.classList.contains('a-contrast'), r.classList.contains('a-read'), r.style.zoom, r.scrollWidth - r.clientWidth]; }")
                check(f"{name} at {width}px, {theme}: the saved contrast, reading spacing and text size are applied", got[0] and got[1] and got[2] == "1.4", got)
                check(f"{name} at {width}px, {theme}, large text: nothing scrolls sideways", got[3] <= 0, f"{got[3]}px")
                sm.unroute_all(behavior="ignoreErrors")
                sm.context.close()
    b.close()
srv.stop()
print()
print("all passed" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)

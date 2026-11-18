"""The home page shows one of four states (17.11.2026), in this order:
 1. "first": no Gemini key and no paid AI app;  2. "live": a lecture is recorded now;
 3. "ended": the lecture of this run was saved and not opened yet;  4. "day": everything else.
Checks: the state is picked right (also: an ended lecture that was opened goes back to "day"), the state changes by
itself without a reload, one solid-green control and at most one shadow in each state, nothing scrolls sideways at
320 px, the side column goes under the main card below 760 px, and "התחלת הרצאה" only asks for the quick-start window.
The server is real (a made-up library); /api/app and /api/live are changed on the way to the page to play each state.
Needs Playwright and Edge or Chrome; skips when missing. HOME_SHOTS=<folder> also saves a picture of every state
(light and dark, 1280 and 390 px).
  python tools/test_home_modes.py"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP playwright is not installed")
    sys.exit(0)
TMP = tempfile.mkdtemp()
os.environ["BZM_DATA_DIR"] = os.path.join(TMP, "data")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "local")
os.environ["BZM_NO_BROWSER"] = "1"
os.makedirs(os.environ["BZM_DATA_DIR"])
os.makedirs(os.environ["LOCALAPPDATA"])
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []
SHOTS = os.environ.get("HOME_SHOTS", "")


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)))
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


# a made-up library: two courses, the newest lecture has two marks (★) and a slide
LECS = [("מבוא למדעי המחשב", "2026-11-10 10-00 הרצאה", "2026-11-10 10:00", 0),
        ("מבוא למדעי המחשב", "2026-11-12 10-00 הרצאה", "2026-11-12 10:00", 0),
        ("חדוא 1", "2026-11-11 12-00 הרצאה", "2026-11-11 12:00", 0),
        ("חדוא 1", "2026-11-13 12-00 הרצאה", "2026-11-13 12:00", 2)]
for i, (c, name, when, marks) in enumerate(LECS):
    d = os.path.join(L.LIB_DIR, c, name)
    os.makedirs(os.path.join(d, "שקופיות"), exist_ok=True)
    rows = [f"# תמלול הרצאה (עברית) - התחלה {when}",
            "[10:01:00 | +0:01:00] היום נדבר על נגזרות של פונקציות מורכבות.",
            "[10:02:00 | +0:02:00] כלל השרשרת אומר שגוזרים את החיצונית ואז כופלים בפנימית."]
    if marks:
        rows += ["[10:02:30 | +0:02:30] [סימון: חשוב]", "[10:03:00 | +0:03:00] בואו נראה דוגמה עם סינוס.",
                 "[10:04:00 | +0:04:00] [סימון: חשוב]"]
    with open(os.path.join(d, name + ".txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    t = time.time() - (len(LECS) - i) * 3600
    os.utime(os.path.join(d, name + ".txt"), (t, t))
NEWEST = "חדוא 1/2026-11-13 12-00 הרצאה"
L.save_settings(consent_ok=True)
srv = L.AppServer()
assert srv.start()
url = srv.url.rstrip("/")

# the states, as the server would say them
NOW = time.time()
LIVE = {"kind": "live", "lang": "he", "title": "", "course": "חדוא 1", "course_now": "חדוא 1", "moving": False, "suggest": None,
        "saved": None, "ready": True, "done": False, "stopping": False, "error": None, "started": NOW - 754, "transcript": None,
        "yt": None, "ready_at": NOW - 750, "discard": False, "quick_stop_s": 10, "stopping_for": 0}
ENDED = dict(LIVE, done=True, saved={"course": "חדוא 1", "minutes": 48, "slides": 12, "f": NEWEST})
KEY = {"has_key": True, "ask": True, "plan": "free"}
NOKEY = {"has_key": False, "ask": False, "plan": "free"}
LIVE_FEED = {"total": 6, "since": 0, "draft": "", "pending": 0, "lag": 0, "fast": False, "shot": None, "info": {}, "ended": False,
             "items": [{"t": NOW - 300, "c": "10:20:00", "x": "נתחיל עם ההגדרה של גבול."},
                       {"t": NOW - 200, "c": "10:21:40", "x": "גבול הוא הערך שהפונקציה מתקרבת אליו."},
                       {"t": NOW - 190, "c": "10:21:50", "x": "[סימון: חשוב]"},
                       {"t": NOW - 100, "c": "10:23:20", "x": "עכשיו נראה למה זה עובד גם מצד שמאל."},
                       {"t": NOW - 60, "c": "10:24:00", "x": "וזה בדיוק המשפט שנשתמש בו בתרגיל."}]}

state = {"math": KEY, "session": None}


def launch(p):
    for kw in ({"channel": "msedge"}, {"channel": "chrome"}, {}):
        try:
            return p.chromium.launch(headless=True, **kw)
        except Exception:
            continue
    return None


COUNT_JS = """() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && (!e.checkVisibility || e.checkVisibility({contentVisibilityAuto: true, visibilityProperty: true})); };
  const probe = document.createElement("i"); probe.style.color = "var(--accent)"; document.body.appendChild(probe);
  const green = getComputedStyle(probe).color; probe.remove();
  const home = document.querySelector("#vHome");
  const all = [...home.querySelectorAll("*")].filter(vis);
  const greens = all.filter(e => getComputedStyle(e).backgroundColor === green && (e.matches("button,a,[role=button]")));
  const shadows = all.filter(e => getComputedStyle(e).boxShadow !== "none");
  return {mode: home.dataset.mode, greens: greens.map(e => e.id || e.textContent.trim().slice(0, 30)), shadows: shadows.map(e => e.id || e.className),
          wide: document.documentElement.scrollWidth - document.documentElement.clientWidth};
}"""


with sync_playwright() as p:
    b = launch(p)
    if b is None:
        print("SKIP no browser for Playwright")
        sys.exit(0)
    cmds = []

    def page(width=1280, scheme="light"):
        ctx = b.new_context(viewport={"width": width, "height": 900}, locale="he-IL", color_scheme=scheme)
        pg = ctx.new_page()
        pg.add_init_script("localStorage.setItem('bzm.consent','1');localStorage.setItem('bzm.tipSet','1');localStorage.setItem('bzm.noLiveTip','1')")

        def app_route(route):
            r = route.fetch()
            d = r.json()
            d["math"] = dict(d.get("math") or {}, **state["math"])
            d["session"] = state["session"]
            d["update"] = None
            if "go" in state:
                d["go"] = state["go"]
            route.fulfill(response=r, body=json.dumps(d), headers=dict(r.headers, **{"content-type": "application/json"}))

        def live_route(route):
            route.fulfill(status=200, body=json.dumps(LIVE_FEED), headers={"content-type": "application/json"})

        def cmd_route(route):
            try:
                body = json.loads(route.request.post_data or "{}")
            except ValueError:
                body = {}
            if body.get("action") in ("quick_new", "toggle_mini"):
                cmds.append(body.get("action"))
                route.fulfill(status=200, body=json.dumps({"ok": True, "opened": True}), headers={"content-type": "application/json"})
            else:
                route.continue_()
        pg.route("**/api/app*", app_route)
        pg.route("**/api/live*", live_route)
        pg.route("**/api/cmd", cmd_route)
        pg.goto(url + "/")
        return ctx, pg

    def wait_mode(pg, mode, ms=6000):
        try:
            pg.wait_for_function("m => document.querySelector('#vHome').dataset.mode === m", arg=mode, timeout=ms)
            return True
        except Exception:
            return False

    def one_green(pg, name):
        c = pg.evaluate(COUNT_JS)
        check(name + ": one solid green", len(c["greens"]) == 1, c["greens"])
        check(name + ": at most one shadow", len(c["shadows"]) <= 1, c["shadows"])
        return c

    def shot(pg, name):
        if SHOTS:
            os.makedirs(SHOTS, exist_ok=True)
            pg.wait_for_timeout(300)
            pg.screenshot(path=os.path.join(SHOTS, name + ".png"), full_page=True)

    # --- the states, one page that changes by itself (no reload) ---
    state.update(math=NOKEY, session=None)
    ctx, pg = page()
    check("no key: first time", wait_mode(pg, "first"), pg.evaluate("document.querySelector('#vHome').dataset.mode"))
    one_green(pg, "first")
    check("first: no popup any more", pg.locator("#setupCard").count() == 0)
    check("first: step 2 is grey until step 1 is done", pg.evaluate("document.querySelector('#stFirst').classList.contains('off') && document.querySelector('#stFirst').getAttribute('aria-disabled') === 'true'"))
    check("first: the video is there", pg.locator("#hFirst video[src='/teaser.mp4']").count() == 1)
    state.update(math=dict(NOKEY, plan="paid"))
    check("a paid AI app (no key): not the first time", wait_mode(pg, "day"))
    state.update(math=KEY, session=dict(LIVE))
    check("a lecture recorded now: live (without a reload)", wait_mode(pg, "live"))
    pg.wait_for_function("document.querySelectorAll('#hlNow li').length === 3", timeout=6000)
    check("live: the last three lines, the newest is the now-line",
          pg.evaluate("[...document.querySelectorAll('#hlNow li')].map(l => l.className)") == ["", "", "now"])
    check("live: the marks so far", "· 1" in pg.inner_text("#hlMarksT"), pg.inner_text("#hlMarksT"))
    check("live: recording pill with the time", pg.inner_text("#hlRec").startswith("מקליט · 12:"), pg.inner_text("#hlRec"))
    check("live: the course and the kind", pg.inner_text("#hlCourse") == "חדוא 1" and "עברית" in pg.inner_text("#hlKind"))
    one_green(pg, "live")
    pg.click("#hLive [data-float]")
    pg.wait_for_timeout(300)
    check("live: the green button opens the floating window", "toggle_mini" in cmds, cmds)
    state.update(session=dict(ENDED))
    check("the lecture ended in this run: ended", wait_mode(pg, "ended"))
    pg.wait_for_function("document.querySelectorAll('#heMarks li').length === 2", timeout=6000)
    check("ended: the marks, each opens 8 s before", f"{L.MARK_LEAD_S if hasattr(L, 'MARK_LEAD_S') else 8} שניות" in pg.inner_text("#heLead"), pg.inner_text("#heLead"))
    check("ended: title says how many", pg.inner_text("#heTitle").startswith("2 רגעים"), pg.inner_text("#heTitle"))
    check("ended: the line under the title", "48 דקות" in pg.inner_text("#heSub") and "12 שקופיות" in pg.inner_text("#heSub"), pg.inner_text("#heSub"))
    one_green(pg, "ended")
    pg.click("#heMarks li >> nth=0 >> button")
    pg.wait_for_function("location.hash.startsWith('#t=')", timeout=4000)
    at = pg.evaluate("decodeURIComponent(location.hash)")
    check("ended: 'לפתוח כאן' opens the lecture a few seconds before the mark", at.endswith("&at=142"), at)
    pg.evaluate("location.hash = ''")
    check("an ended lecture that was opened: back to a regular day", wait_mode(pg, "day"))
    one_green(pg, "day")
    check("day: the green card is the newest lecture with its marks",
          "חדוא 1" in pg.inner_text("#resTitle") and "2 סימונים" in pg.inner_text("#resSub"), pg.inner_text("#homeResume"))
    check("day: lecture number counted in the course", "הרצאה 2" in pg.inner_text("#resTitle"), pg.inner_text("#resTitle"))
    check("day: two course cards", pg.locator("#hCourses li").count() == 2)
    check("day: three recent lectures, each with 'פתיחה'", pg.locator("#hRecent li").count() == 3 and pg.locator("#hRecent button").count() == 3)
    pg.click("#startQuick")
    pg.wait_for_timeout(400)
    check("day: 'התחלת הרצאה' only asks for the quick-start window", "quick_new" in cmds, cmds)
    pg.click("#homeResume")
    pg.wait_for_function("location.hash.startsWith('#t=')", timeout=4000)
    at = pg.evaluate("decodeURIComponent(location.hash)")
    check("day: the green card opens the lecture at its first mark", at.endswith(NEWEST + "&at=142"), at)
    pg.evaluate("location.hash = ''")
    pg.click("#recTile")
    check("day: the recording box opens and the green card steps aside", pg.is_visible("#recBox") and not pg.is_visible("#homeResume"))
    one_green(pg, "day with the recording box")
    ctx.close()

    # --- "הדבקת מפתח" in the floating window while the app is open: the open window goes to the settings (no second window) ---
    state.update(math=KEY, session=None)
    state.pop("go", None)
    ctx, pg = page()
    wait_mode(pg, "day")
    pg.wait_for_timeout(1500)
    check("go: nothing asked, the page stays at home", pg.evaluate("location.hash") in ("", "#"), pg.evaluate("location.hash"))
    state["go"] = {"view": "settings", "n": 5}
    pg.wait_for_function("location.hash === '#settings'", timeout=6000)
    check("go: the server asks for the settings, the open window shows them", pg.is_visible("#vSettings"))
    pg.evaluate("location.hash = ''")
    pg.wait_for_timeout(2500)
    check("go: the same request is not played again", pg.evaluate("location.hash") in ("", "#"), pg.evaluate("location.hash"))
    ctx.close()
    state["go"] = {"view": "settings", "n": 5}
    ctx, pg = page()   # (a page that opens after the request: it only remembers it)
    wait_mode(pg, "day")
    pg.wait_for_timeout(2000)
    check("go: an old request is not replayed by a window that opens later", pg.evaluate("location.hash") in ("", "#"), pg.evaluate("location.hash"))
    ctx.close()
    state.pop("go", None)

    # --- the side column under the main card below 760 px; no sideways scroll at 320 ---
    for mode, st in (("first", {"math": NOKEY, "session": None}), ("live", {"math": KEY, "session": dict(LIVE)}),
                     ("ended", {"math": KEY, "session": dict(ENDED, started=NOW - 1)}), ("day", {"math": KEY, "session": None})):
        state.update(st)
        for w in (320, 700):
            ctx, pg = page(w)
            wait_mode(pg, mode)
            pg.wait_for_timeout(600)
            c = pg.evaluate(COUNT_JS)
            check(f"{mode} at {w}px: no sideways scroll", c["wide"] <= 0, c["wide"])
            if mode != "day":
                under = pg.evaluate(f"(() => {{ const s = document.querySelector('#h{mode[0].upper() + mode[1:]} .hside'), m = document.querySelector('#h{mode[0].upper() + mode[1:]} .hmain'); return s.getBoundingClientRect().top >= m.getBoundingClientRect().bottom - 1; }})()")
                check(f"{mode} at {w}px: the side column is under the main card", under)
            ctx.close()
        if SHOTS:
            for scheme in ("light", "dark"):
                for w in (1280, 390):
                    ctx, pg = page(w, scheme)
                    wait_mode(pg, mode)
                    if mode == "live":
                        pg.wait_for_function("document.querySelectorAll('#hlNow li').length === 3", timeout=6000)
                    if mode == "ended":
                        pg.wait_for_function("document.querySelectorAll('#heMarks li').length === 2", timeout=6000)
                    shot(pg, f"{mode}-{scheme}-{w}")
                    ctx.close()

    # --- accessibility settings: large text, high contrast, no motion: still one green, no sideways scroll ---
    state.update(math=KEY, session=dict(LIVE))
    ctx, pg = page(390)
    pg.add_init_script("localStorage.setItem('bzm.a11y', JSON.stringify({zoom: 1, tx: 1.4, contrast: true, still: true}))")
    pg.reload()
    wait_mode(pg, "live")
    pg.wait_for_timeout(600)
    c = pg.evaluate(COUNT_JS)
    check("live with large text and high contrast: no sideways scroll", c["wide"] <= 0, c["wide"])
    check("no motion: the recording dot is still", pg.evaluate("getComputedStyle(document.querySelector('#hlRec'), '::before').animationName") in ("none", ""))
    ctx.close()
    b.close()
srv.stop() if hasattr(srv, "stop") else None
print("all passed" if not fails else f"{len(fails)} failed")
sys.exit(1 if fails else 0)

"""Found in the deep review of 2.22 (15.11.2026), in a real browser:
 - the course shown at home (in the recording box since 17.11.2026) is the saved one, whichever of /api/app and /api/library answers first (P1), and the same in the quick-start window;
 - the top bar keeps one row at 390 px on every tab, the dot of a lecture's details never hangs at the start of a line;
 - the checkbox of the floating button sits on the first line of its text; the accessibility tab has its title;
 - the star in the small window says something when there is no lecture.
Needs Playwright and Edge or Chrome; skips when missing.
  python tools/test_review_222.py"""
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


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)))
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


for c in ("אלגוריתמים", "חדוא 2", "פיזיקה 1"):
    for i in (1, 2):
        d = os.path.join(L.LIB_DIR, c, "הרצאה %d" % i)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "הרצאה %d.txt" % i), "w", encoding="utf-8") as f:
            f.write("[09:01:00 | +0:01:00] שלום" + chr(10))
L.save_settings(course="פיזיקה 1", consent_ok=True)
srv = L.AppServer()
assert srv.start()
url = srv.url.rstrip("/")


def launch(p):
    for kw in ({"channel": "msedge"}, {"channel": "chrome"}, {}):
        try:
            return p.chromium.launch(headless=True, **kw)
        except Exception:
            continue
    return None


def hold(which, held):
    """A request whose URL has `which` is held until the test lets it go (the page keeps running meanwhile)."""
    def handler(route, request=None):
        if which in route.request.url:
            held.append(route)
        else:
            route.continue_()
    return handler


with sync_playwright() as p:
    b = launch(p)
    if b is None:
        print("SKIP no browser for Playwright")
        sys.exit(0)

    def page(path="/", width=1100, held=None, which=None):
        ctx = b.new_context(viewport={"width": width, "height": 900}, locale="he-IL")
        pg = ctx.new_page()
        pg.add_init_script("localStorage.setItem('bzm.consent','1');localStorage.setItem('bzm.setupNo','1');localStorage.setItem('bzm.how','1')")
        if which:
            pg.route("**/api/**", hold(which, held))
        pg.goto(url + path)
        pg.wait_for_timeout(500)
        pg.evaluate("document.querySelectorAll('.modal').forEach(m => { if (m.id !== 'consent') m.hidden = true })")
        return pg

    def late(path, which, sel, expect, note):
        held = []
        pg = page(path, held=held, which=which)
        pg.wait_for_timeout(1500)   # (the other answer is in; this one is still held)
        early = pg.evaluate("typeof curCourse === 'undefined' ? null : curCourse")
        for r in held:
            r.continue_()
        pg.wait_for_timeout(2500)
        v = pg.eval_on_selector(sel, "e => e.value")
        pg.context.close()
        return early, v

    # ---- P1: the saved course at home, whichever answer comes first ----
    for which in ("/api/app", "/api/library"):
        early, v = late("/", which, "#courseSel", "פיזיקה 1", which)
        check("home, the recording box: the saved course is shown when " + which + " answers late", v == "פיזיקה 1", (early, v))
        if which == "/api/library":   # the course list came before /api/app: no wrong course is chosen for the student in the meantime
            pass
    early, v = late("/", "/api/app", "#courseSel", "", "")
    check("home, the recording box: before /api/app answers the page chooses no course by itself", early in ("", None), early)
    # the same when there is no saved course: the first real course, as before
    L.save_settings(course="")
    early, v = late("/", "/api/app", "#courseSel", "", "")
    check("home, the recording box: with no saved course, a real course is shown (not 'ללא קורס') once both answers are in", v == "אלגוריתמים", v)
    L.save_settings(course="פיזיקה 1")
    # ---- the quick-start window ----
    for which in ("/api/app", "/api/library"):
        early, v = late("/quick", which, "#course", "פיזיקה 1", which)
        check("quick-start window: the saved course is shown when " + which + " answers late", v == "פיזיקה 1", v)

    # ---- the top bar at 390 px: one row on every tab ----
    pg = page(width=390)
    heights = {}
    for tab in ("home", "courses", "how", "settings"):
        pg.click('[data-nav="%s"]' % tab)
        pg.wait_for_timeout(350)
        heights[tab] = pg.evaluate("Math.round(document.querySelector('.bar').getBoundingClientRect().height)")
    check("top bar: the same height on every tab at 390 px (no jump to two rows)", len(set(heights.values())) == 1, heights)
    pg.click('[data-nav="courses"]')
    pg.wait_for_timeout(500)
    mp = pg.evaluate("(() => { const e = document.querySelector('#lib .m .mp'); return e ? getComputedStyle(e).whiteSpace : null })()")
    check("lecture list: each detail keeps its dot and never breaks inside (nowrap)", mp == "nowrap", mp)
    pg.context.close()

    # ---- the settings: the checkbox of the button, the title of the accessibility tab ----
    for width in (1100, 360):
        pg = page(width=width)
        pg.click('[data-nav="settings"]')
        pg.wait_for_timeout(300)
        pg.evaluate("openSettings('cap')")
        pg.wait_for_timeout(500)
        gap = pg.evaluate("(() => { const c = document.querySelector('#miniBtn'), l = c.closest('label'); return Math.round(c.getBoundingClientRect().top - l.getBoundingClientRect().top) })()")
        check("settings: the floating-button checkbox is on the first line of its text at %d px (top gap %s)" % (width, gap), 0 <= gap < 14, gap)
        pg.evaluate("openSettings('a11y')")
        pg.wait_for_timeout(300)
        h = pg.evaluate("(() => { const h = document.querySelector('#set-a11y h2'); return h ? h.textContent : '' })()")
        check("settings: the accessibility tab opens with a title", "נגישות" in h, h)
        pg.context.close()

    # ---- the star in the small window without a lecture ----
    pg = page("/mini")
    pg.wait_for_timeout(500)
    pg.click("#markImp")
    pg.wait_for_timeout(600)
    toast = pg.evaluate("(() => { const t = document.querySelector('#toast'); return [t.classList.contains('on'), t.textContent] })()")
    check("small window: the star with no lecture shows a message", toast[0] and len(toast[1].strip()) > 5, toast)
    pg.context.close()
    b.close()

srv.stop()
print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.exit(1 if fails else 0)

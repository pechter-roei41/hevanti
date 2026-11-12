"""Design round 3 (12.11.2026): the decisions that were taken stay taken. One solid green on the home page; one shape for "where am I"
and one for "a choice"; the lecture menu keeps its destructive item apart; the tool's messages are in the report dialog and not at
the foot of every screen; the settings answers tab is split. Needs Playwright and Edge or Chrome; skips when missing.
  python3 tools/test_design3.py"""
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
LEC_HASH = "#t=%D7%A4%D7%99%D7%96%D7%99%D7%A7%D7%94%201/" + LECT.replace(" ", "%20")
COURSE_HASH = "#c=%D7%A4%D7%99%D7%96%D7%99%D7%A7%D7%94%201"
# the colour of a token as the browser draws it, so a rule is compared with the real thing
TOKEN = """(v) => { const p = document.createElement('i'); p.style.background = 'var(%s)'; document.body.appendChild(p); const c = getComputedStyle(p).backgroundColor; p.remove(); return c; }"""


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
with sync_playwright() as p:
    b = launch(p)
    if b is None:
        print("SKIP no browser for Playwright")
        sys.exit(0)
    for theme in ("light", "dark"):
        def page(w=1280, h=900, hash_="#"):
            pg = b.new_context(viewport={"width": w, "height": h}, locale="he-IL", color_scheme=theme).new_page()
            pg.goto(url + "/" + hash_)
            pg.wait_for_timeout(1200)
            pg.evaluate("document.querySelectorAll('.modal').forEach(m => m.hidden = true); document.documentElement.dataset.theme = '%s'" % theme)
            return pg

        def tok(pg, name):
            return pg.evaluate(TOKEN % name, name)

        pg = page()
        solid = pg.evaluate("""() => { const p = document.createElement('button'); p.className = 'btn'; document.body.appendChild(p); const g = getComputedStyle(p).backgroundColor; p.remove();
            return [...document.querySelectorAll('#vHome button, #vHome a')].filter(x => x.offsetParent !== null && getComputedStyle(x).backgroundColor === g).map(x => x.textContent.trim().slice(0, 20)); }""")
        check(f"home, {theme}: one solid green control (the live lecture card)", len(solid) == 1, solid)
        ver = pg.evaluate("document.querySelector('#ver').textContent")
        check(f"home, {theme}: the foot has the date and not a second version number, no message log, and the app closes from it",
              ver == "עודכנה ב-" + L.VERSION_DATE and L.VERSION not in ver and pg.evaluate("!document.querySelector('main > #logBox')") and pg.is_visible("#quitBtn"), ver)
        check(f"report dialog, {theme}: the tool's messages are in it", pg.evaluate("!!document.querySelector('#report #logBox')"))
        nav = pg.evaluate("(() => { const s = getComputedStyle(document.querySelector('.nav button[aria-current=page]')); return [s.backgroundColor, s.fontWeight]; })()")
        check(f"navigation, {theme}: the current tab is sunk paper, 800", nav[0] == tok(pg, "--sunk") and nav[1] == "800", nav)
        pg.context.close()

        pc = page(hash_=COURSE_HASH)
        cs = pc.evaluate("getComputedStyle(document.querySelector('.ctabs button[aria-selected=true]')).backgroundColor")
        check(f"course page tabs, {theme}: the selected tab is sunk paper like the top bar", cs == tok(pc, "--sunk"), cs)
        pc.context.close()

        pl = page(hash_="#courses")
        ft = pl.evaluate("(() => { const e = document.querySelector('#libTabs button[aria-pressed=true]'); return e ? getComputedStyle(e).backgroundColor : null; })()")
        check(f"course filter, {theme}: the chosen course is soft green, not the heaviest thing on the screen", ft == tok(pl, "--accent-soft"), ft)
        pl.context.close()

        pp = page(hash_=LEC_HASH)
        pp.click("#pastMenu summary")
        mn = pp.evaluate("""() => { const d = document.querySelector('#pastDelShots'), m = document.querySelector('#pastMore'), p = document.createElement('i'); p.style.color = 'var(--rec)'; document.body.appendChild(p);
            const rec = getComputedStyle(p).color; p.remove();
            return {rec: getComputedStyle(d).color === rec, sep: !!d.previousElementSibling && d.previousElementSibling.matches('hr'), neutral: getComputedStyle(m).color !== rec, label: m.textContent.trim(),
                    head: document.querySelector('#pastAsk .head').hidden}; }""")
        check(f"lecture menu, {theme}: the delete item is apart (a rule above it) and in the destructive colour; the rename item is neutral",
              mn["rec"] and mn["sep"] and mn["neutral"] and mn["label"] == "העברה או שינוי שם", mn)
        check(f"lecture page, {theme}: the question box does not repeat its title", mn["head"], mn)
        pp.context.close()

        ps = page(hash_="#settings")
        tabs = ps.evaluate("[...document.querySelectorAll('#setTabs > *')].map(x => x.textContent.trim())")
        check(f"settings, {theme}: the tabs", tabs == ["מפתח", "התאמת התשובות", "צילום וטשטוש", "נגישות", "מתקדם", "פרטיות"], tabs)
        h = ps.evaluate("document.querySelector('#set-key').getBoundingClientRect().height")
        check(f"settings, {theme}: the key tab is no longer 933px long", h < 700, h)
        ps.context.close()

        pn = page(320, 700, LEC_HASH)
        pn.click("#pastMenu summary")
        sw = pn.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        box = pn.evaluate("(() => { const r = document.querySelector('#pastMenu .menu').getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right)]; })()")
        check(f"lecture menu at 320px, {theme}: open, it stays on the screen", sw <= 0 and box[0] >= 0 and box[1] <= 320, (sw, box))
        pn.context.close()
    b.close()
srv.stop()
print()
print("all passed" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)

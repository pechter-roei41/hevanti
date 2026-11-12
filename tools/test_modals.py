"""Every dialog of the app works with the keyboard (audit 12.11.2026, #37): when it opens the focus goes into it and the page behind it
cannot be reached, Tab stays inside it, Escape is its own cancel button, and the focus goes back where it was. Needs Playwright and
Edge or Chrome; skips when missing.
  python3 tools/test_modals.py"""
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
os.makedirs(os.path.join(TMP, "data", "הקורסים שלי", "פיזיקה 1"))
os.makedirs(os.environ["LOCALAPPDATA"])
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
L.save_settings(consent_ok=True)

INSIDE = "(id) => { const m = document.getElementById(id); return !!m && m.contains(document.activeElement); }"
with sync_playwright() as p:
    b = launch(p)
    if b is None:
        print("SKIP no browser for Playwright")
        sys.exit(0)
    pg = b.new_context(viewport={"width": 1100, "height": 800}, locale="he-IL").new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url + "/#settings")
    pg.wait_for_timeout(900)
    pg.evaluate("document.querySelectorAll('.modal').forEach(m => m.hidden = true)")
    pg.wait_for_timeout(100)
    # a button on the page opens a dialog (the display and accessibility one, or the confirm one as a fallback)
    opener = pg.evaluate("""() => { const b = document.createElement('button'); b.id = 'testOpener'; b.textContent = 'x';
        document.querySelector('main').appendChild(b); b.focus(); return document.activeElement === b; }""")
    # the confirm dialog, opened the way the app opens it (its buttons are wired when it opens)
    pg.evaluate("() => { window.__r = 'open'; confirmBox('בדיקה', 'טקסט').then(v => { window.__r = v; }); return 1; }")
    pg.wait_for_timeout(150)
    check("a dialog that opens takes the focus", pg.evaluate(INSIDE, "confirm"), pg.evaluate("document.activeElement && document.activeElement.outerHTML.slice(0, 120)"))
    check("the page behind an open dialog cannot be reached (inert)", pg.evaluate("document.querySelector('main').hasAttribute('inert') && document.querySelector('header').hasAttribute('inert')"))
    stayed = True
    for _ in range(12):
        pg.keyboard.press("Tab")
        stayed = stayed and pg.evaluate(INSIDE, "confirm")
    for _ in range(6):
        pg.keyboard.press("Shift+Tab")
        stayed = stayed and pg.evaluate(INSIDE, "confirm")
    check("Tab and Shift+Tab stay inside the dialog", stayed)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)
    check("Escape is the dialog's own cancel button (it closes, and answers 'no')", pg.evaluate("document.getElementById('confirm').hidden") and pg.evaluate("window.__r") is False, pg.evaluate("window.__r"))
    check("...the page can be reached again, and the focus is back where it was",
          not pg.evaluate("document.querySelector('main').hasAttribute('inert')") and opener and pg.evaluate("document.activeElement && document.activeElement.id") == "testOpener",
          pg.evaluate("document.activeElement && document.activeElement.id"))
    # the dialogs whose close button is always wired close with Escape too
    bad = []
    for mid in ("report", "offer", "conn", "renCourse", "capModal"):
        pg.evaluate("(id) => { document.querySelectorAll('.modal').forEach(m => m.hidden = true); document.getElementById(id).hidden = false; }", mid)
        pg.wait_for_timeout(80)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(150)
        if not pg.evaluate("(id) => document.getElementById(id).hidden", mid):
            bad.append(mid)
    check("those dialogs close with Escape", not bad, bad)
    check("no script errors", not errors, errors[:3])
    b.close()
srv.stop()
print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.exit(1 if fails else 0)

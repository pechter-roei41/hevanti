"""The core in a real browser: the marks tab of a lecture, the first-time consent, and the ask box (answers inside Hevanti,
copy buttons only without a key or when chosen in the settings). Needs Playwright and Edge or Chrome; skips when missing.
  python3 tools/test_core_ui.py"""
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


srv = L.AppServer()
assert srv.start()
url = srv.url.rstrip("/")
entry = {"title": "הרצאה", "course": "קורס", "when": "11:04 2026-11-01", "lang": "he", "length": "00:40:04", "lines": 12,
         "kind": "rec", "has_media": True, "f": "c/t"}
lines = [{"t": i * 5, "c": "00:%02d" % i, "x": "שורה מספר %d בתמלול" % i} for i in range(12)]
lines.insert(4, {"t": 20, "c": "00:20", "note": "סימון: לא הבנתי"})
lines.insert(9, {"t": 45, "c": "00:45", "note": "סימון: חשוב"})
no_marks = [x for x in lines if not x.get("note")]


def launch(p):
    for kw in ({"channel": "msedge"}, {"channel": "chrome"}, {}):
        try:
            return p.chromium.launch(headless=True, **kw)
        except Exception:
            continue
    return None


with sync_playwright() as p:
    b = launch(p)
    if b is None:
        print("SKIP no browser for Playwright")
        sys.exit(0)

    def page(data=None):
        pg = b.new_context(viewport={"width": 1100, "height": 900}, locale="he-IL").new_page()
        pg.errs = []
        pg.on("pageerror", lambda e: pg.errs.append(str(e)))
        if data is not None:
            pg.route("**/api/transcript*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(data)))
        pg.goto(url + "/")
        pg.wait_for_timeout(1200)
        pg.evaluate("document.querySelectorAll('.modal').forEach(m => { if (m.id !== 'consent') m.hidden = true })")
        return pg

    # ---- the marks tab of a lecture ----
    pg = page({"entry": entry, "lines": lines, "summary": ""})
    pg.evaluate("openPast('c/t')")
    pg.wait_for_timeout(800)
    check("marks tab: shown when the lecture has marks", not pg.evaluate("document.querySelector('#pastTabs').hidden"))
    check("marks tab: study first", not pg.evaluate("document.querySelector('#pastPanelStudy').hidden"))
    pg.click("[data-pt=marks]")
    rows = pg.evaluate("[...document.querySelectorAll('#pastMkList .mk')].map(x => x.innerText)")
    check("marks tab: a row per mark, with what was said before", len(rows) == 2 and "לפני הסימון נאמר" in rows[0] and "לא הבנתי" in rows[0] and "חשוב" in rows[1], rows)
    pg.click("#pastMkList .mk button")
    pg.wait_for_timeout(300)
    check("marks tab: 'in the transcript' opens it at the moment", pg.evaluate(
        "[!document.querySelector('#pastPanelStudy').hidden, document.querySelector('#pastTrFold').open, !!document.querySelector('#pastLines li.hit')]") == [True, True, True])
    check("marks tab: no script errors", pg.errs == [], pg.errs)
    pg = page({"entry": entry, "lines": no_marks, "summary": ""})
    pg.evaluate("openPast('c/t')")
    pg.wait_for_timeout(800)
    check("marks tab: hidden when there are no marks", pg.evaluate("document.querySelector('#pastTabs').hidden"))

    # ---- the first-time consent before a lecture starts ----
    pg = page()
    pg.evaluate("localStorage.removeItem('bzm.consent')")
    pg.click("[data-start=he]")
    pg.wait_for_timeout(300)
    check("consent: asked before the first lecture", pg.is_visible("#consent"))
    check("consent: 'continue' is locked until the box is checked", pg.evaluate("document.querySelector('#consOk').disabled"))
    pg.click("#consNo")
    pg.wait_for_timeout(300)
    check("consent: cancel starts nothing", not pg.is_visible("#consent") and pg.evaluate("location.hash") in ("", "#"), pg.evaluate("location.hash"))
    pg.click("[data-start=he]")
    pg.check("#consCheck")
    check("consent: 'continue' opens once the box is checked", not pg.evaluate("document.querySelector('#consOk').disabled"))
    check("consent: nothing is remembered before it is accepted", pg.evaluate("localStorage.getItem('bzm.consent')") is None)

    # ---- the ask box ----
    pg = page()
    pg.evaluate("""() => { window.__d = document.createElement('div'); document.body.appendChild(window.__d);
      window.__a = BZMAsk.mount(window.__d, {context: q => q, toast() {}}); }""")
    vis = "() => [...__d.querySelectorAll('.ais button')].filter(b => !b.hidden).map(b => b.textContent)"
    pg.evaluate("BZMAsk.setBuiltin(false); BZMAsk.setExternal(false)")
    names = pg.evaluate(vis)
    check("ask box without a key: the copy buttons are there, and it says where to get the key", "ChatGPT" in names and "תשובה כאן" not in names
          and "מפתח" in pg.evaluate("__d.querySelector('p.hint').textContent"), names)
    pg.evaluate("BZMAsk.setBuiltin(true); BZMAsk.setExternal(false)")
    check("ask box with a key: only 'answer here' (answers are inside Hevanti)", pg.evaluate(vis) == ["תשובה כאן"], pg.evaluate(vis))
    pg.evaluate("BZMAsk.setExternal(true)")
    check("ask box with a key and 'external AI' on: the copy buttons come back", {"תשובה כאן", "ChatGPT", "Gemini", "Claude"} <= set(pg.evaluate(vis)), pg.evaluate(vis))
    pg.evaluate("BZMAsk.setExternal(false)")
    check("ask box: the paid-plan question is not asked while it is off", pg.evaluate("BZMAsk.setPlan(''); __d.querySelector('.plan').hidden"))

    # ---- own instructions for the answers (Settings) ----
    L.save_settings(math={"key": L.keep_secret("AQ.fake"), "ask": True})
    pg = page()
    pg.evaluate("openSettings('key')")
    pg.wait_for_timeout(500)
    check("own instructions: the field is there, and open once a key is saved", pg.is_visible("#notesIn") and not pg.evaluate("document.querySelector('#notesIn').disabled"))
    pg.click("[data-note]")
    typed = pg.evaluate("document.querySelector('#notesIn').value")
    check("own instructions: an example adds its text", typed != "" and pg.evaluate("document.querySelector('#notesCount').textContent") == f"{len(typed)}/500", typed)
    pg.click("#notesSave")
    pg.wait_for_timeout(600)
    check("own instructions: saved by Hevanti", L.math_settings().get("notes") == typed.strip(), (typed, L.math_settings().get("notes")))
    pg.reload()
    pg.wait_for_timeout(1200)
    pg.evaluate("openSettings('key')")
    pg.wait_for_timeout(400)
    check("own instructions: still there after a reload", pg.evaluate("document.querySelector('#notesIn').value") == typed.strip())
    check("own instructions: no script errors", pg.errs == [], pg.errs)
    L.save_settings(math={})
    pg = page()
    pg.evaluate("openSettings('key')")
    check("own instructions: without a key the field is closed", pg.evaluate("document.querySelector('#notesIn').disabled"))

    # ---- report a problem ----
    pg = page()
    perr = []
    pg.on("pageerror", lambda e: perr.append(str(e)))
    pg.click("#repBtn")
    pg.wait_for_function("document.querySelector('#repText').value.includes('Windows')", timeout=8000)
    rep = pg.evaluate("document.querySelector('#repText').value")
    check("report a problem: the details are shown, with a place to say what happened", pg.is_visible("#report") and rep.startswith("מה קרה") and "הבנתי " in rep, rep[:200])
    check("report a problem: the GitHub button opens a new issue", pg.evaluate("document.querySelector('#repGit').href").endswith("/issues/new"))
    pg.click("#repClose")
    check("report a problem: closes, no script errors", not pg.is_visible("#report") and perr == [], perr)

    # ---- the floating window ----
    mini = b.new_context(viewport={"width": 420, "height": 760}, locale="he-IL").new_page()
    errs = []
    mini.on("pageerror", lambda e: errs.append(str(e)))
    mini.goto(url + "/mini")
    mini.wait_for_timeout(1200)
    check("floating window: the question box and both marks", mini.is_visible("textarea") and mini.is_visible("#markImp") and mini.is_visible("#markLost"))
    marked = []
    mini.route("**/api/cmd", lambda r: (marked.append(json.loads(r.request.post_data or "{}")), r.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, "kind": "lost"})))[1])
    mini.click("#markLost")
    mini.wait_for_timeout(300)
    check("floating window: '?' sends a mark to Hevanti", any(m.get("action") in ("mark", "mark_moment") or "mark" in str(m.get("action")) for m in marked), marked)
    # an AI chosen in the floating window: the window goes away (it stays on top, the AI would open behind it)
    marked.clear()
    mini.evaluate("BZMAsk.setBuiltin(false)")
    mini.fill("textarea", "מה זה?")
    mini.click("button[data-ai=gemini]")
    mini.wait_for_timeout(1500)
    check("floating window: choosing Gemini hides the floating window", any(m.get("action") == "hide_mini" for m in marked), marked)
    check("floating window: no script errors", errs == [], errs)
    b.close()

print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.exit(1 if fails else 0)
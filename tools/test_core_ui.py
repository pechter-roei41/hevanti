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
    check("marks tab: ...and from a few seconds BEFORE the mark (a mark is made after the lecturer said it)",
          pg.evaluate("[MARK_LEAD_S, document.querySelector('#pastLines li.hit')._x.t]") == [8, 10], pg.evaluate("document.querySelector('#pastLines li.hit')._x.t"))
    check("marks tab: no script errors", pg.errs == [], pg.errs)
    # the course page's list of marks opens the lecture a few seconds before the mark
    pg = page()
    pg.route("**/api/marks*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(
        {"marks": [{"f": "c/t", "title": "הרצאה", "when": "x", "t": 20, "c": "00:20", "kind": "חשוב", "said": "משהו"}]})))
    pg.evaluate("courseName = 'קורס'; drawMarks('קורס')")
    pg.wait_for_timeout(500)
    pg.evaluate("document.querySelector('#mkList .mk button').click()")   # (the course page is not the one on view: a script click)
    pg.wait_for_timeout(200)
    check("course marks: 'open at this moment' is 8 seconds before the mark", pg.evaluate("location.hash").endswith("&at=12"), pg.evaluate("location.hash"))
    pg = page({"entry": entry, "lines": no_marks, "summary": ""})
    pg.evaluate("openPast('c/t')")
    pg.wait_for_timeout(800)
    check("marks tab: hidden when there are no marks", pg.evaluate("document.querySelector('#pastTabs').hidden"))

    # ---- the sources of an answer: times in square brackets become chips; a click only for a time that was sent ----
    pg = page()
    r = pg.evaluate("""() => {
      const out = {}, t = document.createElement('div'); document.body.appendChild(t); window.__go = [];
      BZMAsk.render(document, t, "הסבר [00:20:44] ועוד [00:99:99] וגם [1:05] ו**בולד** כאן.", {go: l => window.__go.push(l), known: new Set(["00:20:44", "01:05"])});
      out.buttons = [...t.querySelectorAll('button.src')].map(b => b.textContent);
      out.plain = [...t.querySelectorAll('span.src')].map(b => b.textContent);
      t.querySelector('button.src').click(); out.went = window.__go.slice();
      const u = document.createElement('div'); document.body.appendChild(u);
      BZMAsk.render(document, u, "ללא עמוד תמלול [00:20:44].");
      out.noGo = [u.querySelectorAll('button.src').length, u.querySelectorAll('span.src').length, u.textContent];
      return out; }""")
    check("sources: a time that was sent is a button, a made-up time is only text", r["buttons"] == ["⏱ 00:20:44", "⏱ 01:05"] and r["plain"] == ["⏱ 00:99:99"], r)
    check("sources: a click goes to that line of the transcript", r["went"] == ["00:20:44"], r)
    check("sources: a page that cannot open the transcript (the floating window): chips, not buttons", r["noGo"][0] == 0 and r["noGo"][1] == 1, r)

    # ---- the course of the lecture about to start: guessed, selected, with the reason; until the student chooses ----
    L.create_course("אלגברה לינארית")
    L.create_course("פיזיקה")
    pg = page()
    guess = {"ok": True, "course": "פיזיקה", "why": "title", "detail": "Zoom - פיזיקה 1"}

    def cmd(route):
        body = json.loads(route.request.post_data or "{}")
        if body.get("action") == "guess_course":
            route.fulfill(status=200, content_type="application/json", body=json.dumps(guess))
        else:
            route.continue_()
    pg.route("**/api/cmd", cmd)
    pg.evaluate("autoCourse()")
    pg.wait_for_timeout(600)
    check("course guess: selected, with the reason beside it", pg.evaluate("document.querySelector('#courseSel').value") == "פיזיקה"
          and "נבחר לפי החלון" in pg.evaluate("document.querySelector('#courseAuto').textContent") and pg.is_visible("#courseAuto"),
          pg.evaluate("[document.querySelector('#courseSel').value, document.querySelector('#courseAuto').textContent]"))
    pg.select_option("#courseSel", "אלגברה לינארית")
    pg.wait_for_timeout(300)
    pg.evaluate("autoCourse()")
    pg.wait_for_timeout(600)
    check("course guess: after the student chooses a course, it is never changed again", pg.evaluate("document.querySelector('#courseSel').value") == "אלגברה לינארית"
          and not pg.is_visible("#courseAuto"), pg.evaluate("document.querySelector('#courseSel').value"))
    guess = {"ok": True, "course": "פיזיקה", "why": "schedule", "detail": "2 הרצאות קודמות ביום ראשון בסביבות 11:00"}
    pg = page()
    pg.route("**/api/cmd", cmd)
    pg.evaluate("autoCourse()")
    pg.wait_for_timeout(600)
    check("course guess: by the weekly schedule it says so", "המערכת השבועית" in pg.evaluate("document.querySelector('#courseAuto').textContent"), pg.evaluate("document.querySelector('#courseAuto').textContent"))
    guess = {"ok": True}
    pg = page()
    pg.route("**/api/cmd", cmd)
    pg.evaluate("autoCourse()")
    pg.wait_for_timeout(500)
    check("course guess: no guess, no note and nothing changed", not pg.is_visible("#courseAuto"))

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
    top, foot = pg.evaluate("document.querySelector('#verTop').textContent"), pg.evaluate("document.querySelector('#ver').textContent")
    check("beta: the header and the footer say it is a beta, with the version", top.startswith("בטא ") and "בטא" in foot and L.VERSION in top and L.VERSION in foot, (top, foot))
    pg.click("#repBtn")
    pg.wait_for_function("document.querySelector('#repText').value.includes('Windows')", timeout=8000)
    rep = pg.evaluate("document.querySelector('#repText').value")
    check("report a problem: the details are shown, with a place to say what happened", pg.is_visible("#report") and rep.startswith("מה קרה") and "הבנתי " in rep, rep[:200])
    check("report a problem: the GitHub button opens a new issue", pg.evaluate("document.querySelector('#repGit').href").endswith("/issues/new"))
    pg.click("#repClose")
    check("report a problem: closes, no script errors", not pg.is_visible("#report") and perr == [], perr)

    # ---- the top bar (2.14): tabs, the settings page, the guide, light / dark ----
    pg = page()
    cur = "[...document.querySelectorAll('[data-nav][aria-current=page]')].map(a => a.dataset.nav)"
    check("top bar: four tabs, home is the current one", pg.evaluate("[...document.querySelectorAll('[data-nav]')].map(a => a.textContent.trim())")
          == ["בית", "הקורסים שלי", "איך משתמשים", "הגדרות"] and pg.evaluate(cur) == ["home"], pg.evaluate(cur))
    check("home: only starting a lecture (the course list is its own tab)", pg.is_visible("[data-start=he]") and not pg.is_visible("#lib"))
    pg.click("[data-nav=courses]")
    pg.wait_for_timeout(500)
    check("tab 'my courses': the courses and the search", pg.is_visible("#lib") and pg.is_visible("#libFind") and pg.evaluate(cur) == ["courses"], pg.evaluate(cur))
    pg.click("[data-nav=settings]")
    pg.wait_for_timeout(500)
    check("tab 'settings': a page with its menu, not a popup", pg.is_visible("#vSettings") and pg.is_visible("#settab-cap") and pg.is_visible("#set-key")
          and pg.evaluate(cur) == ["settings"])
    pg.click("#settab-cap")
    check("settings: the menu switches the part", pg.is_visible("#set-cap") and not pg.is_visible("#set-key"))
    pg.go_back()
    pg.wait_for_timeout(400)
    check("settings: Back returns to the page before", pg.is_visible("#lib"), pg.evaluate("location.hash"))
    pg.click("[data-nav=how]")
    pg.wait_for_timeout(400)
    check("tab 'how to use': the video and the guide, inside the app", pg.is_visible("#vHow video") and pg.is_visible("#g-key") and pg.is_visible("#g-fix"))
    before = pg.evaluate("matchMedia('(prefers-color-scheme: dark)').matches")
    pg.click("#themeBtn")
    pg.wait_for_timeout(400)
    want = "light" if before else "dark"
    check("light/dark: the button switches, and Hevanti keeps the choice", pg.evaluate("document.documentElement.dataset.theme") == want
          and L.ui_theme() == want and pg.evaluate("getComputedStyle(document.body).backgroundColor") != "", (pg.evaluate("document.documentElement.dataset.theme"), L.ui_theme()))
    mini0 = b.new_context(viewport={"width": 420, "height": 600}, locale="he-IL").new_page()
    mini0.goto(url + "/mini")
    mini0.wait_for_timeout(1500)
    check("light/dark: the floating window follows it", mini0.evaluate("document.documentElement.dataset.theme") == want, mini0.evaluate("document.documentElement.dataset.theme"))
    mini0.context.close()
    L.save_settings(theme="")
    check("top bar: no script errors", pg.errs == [], pg.errs)

    # ---- the floating window ----
    mini = b.new_context(viewport={"width": 420, "height": 760}, locale="he-IL").new_page()
    errs = []
    mini.on("pageerror", lambda e: errs.append(str(e)))
    # The window asks Hevanti every 4 seconds what is running and whether "answer here" is set up, and shows or hides its parts by
    # that. A test that only flips those parts by hand races with that poll (the button it clicks is hidden again): so the test says
    # what Hevanti answers - a lecture is running, and "answer here" is on or off - and the window follows it, as in real use.
    mini_state = {"live": True, "ask": True}

    def mini_app(route):
        resp = route.fetch()
        d = resp.json()
        d["session"] = {"kind": "live", "done": False, "course": "פיזיקה"} if mini_state["live"] else None
        d["math"] = dict(d.get("math") or {}, ask=mini_state["ask"])
        route.fulfill(response=resp, body=json.dumps(d))
    mini.route("**/api/app*", mini_app)
    mini.goto(url + "/mini")
    mini.wait_for_timeout(1200)
    check("floating window: the question box and the ★ mark (no '?')", mini.is_visible("textarea") and mini.is_visible("#markImp") and mini.query_selector("#markLost") is None)
    marked = []
    mini.route("**/api/cmd", lambda r: (marked.append(json.loads(r.request.post_data or "{}")), r.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, "kind": "חשוב"})))[1])
    mini.click("#markImp")
    mini.wait_for_timeout(300)
    check("floating window: ★ sends an 'important' mark to Hevanti", any(m.get("action") == "mark" and m.get("kind") == "important" for m in marked), marked)
    # the first key of a question asks Hevanti for a picture of the screen of that moment - once per question
    marked.clear()
    mini.fill("textarea", "מ")
    mini.wait_for_timeout(200)
    mini.fill("textarea", "מה זה")
    mini.wait_for_timeout(300)
    check("floating window: the first key of a question asks for a picture (once)", [m.get("action") for m in marked].count("snap_question") == 1, marked)
    mini.fill("textarea", "")
    # "what I missed": three buttons, each a ready question over the last 3 / 7 / 15 minutes
    asked = []
    mini.route("**/api/ask", lambda r: (asked.append(json.loads(r.request.post_data or "{}")), r.fulfill(status=200, content_type="text/plain", body="סיכום"))[1])
    mini_state["ask"] = True
    mini.evaluate("pollApp()")
    mini.wait_for_selector("#miss button[data-m='3']", state="visible", timeout=10000)
    check("floating window: three 'what I missed' buttons", mini.evaluate("[...document.querySelectorAll('#miss button')].map(b => b.dataset.m).join()") == "3,7,15")
    for n in (3, 7, 15):
        mini.wait_for_selector(f"#miss button[data-m='{n}']", state="visible", timeout=10000)
        mini.click(f"#miss button[data-m='{n}']")
        mini.wait_for_timeout(600)
    check("floating window: each sends its minutes, from the small window, with a ready question",
          [a.get("minutes") for a in asked] == [3, 7, 15] and all(a.get("where") == "mini" and "פספסתי" in a.get("question", "") for a in asked), asked)
    check("floating window: a ready question does not ask for a picture of its own", [m.get("action") for m in marked].count("snap_question") == 1, marked)
    # an AI chosen in the floating window: the window goes away (it stays on top, the AI would open behind it)
    marked.clear()
    mini_state["ask"] = False
    mini.evaluate("pollApp()")
    mini.wait_for_selector("button[data-ai=gemini]", state="visible", timeout=10000)
    mini.fill("textarea", "מה זה?")
    mini.click("button[data-ai=gemini]")
    mini.wait_for_timeout(1500)
    check("floating window: choosing Gemini hides the floating window", any(m.get("action") == "hide_mini" for m in marked), marked)
    check("floating window: no script errors", errs == [], errs)

    # ---- 2.18: the missing-key bar, the settings, Hebrew counts, no date and time twice ----
    L.save_settings(math={})
    pg = b.new_context(viewport={"width": 1100, "height": 900}, locale="he-IL").new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(url + "/")
    pg.wait_for_function("document.querySelector('#keyBar') && !document.querySelector('#keyBar').hidden", timeout=8000)
    check("no key: a bar above the cards says so, with a button to paste the key",
          "חסר מפתח Gemini" in pg.inner_text("#keyBar") and pg.inner_text("#keyBarGo") == "הדבקת מפתח", pg.inner_text("#keyBar"))
    check("...it is above the cards that start a lecture", pg.evaluate("document.querySelector('#keyBar').getBoundingClientRect().bottom <= document.querySelector('.starts').getBoundingClientRect().top"))
    check("...in the caution colours (the page's own caution paper), over the whole width",
          pg.evaluate("""() => { const p = document.createElement('div'); p.style.cssText = 'background:var(--warn-bg);color:var(--warn-fg)'; document.body.appendChild(p);
              const a = getComputedStyle(p), b = getComputedStyle(document.querySelector('#keyBar')), r = document.querySelector('#keyBar').getBoundingClientRect(),
                    c = document.querySelector('.starts').getBoundingClientRect();
              const ok = a.backgroundColor === b.backgroundColor && a.color === b.color && Math.abs(r.width - c.width) < 4; p.remove(); return ok; }"""))
    check("...and the small status line says nothing more about the key", pg.evaluate("document.querySelector('#homeAns').hidden"))
    pg.click("#setupLater")
    check("'not now' closes the first-start card", not pg.is_visible("#setupCard"))
    pg.click("#keyBarGo")
    check("the button in the bar opens the paste-the-key card again, with the cursor in the box",
          pg.is_visible("#setupCard") and pg.evaluate("document.activeElement.id") == "setupKey", pg.evaluate("document.activeElement.id"))
    L.save_settings(math={"key": L.keep_secret("AQ.fake"), "ask": True})
    pg.wait_for_function("document.querySelector('#keyBar').hidden", timeout=8000)
    check("with a key: the bar is gone, and the status line is back", not pg.evaluate("document.querySelector('#homeAns').hidden") and "מוכן" in pg.inner_text("#homeAns"), pg.inner_text("#homeAns"))
    check("the keyboard shortcuts have a row of their own, under the status",
          pg.evaluate("document.querySelector('.hkeys').getBoundingClientRect().top >= document.querySelector('#homeAns').getBoundingClientRect().bottom - 1"))
    L.save_settings(math={"plan": "paid"})
    pg.wait_for_function("document.querySelector('#keyBar').hidden && document.querySelector('#homeAns').textContent.includes('מנוי')", timeout=8000)
    check("a paid AI plan and no key: no bar (the questions go to the student's AI app)", "מנוי" in pg.inner_text("#homeAns"), pg.inner_text("#homeAns"))
    L.save_settings(math={"key": L.keep_secret("AQ.fake"), "ask": True})

    pg.evaluate("openSettings('key')")
    pg.wait_for_timeout(500)
    heads = pg.evaluate("[...document.querySelectorAll('#set-key .optbox h4')].map(h => h.textContent.trim())")
    check("settings: the groups are not numbered", heads and not any(h[:1].isdigit() for h in heads), heads)
    check("settings: the privacy notes are in the caution colours, not the error red",
          pg.evaluate("""() => { const n = document.querySelector('#set-key .optbox .warn'), p = document.createElement('div');
              p.style.cssText = 'background:var(--warn-bg);color:var(--warn-fg)'; document.body.appendChild(p);
              const a = getComputedStyle(p), b = getComputedStyle(n); const ok = a.backgroundColor === b.backgroundColor && a.color === b.color; p.remove(); return ok; }"""))
    check("settings: ...and not bold red", pg.evaluate("getComputedStyle(document.querySelector('#set-key .optbox .warn')).fontWeight") in ("600", "500"))

    counts = pg.evaluate("[nLec(0), nLec(1), nLec(2), nLec(5), nTerm(1), nTerm(2), nTerm(30), nLine(1), nLine(2), nSlide(1), nSlide(7), nShot(1)]")
    check("Hebrew counts: one, two, many, none", counts == ["אין הרצאות", "הרצאה אחת", "שתי הרצאות", "5 הרצאות", "מונח אחד", "שני מונחים", "30 מונחים",
                                                             "שורה אחת", "שתי שורות", "שקופית אחת", "7 שקופיות", "צילום אחד"], counts)
    course = "קורס ספירה"
    L.create_course(course)
    for nm, head in (("2026-11-02 10-00 הרצאה", "2026-11-02 10:00"), ("מבוא לגבולות", "2026-11-09 08:30")):
        d = os.path.join(L.course_dir(course), nm)
        os.makedirs(d)
        with open(os.path.join(d, nm + ".txt"), "w", encoding="utf-8") as f:
            f.write(f"# תמלול הרצאה (עברית) - התחלה {head}\n[{head[-5:]}:00 | +0:00:05] שלום לכולם\n# סוף\n")
    from urllib.parse import quote
    pg.goto(url + "/#c=" + quote(course))
    pg.reload()   # (the library is read when the page opens: the lectures above were made after it)
    pg.wait_for_function("document.querySelectorAll('#cLib li').length === 2", timeout=8000)
    pg.wait_for_timeout(600)
    meta = pg.evaluate("[...document.querySelectorAll('#cLib li')].map(li => [li.querySelector('.t').textContent, li.querySelector('.m').textContent])")
    auto = [m for m in meta if m[0].startswith("הרצאה 02.11.2026")]
    named = [m for m in meta if m[0] == "מבוא לגבולות"]
    check("a lecture whose title is its date and time: the line under it does not say them again",
          len(auto) == 1 and "10:00" not in auto[0][1] and "2026-11-02" not in auto[0][1] and "עברית" in auto[0][1], meta)
    check("a lecture with a name of its own: the line under it has the date and time", len(named) == 1 and "2026-11-09 08:30" in named[0][1], meta)
    check("one line under a lecture: a line in singular", all("שורה אחת" in m[1] for m in meta), meta)
    check("the course page: 'two lectures', not '2 lectures'", "שתי הרצאות" in pg.inner_text("#cSub") and "שתי הרצאות" in pg.inner_text("#ctLec"), (pg.inner_text("#cSub"), pg.inner_text("#ctLec")))
    check("the summary line is built from the same list as the lectures (and is not 'no lectures' above a list)",
          "אין הרצאות" not in pg.inner_text("#cSize") and "עוד אין הרצאות" not in pg.inner_text("#cSize") and "שתי הרצאות" in pg.inner_text("#cSize"), pg.inner_text("#cSize"))
    pg.evaluate("openPast(%s)" % json.dumps(course + "/2026-11-02 10-00 הרצאה"))
    pg.wait_for_timeout(1000)
    sub = pg.inner_text("#pastSub")
    check("a saved lecture: the line under its title does not repeat the date and time either", "10:00" not in sub and "2026-11-02" not in sub and "שורה אחת" in sub, sub)
    check("2.18 page: no script errors", pg.errs == [], pg.errs)

    # ---- the transcript is behind: the floating window says so, in seconds, over 10 ----
    lagp = b.new_context(viewport={"width": 420, "height": 760}, locale="he-IL").new_page()
    lag_errs = []
    lagp.on("pageerror", lambda e: lag_errs.append(str(e)))
    state = {"lag": 25, "live": True}
    lagp.route("**/api/app*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(
        {"session": {"kind": "live", "done": False, "course": "פיזיקה"} if state["live"] else None, "math": {"ask": True}, "ai_apps": {}, "connect": {}})))
    lagp.route("**/api/live*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(
        {"total": 0, "items": [], "lag": state["lag"], "info": {}}) if state["live"] else json.dumps({"none": True})))
    lagp.goto(url + "/mini")
    lagp.wait_for_timeout(800)

    def poll():
        lagp.evaluate("async () => { await pollApp(); await pollLive(); }")
        return lagp.evaluate("[!document.querySelector('#lag').hidden, document.querySelector('#lag').textContent]")
    shown, txt = poll()
    check("floating window: the transcript is 25 seconds behind - it says so, in seconds", shown and "מאחר ב-25 שניות" in txt, (shown, txt))
    state["lag"] = 10
    check("floating window: 10 seconds is not worth a warning", poll()[0] is False)
    state["lag"] = 11
    check("floating window: over 10 seconds it is shown", poll()[0] is True)
    state["lag"] = 3
    check("floating window: caught up - the warning goes away", poll()[0] is False)
    state["lag"], state["live"] = 40, False
    check("floating window: no lecture - no warning", poll()[0] is False)
    check("floating window: the warning is a status the screen reader announces", lagp.evaluate("document.querySelector('#lag').getAttribute('role')") == "status")
    check("floating window (lag): no script errors", lag_errs == [], lag_errs)
    b.close()

print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.exit(1 if fails else 0)
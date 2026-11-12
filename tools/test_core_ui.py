"""The core in a real browser: the marks tab of a lecture, the first-time consent, and the ask box (answers inside Hevanti,
copy buttons only without a key or when chosen in the settings). Needs Playwright and Edge or Chrome; skips when missing.
  python3 tools/test_core_ui.py"""
import json
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request

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
    # a marked moment: the highlighter band over the line said before the mark and over the mark row, a ★ and "מסומנת" for the screen reader
    MARKED = """() => { const probe = document.createElement('i'); probe.style.background = 'var(--mark-line)'; probe.style.color = 'var(--fg)'; document.body.appendChild(probe);
        const band = getComputedStyle(probe).backgroundColor, ink = getComputedStyle(probe).color; probe.remove();
        const rows = [...document.querySelectorAll('#pastLines li.mark')];
        return {band, rows: rows.map(r => { const p = r.previousElementSibling, b = getComputedStyle(r), pb = p && getComputedStyle(p), ts = p && p.querySelector('.ts');
          return {row: b.backgroundColor === band, text: r.textContent, prevMarked: !!p && p.classList.contains('marked'), prevBand: !!p && pb.backgroundColor === band,
                  star: p ? (p.querySelector('.mstar') || {}).textContent : null, starHidden: p && p.querySelector('.mstar') ? p.querySelector('.mstar').getAttribute('aria-hidden') : null,
                  sr: p ? (p.querySelector('.sr-only') || {}).textContent : null, tsInk: !!ts && getComputedStyle(ts).color === ink, prevText: p ? p.textContent : ''}; }),
          plain: [...document.querySelectorAll('#pastLines li:not(.marked):not(.mark):not(.note)')].filter(l => getComputedStyle(l).backgroundColor === band).length }; }"""
    for theme, scheme in (("light", "light"), ("dark", "dark")):
        for motion in ("no-preference", "reduce"):
            mk = b.new_context(viewport={"width": 1100, "height": 900}, locale="he-IL", color_scheme=scheme, reduced_motion=motion).new_page()
            mk.route("**/api/transcript*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"entry": entry, "lines": lines, "summary": ""})))
            mk.goto(url + "/")
            mk.wait_for_timeout(900)
            mk.evaluate(f"document.documentElement.dataset.theme = '{theme}'; document.querySelectorAll('.modal').forEach(m => m.hidden = true); openPast('c/t')")
            mk.wait_for_timeout(900)
            m = mk.evaluate(MARKED)
            check(f"marked moments, {theme}, motion {motion}: each mark row and the line before it are one highlighter band (mark-line)",
                  len(m["rows"]) == 2 and all(r["row"] and r["prevMarked"] and r["prevBand"] for r in m["rows"]), m)
            check(f"...the first is an old '?' mark and the second a ★ mark: the same band, the glyph tells them apart",
                  m["rows"][0]["star"] == "?" and m["rows"][1]["star"] == "★" and "? סימנת" in m["rows"][0]["text"] and "★ סימנת" in m["rows"][1]["text"], m["rows"])
            check("...the ★ is hidden from the screen reader and the words 'מסומנת' are said instead (so it never relies on yellow alone)",
                  all(r["starHidden"] == "true" and r["sr"] == "מסומנת: " for r in m["rows"]), m["rows"])
            check("...the time on a marked line is ink (not muted), and no ordinary line has the band", all(r["tsInk"] for r in m["rows"]) and m["plain"] == 0, m)
            if theme == "light" and motion == "no-preference":
                mk.evaluate("document.documentElement.classList.add('a-contrast')")
                check("...in high-contrast mode a marked line also has an outline (not colour alone)",
                      mk.evaluate("getComputedStyle(document.querySelector('#pastLines li.mark')).outlineStyle") == "solid")
            mk.context.close()

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
    r2 = pg.evaluate("""() => { const t = document.createElement('div'); document.body.appendChild(t);
      BZMAsk.render(document, t, "הנקודה קבועה [12:36:33, 12:40:58] והשני [12:36:54-12:40:11] ועוד [12:36:33; 99:99:99] וסתם [ממש].", {go: () => {}, known: new Set(["12:36:33", "12:40:58", "12:36:54", "12:40:11"])});
      return {buttons: [...t.querySelectorAll('button.src')].map(b => b.textContent), plain: [...t.querySelectorAll('span.src')].map(b => b.textContent), text: t.textContent}; }""")
    check("sources: several times in one pair of brackets are separate chips, and no square bracket is left around a time",
          r2["buttons"] == ["⏱ 12:36:33", "⏱ 12:40:58", "⏱ 12:36:54", "⏱ 12:40:11", "⏱ 12:36:33"] and r2["plain"] == ["⏱ 99:99:99"]
          and "[12" not in r2["text"] and "[ממש]" in r2["text"], r2)
    check("sources: a click goes to that line of the transcript", r["went"] == ["00:20:44"], r)
    for theme in ("light", "dark"):
        pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
        st = pg.evaluate("""() => { const t = document.querySelector('.askp, body'); const css = n => { const e = document.createElement('div'); e.className = 'askp'; document.body.appendChild(e);
              BZMAsk.render(document, e, '[00:20:44] [00:99:99]', {go: () => {}, known: new Set(['00:20:44'])}); const b = e.querySelector('button.src'), x = e.querySelector('span.src');
              const f = el => { const c = getComputedStyle(el); return {u: c.textDecorationLine, color: c.color, bg: c.backgroundColor, border: c.borderTopWidth, font: c.fontFamily.toLowerCase()}; };
              const out = {b: f(b), x: f(x), muted: getComputedStyle(document.documentElement).getPropertyValue('--muted').trim(), accent: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()};
              const probe = c => { const i = document.createElement('i'); i.style.color = c; document.body.appendChild(i); const v = getComputedStyle(i).color; i.remove(); return v; };
              out.mutedRgb = probe(out.muted); out.accentRgb = probe(out.accent); e.remove(); return out; }; return css(); }""")
        check(f"sources, {theme}: a time that can be opened looks like a link (underlined, green), and one that cannot is plain muted text",
              "underline" in st["b"]["u"] and st["b"]["color"] == st["accentRgb"] and st["x"]["u"] == "none" and st["x"]["color"] == st["mutedRgb"]
              and st["x"]["bg"] == "rgba(0, 0, 0, 0)" and st["x"]["border"] == "0px" and "underline" not in st["x"]["u"], st)
    pg.evaluate("document.documentElement.dataset.theme = ''")
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
    pg.evaluate("openSettings('tune')")
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
    pg.evaluate("openSettings('tune')")
    pg.wait_for_timeout(400)
    check("own instructions: still there after a reload", pg.evaluate("document.querySelector('#notesIn').value") == typed.strip())
    check("own instructions: no script errors", pg.errs == [], pg.errs)
    L.save_settings(math={})
    pg = page()
    pg.evaluate("openSettings('tune')")
    check("own instructions: without a key the field is closed", pg.evaluate("document.querySelector('#notesIn').disabled"))

    # ---- report a problem ----
    pg = page()
    perr = []
    pg.on("pageerror", lambda e: perr.append(str(e)))
    top, foot = pg.evaluate("document.querySelector('#verTop').textContent"), pg.evaluate("document.querySelector('#ver').textContent")
    check("beta: the header says it is a beta, with the version; the footer has only the date (design 3: no second version number)", top.startswith("בטא ") and L.VERSION in top and L.VERSION not in foot and L.VERSION_DATE in foot, (top, foot))
    TEST_MAIL = "support@example.test"   # (a made-up address: the real one is set in REPORT_EMAIL when Hevanti has one)
    mail_now = {"v": ""}

    def diag_route(route):
        resp = route.fetch(); d = resp.json(); d["mail"] = mail_now["v"]
        route.fulfill(response=resp, body=json.dumps(d))
    pg.route("**/api/diag", diag_route)
    pg.click("#repBtn")
    pg.wait_for_function("document.querySelector('#repText').value.includes('Windows')", timeout=8000)
    rep = pg.evaluate("document.querySelector('#repText').value")
    check("report a problem: the details are shown, with a place to say what happened", pg.is_visible("#report") and rep.startswith("מה קרה") and "הבנתי " in rep, rep[:200])
    check("report a problem: the GitHub button opens a new issue", pg.evaluate("document.querySelector('#repGit').href").endswith("/issues/new"))
    check("report a problem: no support address - no e-mail button, no address, and the way to send says so in words",
          pg.is_hidden("#repMail") and pg.is_hidden("#repMailHelp") and pg.is_visible("#repNoMail") and "מי שנתן לכם" in pg.inner_text("#repNoMail"), pg.inner_text("#repNoMail"))
    pg.click("#repClose")
    mail_now["v"] = TEST_MAIL
    pg.click("#repBtn")
    pg.wait_for_function("document.querySelector('#repText').value.includes('Windows')", timeout=8000)
    mail_href = urllib.parse.unquote(pg.evaluate("document.querySelector('#repMail').href"))
    check("report a problem: with a support address, a button writes to it, with the version in the subject, and nothing of the details in the link (they are pasted)",
          mail_href.startswith("mailto:" + TEST_MAIL + "?subject=הבנתי ") and "דיווח על תקלה" in mail_href and "מחשב" not in mail_href.split("body=")[0] and len(mail_href) < 300 and pg.is_visible("#repMail"), mail_href)
    check("report a problem: ...and the address is shown (for those without a mail program), with a copy button",
          pg.evaluate("document.querySelector('#repAddr').textContent") == TEST_MAIL and pg.is_visible("#repAddrCopy") and pg.is_hidden("#repNoMail"))
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
    mini_state = {"live": True, "ask": True, "mark_n": 0}

    def mini_app(route):
        resp = route.fetch()
        d = resp.json()
        d["session"] = {"kind": "rec" if mini_state.get("rec") else "live", "done": False, "course": "פיזיקה"} if mini_state["live"] else None
        if d["session"]:   # (a lecture that has been transcribing for 2 minutes; "fresh": 4 seconds; "loading": the model is still loading)
            d["session"].update(ready=not mini_state.get("loading"), ready_at=time.time() - (4 if mini_state.get("fresh") else 120), quick_stop_s=10)
        d["math"] = dict(d.get("math") or {}, ask=mini_state["ask"])
        if "run" in mini_state:
            d["run"] = mini_state.pop("run")   # (once: one look at Hevanti that says another run)
        if mini_state.get("stopping") and d["session"]:
            d["session"].update(stopping=True, stopping_for=8)
        if mini_state.get("saved"):
            d["session"] = {"kind": "live", "done": True, "course": "פיזיקה", "saved": {"course": "פיזיקה", "minutes": 46, "slides": 9, "f": "פיזיקה/הרצאה 3"}}
        if mini_state.get("suggest") and d["session"]:
            d["session"]["suggest"] = {"course": "אלגוריתמים", "why": "slide", "detail": ""}
        d["mark_n"] = mini_state["mark_n"]   # (Hevanti's count of marks: a mark made with the keyboard raises it)
        route.fulfill(response=resp, body=json.dumps(d))
    mini.route("**/api/app*", mini_app)
    mini.goto(url + "/mini")
    mini.wait_for_timeout(1200)
    check("floating window: the question box and the ★ mark (no '?')", mini.is_visible("textarea") and mini.is_visible("#markImp") and mini.query_selector("#markLost") is None)
    run_meta = mini.evaluate("() => document.querySelector('meta[name=bzm-run]').content")
    live_run = json.loads(urllib.request.urlopen(url + "/api/app").read().decode("utf-8")).get("run")
    check("floating window: it knows which run of Hevanti gave it the page (a window left open from an earlier run reloads itself)", run_meta == live_run and live_run, (run_meta, live_run))
    mini.evaluate("() => { window.__same_page = true; }")
    mini_state["run"] = "another-run"
    mini.wait_for_timeout(4800)
    reloaded = mini.evaluate("() => window.__same_page !== true")
    check("floating window: a different run answers - it loads the page again", reloaded)
    mini.wait_for_timeout(4800)   # (the page that was loaded again learns Hevanti's count of marks from its first look)
    marked = []
    mini.route("**/api/cmd", lambda r: (marked.append(json.loads(r.request.post_data or "{}")), r.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, "kind": "חשוב"})))[1])
    mini.click("#markImp")
    mini.wait_for_timeout(300)
    check("floating window: ★ sends an 'important' mark to Hevanti", any(m.get("action") == "mark" and m.get("kind") == "important" for m in marked), marked)
    toast = mini.evaluate("""() => { const e = document.querySelector('#toast'), s = e.querySelector('.star'), c = getComputedStyle(s);
        return {on: e.classList.contains('on'), text: e.textContent, star: s.textContent, band: c.backgroundColor,
                want: getComputedStyle(document.documentElement).getPropertyValue('--mark-line').trim(), centred: Math.abs((e.getBoundingClientRect().left + e.getBoundingClientRect().right) / 2 - innerWidth / 2) < 3,
                narrower: e.getBoundingClientRect().width < innerWidth - 20}; }""")
    check("floating window: the mark message is a card with a yellow ★ (the highlighter colour) and the word, in the middle, not a bar across", toast["on"] and toast["star"] == "★" and "סומן" in toast["text"] and toast["centred"] and toast["narrower"], toast)
    mini.wait_for_timeout(3300)   # (the message goes away)
    mini_state["mark_n"] = 1   # a mark made with Ctrl+Alt+M: Hevanti's count goes up, and the window says it too
    try:   # (the window looks every 4 seconds: wait for the message, not for a fixed time)
        mini.wait_for_function("() => document.querySelector('#toast').classList.contains('on') && document.querySelector('#toast .star') !== null", timeout=7000)
        seen_key = True
    except Exception:
        seen_key = False
    check("floating window: a mark made with the keyboard shows the same message", seen_key)
    mini.wait_for_function("() => !document.querySelector('#toast').classList.contains('on')", timeout=8000)
    mini.wait_for_timeout(4600)   # (a whole look later)
    check("floating window: ...and only once for one mark", not mini.evaluate("() => document.querySelector('#toast').classList.contains('on')"))
    # ---- stop from the small window: two presses, then a card says the lecture was saved ----
    marked.clear()
    mini.evaluate("pollApp()")
    mini.wait_for_selector("#stopBtn", state="visible", timeout=5000)
    check("floating window: a live lecture has a stop button in the title row", mini.inner_text("#stopBtn") == "עצירה")
    mini.click("#stopBtn")
    check("floating window: the first press only asks (a short word, so the course name is not cut), and nothing stops yet",
          mini.inner_text("#stopBtn") == "לעצור?" and not any(m.get("action") == "stop" for m in marked), marked)
    mini.wait_for_timeout(3400)
    check("floating window: not pressed again - it goes back to \"עצירה\" after 3 seconds", mini.inner_text("#stopBtn") == "עצירה" and not any(m.get("action") == "stop" for m in marked))
    mini.click("#stopBtn"); mini.click("#stopBtn")
    mini.wait_for_timeout(500)
    check("floating window: the second press stops", any(m.get("action") == "stop" for m in marked), marked)
    mini_state["stopping"] = True
    mini.evaluate("pollApp()")
    mini.wait_for_timeout(300)
    check("floating window: while it stops and saves it says so (with the seconds), and the stop button is gone", "עוצר ושומר" in mini.inner_text("#lec") and "8" in mini.inner_text("#lec") and mini.is_hidden("#stopBtn"), mini.inner_text("#lec"))
    mini_state["stopping"] = False
    mini_state["saved"] = True
    mini.evaluate("pollApp()")
    mini.wait_for_selector("#saved", state="visible", timeout=5000)
    sv_txt = mini.inner_text("#saved")
    check("floating window: the lecture was saved - a card says so, with the course, minutes and slides, instead of the question box",
          "נשמרה בהצלחה" in sv_txt and "פיזיקה" in sv_txt and "46 דקות" in sv_txt and "9 שקפים" in sv_txt and mini.is_hidden("#box"), sv_txt)
    marked.clear()
    mini.click("#savedOpen")
    mini.wait_for_timeout(400)
    check("floating window: 'open the lecture in the app' sends the lecture, and the window goes", any(m.get("action") == "open_lecture" and m.get("f") == "פיזיקה/הרצאה 3" for m in marked) and any(m.get("action") == "hide_mini" for m in marked), marked)
    mini.evaluate("pollApp()")
    mini.wait_for_timeout(300)
    check("floating window: the card does not come back for the same lecture", mini.is_hidden("#saved"))
    mini_state["saved"] = False
    mini.evaluate("pollApp()")
    mini.wait_for_timeout(300)
    # ---- no lecture: the same button starts a new one (the quick-start window) ----
    mini_state["live"] = False
    marked.clear()
    mini.evaluate("pollApp()")
    mini.wait_for_timeout(300)
    check("floating window: with no lecture the button reads \"התחלת הרצאה חדשה\" (not \"עצירה\")", mini.is_visible("#stopBtn") and mini.inner_text("#stopBtn") == "התחלת הרצאה חדשה", mini.inner_text("#stopBtn"))
    mini.click("#stopBtn")
    mini.wait_for_timeout(300)
    check("floating window: one press asks Hevanti for the quick-start window, and nothing else (no stop, no second press)",
          [m.get("action") for m in marked] == ["quick_new"], marked)
    mini_state["live"] = True
    mini.evaluate("pollApp()")
    mini.wait_for_timeout(300)
    check("floating window: a lecture starts - the button goes back to \"עצירה\"", mini.inner_text("#stopBtn") == "עצירה")
    # ---- a lecture stopped right after it started: the same question as in the app (QUICK_STOP_S) ----
    mini_state["loading"] = True; marked.clear()
    mini.evaluate("pollApp()"); mini.wait_for_timeout(300)
    mini.click("#stopBtn"); mini.click("#stopBtn"); mini.wait_for_timeout(400)
    check("floating window: stopped while the model still loads - cancelled at once, without saving (and no question)",
          any(m.get("action") == "stop" and m.get("discard") is True for m in marked) and mini.is_hidden("#short"), marked)
    mini_state["loading"] = False; mini_state["fresh"] = True; marked.clear()
    mini.evaluate("pollApp()"); mini.wait_for_timeout(300)
    mini.click("#stopBtn"); mini.click("#stopBtn"); mini.wait_for_timeout(400)
    check("floating window: stopped 4 seconds after the start - it asks whether to delete, and nothing is sent yet",
          mini.is_visible("#short") and "שניות" in mini.inner_text("#shortInfo") and not any(m.get("action") == "stop" for m in marked), (mini.inner_text("#short"), marked))
    mini.click("#shortSave"); mini.wait_for_timeout(400)
    check("floating window: \"לעצור ולשמור\" stops and keeps it", any(m.get("action") == "stop" and m.get("discard") is False for m in marked), marked)
    marked.clear()
    mini.evaluate("pollApp()"); mini.wait_for_timeout(300)
    mini.click("#stopBtn"); mini.click("#stopBtn"); mini.wait_for_timeout(300)
    mini.click("#shortDel"); mini.wait_for_timeout(400)
    check("floating window: \"עצירה ומחיקה\" stops and deletes it", any(m.get("action") == "stop" and m.get("discard") is True for m in marked), marked)
    sk = mini.evaluate("""() => { const f = (t) => BZMAsk.stopKind({kind: "live", ready: true, ready_at: 1000, quick_stop_s: 10}, 1000 + t).kind;
        return [f(4), f(10), f(10.5), f(300), BZMAsk.stopKind({kind: "live", ready: false}).kind, BZMAsk.stopKind({kind: "rec"}).kind]; }""")
    check("stop rule (one function, ask.js): under the limit and exactly on it ask; over it saves; still loading cancels; a recording is never asked",
          sk == ["short", "short", "normal", "normal", "cancel", "normal"], sk)
    mini_state["fresh"] = False
    mini_state["live"] = False; mini.evaluate("pollApp()"); mini.wait_for_timeout(300)
    mini_state["live"] = True; mini.evaluate("pollApp()"); mini.wait_for_timeout(300)
    marked.clear()
    mini.click("#stopBtn"); mini.click("#stopBtn"); mini.wait_for_timeout(400)
    check("floating window: a lecture of 2 minutes stops and is saved, with no question", mini.is_hidden("#short") and any(m.get("action") == "stop" and m.get("discard") is False for m in marked), marked)
    mini_state["live"] = True
    mini.evaluate("pollApp()"); mini.wait_for_timeout(300)
    mini_state["rec"] = True
    mini.evaluate("pollApp()")
    mini.wait_for_timeout(300)
    check("floating window: a recording being watched in the player is not stopped from here (no stop button)", mini.is_hidden("#stopBtn"))
    mini_state["rec"] = False
    mini.evaluate("pollApp()")
    mini.wait_for_timeout(300)

    # ---- a course read from the first slide is offered in the small window: one press takes it, or says no ----
    mini_state["suggest"] = True
    mini.evaluate("pollApp()")
    mini.wait_for_selector("#sug", state="visible", timeout=5000)
    check("floating window: a course read from the first slide is offered, with the name", "אלגוריתמים" in mini.inner_text("#sugText") and "השקף הראשון" in mini.inner_text("#sugText"), mini.inner_text("#sugText"))
    marked.clear()
    mini.click("#sugYes")
    mini.wait_for_timeout(500)
    check("floating window: 'move' sends the course (the lecture moves when it is saved) and tells when", any(m.get("action") == "set_lecture_course" and m.get("course") == "אלגוריתמים" for m in marked) and mini.is_hidden("#sug"), marked)
    mini.evaluate("pollApp()")
    mini.wait_for_selector("#sug", state="visible", timeout=5000)
    marked.clear()
    mini.click("#sugNo")
    mini.wait_for_timeout(400)
    check("floating window: 'not now' tells Hevanti, and the offer goes", any(m.get("action") == "suggest_dismiss" for m in marked) and mini.is_hidden("#sug"), marked)
    mini_state["suggest"] = False
    mini.evaluate("pollApp()")
    mini.wait_for_timeout(300)
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
    greens = mini.evaluate("""() => { const p = document.createElement('i'); p.style.background = 'var(--accent)'; document.body.appendChild(p); const green = getComputedStyle(p).backgroundColor; p.remove();
        return [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null && getComputedStyle(b).backgroundColor === green).map(b => b.textContent.trim()); }""")
    check("floating window: exactly one solid green control: 'answer here'", greens == ["תשובה כאן"], greens)
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
    check("...its button is a ghost button, not a solid green one (the home page already has the one green action: the lecture card)",
          pg.evaluate("""() => { const b = getComputedStyle(document.querySelector('#keyBarGo')), g = getComputedStyle(document.querySelector('.start[data-start=he]'));
              return b.backgroundColor === 'rgba(0, 0, 0, 0)' && b.backgroundColor !== g.backgroundColor; }"""))
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
    check("with a key: the bar is gone, and the status line stays quiet (design 3: ready is said once, in the top bar)", pg.evaluate("document.querySelector('#homeAns').hidden") and pg.inner_text("#statePill") == "מוכן", (pg.inner_text("#statePill"),))
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
          pg.evaluate("""() => { const n = document.querySelector('#setBody .optbox .warn'), p = document.createElement('div');
              p.style.cssText = 'background:var(--warn-bg);color:var(--warn-fg)'; document.body.appendChild(p);
              const a = getComputedStyle(p), b = getComputedStyle(n); const ok = a.backgroundColor === b.backgroundColor && a.color === b.color; p.remove(); return ok; }"""))
    check("settings: ...and not bold red", pg.evaluate("getComputedStyle(document.querySelector('#setBody .optbox .warn')).fontWeight") in ("600", "500"))

    counts = pg.evaluate("[nLec(0), nLec(1), nLec(2), nLec(5), nTerm(1), nTerm(2), nTerm(30), nLine(1), nLine(2), nSlide(1), nSlide(7), nShot(1)]")
    check("Hebrew counts: one, two, many, none", counts == ["אין הרצאות", "הרצאה אחת", "שתי הרצאות", "5 הרצאות", "מונח אחד", "שני מונחים", "30 מונחים",
                                                             "שורה אחת", "שתי שורות", "שקופית אחת", "7 שקופיות", "צילום אחד"], counts)
    course = "קורס ספירה"
    L.create_course(course)
    for nm, head in (("2026-11-02 10-00 הרצאה", "2026-11-02 10:00"), ("מבוא לגבולות", "2026-11-09 08:30")):
        d = os.path.join(L.course_dir(course), nm)
        os.makedirs(d)
        with open(os.path.join(d, nm + ".txt"), "w", encoding="utf-8") as f:
            slides = "".join(f"[{head[-5:]}:0{i} | +0:00:0{i}] [צילום מסך: {course}/{nm}/שקופיות/s{i}.jpg]\n" for i in (1, 2)) if nm == "מבוא לגבולות" else ""
            f.write(f"# תמלול הרצאה (עברית) - התחלה {head}\n[{head[-5:]}:00 | +0:00:05] שלום לכולם\n{slides}# סוף\n")
    from urllib.parse import quote
    pg.goto(url + "/#c=" + quote(course))
    pg.reload()   # (the library is read when the page opens: the lectures above were made after it)
    pg.wait_for_function("document.querySelectorAll('#cLib li').length === 2", timeout=8000)
    pg.wait_for_timeout(600)
    meta = pg.evaluate("[...document.querySelectorAll('#cLib li')].map(li => [li.querySelector('.t').textContent, li.querySelector('.m').textContent])")
    auto = [m for m in meta if m[0].startswith("הרצאה 02.11.2026")]
    named = [m for m in meta if m[0] == "מבוא לגבולות"]
    check("a lecture whose title is its date and time: the line under it has only the length (not the date and time again, not the language, not the lines)",
          len(auto) == 1 and auto[0][1] == "אורך 00:00:05", meta)
    check("a lecture with a name of its own: the date in one format (09.11.2026), the length, the slides - and no time, language or lines",
          len(named) == 1 and named[0][1] == "09.11.2026 · אורך 00:00:05 · שתי שקופיות", meta)
    check("the line under a lecture has no ISO date and no 'lines'", all("2026-" not in m[1] and "שורה" not in m[1] and "עברית" not in m[1] for m in meta), meta)
    check("the course page: 'two lectures', not '2 lectures'", "שתי הרצאות" in pg.inner_text("#cSub") and "שתי הרצאות" in pg.inner_text("#ctLec"), (pg.inner_text("#cSub"), pg.inner_text("#ctLec")))
    check("the summary line is built from the same list as the lectures (and is not 'no lectures' above a list)",
          "אין הרצאות" not in pg.inner_text("#cSize") and "עוד אין הרצאות" not in pg.inner_text("#cSize") and "שתי הרצאות" in pg.inner_text("#cSize"), pg.inner_text("#cSize"))
    pg.evaluate("openPast(%s)" % json.dumps(course + "/2026-11-02 10-00 הרצאה"))
    pg.wait_for_timeout(1000)
    sub = pg.inner_text("#pastSub")
    check("a saved lecture: the line under its title is the same line (the course, the length) - no date and time again, no language, no lines",
          sub == course + " · אורך 00:00:05", sub)
    check("...the language and the number of lines are with the transcript, on the same page", pg.inner_text("#pastTrCount") == "עברית · שורה אחת", pg.inner_text("#pastTrCount"))
    pg.evaluate("openPast(%s)" % json.dumps(course + "/מבוא לגבולות"))
    pg.wait_for_timeout(1000)
    check("a saved lecture with a name: the course, the date in one format, the length, the slides", pg.inner_text("#pastSub") == course + " · 09.11.2026 · אורך 00:00:05 · שתי שקופיות", pg.inner_text("#pastSub"))
    check("2.18 page: no script errors", pg.errs == [], pg.errs)

    # ---- 2.19 colours: a search match is soft green (yellow is only the student's ★), the ask box has one solid green, the AI used last is a ghost button ----
    for theme in ("light", "dark"):
        cp = b.new_context(viewport={"width": 1100, "height": 900}, locale="he-IL", color_scheme=theme).new_page()
        cp.errs = []
        cp.on("pageerror", lambda e: cp.errs.append(str(e)))
        cp.route("**/api/ask", lambda r: r.fulfill(status=200, content_type="text/plain", body="תשובה"))
        cp.goto(url + "/")
        cp.wait_for_timeout(900)
        cp.evaluate(f"""() => {{ document.documentElement.dataset.theme = '{theme}'; document.querySelectorAll('.modal').forEach(m => m.hidden = true);
            localStorage.setItem('bzm.ai', 'claude');
            window.__d = document.createElement('div'); document.body.appendChild(window.__d);
            window.__a = BZMAsk.mount(window.__d, {{context: q => q, toast() {{}}}}); BZMAsk.setBuiltin(true); BZMAsk.setExternal(true); }}""")
        cp.evaluate("__a.askHere('שאלה')")
        r = cp.evaluate("""() => { const col = v => { const i = document.createElement('i'); i.style.background = v; document.body.appendChild(i); const c = getComputedStyle(i).backgroundColor; i.remove(); return c; };
            const soft = col('var(--accent-soft)'), green = col('var(--accent)'), yellow = col('var(--mark)');
            const m = document.createElement('mark'); m.textContent = 'x'; document.body.appendChild(m); const ms = getComputedStyle(m); const mark = {bg: ms.backgroundColor, shadow: ms.boxShadow}; m.remove();
            const q = getComputedStyle(__d.querySelector('.qa .q')).backgroundColor;
            const last = __d.querySelector('.ais button.last'), ls = last && getComputedStyle(last), la = last && getComputedStyle(last, '::after').content;
            const rules = [...document.styleSheets].flatMap(s => { try { return [...s.cssRules]; } catch (e) { return []; } }).filter(r => r.selectorText && r.selectorText.includes('a-contrast') && r.selectorText.includes('focus-visible')).map(r => r.cssText);
            return {soft, green, yellow, mark, q, lastBg: last ? ls.backgroundColor : null, lastAfter: la, rules,
                    solid: [...__d.querySelectorAll('button')].filter(b => b.offsetParent !== null && getComputedStyle(b).backgroundColor === green).map(b => b.textContent.trim())}; }""")
        check(f"search match, {theme}: soft green with a green underline, not yellow", r["mark"]["bg"] == r["soft"] and r["mark"]["bg"] != r["yellow"] and r["mark"]["shadow"] != "none", r["mark"])
        check(f"high-contrast focus ring, {theme}: ink, not yellow", r["rules"] and all("var(--fg)" in x and "--mark" not in x for x in r["rules"]), r["rules"])
        check(f"the question bubble, {theme}: soft green, not solid", r["q"] == r["soft"] and r["q"] != r["green"], (r["q"], r["soft"]))
        check(f"the ask box after a question, {theme}: 'answer here' is the one solid green control", r["solid"] == ["תשובה כאן"], r["solid"])
        check(f"the AI used last, {theme}: a ghost button that says 'אחרון', not solid green", r["lastBg"] == "rgba(0, 0, 0, 0)" and "אחרון" in (r["lastAfter"] or ""), (r["lastBg"], r["lastAfter"]))
        check(f"colours, {theme}: no script errors", cp.errs == [], cp.errs)
        cp.context.close()

    # ---- 2.19, stage 9: the guide's text is about 70 characters a line, and the video, the chapters and the "something is wrong" table hold ----
    for theme in ("light", "dark"):
        gd = b.new_context(viewport={"width": 1280, "height": 900}, locale="he-IL", color_scheme=theme).new_page()
        gd.errs = []
        gd.on("pageerror", lambda e: gd.errs.append(str(e)))
        gd.goto(url + "/#how")
        gd.wait_for_timeout(1500)
        gd.evaluate(f"document.documentElement.dataset.theme = '{theme}'; document.querySelectorAll('.modal').forEach(m => m.hidden = true)")
        r = gd.evaluate("""() => { const per = [];
            for (const el of document.querySelectorAll('.guide p, .guide li')) { const t = el.firstChild && el.firstChild.nodeType === 3 && el.firstChild.length > 80 ? el.firstChild : null; if (!t) continue;   // (text that starts the element, so it starts a line)
              const rg = document.createRange(); let first = null, n = 0;
              for (let i = 0; i < t.length; i++) { rg.setStart(t, i); rg.setEnd(t, i + 1); const b = rg.getBoundingClientRect(); if (first === null) first = Math.round(b.top); if (Math.round(b.top) !== first) break; n++; }
              per.push(n); }
            const vid = document.querySelector('.howvid video').getBoundingClientRect(), ch = document.querySelector('#howChapters').getBoundingClientRect(), g = document.querySelector('.guide').getBoundingClientRect();
            const dt = document.querySelector('.gfix dt').getBoundingClientRect(), dd = document.querySelector('.gfix dd').getBoundingClientRect();
            return {per, guide: Math.round(g.width), video: [Math.round(vid.width), Math.round(vid.height)], chapters: [Math.round(ch.width), Math.round(ch.height)], sameRow: Math.abs(vid.top - ch.top) < 30,
                    overflow: document.documentElement.scrollWidth > window.innerWidth, table2cols: Math.abs(dt.top - dd.top) < 12 && dt.left !== dd.left, chaptersCount: document.querySelectorAll('#howChapters button').length}; }""")
        check(f"guide, {theme}: the running text is 60 to 80 characters a line (about 70)", r["per"] and min(r["per"]) >= 60 and max(r["per"]) <= 80, r)
        check(f"guide, {theme}: the text column is narrower than it was (720px)", r["guide"] < 640, r)
        check(f"guide, {theme}: the video keeps its size (16:9) and the chapters list is beside it", r["video"][0] > 500 and abs(r["video"][0] / r["video"][1] - 16 / 9) < 0.05 and r["sameRow"] and r["chaptersCount"] == 12, r)
        check(f"guide, {theme}: the 'something is wrong' table keeps its two columns, and nothing overflows sideways", r["table2cols"] and not r["overflow"], r)
        check(f"guide, {theme}: no script errors", gd.errs == [], gd.errs)
        gd.context.close()

    # ---- 2.19, stage 8: settings - a quiet delete-key link, a short "today" line, the model in Advanced, green checkboxes ----
    for theme in ("light", "dark"):
        sp = b.new_context(viewport={"width": 1200, "height": 1000}, locale="he-IL", color_scheme=theme).new_page()
        sp.errs = []
        sp.on("pageerror", lambda e: sp.errs.append(str(e)))

        def set_app(route):
            resp = route.fetch()
            d = resp.json()
            d["math"] = dict(d.get("math") or {}, has_key=True, ask=True, on=True, model="gemini-3-flash", done=12, skipped=3, waiting=1,
                             today={"asks": 8, "reads": 58, "skipped": 3, "failed": 0, "quota": 0})
            route.fulfill(response=resp, body=json.dumps(d))
        sp.route("**/api/app*", set_app)
        sp.goto(url + "/#settings")
        sp.wait_for_timeout(1200)
        sp.evaluate(f"document.documentElement.dataset.theme = '{theme}'; document.querySelectorAll('.modal').forEach(m => m.hidden = true); openSettings('key')")
        sp.wait_for_timeout(600)
        st = sp.inner_text("#mathStat")
        check(f"settings, {theme}: the state line is short - the key is saved, and today: 8 questions, 58 slides read", st == "המפתח שמור. היום: 8 שאלות, 58 שקופיות נקראו.", st)
        check(f"settings, {theme}: the model's name is not on the Answers tab", "gemini-3" not in sp.inner_text("#set-key"), sp.inner_text("#set-key")[:300])
        r = sp.evaluate("""() => { const f = document.querySelector('#mathForget'), c = getComputedStyle(f), s = document.querySelector('#mathStat');
            const probe = document.createElement('i'); probe.style.color = 'var(--muted)'; document.body.appendChild(probe); const muted = getComputedStyle(probe).color; probe.remove();
            return {visible: f.offsetParent !== null, muted: c.color === muted, bg: c.backgroundColor, border: c.borderTopWidth, tag: f.tagName, ul: c.textDecorationLine,
                    sameRow: f.parentElement === s.parentElement && Math.abs(f.getBoundingClientRect().top - s.getBoundingClientRect().top) < 24}; }""")
        check(f"settings, {theme}: 'delete the key' is a quiet text link (muted, underlined, no fill, no border) on the line that says the key is saved",
              r["visible"] and r["muted"] and r["bg"] == "rgba(0, 0, 0, 0)" and r["border"] == "0px" and "underline" in r["ul"] and r["sameRow"], r)
        sp.click("#mathForget")
        sp.wait_for_timeout(300)
        check(f"settings, {theme}: it still asks before it deletes (the existing confirmation)", sp.is_visible("#confOk"))
        sp.click("#confNo")
        sp.evaluate("openSettings('ai')")
        sp.wait_for_timeout(500)
        tech = sp.inner_text("#mathTech")
        check(f"settings, {theme}: the model and the slide reading of this run are in Advanced", "gemini-3-flash" in tech and "נקראו בהפעלה הזו 12 שקופיות" in tech and "עוד 3 לא נשלחו" in tech, tech)
        acc = sp.evaluate("""() => { const probe = document.createElement('i'); probe.style.color = 'var(--accent)'; document.body.appendChild(probe); const g = getComputedStyle(probe).color; probe.remove();
            const r = document.createElement('input'); r.type = 'radio'; document.body.appendChild(r); const rr = getComputedStyle(r).accentColor; r.remove();
            return {green: g, all: [...document.querySelectorAll('input[type=checkbox]')].map(c => getComputedStyle(c).accentColor === g), radio: rr === g}; }""")
        check(f"settings, {theme}: every checkbox and radio is the board green (accent-color), not the system blue", acc["all"] and all(acc["all"]) and acc["radio"], acc)
        check(f"settings, {theme}: no script errors", sp.errs == [], sp.errs)
        sp.context.close()

    # ---- 2.19, stage 6: the lecture page - the three study cards are not inside a card, the summary card is soft green, "answer here" is the one solid green ----
    for theme in ("light", "dark"):
        lp = b.new_context(viewport={"width": 1200, "height": 1000}, locale="he-IL", color_scheme=theme).new_page()
        lp.errs = []
        lp.on("pageerror", lambda e: lp.errs.append(str(e)))
        lp.route("**/api/transcript*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"entry": entry, "lines": no_marks, "summary": ""})))

        def lp_app(route):
            resp = route.fetch()
            d = resp.json()
            d["math"] = dict(d.get("math") or {}, has_key=True, ask=True, on=True)
            route.fulfill(response=resp, body=json.dumps(d))
        lp.route("**/api/app*", lp_app)
        lp.goto(url + "/")
        lp.wait_for_timeout(900)
        lp.evaluate(f"document.documentElement.dataset.theme = '{theme}'; document.querySelectorAll('.modal').forEach(m => m.hidden = true); openPast('c/t')")
        lp.wait_for_timeout(900)
        lp.evaluate("document.querySelector('#pastAskFold').open = true")
        lp.wait_for_selector("#pastAsk .ais button", timeout=8000)
        r = lp.evaluate("""() => { const probe = document.createElement('i'); probe.style.background = 'var(--accent-soft)'; document.body.appendChild(probe);
            const soft = getComputedStyle(probe).backgroundColor; probe.style.background = 'var(--accent)'; const green = getComputedStyle(probe).backgroundColor; probe.remove();
            const st = getComputedStyle(document.querySelector('#pastStudy')), main = getComputedStyle(document.querySelector('.tile.main'));
            return {soft, green, mainBg: main.backgroundColor, studyBorder: st.borderTopWidth, studyBg: st.backgroundColor, studyPad: st.paddingTop,
                    nested: document.querySelectorAll('#vPast .card .card, #vPast .card .tile, #pastStudy.card').length,
                    tiles: [...document.querySelectorAll('#pastStudy .tile')].filter(t => !t.hidden).length, tileBorder: getComputedStyle(document.querySelector('.tile')).borderTopWidth,
                    solid: [...document.querySelectorAll('#vPast button, #vPast a.btn')].filter(x => x.offsetParent !== null && getComputedStyle(x).backgroundColor === green).map(x => x.textContent.trim())}; }""")
        check(f"lecture page, {theme}: the summary card is soft green, not solid", r["mainBg"] == r["soft"] and r["mainBg"] != r["green"], r)
        check(f"lecture page, {theme}: what holds the three study cards is not a card (no border, no fill, no padding), and no card is inside a card",
              r["studyBorder"] == "0px" and r["studyBg"] == "rgba(0, 0, 0, 0)" and r["studyPad"] == "0px" and r["nested"] == 0, r)
        check(f"lecture page, {theme}: the three cards are still cards (a border each)", r["tiles"] == 3 and r["tileBorder"] != "0px", r)
        check(f"lecture page, {theme}, the question box open: 'answer here' is the one solid green control", r["solid"] == ["תשובה כאן"], r["solid"])
        check(f"lecture page, {theme}: no script errors", lp.errs == [], lp.errs)
        lp.context.close()

    # ---- 2.19, stage 5: the graphics card capsule in the top bar exists only when there is something to press ----
    gpu_state = {"gpu": {"cards": 0, "libs_ok": False, "state": "", "msg": ""}, "device": "CPU"}
    cmds = []
    gp = b.new_context(viewport={"width": 1100, "height": 800}, locale="he-IL").new_page()
    gp.errs = []
    gp.on("pageerror", lambda e: gp.errs.append(str(e)))

    def gpu_app(route):
        resp = route.fetch()
        d = resp.json()
        d["gpu"], d["device"] = gpu_state["gpu"], gpu_state["device"]
        route.fulfill(response=resp, body=json.dumps(d))
    gp.route("**/api/app*", gpu_app)
    gp.route("**/api/cmd", lambda r: (cmds.append(json.loads(r.request.post_data or "{}")), r.fulfill(content_type="application/json", body=json.dumps({"ok": True, "gpu": {"cards": 1, "libs_ok": False, "state": "installing", "msg": ""}})))[1])
    gp.goto(url + "/")
    gp.evaluate("document.querySelectorAll('.modal').forEach(m => m.hidden = true)")

    def gpu_seen(hash_):
        gp.evaluate(f"location.hash = '{hash_}'")
        gp.wait_for_timeout(1700)
        return gp.evaluate("""() => { const vis = e => !!e && !e.hidden && e.offsetParent !== null;
            return {pill: vis(document.querySelector('#gpuPill')), pillText: document.querySelector('#gpuPill').innerText, bar: vis(document.querySelector('#gpuBar')),
                    barBtn: vis(document.querySelector('#gpuGo')), dev: !!document.querySelector('#devPill'),
                    installs: [...document.querySelectorAll('#gpuPillGo, #gpuGo')].filter(vis).length}; }""")
    for name, g, dev in (("no NVIDIA card (the computer works on the processor)", {"cards": 0, "libs_ok": False, "state": "", "msg": ""}, "CPU"),
                         ("a card that is in use", {"cards": 1, "libs_ok": True, "state": "", "msg": ""}, "GPU"),
                         ("a card and the processor works on the card's libraries being installed", {"cards": 1, "libs_ok": False, "state": "installing", "msg": ""}, "CPU")):
        gpu_state["gpu"], gpu_state["device"] = g, dev
        for h in ("how", "courses"):
            r = gpu_seen(h)
            check(f"graphics-card capsule, {name}, page {h}: not in the top bar, and no status pill for the device", not r["pill"] and not r["dev"], r)
    gpu_state["gpu"], gpu_state["device"] = {"cards": 1, "libs_ok": False, "state": "", "msg": ""}, "CPU"
    r = gpu_seen("how")
    check("a card that is not used, on another page: the capsule is in the top bar with the install button", r["pill"] and "NVIDIA" in r["pillText"] and r["installs"] == 1, r)
    r = gpu_seen("")
    check("...on the home page the bar below says it with its own button, and the capsule is gone (one install button, never two)",
          r["bar"] and r["barBtn"] and not r["pill"] and r["installs"] == 1, r)
    gpu_seen("how")
    del cmds[:]
    gp.click("#gpuPillGo")
    gp.wait_for_timeout(500)
    check("the capsule's button installs (the same action as the home bar's)", any(c.get("action") == "install_gpu" for c in cmds), cmds)
    for st, word in (("failed", "לנסות שוב"), ("done", "סגירה")):
        gpu_state["gpu"] = {"cards": 1, "libs_ok": False, "state": st, "msg": ""}
        r = gpu_seen("how")
        check(f"capsule, state {st}: its button says '{word}'", r["pill"] and word in r["pillText"] and r["installs"] == 1, r)
    check("graphics-card capsule: no script errors", gp.errs == [], gp.errs)
    gp.context.close()

    # ---- 2.19, stage 2: the live lecture screen has one solid green: "answer here" ----
    live_now = {"yes": True}
    lv = b.new_context(viewport={"width": 1280, "height": 900}, locale="he-IL").new_page()
    lv.errs = []
    lv.on("pageerror", lambda e: lv.errs.append(str(e)))

    def live_app(route):
        resp = route.fetch()
        d = resp.json()
        d["session"] = {"kind": "live", "lang": "he", "title": "", "course": "פיזיקה", "ready": True, "done": False, "stopping": False, "started": 0, "yt": False}
        d["math"] = dict(d.get("math") or {}, has_key=True, ask=True, on=True)
        route.fulfill(response=resp, body=json.dumps(d))
    lv.route("**/api/app*", live_app)
    lv.route("**/api/live*", lambda r: r.fulfill(content_type="application/json", body=json.dumps({"total": 0, "since": 0, "draft": "", "pending": 0, "lag": 0, "fast": False, "shot": None, "info": {}, "ended": False, "items": []})))
    lv.goto(url + "/#live")
    lv.wait_for_selector("#liveAsk .ais button", timeout=10000)
    lv.evaluate("document.querySelectorAll('.modal').forEach(m => m.hidden = true)")
    SOLID = """() => [...document.querySelectorAll('#vLive button, #vLive a.btn')].filter(b => b.offsetParent !== null && !b.hidden)
          .filter(b => { const c = getComputedStyle(b).backgroundColor; return c !== 'rgba(0, 0, 0, 0)' && c === getComputedStyle(document.documentElement).getPropertyValue('--accent-solid-probe') || false; }).length"""
    solid = lv.evaluate("""() => { const p = document.createElement('button'); p.className = 'btn'; document.body.appendChild(p); const green = getComputedStyle(p).backgroundColor; p.remove();
        return [...document.querySelectorAll('#vLive button, #vLive a.btn')].filter(b => b.offsetParent !== null && getComputedStyle(b).backgroundColor === green).map(b => b.textContent.trim()); }""")
    check("live lecture screen: exactly one solid green control, and it is 'answer here'", solid == ["תשובה כאן"], solid)
    for sel, what in (("[data-float]", "the small window"), ("#markImp", "mark ★"), ("#liveStop", "stop")):
        check(f"live lecture screen: {what} is a ghost button", lv.evaluate(f"getComputedStyle(document.querySelector('#vLive {sel}')).backgroundColor") == "rgba(0, 0, 0, 0)")
    rects = lv.evaluate("['#markImp', '[data-float]', '#liveStop', '.livebar .what b'].map(s => { const r = document.querySelector('#vLive ' + s).getBoundingClientRect(); return [Math.round(r.top), Math.round(r.bottom)]; })")
    check("live lecture screen: stop is in the same row as the title and the other actions (not a row of its own)",
          max(r[0] for r in rects[:3]) < min(r[1] for r in rects[:3]) and abs(rects[2][0] - rects[0][0]) < 4, rects)
    lv.set_viewport_size({"width": 600, "height": 900})
    lv.wait_for_timeout(300)
    acts = lv.evaluate("[...document.querySelectorAll('#vLive .acts button')].filter(b => !b.hidden).map(b => Math.round(b.getBoundingClientRect().top))")
    check("live lecture screen, narrow: the actions stay together in one row (stop is never alone)", len(set(acts)) == 1, acts)
    check("live lecture screen: no script errors", lv.errs == [], lv.errs)
    lv.context.close()

    # ---- 2.19, stage 1: the placeholder of every field is ink-muted (not the browser's grey) ----
    PH = """() => { const out = []; for (const tag of ['input', 'textarea']) { const e = document.createElement(tag); if (tag === 'input') e.type = 'search'; e.placeholder = 'x';
          document.body.appendChild(e); const c = getComputedStyle(e, '::placeholder'); const m = getComputedStyle(document.documentElement).getPropertyValue('--muted').trim();
          const probe = document.createElement('i'); probe.style.color = m; document.body.appendChild(probe);
          out.push([c.color === getComputedStyle(probe).color, c.opacity]); e.remove(); probe.remove(); } return out; }"""
    for page_name, path in (("app", "/"), ("floating window", "/mini"), ("player", "/player")):
        for theme in ("light", "dark"):
            ph = b.new_context(viewport={"width": 900, "height": 700}, locale="he-IL", color_scheme=theme).new_page()
            ph.goto(url + path)
            ph.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            ph.wait_for_timeout(300)
            r = ph.evaluate(PH)
            check(f"placeholder, {page_name}, {theme}: ink-muted at full strength (a text box and a search box)", r == [[True, "1"], [True, "1"]], r)
            ph.context.close()

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
    check("...in the row of \"תשובה כאן\" (where one decides to ask), not in the title row that a long course name needs",
          lagp.evaluate("document.querySelector('#lag').closest('header')") is None
          and lagp.evaluate("""() => { const l = document.querySelector('#lag').getBoundingClientRect(), b = document.querySelector('#box .ais button.here').getBoundingClientRect();
              return Math.abs((l.top + l.bottom) / 2 - (b.top + b.bottom) / 2) < 12 && l.right <= innerWidth && l.left >= 0 && l.right < b.left || l.left > b.right; }"""))
    check("...and the title row is whole: the course name is not cut by it", lagp.evaluate("""() => { const t = document.querySelector('#lec'); return t.scrollWidth <= t.clientWidth + 1; }"""))
    check("...with the whole sentence for the screen reader and the pointer",
          "התמלול מאחר ב-25 שניות" in lagp.evaluate("document.querySelector('#lag').getAttribute('aria-label')"))
    check("...a caution pill: not green", lagp.evaluate("""() => { const p = document.createElement('div'); p.style.cssText = 'background:var(--warn-bg);color:var(--warn-fg)'; document.body.appendChild(p);
          const a = getComputedStyle(p), b = getComputedStyle(document.querySelector('#lag')); const ok = a.backgroundColor === b.backgroundColor && a.color === b.color; p.remove(); return ok; }"""))
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

    # ---- a settings save that failed is told (once per failure), in the floating window and in the app ----
    saves = {"n": 1}
    for page_name, path in (("floating window", "/mini"), ("app", "/")):
        sp = b.new_context(viewport={"width": 1100, "height": 800}, locale="he-IL").new_page()

        def patched(route):
            resp = route.fetch()
            d = resp.json()
            d["save_failed"] = {"n": saves["n"], "msg": "לא הצלחתי לשמור את ההגדרות. לנסות שוב."}
            route.fulfill(response=resp, body=json.dumps(d))
        sp.route("**/api/app*", patched)
        sp.goto(url + path)
        sp.wait_for_function("document.querySelector('#toast') && document.querySelector('#toast').textContent.includes('לא הצלחתי לשמור')", timeout=8000)
        check(f"{page_name}: a save that failed is shown in words", "לנסות שוב" in sp.inner_text("#toast"), sp.inner_text("#toast"))
        sp.evaluate("document.querySelector('#toast').textContent = ''; document.querySelector('#toast').classList.remove('on')")
        sp.wait_for_timeout(4500)
        check(f"{page_name}: the same failure is not shown again on every poll", sp.evaluate("document.querySelector('#toast').textContent") == "")
        saves["n"] += 1
        sp.wait_for_function("document.querySelector('#toast').textContent.includes('לא הצלחתי לשמור')", timeout=8000)
        check(f"{page_name}: a new failure is shown", True)
        sp.context.close()

    # ---- "no animations and motion": the app tells the tool (the floating button is drawn by the tool, not by the page) ----
    st_ = page()
    st_.posts = []
    st_.route("**/api/cmd", lambda r: (st_.posts.append(json.loads(r.request.post_data or "{}")), r.fulfill(content_type="application/json", body=json.dumps({"ok": True})))[1])
    st_.evaluate("a11ySet('still', true)")
    st_.wait_for_timeout(300)
    st_.evaluate("a11ySet('still', false)")
    st_.wait_for_timeout(300)
    seq = [p_.get("on") for p_ in st_.posts if p_.get("action") == "a11y_still"]
    check("accessibility: choosing 'no animations and motion' (and unchoosing it) is told to the tool, for the floating button", seq == [True, False], st_.posts)
    st_.context.close()

    # ---- the live view: the course of the lecture that records can be changed, and an offer from the first slide ----
    lc = page()
    lc.posts = []
    lc.route("**/api/cmd", lambda r: (lc.posts.append(json.loads(r.request.post_data or "{}")), r.fulfill(content_type="application/json", body=json.dumps({"ok": True})))[1])
    lc.evaluate("""() => { courses = [{name: 'אלגוריתמים'}, {name: 'פיזיקה'}, {name: 'ללא קורס'}]; document.querySelector('#vLive').hidden = false;
        drawLiveCourse({kind: 'live', done: false, ready: true, yt: null, course: 'פיזיקה', moving: false, suggest: {course: 'אלגוריתמים', why: 'slide'}}); }""")
    check("live view: the course of the recording lecture is shown and can be changed (every course, and without a course)",
          lc.is_visible("#liveCourse") and lc.evaluate("[...document.querySelectorAll('#liveCourse option')].map(o => o.value)") == ["אלגוריתמים", "פיזיקה", "ללא קורס"] and lc.evaluate("document.querySelector('#liveCourse').value") == "פיזיקה")
    check("live view: a course offered from the first slide is shown, with the name", lc.is_visible("#liveSug") and "אלגוריתמים" in lc.inner_text("#liveSugText"))
    lc.select_option("#liveCourse", "אלגוריתמים")
    lc.wait_for_timeout(300)
    check("live view: choosing a course sends it", any(p_.get("action") == "set_lecture_course" and p_.get("course") == "אלגוריתמים" for p_ in lc.posts), lc.posts)
    lc.click("#liveSugYes")
    lc.wait_for_timeout(300)
    check("live view: 'move' on the offer sends that course and the offer goes", [p_ for p_ in lc.posts if p_.get("action") == "set_lecture_course"][-1].get("course") == "אלגוריתמים" and lc.is_hidden("#liveSug"))
    lc.evaluate("drawLiveCourse({kind: 'live', done: false, ready: true, yt: null, course: 'אלגוריתמים', moving: true, suggest: null})")
    check("live view: a lecture that will move says so, in words", "תועבר לקורס" in lc.inner_text("#liveCourseNote") and "אלגוריתמים" in lc.inner_text("#liveCourseNote"), lc.inner_text("#liveCourseNote"))
    lc.evaluate("drawLiveCourse({kind: 'live', done: false, ready: true, yt: {id: 'x'}, course: 'פיזיקה', moving: false, suggest: null})")
    check("live view: a YouTube video has no course row (it opens in the player)", lc.is_hidden("#liveCourseRow"))
    lc.context.close()

    # ---- the quick-start window (F1): course, kind, start in the background, open the app ----
    def quick_page(theme="light", guess=None, last="פיזיקה", start_ok=True, delay_guess=0):
        qp = b.new_context(viewport={"width": 380, "height": 364}, locale="he-IL").new_page()
        qp.errs, qp.posts = [], []
        qp.on("pageerror", lambda e: qp.errs.append(str(e)))
        qp.route("**/api/library*", lambda r: r.fulfill(content_type="application/json", body=json.dumps(
            {"items": [], "courses": [{"name": "אלגוריתמים", "lectures": 3}, {"name": "פיזיקה", "lectures": 2}, {"name": "ללא קורס", "lectures": 1}]})))

        def app_route(r):
            resp = r.fetch(); d = resp.json(); d["course"] = last; d["theme"] = theme
            r.fulfill(response=resp, body=json.dumps(d))
        qp.route("**/api/app*", app_route)

        def cmd(r):
            body = json.loads(r.request.post_data or "{}")
            qp.posts.append(body)
            a = body.get("action")
            if a == "guess_course":
                if delay_guess:
                    time.sleep(delay_guess)
                out = {"ok": True, **(guess or {})}
            elif a == "start_live":
                out = {"ok": bool(start_ok)} if start_ok else {"ok": False, "error": "הבנתי עוד מסיימת לתמלל את ההרצאה הקודמת."}
            else:
                out = {"ok": True}
            r.fulfill(content_type="application/json", body=json.dumps(out))
        qp.route("**/api/cmd", cmd)
        qp.goto(url + "/quick")
        qp.wait_for_timeout(900)
        return qp

    q = quick_page(guess={"course": "אלגוריתמים", "why": "title", "detail": "זום - אלגוריתמים"})
    check("quick start: the window's title: Hevanti first, then the window, and it has the logo (not the browser's globe)", q.title() == "הבנתי · חלון התחלה מהירה" and q.evaluate("!!document.querySelector('link[rel=icon]')"), q.title())
    check("quick start: the courses, \"ללא קורס\", and a new course last",
          q.evaluate("[...document.querySelectorAll('#course option')].map(o => o.textContent)") == ["אלגוריתמים", "פיזיקה", "ללא קורס", "+ קורס חדש..."])
    check("quick start: the course is chosen from the title of a window, with the reason and \"you can change it\"",
          q.evaluate("document.querySelector('#course').value") == "אלגוריתמים" and "זוהה מכותרת החלון" in q.inner_text("#noteText") and "אפשר להחליף" in q.inner_text("#noteText"), q.inner_text("#noteText"))
    q.select_option("#course", "פיזיקה")
    check("quick start: the student chooses a course himself - the note goes away", q.is_hidden("#note"))
    check("quick start: \"חיה עברית\" is chosen first", q.evaluate("document.querySelector('[data-kind=he]').getAttribute('aria-checked')") == "true" and q.inner_text("#go") == "התחל תמלול")
    q.focus("[data-kind=he]")
    q.keyboard.press("ArrowLeft")
    check("quick start: the arrows move between the kinds (a radio group)", q.evaluate("document.querySelector('[data-kind=en]').getAttribute('aria-checked')") == "true")
    q.click("#go")
    q.wait_for_timeout(500)
    starts = [p_ for p_ in q.posts if p_.get("action") == "start_live"]
    check("quick start: \"start\" starts a live lecture in the chosen language and course", starts == [{"action": "start_live", "lang": "en", "course": "פיזיקה"}], starts)
    check("quick start: ...and then the small window is closed (the lecture runs in the background)", [p_.get("action") for p_ in q.posts][-1] == "quick_close", q.posts)
    q.context.close()

    q = quick_page(guess={})
    check("quick start: no guess - the course of the last lecture, said so", q.evaluate("document.querySelector('#course').value") == "פיזיקה" and "הקורס של ההרצאה הקודמת" in q.inner_text("#noteText"))
    q.click("[data-kind=rec]")
    check("quick start: \"מוקלטת\" - the main button says it goes on in the app (nothing starts here)", q.inner_text("#go") == "המשך באפליקציה")
    q.click("#go")
    q.wait_for_timeout(400)
    check("quick start: \"מוקלטת\" opens the app at the recording box and starts nothing",
          any(p_.get("action") == "quick_open_app" and p_.get("view") == "rec" for p_ in q.posts) and not any(p_.get("action") == "start_live" for p_ in q.posts), q.posts)
    q.context.close()

    q = quick_page(guess={})
    q.click("#app")
    q.wait_for_timeout(400)
    check("quick start: \"פתח את האפליקציה\" opens the app and starts nothing",
          any(p_.get("action") == "quick_open_app" and not p_.get("view") for p_ in q.posts) and not any(p_.get("action") == "start_live" for p_ in q.posts), q.posts)
    q.context.close()

    q = quick_page(guess={})
    q.select_option("#course", "__new")
    check("quick start: \"+ new course\" opens a name field right there (the list keeps the course it had)", q.is_visible("#newName") and q.evaluate("document.querySelector('#course').value") == "פיזיקה")
    q.fill("#newName", "תרמודינמיקה")
    q.keyboard.press("Enter")
    q.wait_for_timeout(400)
    opts = q.evaluate("[...document.querySelectorAll('#course option')].map(o => o.value)")
    check("quick start: the course is created, put before \"ללא קורס\" and chosen, and it says so",
          any(p_.get("action") == "new_course" and p_.get("name") == "תרמודינמיקה" for p_ in q.posts) and q.evaluate("document.querySelector('#course').value") == "תרמודינמיקה"
          and opts.index("תרמודינמיקה") < opts.index("ללא קורס") and q.is_hidden("#newc") and "נוצר" in q.inner_text("#noteText"), (opts, q.posts))
    q.click("#go")
    q.wait_for_timeout(400)
    check("quick start: ...and the lecture starts in it", any(p_.get("action") == "start_live" and p_.get("course") == "תרמודינמיקה" for p_ in q.posts), q.posts)
    q.select_option("#course", "__new")
    q.click("#newNo")
    check("quick start: \"cancel\" closes the field and keeps the course", q.is_hidden("#newc") and q.evaluate("document.querySelector('#course').value") == "תרמודינמיקה")
    q.context.close()

    q = quick_page(guess={}, start_ok=False)
    q.click("#go")
    q.wait_for_timeout(500)
    check("quick start: a start that is refused says why, and the button can be pressed again",
          "מסיימת לתמלל" in q.inner_text("#msg") and q.is_enabled("#go") and not any(p_.get("action") == "quick_close" for p_ in q.posts))
    q.context.close()

    for theme in ("light", "dark"):
        q = quick_page(theme=theme, guess={})
        st = q.evaluate("""() => { const css = (e, p) => getComputedStyle(e)[p], v = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
            const rgb = c => { const d = document.createElement('div'); d.style.color = c; document.body.appendChild(d); const r = getComputedStyle(d).color; d.remove(); return r; };
            const sel = document.querySelector('[data-kind=he]'), go = document.querySelector('#go'), app = document.querySelector('#app');
            let solid = 0; for (const e of document.querySelectorAll('button')) if (css(e, 'backgroundColor') === rgb(v('--accent'))) solid++;
            return {solid, goBg: css(go, 'backgroundColor') === rgb(v('--accent')), selBg: css(sel, 'backgroundColor') === rgb(v('--accent-soft')), appBg: css(app, 'backgroundColor'),
                    noOverflow: document.documentElement.scrollWidth <= innerWidth, small: document.documentElement.scrollHeight <= 364,
                    sameHeight: Math.abs(go.getBoundingClientRect().height - app.getBoundingClientRect().height) < 1, sameWidth: Math.abs(go.getBoundingClientRect().width - app.getBoundingClientRect().width) < 1,
                    name: document.body.innerText.split("הבנתי").length - 1}; }""")
        check(f"quick start, {theme}: one solid green button (start); the chosen kind is the soft green; the app button is a ghost", st["solid"] == 1 and st["goBg"] and st["selBg"] and st["appBg"] == "rgba(0, 0, 0, 0)", st)
        check(f"quick start, {theme}: it fits a small window, without a sideways scroll", st["noOverflow"] and st["small"], st)
        check(f"quick start, {theme}: the start button and \"open the app\" are a pair (same width and height), and the name Hevanti is not written in the window (it is in the title bar)", st["sameHeight"] and st["sameWidth"] and st["name"] == 0, st)
        check(f"quick start, {theme}: no script errors", q.errs == [], q.errs)
        q.context.close()
    b.close()

print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.exit(1 if fails else 0)
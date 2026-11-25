"""The floating window's ask box (25.11.2026): the round arrow button is inside the writing box (live only with text, and it is the stop
button while an answer comes), the box is one line and grows to 4 lines then scrolls, Enter sends and Shift+Enter is a new line, there is no
resize handle, and "עוד פרטים" / "תן דוגמה" sit at the end of the last answer only. Against a made-up answer. Needs Playwright and
Edge or Chrome; skips when missing.
  python3 tools/test_mini_send.py"""
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


srv = L.AppServer()
assert srv.start()
url = srv.url.rstrip("/")
ANS = "בהרצאה הוסבר משהו.\n" + "\n".join("- נקודה %d: הסבר ארוך שמתפרש על יותר משורה אחת בחלון הקטן" % i for i in range(1, 9))


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
    pg = b.new_context(viewport={"width": 380, "height": 640}, locale="he-IL").new_page()
    errs, asks = [], []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/api/app*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(
        {"session": {"kind": "live", "done": False, "course": "פיזיקה"}, "math": {"ask": True}, "ai_apps": {}, "connect": {}, "has_key": True})))
    pg.route("**/api/live*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"total": 0, "items": [], "lag": 0, "info": {}})))
    pg.route("**/api/ask", lambda r: (asks.append(json.loads(r.request.post_data or "{}")), r.fulfill(status=200, content_type="text/plain", body=ANS))[1])
    pg.goto(url + "/mini")
    pg.wait_for_selector(".inbox button.send", timeout=10000)
    pg.wait_for_timeout(600)
    check("the empty box is one line from the start (also when the window was hidden at first)", pg.evaluate("document.querySelector('.inbox textarea').getBoundingClientRect().height") < 50, pg.evaluate("document.querySelector('.inbox textarea').getBoundingClientRect().height"))
    pg.wait_for_timeout(800)
    H = "() => Math.round(document.querySelector('.inbox textarea').getBoundingClientRect().height)"
    BTN = ".inbox button.send"

    check("the old big 'תשובה כאן' row is gone", pg.evaluate("![...document.querySelectorAll('button')].some(b => b.offsetParent && b.textContent.trim() === 'תשובה כאן')"))
    check("the arrow button has the name 'שליחה' and the tip 'שליחה (Enter)'", pg.get_attribute(BTN, "aria-label") == "שליחה" and pg.get_attribute(BTN, "title") == "שליחה (Enter)")
    check("it is inside the writing box, at its LEFT (the end of a Hebrew line), and round", pg.evaluate("""() => { const i = document.querySelector('.inbox').getBoundingClientRect(), t = document.querySelector('.inbox textarea').getBoundingClientRect(),
        b = document.querySelector('.inbox button.send'), r = b.getBoundingClientRect(); return b.getBoundingClientRect().right <= i.right && r.left < t.left + 5 && r.left >= i.left && getComputedStyle(b).borderRadius === '50%' && Math.abs(r.width - r.height) < 1; }"""))
    check("empty box: the button is dimmed and cannot be pressed (and not reached by Tab)", pg.is_disabled(BTN))
    check("no resize handle on the box", pg.evaluate("getComputedStyle(document.querySelector('.inbox textarea')).resize") == "none")
    h1 = pg.evaluate(H)
    check("one line by default", h1 < 50, h1)

    # the look of the answers area (25.11.2026)
    check("a hairline under the 'what did I miss' row, in the border colour", pg.evaluate("""() => { const s = getComputedStyle(document.querySelector('#miss')); return s.borderBottomWidth === '1px' && s.borderBottomStyle === 'solid'; }"""))
    check("the answers area has a thin round scroll bar (4px, no arrows)", pg.evaluate("""() => { const c = document.querySelector('.conv'); return getComputedStyle(c, '::-webkit-scrollbar').width === '4px' && getComputedStyle(c, '::-webkit-scrollbar-button').display === 'none'; }"""))
    check("the fade at the top does not block clicks, and is off until the text is scrolled", pg.evaluate("""() => { const w = document.querySelector('.convwrap'), f = getComputedStyle(w, '::before');
        return f.pointerEvents === 'none' && f.opacity === '0' && f.height === '20px' && f.backgroundImage.includes('linear-gradient'); }"""))
    check("empty state: a question mark, the sentence, the small line and two example questions", pg.evaluate("""() => { const e = document.querySelector('.empty'); return !e.hidden && !!e.querySelector('svg')
        && e.textContent.includes('שאל כל דבר על מה שנאמר בהרצאה') && e.textContent.includes('או לחץ על אחת מהשאלות האלה:')
        && [...e.querySelectorAll('.ex button')].map(b => b.textContent).join('|') === 'מה הנושא המרכזי עד עכשיו?|תסביר שוב את מה שנאמר עכשיו'; }"""))
    check("empty state is in the middle of the area", pg.evaluate("""() => { const e = document.querySelector('.empty').getBoundingClientRect(), c = document.querySelector('.convwrap').getBoundingClientRect(); return Math.abs((e.top + e.bottom) / 2 - (c.top + c.bottom) / 2) < 30; }"""))
    check("the small window's transparency starts at 80%", L.mini_opacity() == 80, L.mini_opacity())
    pg.click(".empty .ex button:first-child")
    pg.wait_for_selector(".qa .a:not(.wait)", timeout=8000)
    check("an example question is sent exactly as it is, and the empty state goes", [a.get("question") for a in asks] == ["מה הנושא המרכזי עד עכשיו?"] and pg.evaluate("document.querySelector('.empty').hidden"), asks)
    pg.evaluate("document.querySelector('.conv').scrollTop = 80")
    pg.wait_for_timeout(300)
    check("scrolled text: the fade shows at the top, and the bar shows while scrolling", pg.evaluate("""() => { const w = document.querySelector('.convwrap'); return w.classList.contains('scrolled') && getComputedStyle(w, '::before').opacity === '1' && w.classList.contains('scrolling'); }"""))
    pg.evaluate("document.querySelector('.conv').scrollTop = 0")
    check("the 'עוד פרטים' / 'תן דוגמה' buttons are under the last answer, in the flow: they never cover its text", pg.evaluate("""() => { const f = document.querySelector('.followbar'), q = [...document.querySelectorAll('.qa')].pop().getBoundingClientRect(), r = f.getBoundingClientRect(); return getComputedStyle(f).position === 'static' && r.top >= q.bottom - 1 && r.height > 20; }"""))
    asks.clear()

    pg.fill("textarea", "שאלה קצרה")
    check("with text, the button is live", not pg.is_disabled(BTN))
    check("a short question keeps one line", pg.evaluate(H) == h1, pg.evaluate(H))
    pg.fill("textarea", "שאלה ארוכה מאוד שגורמת לתיבה לגדול " * 3)
    h2 = pg.evaluate(H)
    check("a longer question makes the box grow", h2 > h1, (h1, h2))
    pg.fill("textarea", "שורה\n" * 12)
    h3 = pg.evaluate(H)
    ov = pg.evaluate("getComputedStyle(document.querySelector('.inbox textarea')).overflowY")
    check("it stops at 4 lines and then scrolls", h1 * 2.5 < h3 < h1 * 4.6 and ov == "auto", (h1, h3, ov))
    pg.fill("textarea", "שורה\n" * 4 + "x")
    check("exactly 4 lines is the limit", abs(pg.evaluate(H) - h3) <= 1, (pg.evaluate(H), h3))

    # Shift+Enter is a new line and sends nothing; Enter sends
    pg.fill("textarea", "")
    pg.focus("textarea")
    pg.keyboard.type("שלום")
    pg.keyboard.press("Shift+Enter")
    pg.keyboard.type("עולם")
    pg.wait_for_timeout(200)
    check("Shift+Enter makes a new line and sends nothing", pg.input_value("textarea") == "שלום\nעולם" and not asks and pg.evaluate(H) > h1, (pg.input_value("textarea"), asks))
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".qa .a:not(.wait)", timeout=8000)
    pg.wait_for_timeout(400)
    check("Enter sends the question as it was typed (Hebrew, two lines)", [a.get("question") for a in asks] == ["שלום\nעולם"], asks)
    check("after sending, the box is empty and back to one line, and the button is dimmed", pg.input_value("textarea") == "" and pg.evaluate(H) == h1 and pg.is_disabled(BTN), (pg.input_value("textarea"), pg.evaluate(H)))

    # the answer area: follow-ups at the end of the last answer only
    check("'עוד פרטים' and 'תן דוגמה' are inside the answer area, after the last answer", pg.evaluate("""() => { const c = document.querySelector('.conv'), f = c.querySelector('.followbar');
        return !!f && c.lastElementChild === f && f.previousElementSibling.classList.contains('qa') && !f.hidden && [...f.querySelectorAll('button')].every(x => !x.hidden); }"""))
    check("...and not in a fixed row above the box", pg.evaluate("document.querySelectorAll('.followbar').length") == 1)
    check("the answer area takes the height that was freed (down to the writing box)", pg.evaluate("""() => { const c = document.querySelector('.conv').getBoundingClientRect(), i = document.querySelector('.inbox').getBoundingClientRect();
        return i.top - c.bottom < 16 && c.height > 300; }"""))
    check("the new answer is shown from its start (the question is at the top of the area)", pg.evaluate("""() => { const c = document.querySelector('.conv'), q = [...c.querySelectorAll('.qa')].pop(); return Math.abs(q.getBoundingClientRect().top - c.getBoundingClientRect().top) < 12; }"""))

    # the arrow button sends; a second answer moves the follow-ups to its end
    pg.fill("textarea", "שאלה שנייה")
    pg.click(BTN)
    pg.wait_for_function("document.querySelectorAll('.qa').length === 3 && !document.querySelector('.qa .a.wait')", timeout=8000)
    pg.wait_for_timeout(400)
    check("the arrow sends the question", [a.get("question") for a in asks] == ["שלום\nעולם", "שאלה שנייה"], asks)
    check("the follow-ups moved to the end of the new answer (still one set)", pg.evaluate("""() => { const c = document.querySelector('.conv'); return c.querySelectorAll('.followbar').length === 1 && c.lastElementChild.classList.contains('followbar') && c.children.length === 4; }"""))
    pg.wait_for_function("!document.querySelector('.inbox button.send').classList.contains('stop')", timeout=8000)
    pg.click(".followbar button:has-text('עוד פרטים')")
    pg.wait_for_function("document.querySelectorAll('.qa').length === 4", timeout=8000)
    pg.wait_for_timeout(300)
    pg.wait_for_function("!document.querySelector('.inbox button.send').classList.contains('stop')", timeout=8000)
    pg.click(".followbar button:has-text('תן דוגמה')")
    pg.wait_for_function("document.querySelectorAll('.qa').length === 5", timeout=8000)
    check("'עוד פרטים' and 'תן דוגמה' still ask exactly as before", [a.get("question") for a in asks][-2:] == ["עוד פרטים", "תן דוגמה"], asks)

    # a question typed in two lines is shown in two lines; a long sentence breaks into lines of about 34 characters at most (25.11.2026)
    pg.wait_for_function("!document.querySelector('.inbox button.send').classList.contains('stop')", timeout=8000)
    pg.fill("textarea", "שלום")
    pg.keyboard.press("Shift+Enter")
    pg.keyboard.type("עולם")
    pg.keyboard.press("Enter")
    pg.wait_for_function("document.querySelectorAll('.qa').length === 6 && !document.querySelector('.qa .a.wait')", timeout=8000)
    check("a question typed in two lines is shown in two lines (the new line is kept)", pg.evaluate("""() => { const q = [...document.querySelectorAll('.qa .q')].pop();
        return getComputedStyle(q).whiteSpace === 'pre-wrap' && q.textContent === 'שלום\\nעולם' && q.getBoundingClientRect().height > 40; }"""))
    pg.wait_for_function("!document.querySelector('.inbox button.send').classList.contains('stop')", timeout=8000)
    pg.fill("textarea", "זו שאלה ארוכה מאוד שנכתבת בלי ירידת שורה ידנית ומכילה הרבה מילים כדי לראות איך היא נשברת")
    pg.press("textarea", "Enter")
    pg.wait_for_function("document.querySelectorAll('.qa').length === 7 && !document.querySelector('.qa .a.wait')", timeout=8000)
    lw = pg.evaluate("""() => { const q = [...document.querySelectorAll('.qa .q')].pop(), cs = getComputedStyle(q);
        return {w: q.getBoundingClientRect().width, cw: document.querySelector('.conv').clientWidth, wrap: cs.overflowWrap, h: q.getBoundingClientRect().height, fs: parseFloat(cs.fontSize)}; }""")
    check("a long question is a bubble of limited width and wraps to several lines", lw["w"] <= lw["cw"] * 0.88 + 1 and lw["h"] > lw["fs"] * 3 and lw["wrap"] == "anywhere", lw)

    pg.wait_for_function("!document.querySelector('.inbox button.send').classList.contains('stop')", timeout=8000)
    # while an answer comes the arrow is the stop button
    slow = []
    pg.unroute("**/api/ask")
    pg.route("**/api/ask", lambda r: slow.append(r))   # never answered: stays busy
    pg.fill("textarea", "שאלה שתיתקע")
    pg.press("textarea", "Enter")
    pg.wait_for_function("document.querySelector('.inbox button.send').classList.contains('stop')", timeout=5000)
    check("while the answer comes the button is 'עצירה' and live even with an empty box", pg.get_attribute(BTN, "aria-label") == "עצירה" and not pg.is_disabled(BTN))
    pg.click(BTN)
    pg.wait_for_function("!document.querySelector('.inbox button.send').classList.contains('stop')", timeout=5000)
    check("a click on it stops, and it goes back to 'שליחה'", pg.get_attribute(BTN, "aria-label") == "שליחה")
    check("no script errors", not errs, errs)
    b.close()
srv.stop()
print()
print("all passed" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)

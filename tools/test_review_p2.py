"""Regression tests for the P2 findings of the independent review of 16.11.2026: one check per finding (the pages are checked
by reading them, and in a browser when Playwright and Edge or Chrome exist).
  python3 tools/test_review_p2.py"""
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp()
os.environ.update(BZM_DATA_DIR=os.path.join(TMP, "data"), LOCALAPPDATA=os.path.join(TMP, "local"), BZM_NO_BROWSER="1", PYTHONUTF8="1")
os.makedirs(os.environ["LOCALAPPDATA"], exist_ok=True)
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

L.ERROR_LOG = os.path.join(TMP, "error_log.txt")
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)[:400]), flush=True)
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


def read(*parts):
    with open(os.path.join(HERE, *parts), encoding="utf-8") as f:
        return f.read()


PROG = ("System", "Program")
APP, PLAYER, MINI, QUICK, ASK = (read(*PROG, f) for f in ("app.html", "player.html", "mini.html", "quick.html", "ask.js"))
PY = read(*PROG, "live_transcribe.py")

# 1. the backup goes to the real Documents folder (OneDrive may have moved it)
check("backup: goes to _documents(), not ~/Documents", "out_dir = out_dir or _documents()" in PY)

# 2. a damaged settings file with no .bak is reported once, not on every read
os.makedirs(L.LOCAL_DIR, exist_ok=True)
for ext in ("", ".bak", ".corrupt"):
    try:
        os.remove(L.SETTINGS_FILE + ext)
    except OSError:
        pass
with open(L.SETTINGS_FILE, "w", encoding="utf-8") as f:
    f.write("{not json")
logged = []
orig_log = L.log
L.log = lambda *a, **k: logged.append(a)
for _ in range(5):
    L.load_settings()
L.log = orig_log
check("damaged settings, no .bak: reported once over five reads", len(logged) == 1, len(logged))
check("damaged settings: the damaged copy is kept as .corrupt", os.path.exists(L.SETTINGS_FILE + ".corrupt"))

# 3. "report a problem": paths and e-mail addresses are cleaned whatever the case
home = os.path.expanduser("~")
with open(L.ERROR_LOG, "w", encoding="utf-8") as f:
    f.write("--- x\nfile " + home.lower() + "\\a.txt and " + home.upper() + "\\b.txt mail dana@gmail.com\n")
t = L.diag_text()
check("report: the home folder is hidden in any case", home.lower() not in t.lower(), t[-300:])
check("report: an e-mail address is hidden", "dana@gmail.com" not in t, t[-300:])
os.environ["USERNAME"] = "ab"
with open(L.ERROR_LOG, "w", encoding="utf-8") as f:
    f.write("--- x\nuser AB did a thing; table is fine\n")
t = L.diag_text()
check("report: a short user name is hidden too, but not inside other words", "AB did" not in t and "table is fine" in t, t[-200:])

# 4. uninstall: the shared model folder loses only Hevanti's own folders
src = PY[PY.index("def uninstall():"):]
check("uninstall: the shared folder is not removed whole", "_hevanti_model_subdirs()" in src and "zipformer-he" in PY[PY.index("def _hevanti_model_subdirs"):][:300])
check("uninstall: the question about the recordings mentions the deleted folder", "deleted" in src[:src.index("ההקלטות שהורדו נמחקו")])

# 5. a recording offered through a link is marked as such, with its whole address
check("#rec= offer: marked as from a link, and the full address is shown", 'via: "link"' in APP and "offVia" in APP and 'd.get("via") == "link"' in PY)

# 6. the player: the app's settings, tokens, keyboard
check("player: applies the app's display and accessibility settings", "bzm.a11y" in PLAYER and "a-contrast" in PLAYER and "--tx" in PLAYER)
check("player: marks use the tokens (no hard-coded yellow or red)", not re.search(r"#d99a00|#d9534f|rgba\(232,176,0|rgba\(217,83,79", PLAYER))
check("app: the mark star on a card is not #C79A00 on white", "#C79A00" not in APP)
check("player: a transcript line and a mark badge can be used with the keyboard", "li.tabIndex = 0" in PLAYER and "b.tabIndex = 0" in PLAYER and "מסומנת:" in PLAYER)

# 8. tabs: arrows, one stop in the Tab order
check("tabs: roving tabindex and arrow keys for settings, a lecture and a course", '"setTabs", "pastTabs", "cTabs"' in APP and "ArrowLeft" in APP and '"Home"' in APP)

# 9. headings
check("headings: a lecture, a course and the live screen have an h1; the page title follows the view",
      all(f'<h1 id="{i}"' in APP for i in ("liveWhat", "pastTitle", "cTitle", "ytWhat")) and "function setDocTitle" in APP and "<h4" not in APP)

# 10. the enlarged picture and the region picker
check("big picture: a dialog; the pictures open with the keyboard", 'id="big" hidden role="dialog"' in APP and "function zoomable" in APP and APP.count("zoomable(im") == 3)
check("region picker: says how to choose without a mouse", "בלי עכבר" in APP)

# 11. the delete confirmation does not focus the delete button
check("confirm: with a danger button the focus goes to cancel", '(okLabel ? $("#confNo") : $("#confOk")).focus()' in APP)

# 12. a double click runs once
check("rename / move / new course: a busy guard", APP.count("busyGuard(") >= 4 and "function busyGuard" in APP)

# 13/14. course names
check("course name: gershayim stay, a colon becomes a dash", L.clean_name('חדו"א 1') == "חדו״א 1" and L.clean_name("a:b") == "a - b", L.clean_name('חדו"א 1'))
os.makedirs(L.LIB_DIR, exist_ok=True)
a = L.create_course("Math")
existed1 = L.CREATED_COURSE["existed"]
b = L.create_course("math")
check("course: 'math' next to 'Math' is the same course, and it is said to exist", a == "Math" and b == "Math" and L.CREATED_COURSE["existed"] and not existed1, (a, b))

# 15. the glossary
words = L.write_glossary("Math", "Newton\nnewton\nNEWTON\nf(x,y)\n# note\n" + "\n".join(f"t{i}" for i in range(400)))
check("glossary: no duplicates by case, a comma stays inside a term, a # line is dropped, 300 at most",
      len(words) == 300 and words[0] == "Newton" and "f(x,y)" in words and "# note" not in words and "newton" not in words, (len(words), words[:3]))
check("glossary: says how many did not fit", L.write_glossary.dropped == 102 and "r.dropped" in APP, L.write_glossary.dropped)
srv = L.AppServer()
assert srv.start()
base = srv.url.rstrip("/")
big = json.dumps({"action": "save_glossary", "course": "Math", "text": "x" * 70000}).encode()
req = urllib.request.Request(base + "/api/cmd", big, {"X-BZM": "1", "Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        code, body = r.status, json.loads(r.read())
except urllib.error.HTTPError as e:
    code, body = e.code, json.loads(e.read() or b"{}")
check("a body over 64KB: 413 with an explanation, not 'unknown command'", code == 413 and "גדולה" in body.get("error", ""), (code, body))

# 16. another window changed the library
check("library changed in another window: the course and lecture screens notice", "נמחק או שונה שמו בחלון אחר" in APP and '["home", "courses", "course", "past"]' in APP)

# 17-29 wording
check("privacy page: no 'AI מובנה' (a setting that does not exist)", "AI מובנה" not in APP)
check("README.md: the slide-pictures sentence agrees with the privacy section, and the video is half a minute", "send every slide" in read("README.md") and "one-minute video" not in read("README.md"))
check("no gear icon / API key in the texts", "גלגל השיניים" not in read("README.txt") and "מפתח API" not in read("README.txt"))
check("no 'Setup' folder in the messages", "בתיקייה Setup" not in PY)
check("the shortcut is 'של הבנתי', not Latin 'Hevanti' alone", "לחיצה כפולה על Hevanti" not in APP and "ב-Hevanti" + chr(92) * 2 + "deleted" not in APP and "את Hevanti" not in PLAYER)
check("no 'בלי מכסה' for the paid plan", "בלי מכסה" not in APP + ASK)
check("the small window has one name in the app", "חלון שאלות קטן" not in APP and "החלון הצף" not in APP and "הכפתור הצף" not in APP)
check("plural: marks and minutes", "1 ★ סימונים" not in APP and "heN(mine.length" in APP and "heN(sv.minutes" in MINI and "function heN" in MINI)
check("quick start: 'חיה בעברית' / 'חיה באנגלית'", "חיה עברית" not in QUICK and "חיה בעברית" in QUICK)
check("the opacity slider is labelled by what it is", "אטימות החלון הקטן (שמאלה: יותר שקוף)" in APP)
check("no internal names in the errors the student sees", "אין חיבור ל-Gemini (" not in PY and "ההורדה נקטעה באמצע (" not in PY and "ה-API של Gemini" not in PY and '" (" + why_code' not in PY)
check("removed words are gone from messages", "הכנה למבחן" not in PY and "וכרטיסיות" not in PY)

# 30. the first-time dialog: one solid green
check("first-time dialog: the link to Google is a ghost button", 'class="btn ghost small" id="setupOpen"' in APP)

# 31-35 CSS
check("narrow marks card: text on the whole width at 480px", "@media (max-width:480px){.mk .ic{grid-row:auto}.mk .sa{grid-column:1/-1}}" in APP)
check("a transcript line with no spaces wraps", ".lines li{line-height:1.7;overflow-wrap:anywhere}" in APP)
check("a dialog fits a zoomed narrow window", "100vw / var(--zoom,1)" in APP and '"--zoom"' in APP)
check("a lecture title cut with … has the whole name as a tooltip", "t.title = e.title" in APP)
check("settings checkboxes share one layout", all(f'<label class="row miniopt"><input type="checkbox" id="{i}">' in APP for i in ("askOn", "planPaid", "mathOn")))

# ---- the browser part (skipped without Playwright and a browser)
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
if sync_playwright:
    L.save_settings(consent_ok=True)
    with sync_playwright() as p:
        br = None
        for kw in ({"channel": "msedge"}, {"channel": "chrome"}, {}):
            try:
                br = p.chromium.launch(headless=True, **kw)
                break
            except Exception:
                continue
        if br is None:
            print("SKIP no browser for the browser part")
        else:
            url = base
            pg = br.new_context(viewport={"width": 1100, "height": 800}, locale="he-IL").new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(url + "/#settings")
            pg.wait_for_timeout(900)
            pg.evaluate("document.querySelectorAll('.modal').forEach(m => m.hidden = true)")
            tabs = pg.evaluate("[...document.querySelectorAll('#setTabs [role=tab]')].map(b => b.tabIndex)")
            check("browser: settings tabs are one stop in the Tab order", tabs.count(0) == 1 and len(tabs) >= 5, tabs)
            pg.focus("#setTabs [role=tab][aria-selected='true']")
            before = pg.evaluate("document.activeElement.id")
            pg.keyboard.press("ArrowDown")
            pg.wait_for_timeout(200)
            after = pg.evaluate("document.activeElement.id")
            check("browser: an arrow moves to the next settings tab and selects it",
                  before != after and pg.evaluate("document.activeElement.getAttribute('aria-selected')") == "true", (before, after))
            check("browser: the title of the page says where you are", "הגדרות" in pg.title(), pg.title())
            check("browser: the settings page has no h4", pg.evaluate("document.querySelectorAll('#vSettings h4').length") == 0)
            # the delete confirmation: Enter right after it opens does not confirm
            pg.evaluate("() => { window.__r = null; confirmBox('למחוק?', 'x', 'מחיקה').then(v => { window.__r = v; }); }")
            pg.keyboard.press("Enter")
            pg.wait_for_timeout(150)
            check("browser: Enter on a delete confirmation cancels", pg.evaluate("window.__r") is False, pg.evaluate("window.__r"))
            check("browser: no page errors", not errs, errs)
            # a narrow window with a high zoom: the dialog stays inside the screen
            pg3 = br.new_context(viewport={"width": 320, "height": 640}, locale="he-IL").new_page()
            pg3.goto(url + "/")
            pg3.wait_for_timeout(600)
            pg3.evaluate("localStorage.setItem('bzm.a11y', JSON.stringify({zoom: 1.5, tx: 1.3}))")
            pg3.reload()
            pg3.wait_for_timeout(900)
            rect = pg3.evaluate("(() => { const c = document.querySelector('.modal:not([hidden]) .card'); if (!c) return null; const r = c.getBoundingClientRect(); return [r.left, r.right, innerWidth]; })()")
            if rect:
                check("browser: a dialog at zoom 150% in 320px is not cut at the side", rect[0] >= -1 and rect[1] <= rect[2] + 1, rect)
            else:
                print("SKIP no dialog open at first start")
            br.close()

print()
print("all passed" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)

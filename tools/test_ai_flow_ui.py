"""The page's side of the question flow, in a real browser: the answer is written under the question, and when Gemini's free quota
is used up the page says so and offers the student's own AI apps (ChatGPT, Gemini, Claude) with the same question, the one used
last first - in the app's ask box and in the floating window. Against a made-up Gemini on this computer; the AI sites are not
opened for real. Needs Playwright and Edge or Chrome; skips when missing. To use another Chromium: HEVANTI_TEST_CHROMIUM=<path>.
  python3 tools/test_ai_flow_ui.py"""
import json
import os
import re
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP playwright is not installed")
    sys.exit(0)
TMP = tempfile.mkdtemp()
os.environ["BZM_DATA_DIR"] = os.path.join(TMP, "data")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "local")
os.environ["BZM_GEMINI_DIR"] = os.path.join(TMP, "gemini")
# (HOME and USERPROFILE are NOT changed here: Playwright finds Edge and keeps its own files under them on Windows, and with them
# moved the browser was not found there - the test skipped, green, without running)
os.environ["BZM_NO_BROWSER"] = "1"
os.makedirs(os.environ["BZM_DATA_DIR"])
os.makedirs(os.environ["LOCALAPPDATA"])

# ---- a made-up Gemini: every model answers, or says "quota" (this minute / today), or is busy ----
MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
MODE = {"stream": "ok"}


def error(code, msg, details=()):
    return json.dumps({"error": {"code": code, "message": msg, "status": "X", "details": list(details)}}).encode("utf-8")


def quota(day):
    qid = "GenerateRequestsPerDayPerProjectPerModel-FreeTier" if day else "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"
    d = [{"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaId": qid}]}]
    if not day:
        d.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"})
    return error(429, "Resource has been exhausted (e.g. check quota).", d)


class Fake(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def _reply(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        ms = [{"name": "models/" + m, "supportedGenerationMethods": ["generateContent", "streamGenerateContent"]} for m in MODELS]
        self._reply(200, json.dumps({"models": ms}).encode("utf-8")) if "/models" in self.path else self._reply(404, b"{}")

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if "streamGenerateContent" not in self.path:
            return self._reply(200, json.dumps({"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}).encode("utf-8"))
        mode = MODE["stream"]
        if mode.startswith("quota"):
            return self._reply(429, quota(mode == "quota-day"))
        if mode == "503":
            return self._reply(503, error(503, "The model is overloaded."))
        chunks = "".join("data: " + json.dumps({"candidates": [{"content": {"parts": [{"text": t}]}}]}, ensure_ascii=False) + "\n\n"
                         for t in ("שלום ", "לכולם"))
        self._reply(200, chunks.encode("utf-8"), "text/event-stream")


fake = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
fake.daemon_threads = True
threading.Thread(target=fake.serve_forever, daemon=True).start()
os.environ["HEVANTI_GEMINI_URL"] = f"http://127.0.0.1:{fake.server_address[1]}/v1beta"

sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)[:500]), flush=True)
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


L.save_settings(math={"key": L.keep_secret("AQ.fake"), "ask": True})
reader = L.math_reader()
srv = L.AppServer()
assert srv.start()
url = srv.url.rstrip("/")


def reset():
    """No model is resting, and the usual order."""
    reader.cool.clear()
    reader.order, reader.model, reader.misses, reader.quota_err = list(MODELS), MODELS[0], 0, None


def launch(p):
    exe = os.environ.get("HEVANTI_TEST_CHROMIUM")
    tries = ([{"executable_path": exe}] if exe else []) + [{"channel": "msedge"}, {"channel": "chrome"}, {}]
    why = []
    for kw in tries:
        try:
            return p.chromium.launch(headless=True, args=["--no-sandbox"] if exe else [], **kw)
        except Exception as e:
            why.append(f"{kw or 'default'}: {str(e).splitlines()[0][:160] if str(e) else e.__class__.__name__}")
    print("no browser could be started:\n  " + "\n  ".join(why))
    return None


with sync_playwright() as p:
    b = launch(p)
    if b is None:
        if os.environ.get("GITHUB_ACTIONS"):   # in CI a missing browser is a failure: a skip would look green and test nothing
            print("::error title=no browser::the browser test could not start a browser")
            print("FAILED: no browser")
            sys.exit(1)
        print("SKIP no browser for Playwright")
        sys.exit(0)
    ctx = b.new_context(viewport={"width": 1100, "height": 900}, locale="he-IL", permissions=["clipboard-read", "clipboard-write"])
    # the AI sites are not opened for real: whatever is not this computer gets an empty page
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.fulfill(status=200, content_type="text/html", body="<html></html>"))

    def page(path="/"):
        pg = ctx.new_page()
        pg.errs, pg.cmds = [], []
        pg.on("pageerror", lambda e: pg.errs.append(str(e)))
        pg.on("request", lambda r: pg.cmds.append(r.post_data) if r.url.endswith("/api/cmd") and r.post_data else None)
        pg.goto(url + path)
        pg.wait_for_timeout(1200)
        pg.evaluate("document.querySelectorAll('.modal').forEach(m => { m.hidden = true })")
        pg.evaluate("localStorage.removeItem('bzm.ai')")
        return pg

    # ---------------------------------------------------------------- the app's ask box
    pg = page()
    pg.evaluate("""() => { window.__d = document.createElement('div'); document.body.appendChild(window.__d);
      window.__a = BZMAsk.mount(window.__d, {context: q => 'הקשר מההרצאה: ' + q, toast() {}}); BZMAsk.setBuiltin(true); }""")
    alt = "() => [...__d.querySelectorAll('.alt-box .ais button')].map(b => b.textContent)"

    reset()
    MODE["stream"] = "ok"
    pg.evaluate("__a.askHere('מה זה גבול?')")
    ans = pg.evaluate("[...__d.querySelectorAll('.qa .a')].map(x => x.textContent)")
    check("an answer is written under the question", ans == ["שלום לכולם"], ans)
    check("...and no other AI is offered", pg.evaluate("__d.querySelectorAll('.alt-box').length") == 0)

    reset()
    MODE["stream"] = "quota-min"
    pg.evaluate("__a.askHere('מה זה גבול?')")
    err = pg.evaluate("[...__d.querySelectorAll('.qa.err .a')].map(x => x.textContent)")
    check("the quota is used up: the page says so", len(err) == 1 and "מכסה" in err[0], err)
    box = pg.evaluate("(__d.querySelector('.alt-box') || {}).textContent || ''")
    check("...and offers to go on in another AI app, with the same question and context",
          "להמשיך עכשיו באפליקציית AI אחרת" in box and "עוד כ-" in box and "שניות" in box, box)
    check("...ChatGPT, Gemini and Claude", pg.evaluate(alt) == ["ChatGPT", "Gemini", "Claude"], pg.evaluate(alt))
    with pg.expect_popup() as pop:
        pg.click(".alt-box .ais button:has-text('Claude')")
    popup = pop.value
    pg.wait_for_timeout(500)
    copied = pg.evaluate("navigator.clipboard.readText()")
    check("a click copies the question with its context", copied == "הקשר מההרצאה: מה זה גבול?", copied)
    check("...and opens that AI", popup.url.startswith("https://claude.ai/"), popup.url)
    check("...and Hevanti remembers it was the last one used", pg.evaluate("localStorage.getItem('bzm.ai')") == "claude")
    popup.close()

    reset()
    pg.evaluate("__a.askHere('שאלה נוספת')")
    names = pg.evaluate("[...[...__d.querySelectorAll('.qa')].pop().querySelectorAll('.alt-box .ais button')].map(b => b.textContent)")
    last_cls = pg.evaluate("[...__d.querySelectorAll('.qa')].pop().querySelector('.alt-box .ais button').className")
    check("the next time the AI used last is first", names[:1] == ["Claude"] and "last" in last_cls, (names, last_cls))

    reset()
    MODE["stream"] = "quota-day"
    pg.evaluate("__a.askHere('עוד שאלה')")
    box = pg.evaluate("[...__d.querySelectorAll('.alt-box')].pop().textContent")
    check("the day's quota: it says it is for today, not for a moment", "של היום נגמרה" in box and "שניות" not in box, box)

    reset()
    MODE["stream"] = "503"
    before = pg.evaluate("__d.querySelectorAll('.alt-box').length")
    pg.evaluate("__a.askHere('שאלה בזמן עומס')")
    err = pg.evaluate("[...__d.querySelectorAll('.qa.err .a')].pop().textContent")
    check("Gemini busy (not the quota): the page says so", "עמוס" in err, err)
    check("...and offers no other AI (it is not the quota)", pg.evaluate("__d.querySelectorAll('.alt-box').length") == before, before)
    check("the ask box: no script errors", pg.errs == [], pg.errs)

    # ---------------------------------------------------------------- the floating window
    reset()
    MODE["stream"] = "quota-min"
    mini = page("/mini")
    mini.wait_for_selector("textarea")
    mini.wait_for_function("[...document.querySelectorAll('.ais button')].some(b => !b.hidden && b.textContent === 'תשובה כאן')", timeout=8000)
    mini.fill("textarea", "שאלה מהחלון הצף")
    mini.press("textarea", "Enter")
    mini.wait_for_selector(".alt-box", timeout=15000)
    check("floating window: the quota is used up - it offers the AI apps too",
          mini.evaluate("[...document.querySelectorAll('.alt-box .ais button')].map(b => b.textContent)") == ["ChatGPT", "Gemini", "Claude"])
    with mini.expect_popup() as pop:
        mini.click(".alt-box .ais button:has-text('ChatGPT')")
    pop.value.close()
    mini.wait_for_timeout(1200)
    copied = mini.evaluate("navigator.clipboard.readText()")
    print("   (copied from the floating window:", repr(copied), ")")
    check("floating window: the question is copied", "שאלה מהחלון הצף" in copied, copied)
    check("floating window: it goes away so the AI's window is not opened behind it",
          any('"hide_mini"' in (c or "") for c in mini.cmds), mini.cmds)
    check("floating window: no script errors", mini.errs == [], mini.errs)

    b.close()

srv.stop()
print()
print("all passed" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)

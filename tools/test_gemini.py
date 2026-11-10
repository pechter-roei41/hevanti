"""The connection to Gemini (System/Program/live_transcribe.py: gemini_stream, _gemini_http_error and the /api/ask handler) against
a made-up Gemini on this computer (HEVANTI_GEMINI_URL) that answers every way Google does: 400, 401, 403 (several reasons), 404, 429,
5xx, a good stream, an answer stopped by the safety filter or by its length, a connection cut in the middle, and a model that is slow
to start or goes quiet in the middle. It checks what the student is told, which errors try the next model, and that a live question
costs at most two models and a bounded time. Any OS, about 30 seconds:
  python3 tools/test_gemini.py"""
import json
import os
import re
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tmp = tempfile.mkdtemp()
os.environ["BZM_DATA_DIR"] = os.path.join(tmp, "data")
os.environ["BZM_GEMINI_DIR"] = os.path.join(tmp, "gemini")
os.environ["LOCALAPPDATA"] = os.path.join(tmp, "local")
os.environ["HOME"] = os.environ["USERPROFILE"] = os.path.join(tmp, "home")
os.environ["BZM_NO_BROWSER"] = "1"

KEY = "AQ.fake-key"
MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
USAGE = {"usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15}}
BEHAVE = {}   # model -> what its streamed answer does
LOG = []      # the models that got a streamed question, in order


def err(code, status, msg, reason=None):
    d = [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": reason, "domain": "googleapis.com"}] if reason else []
    return code, json.dumps({"error": {"code": code, "message": msg, "status": status, "details": d}}).encode("utf-8")


def quota(day):
    qid = "GenerateRequestsPerDayPerProjectPerModel-FreeTier" if day else "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"
    d = [{"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaId": qid}]}]
    if not day:
        d.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"})
    return 429, json.dumps({"error": {"code": 429, "message": "Resource has been exhausted.", "status": "RESOURCE_EXHAUSTED", "details": d}}).encode("utf-8")


ERRORS = {
    "400-other": err(400, "INVALID_ARGUMENT", "Invalid JSON payload received. Unknown name \"foo\" at 'contents[0]'"),
    "400-key": err(400, "INVALID_ARGUMENT", "API key not valid. Please pass a valid API key.", "API_KEY_INVALID"),
    "400-location": err(400, "FAILED_PRECONDITION", "User location is not supported for the API use."),
    "401": err(401, "UNAUTHENTICATED", "Request had invalid authentication credentials."),
    "403-key": err(403, "PERMISSION_DENIED", "Your API key was reported as invalid.", "API_KEY_INVALID"),
    "403-disabled": err(403, "PERMISSION_DENIED", "Generative Language API has not been used in project 123 before or it is disabled. "
                        "Enable it by visiting https://console.developers.google.com/apis/api/generativelanguage.googleapis.com", "SERVICE_DISABLED"),
    "403-model": err(403, "PERMISSION_DENIED", "Permission denied on resource model models/gemini-x."),
    "403-location": err(403, "PERMISSION_DENIED", "User location is not supported for the API use."),
    "403-plain": err(403, "PERMISSION_DENIED", "The caller does not have permission"),
    "404": err(404, "NOT_FOUND", "models/x is not found for API version v1beta"),
    "429-min": quota(False),
    "429-day": quota(True),
    "500": err(500, "INTERNAL", "An internal error has occurred."),
    "503": err(503, "UNAVAILABLE", "The model is overloaded. Please try again later."),
}


def sse(*chunks):
    return "".join("data: " + json.dumps(c, ensure_ascii=False) + "\n\n" for c in chunks).encode("utf-8")


def text(t, **extra):
    return {"candidates": [{"content": {"parts": [{"text": t}]}, **extra}]}


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
        if "/models" in self.path:
            ms = [{"name": "models/" + m, "supportedGenerationMethods": ["generateContent", "streamGenerateContent"]} for m in MODELS]
            return self._reply(200, json.dumps({"models": ms}).encode("utf-8"))
        self._reply(404, b"{}")

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        model = re.search(r"/models/([^:/?]+)", self.path).group(1)
        if "streamGenerateContent" not in self.path:
            return self._reply(200, json.dumps({"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}).encode("utf-8"))
        LOG.append(model)
        mode = BEHAVE.get(model, "ok")
        if mode in ERRORS:
            return self._reply(*ERRORS[mode])
        if mode == "stall-start":   # nothing at all for a while (a model that "thinks" too long)
            time.sleep(3.5)
        if mode == "stall-mid":   # the first words, then silence
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(sse(text("שלום ")))
            time.sleep(3.5)
            return self.wfile.write(sse(text("לכולם")))
        if mode == "slow-gap":   # words with a pause between them: longer than the start limit, shorter than the silence limit
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(sse(text("שלום ")))
            time.sleep(1.6)
            return self.wfile.write(sse(text("לכולם", finishReason="STOP"), USAGE))
        if mode == "cut":   # the connection ends before what was promised
            body = sse(text("שלום "))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(body) + 500))
            self.end_headers()
            return self.wfile.write(body)
        if mode == "blocked":
            return self._reply(200, sse({"promptFeedback": {"blockReason": "SAFETY"}}), "text/event-stream")
        if mode == "finish-safety":
            return self._reply(200, sse({"candidates": [{"finishReason": "SAFETY"}]}), "text/event-stream")
        if mode == "max-tokens":
            return self._reply(200, sse(text("תשובה חלקית", finishReason="MAX_TOKENS"), USAGE), "text/event-stream")
        if mode == "nothing":
            return self._reply(200, sse({}), "text/event-stream")
        self._reply(200, sse(text("שלום "), text("לכולם", finishReason="STOP"), USAGE), "text/event-stream")


class Quiet(ThreadingHTTPServer):
    def handle_error(self, request, client_address):   # (the client gave up on a slow answer: not worth a traceback)
        pass


fake = Quiet(("127.0.0.1", 0), Fake)
fake.daemon_threads = True
threading.Thread(target=fake.serve_forever, daemon=True).start()
os.environ["HEVANTI_GEMINI_URL"] = f"http://127.0.0.1:{fake.server_address[1]}/v1beta"

sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)[:600]), flush=True)
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


def stream(mode, **kw):
    """One streamed question to a model that behaves like `mode`: (the text, info, the MathError or None, seconds)."""
    BEHAVE.clear()
    BEHAVE["m"] = mode
    info, got, e, t0 = {}, [], None, time.time()
    try:
        for piece in L.gemini_stream(KEY, "m", {"contents": []}, {}, info=info, **kw):
            got.append(piece)
    except L.MathError as x:
        e = x
    return "".join(got), info, e, time.time() - t0


# ------------------------------------------------------------------------------------------ 1. what Google answers
for mode, why in (("400-key", "400 with API_KEY_INVALID"), ("401", "401"), ("403-key", "403 with API_KEY_INVALID")):
    _, _, e, _ = stream(mode)
    check(f"{why}: the key was not accepted, and no other model is tried (it is the key)",
          e is not None and "לא קיבל את המפתח" in str(e) and not e.other and not e.kind, (e and str(e)))

_, _, e, _ = stream("400-other")
check("400 that is not about the key: Google's words are shown", e is not None and "400" in str(e) and "Unknown name" in str(e) and not e.other, (e and str(e)))
_, _, e, _ = stream("403-disabled")
check("403: the API is not enabled in the key's project - said so, in Google's words",
      e is not None and "לא מופעל" in str(e) and "has not been used in project" in str(e) and "מפתח" not in str(e).replace("של המפתח", "") and not e.other, (e and str(e)))
_, _, e, _ = stream("403-model")
check("403: no permission for this model - said so, and another model is tried", e is not None and "הרשאה למודל" in str(e) and e.other, (e and (str(e), e.other)))
for mode in ("400-location", "403-location"):
    _, _, e, _ = stream(mode)
    check(f"{mode}: Gemini is not available where the computer is", e is not None and "באזור" in str(e) and "location is not supported" in str(e), (e and str(e)))
_, _, e, _ = stream("403-plain")
check("403 for another reason: Google's short message, not 'the key is wrong'",
      e is not None and "סירב (403)" in str(e) and "does not have permission" in str(e) and "לא קיבל את המפתח" not in str(e), (e and str(e)))
_, _, e, _ = stream("404")
check("404: the model is gone, another is tried", e is not None and "כבר לא זמין" in str(e) and e.other, (e and str(e)))
_, _, e, _ = stream("429-min")
check("429 for a minute: the quota, with the wait Google gave", e is not None and e.kind == "quota" and e.wait == 38 and e.other, (e and (e.kind, e.wait)))
_, _, e, _ = stream("429-day")
check("429 for the day: said so", e is not None and e.kind == "quota" and e.wait >= 600 and "להיום" in str(e), (e and (e.kind, e.wait, str(e))))
for mode in ("500", "503"):
    _, _, e, _ = stream(mode)
    check(f"{mode}: Gemini is busy, another model is tried, and it is not the quota", e is not None and "עמוס" in str(e) and e.other and not e.kind, (e and str(e)))

# ------------------------------------------------------------------------------------------ 2. a good stream, and one that did not come out whole
t, info, e, _ = stream("ok")
check("a good stream: the words, no warning", t == "שלום לכולם" and e is None and not info, (t, info, e))
t, info, e, _ = stream("blocked")
check("the question was blocked by Google: no words, and a line saying why (with the code)",
      t == "" and e is None and "נחסמה" in info.get("warn", "") and "SAFETY" in info.get("warn", ""), (t, info))
t, info, e, _ = stream("finish-safety")
check("the safety filter stopped the answer before any word: why", t == "" and "מסנן הבטיחות" in info.get("warn", "") and "SAFETY" in info["warn"], (t, info))
t, info, e, _ = stream("max-tokens")
check("the answer was too long: what came out is kept, and it says it was cut",
      t == "תשובה חלקית" and "נקטעה" in info.get("warn", "") and "MAX_TOKENS" in info["warn"], (t, info))
t, info, e, _ = stream("nothing")
check("an empty answer with no reason: it says so", t == "" and info.get("warn") == "Gemini לא החזיר תשובה.", (t, info))

# ------------------------------------------------------------------------------------------ 3. the connection breaks, a model is slow
t, info, e, _ = stream("cut")
check("the connection is cut in the middle: what came is kept, and the error says it was cut", t == "שלום " and e is not None and "נותק" in str(e) and not e.other, (t, e and str(e)))
t, info, e, sec = stream("stall-start", timeout=1.0)
check("a model that does not start in time: 'did not answer in time', the next model is tried", e is not None and "לא ענה בזמן" in str(e) and e.other and t == "" and sec < 3, (e and str(e), sec))
t, info, e, sec = stream("stall-mid", timeout=1.0, read_timeout=1.0)
check("a model that goes quiet in the middle: what came is kept, and it says it stopped", t == "שלום " and e is not None and "הפסיק לענות באמצע" in str(e) and not e.other, (t, e and str(e)))
check("...after the silence limit, not after the start limit plus more", sec < 3, sec)
t, info, e, sec = stream("slow-gap", timeout=1.0, read_timeout=3.0)
check("the start limit and the silence limit are separate: a pause longer than the start limit is fine once it started",
      t == "שלום לכולם" and e is None, (t, e and str(e), sec))

# ------------------------------------------------------------------------------------------ 4. through the server: a live question costs at most two models
L.save_settings(math={"key": L.keep_secret(KEY), "ask": True})
reader = L.math_reader()
app = L.APP if getattr(L, "APP", None) is not None else L.App()
L.APP = app
srv = L.AppServer()
check("server started", srv.start(), srv.url)


def reset():
    BEHAVE.clear()
    del LOG[:]
    reader.cool.clear()
    reader.order, reader.model, reader.misses, reader.quota_err = list(MODELS), MODELS[0], 0, None


def ask(**kw):
    payload = dict({"context": "מה זה גבול?", "question": "מה זה גבול?"}, **kw)
    req = urllib.request.Request(srv.url + "api/ask", method="POST", headers={"Content-Type": "application/json", "X-BZM": "1"},
                                 data=json.dumps(payload).encode("utf-8"))
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8"), time.time() - t0
    except urllib.error.HTTPError as x:
        return x.code, x.read().decode("utf-8"), time.time() - t0


reset()
for m in MODELS:
    BEHAVE[m] = "503"
code, body, _ = ask()
check("a live question with every model busy: only two models are tried (not all three)", len(LOG) == 2, LOG)
check("...and the answer says Gemini is busy", code == 400 and "עמוס" in json.loads(body).get("error", ""), (code, body))
reset()
for m in MODELS:
    BEHAVE[m] = "503"
code, body, _ = ask(task="summary")
check("a whole lecture (a task) may try all the models", len(LOG) == 3, LOG)

reset()
L.GEMINI_START_S, L.GEMINI_LIVE_DEADLINE_S = 1.0, 2.5
for m in MODELS:
    BEHAVE[m] = "stall-start"
code, body, sec = ask()
check("every model slow to start: an error, within the total time (not the start time of each, one after the other)",
      code == 400 and "לא ענה בזמן" in json.loads(body).get("error", "") and sec < 4.5, (code, body, sec))
L.GEMINI_START_S, L.GEMINI_LIVE_DEADLINE_S = 15, 25

reset()
L.GEMINI_TASK_START_S, L.GEMINI_TASK_DEADLINE_S = 1.0, 2.5
for m in MODELS:
    BEHAVE[m] = "stall-start"
code, body, sec = ask(task="summary")
check("a whole lecture: the total time ends the tries too (no new try with less than a second left: the third model is not asked)", len(LOG) == 2 and sec < 5, (LOG, sec))
L.GEMINI_TASK_START_S, L.GEMINI_TASK_DEADLINE_S = 60, 90

reset()
BEHAVE[MODELS[0]] = "blocked"
course = "קורס בדיקת Gemini"
L.create_course(course)
lec = os.path.join(L.course_dir(course), "הרצאה 1")
os.makedirs(lec)
open(os.path.join(lec, "הרצאה 1.txt"), "w", encoding="utf-8").write("[09:01:00 | +0:01:00] שלום\n")
code, body, _ = ask(f=course + "/הרצאה 1")
check("a blocked question: the page gets a line saying why, not an empty answer",
      code == 200 and "⚠ Gemini לא ענה: השאלה נחסמה" in body and "SAFETY" in body, (code, body))
check("...and nothing is kept in the lecture's folder", not os.path.exists(os.path.join(lec, L.QA_NAME)))

reset()
BEHAVE[MODELS[0]] = "max-tokens"
code, body, _ = ask(f=course + "/הרצאה 1")
check("an answer that was too long: the words, then a line saying it was cut", code == 200 and body.startswith("תשובה חלקית") and "⚠ התשובה נקטעה" in body, (code, body))

reset()
L.GEMINI_READ_S = 1.0
BEHAVE[MODELS[0]] = "stall-mid"
code, body, sec = ask()
L.GEMINI_READ_S = 45
check("a model that goes quiet in the middle: the words that came, then a line saying it stopped",
      code == 200 and body.startswith("שלום ") and "⚠ Gemini הפסיק לענות באמצע" in body, (code, body))

reset()
BEHAVE[MODELS[0]] = "cut"
code, body, _ = ask()
check("a connection cut in the middle: the words that came, then a line saying it was cut", code == 200 and body.startswith("שלום ") and "⚠" in body and "נותק" in body, (code, body))

reset()
BEHAVE[MODELS[0]] = "403-disabled"
code, body, _ = ask()
d = json.loads(body)
check("through the server: 403 with the API off is said in Google's words, and it is not the quota",
      code == 400 and "לא מופעל" in d.get("error", "") and not d.get("quota"), (code, body))

srv.stop()
print()
print("all passed" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)

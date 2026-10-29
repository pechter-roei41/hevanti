"""Tests for the free Gemini quota and the "do you have a paid AI plan?" question (System/Program/live_transcribe.py),
against a made-up Gemini server on this computer (HEVANTI_GEMINI_URL): a question that meets the quota is answered
with "quota" and how long to wait (the page then offers the student's own AI apps), the models that said "quota"
rest for a moment (Google is not asked again for every question), and the plan is remembered. Any OS:
  python3 tools/test_quota.py"""
import json
import os
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

# ---- a made-up Gemini: the models, a one-word answer, a streamed answer - or the quota ----
MODE = {"gen": "ok", "stream": "ok"}   # "ok" | "quota-min" | "quota-day"
HITS = {"gen": 0, "stream": 0}
USAGE = {"usageMetadata": {"promptTokenCount": 1234, "candidatesTokenCount": 56, "thoughtsTokenCount": 7, "totalTokenCount": 1297}}
MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-flash-image"]


def quota_body(day):
    qid = "GenerateRequestsPerDayPerProjectPerModel-FreeTier" if day else "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"
    d = [{"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaId": qid}]}]
    if not day:
        d.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"})
    return json.dumps({"error": {"code": 429, "message": "Resource has been exhausted (e.g. check quota).",
                                 "status": "RESOURCE_EXHAUSTED", "details": d}}).encode("utf-8")


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
        stream = "streamGenerateContent" in self.path
        HITS["stream" if stream else "gen"] += 1
        mode = MODE["stream" if stream else "gen"]
        if mode.startswith("quota"):
            return self._reply(429, quota_body(mode == "quota-day"))
        if stream:
            chunks = "".join("data: " + json.dumps({"candidates": [{"content": {"parts": [{"text": t}]}}], **USAGE}, ensure_ascii=False) + "\n\n"
                             for t in ("שלום ", "לכולם"))
            return self._reply(200, chunks.encode("utf-8"), "text/event-stream")
        self._reply(200, json.dumps({"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}).encode("utf-8"))


fake = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
fake.daemon_threads = True
threading.Thread(target=fake.serve_forever, daemon=True).start()
os.environ["HEVANTI_GEMINI_URL"] = f"http://127.0.0.1:{fake.server_address[1]}/v1beta"

sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)[:500]))
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):   # shown on the run's page (annotations)
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


def gemini_error(mode):
    MODE["gen"] = mode
    try:
        L.gemini_call("models/gemini-flash-latest:generateContent", "AQ.fake", {"contents": []})
    except L.MathError as e:
        return e
    return None


# ---- 1. what Google's 429 says ----
e = gemini_error("quota-min")
check("429 per minute: quota, waits what Google says", e is not None and e.kind == "quota" and e.other and e.wait == 38, (e and (e.kind, e.wait)))
e = gemini_error("quota-day")
check("429 per day: quota, said so", e is not None and e.kind == "quota" and e.wait >= 600 and "להיום" in str(e), (e and (e.kind, e.wait, str(e))))
MODE["gen"] = "ok"

# ---- 2. the plan: remembered once, the same everywhere ----
L.save_settings(math={"key": L.keep_secret("AQ.fake"), "ask": True})
reader = L.math_reader()
check("plan: not asked yet", reader.status()["plan"] == "")
r = L.math_set({"plan": "paid"})
check("plan: paid is remembered", r["ok"] and r["math"]["plan"] == "paid" and L.math_settings().get("plan") == "paid", r)
check("plan: the key and the answers are left alone", r["math"]["has_key"] and r["math"]["ask"], r)
r = L.math_set({"plan": "free"})
check("plan: free", r["math"]["plan"] == "free", r)
r = L.math_set({"plan": "whatever"})
check("plan: anything else is 'not asked'", r["math"]["plan"] == "", r)

# ---- 3. a question through the real server ----
srv = L.AppServer()
check("server started", srv.start(), srv.url)


def ask(question="מה זה מומנט?"):
    req = urllib.request.Request(srv.url + "api/ask", method="POST", headers={"Content-Type": "application/json", "X-BZM": "1"},
                                 data=json.dumps({"context": question, "question": question}).encode("utf-8"))
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8")


def asked_json(body, code):
    return json.loads(body) if code in (400, 429) else {}


MODE.update(gen="ok", stream="ok")
code, body = ask()
check("a question is answered, streamed", code == 200 and body == "שלום לכולם", (code, body))
tok = os.path.join(tmp, "local", "Hevanti", "tokens.jsonl")
rows = [json.loads(x) for x in open(tok, encoding="utf-8")] if os.path.isfile(tok) else []
check("tokens: logged for the developer (counts, no text)",
      len(rows) == 1 and rows[0]["prompt"] == 1234 and rows[0]["out"] == 56 and rows[0]["total"] == 1297 and rows[0]["ok"]
      and "מה זה מומנט" not in open(tok, encoding="utf-8").read() and "שלום" not in open(tok, encoding="utf-8").read(), rows)
check("tokens: not sent to the page", "1234" not in body, body)

# every model says "quota" (the minute's): the answer says so, and how long to wait
MODE["stream"] = "quota-min"
HITS["stream"] = 0
code, body = ask()
d = asked_json(body, code)
check("quota: the page is told (429, quota, wait)", code == 429 and d.get("quota") is True and 0 < d.get("wait", 0) <= 60 and "מכסה" in d.get("error", ""), (code, body))
tried = HITS["stream"]
check("quota: the usable models were tried (not the image one)", 1 <= tried <= 3, tried)

# ... and they rest: the next question does not ask Google again
code, body = ask()
d = asked_json(body, code)
check("quota: asked again at once - the same answer", code == 429 and d.get("quota") is True, (code, body))
check("quota: Google was not asked again", HITS["stream"] == tried, (HITS["stream"], tried))
check("quota: the models rest at most a minute", bool(reader.cool) and all(u - time.time() <= 61 for u, _ in reader.cool.values()), reader.cool)

# the rest is over: the question goes through, and the model that answered is free again
for m in list(reader.cool):
    reader.cool[m] = (0, reader.cool[m][1])
MODE["stream"] = "ok"
code, body = ask()
check("after the rest: answered", code == 200 and body == "שלום לכולם", (code, body))
check("after the rest: the model that answered is free", len(reader.cool) < tried, reader.cool)

# the day's quota: said so, but a wrong guess never locks the lecture for long
reader.cool.clear()
MODE["stream"] = "quota-day"
code, body = ask()
d = asked_json(body, code)
check("day quota: told", code == 429 and d.get("quota") and "להיום" in d.get("error", "") and d.get("wait", 0) >= 600, (code, body))
check("day quota: the rest is still at most a minute", bool(reader.cool) and all(u - time.time() <= 61 for u, _ in reader.cool.values()), reader.cool)
MODE["stream"] = "ok"
reader.cool.clear()

# "no model answers" because of the quota is not "no model": the same quota answer, and no more asking meanwhile
reader.model, reader.order, reader.quota_err = "", [], None
MODE["gen"] = "quota-min"
HITS["gen"] = 0
code, body = ask()
d = asked_json(body, code)
check("the check finds the quota: quota answer", code == 429 and d.get("quota") is True, (code, body))
probed = HITS["gen"]
code, body = ask()
d = asked_json(body, code)
check("the check is not repeated for every question", code == 429 and d.get("quota") is True and HITS["gen"] == probed, (code, body, HITS["gen"], probed))

# the quota comes back: the next check finds the models and the question is answered
MODE["gen"] = "ok"
reader.quota_until = 0
code, body = ask()
check("quota back: answered", code == 200 and body == "שלום לכולם", (code, body))

srv.stop()
print()
print("all passed" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)

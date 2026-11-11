"""The question-to-AI flow (System/Program/live_transcribe.py), from the sound to the answer, against a made-up Gemini on this
computer (HEVANTI_GEMINI_URL) and a made-up speaker and Whisper (no model, no sound card, no network). It checks:
  - what is sent: the key only in the header, the question, what was said, the instructions, at most 6 earlier turns
  - the answer as it is streamed (the model's "thoughts" are not shown), and what is kept in the lecture's folder
  - a model that is busy, gone or out of quota: the next one answers, and the one that failed is not asked again at once
  - a wrong key, or every model busy: said clearly, and it is not the quota (the page offers no other AI for it)
  - a lecture in progress: the words that were just transcribed reach Gemini from the floating window, "what I missed"
    asks for its minutes, and when the quota is used up the answer says so while the lecture goes on being written
The page's side of "the quota ran out: go on in another AI app" is in tools/test_ai_flow_ui.py. Any OS, about 30 seconds:
  python3 tools/test_ai_flow.py"""
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

KEY = "AQ.secret-key-for-the-test"
MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
USAGE = {"usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20, "totalTokenCount": 120}}

BEHAVE = {}    # model -> what its streamed answer does (default "ok")
LOG = []       # every request Gemini got: {"model", "stream", "key", "path", "body"}
GEN = {"mode": "ok"}   # the one-word check of the models


def error_body(code, msg, details=None):
    return json.dumps({"error": {"code": code, "message": msg, "status": "X", "details": details or []}}).encode("utf-8")


def quota_body(day):
    qid = "GenerateRequestsPerDayPerProjectPerModel-FreeTier" if day else "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"
    d = [{"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaId": qid}]}]
    if not day:
        d.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"})
    return error_body(429, "Resource has been exhausted (e.g. check quota).", d)


def sse(*chunks):
    return "".join("data: " + json.dumps(c, ensure_ascii=False) + "\n\n" for c in chunks).encode("utf-8")


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
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        stream = "streamGenerateContent" in self.path
        model = re.search(r"/models/([^:/?]+)", self.path).group(1)
        try:
            body = json.loads(raw.decode("utf-8"))
        except ValueError:
            body = None
        LOG.append({"model": model, "stream": stream, "key": self.headers.get("x-goog-api-key"), "path": self.path, "body": body})
        if not stream:
            return self._reply(200, json.dumps({"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}).encode("utf-8"))
        mode = BEHAVE.get(model, "ok")
        if mode == "quota-min":
            return self._reply(429, quota_body(False))
        if mode == "quota-day":
            return self._reply(429, quota_body(True))
        if mode == "503":
            return self._reply(503, error_body(503, "The model is overloaded. Please try again later."))
        if mode == "404":
            return self._reply(404, error_body(404, "models/x is not found for API version v1beta"))
        if mode == "401":
            return self._reply(401, error_body(401, "API key not valid. Please pass a valid API key."))
        if mode == "empty":   # a blocked answer: no words at all
            return self._reply(200, sse({"candidates": [{"finishReason": "SAFETY"}], "promptFeedback": {"blockReason": "SAFETY"}}), "text/event-stream")
        if mode == "thoughts":
            return self._reply(200, sse({"candidates": [{"content": {"parts": [{"text": "מחשב בשקט...", "thought": True}]}}]},
                                        {"candidates": [{"content": {"parts": [{"text": "התשובה "}]}}]},
                                        {"candidates": [{"content": {"parts": [{"text": "האמיתית"}]}}], **USAGE}), "text/event-stream")
        self._reply(200, sse({"candidates": [{"content": {"parts": [{"text": "שלום "}]}}]},
                             {"candidates": [{"content": {"parts": [{"text": "לכולם"}]}}], **USAGE}), "text/event-stream")


fake = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
fake.daemon_threads = True
threading.Thread(target=fake.serve_forever, daemon=True).start()
os.environ["HEVANTI_GEMINI_URL"] = f"http://127.0.0.1:{fake.server_address[1]}/v1beta"

sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import numpy as np  # noqa: E402
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)[:600]), flush=True)
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


L.save_settings(math={"key": L.keep_secret(KEY), "ask": True})
reader = L.math_reader()
app = L.APP if getattr(L, "APP", None) is not None else L.App()
L.APP = app
srv = L.AppServer()
check("server started", srv.start(), srv.url)


def reset():
    """Every model answers, none is resting, and the order is the usual one."""
    BEHAVE.clear()
    del LOG[:]
    reader.cool.clear()
    reader.order, reader.model, reader.misses, reader.quota_err = list(MODELS), MODELS[0], 0, None


def post(payload, timeout=30):
    req = urllib.request.Request(srv.url + "api/ask", method="POST", headers={"Content-Type": "application/json", "X-BZM": "1"},
                                 data=json.dumps(payload).encode("utf-8"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def post_ctx(payload):
    """The small window asks for the text to COPY to another AI app: the question with the last minutes. Nothing is sent to Google."""
    req = urllib.request.Request(srv.url + "api/mini_context", method="POST", headers={"Content-Type": "application/json", "X-BZM": "1"},
                                 data=json.dumps(payload).encode("utf-8"))
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8")).get("context", "")
    except urllib.error.HTTPError as e:
        return e.code, ""


def ask(question="מה זה מומנט?", **kw):
    return post(dict({"context": question, "question": question}, **kw))


def as_json(body):
    try:
        return json.loads(body)
    except ValueError:
        return {}


def asked(model=None):
    """The streamed questions Gemini got (of one model, or all)."""
    return [x for x in LOG if x["stream"] and (model is None or x["model"] == model)]


def user_text(entry):
    """The last user message of a request: what was said, and the question."""
    return "".join(p.get("text", "") for p in entry["body"]["contents"][-1]["parts"])


# ---------------------------------------------------------------------------------- 1. what is sent to Gemini
reset()
history = [{"q": f"שאלה {i}", "a": f"תשובה {i}"} for i in range(8)]
code, body = ask("מה המשפט האחרון?", context="[00:01:02] המרצה אמר שהנגזרת היא קצב שינוי\nהשאלה שלי: מה המשפט האחרון?", history=history)
check("a question is answered, streamed", code == 200 and body == "שלום לכולם", (code, body))
sent = asked()[0] if asked() else {}
check("the key goes in a header, never in the address or the body",
      sent.get("key") == KEY and KEY not in sent.get("path", "") and KEY not in json.dumps(sent.get("body"), ensure_ascii=False), sent.get("path"))
check("what was said and the question are sent", "הנגזרת היא קצב שינוי" in user_text(sent) and "מה המשפט האחרון" in user_text(sent), user_text(sent)[:200])
check("only the last 6 turns of the conversation go with it (and this question)", len(sent["body"]["contents"]) == 6 * 2 + 1, len(sent["body"]["contents"]))
check("...the newest ones", sent["body"]["contents"][0]["parts"][0]["text"] == "שאלה 2", sent["body"]["contents"][0])
check("the fixed instructions are sent, with the rule of never inventing what the lecturer said",
      sent["body"]["systemInstruction"]["parts"][0]["text"] == L.tutor_system(False) and "לעולם אל תמציא מה המרצה אמר" in L.tutor_system(False), L.tutor_system(False)[:200])

L.math_set({"notes": "תענה בשורה אחת, באנגלית"})
reset()
ask()
system = asked()[0]["body"]["systemInstruction"]["parts"][0]["text"]
check("the student's own instructions are added - after the fixed ones, and they cannot cancel the rule",
      "תענה בשורה אחת, באנגלית" in system and system.index("תענה בשורה") > system.index("לעולם אל תמציא מה המרצה אמר"), system[-300:])
L.math_set({"notes": ""})

# ---------------------------------------------------------------------------------- 2. the answer as it is streamed
reset()
BEHAVE[MODELS[0]] = "thoughts"
code, body = ask()
check("the model's own 'thoughts' are not shown, only the answer", code == 200 and body == "התשובה האמיתית", (code, body))

# ---------------------------------------------------------------------------------- 3. a model that fails: the next one answers
reset()
BEHAVE[MODELS[0]] = "quota-min"
code, body = ask()
check("a model out of quota: the next model answers", code == 200 and body == "שלום לכולם", (code, body))
check("...the first was tried once, the second answered", [x["model"] for x in asked()] == [MODELS[0], MODELS[1]], [x["model"] for x in asked()])
check("...and the first rests (at most a minute)", MODELS[0] in reader.cool and reader.cool[MODELS[0]][0] - time.time() <= 61, reader.cool)
del LOG[:]
code, body = ask()
check("the next question goes straight to the model that answers (Google is not asked again for the one that rests)",
      code == 200 and [x["model"] for x in asked()] == [MODELS[1]], [x["model"] for x in asked()])

# the two strong models are out of quota (seen on a real key: the two newest models said "quota" at once, the light one still answered)
reset()
BEHAVE[MODELS[0]] = BEHAVE[MODELS[1]] = "quota-min"
code, body = ask()
check("the two strong models are out of quota: the light model is tried as well, and answers", code == 200 and body == "שלום לכולם", (code, body))
check("...in that order: the two models, then the light one", [x["model"] for x in asked()] == MODELS, [x["model"] for x in asked()])

for mode, what in (("503", "busy"), ("404", "gone (retired)")):
    reset()
    BEHAVE[MODELS[0]] = mode
    code, body = ask()
    check(f"a model that is {what}: the next model answers", code == 200 and body == "שלום לכולם" and asked()[-1]["model"] == MODELS[1], (code, body, [x["model"] for x in asked()]))
    check(f"...and it is tried last from now on", reader.order[-1] == MODELS[0], reader.order)

reset()
for m in MODELS:
    BEHAVE[m] = "503"
code, body = ask()
d = as_json(body)
check("every model busy: said so, and it is not the quota (no other AI is offered for it)",
      code == 400 and d.get("ok") is False and not d.get("quota") and "עמוס" in d.get("error", ""), (code, body))
check("...a live question tried two models, not all three", [x["model"] for x in asked()] == MODELS[:2], [x["model"] for x in asked()])

reset()
BEHAVE[MODELS[0]] = "401"
code, body = ask()
d = as_json(body)
check("a wrong key: said so, and not the quota", code == 400 and not d.get("quota") and "מפתח" in d.get("error", ""), (code, body))
check("...and the other models are not asked (the key is wrong for all of them)", [x["model"] for x in asked()] == [MODELS[0]], [x["model"] for x in asked()])

# ---------------------------------------------------------------------------------- 4. an answer with no words
reset()
BEHAVE[MODELS[0]] = "empty"
course = "קורס בדיקת שאלות"
L.create_course(course)
lecdir = os.path.join(L.course_dir(course), "הרצאה 1")
os.makedirs(lecdir)
with open(os.path.join(lecdir, "הרצאה 1.txt"), "w", encoding="utf-8") as f:
    f.write("[09:01:00 | +0:01:00] שלום לכולם\n")
rel = course + "/הרצאה 1"
qa = os.path.join(lecdir, L.QA_NAME)
code, body = ask("שאלה שנחסמת", f=rel)
check("a blocked answer is not an error: the page gets a line saying why, and nothing is written to the lecture's folder",
      code == 200 and body.strip().startswith("⚠") and "SAFETY" in body and not os.path.exists(qa), (code, body, os.path.exists(qa)))

# ---------------------------------------------------------------------------------- 5. what is kept in the lecture's folder
reset()
code, body = ask("מה זה אינטגרל?", f=rel, at="0:41:02")
kept = open(qa, encoding="utf-8").read() if os.path.isfile(qa) else ""
check("a question and its answer are kept in the lecture's folder", code == 200 and "מה זה אינטגרל?" in kept and "שלום לכולם" in kept and "0:41:02" in kept, kept)
size = len(kept)
BEHAVE[MODELS[0]] = BEHAVE[MODELS[1]] = BEHAVE[MODELS[2]] = "quota-min"
code, body = ask("שאלה שלא תיענה", f=rel)
check("a question that was not answered (the quota) is not kept", code == 429 and len(open(qa, encoding="utf-8").read()) == size, code)
reset()
code, body = ask("סכם", f=rel, task="summary")
summ = os.path.join(lecdir, L.SUMMARY_NAME)
check("a summary of a lecture becomes its summary file", code == 200 and os.path.isfile(summ) and "שלום לכולם" in open(summ, encoding="utf-8").read(), code)

# ---------------------------------------------------------------------------------- 6. no key, or the answers turned off
settings = L.math_settings()
reset()
L.save_settings(math=dict(settings, key=""))
code, body = ask()
check("no key: said so, nothing is sent to Google", code == 400 and "מפתח" in as_json(body).get("error", "") and not asked(), (code, body, len(asked())))
L.save_settings(math=dict(settings, ask=False))
reset()
code, body = ask()
check("answers turned off: nothing is sent to Google", code == 400 and not asked(), (code, body, len(asked())))
L.save_settings(math=settings)

# ---------------------------------------------------------------------------------- 7. the floating window with no lecture
reset()
code, body = post({"where": "mini", "question": "מה אמר?"})
check("the floating window with no lecture running: still answered, and Gemini is told there is no lecture",
      code == 200 and asked() and "אין עכשיו הרצאה פעילה" in user_text(asked()[0]), (code, body))

code, c = post_ctx({"question": "מה אמר?"})
check("copy to another AI with no lecture: the question, and a line saying there is no lecture",
      code == 200 and "אין עכשיו הרצאה פעילה" in c and c.endswith("השאלה שלי: מה אמר?"), (code, c))
check("...it is the same text 'answer here' sends from the floating window", c == user_text(asked()[0]), (c, user_text(asked()[0])))
n_before = len(asked())
post_ctx({"question": "עוד שאלה"})
check("...and copying sends nothing to Gemini", len(asked()) == n_before, (len(asked()), n_before))
req = urllib.request.Request(srv.url + "api/mini_context", method="POST", data=b"{}", headers={"Content-Type": "application/json"})
try:
    urllib.request.urlopen(req, timeout=10)
    refused = False
except urllib.error.HTTPError as e:
    refused = e.code == 403
check("...a request without the page's header is refused (another website cannot read the lecture through it)", refused)

# ---------------------------------------------------------------------------------- 8. a lecture in progress: from sound to answer
SR = 16000
rng = np.random.default_rng(7)


def speech(sec):
    return (rng.normal(0, 0.15, int(sec * SR)).clip(-1, 1) * 32767).astype(np.int16)


class FakeAudio:
    clips, fed = [], threading.Event()

    def __init__(self, q):
        self.q, self.gen, self.sr, self.ch, self.name, self.opened_at = q, 0, SR, 1, "test speakers", 0.0
        self.stop = threading.Event()

    def open(self):
        self.gen += 1
        threading.Thread(target=self._feed, args=(self.gen,), daemon=True).start()

    def _feed(self, gen):
        clip = FakeAudio.clips[0]
        for i in range(0, len(clip), 2048):
            if self.stop.is_set():
                return
            time.sleep(2048 / SR / 10.0)
            self.q.put((gen, time.time(), clip[i:i + 2048].tobytes()))
        FakeAudio.fed.set()

    def alive(self):
        return True

    def close(self):
        self.stop.set()


class NoSpeakers:
    ok = False

    def current(self):
        return None


class NoHotkey:
    def __init__(self, *a, **k):
        pass

    def start(self):
        pass

    def stop(self):
        pass


class FakeWhisper:
    n = 0

    def transcribe(self, audio, **kw):
        FakeWhisper.n += 1

        class Seg:
            pass
        s = Seg()
        s.text, s.start = f"המרצה הסביר משפט מספר {FakeWhisper.n}", 0.0
        return iter([s]), None


L._ensure_packages = lambda *a, **k: None
L.SCREEN_ENABLED = False
L.MEDIA_STATUS = ""
L.AudioInput, L.DefaultSpeakers, L.PauseHotkey = FakeAudio, NoSpeakers, NoHotkey
L.media_status_loop = lambda: None
L.start_quick_draft = lambda slot: None
L.MIN_CHUNK_S, L.MAX_CHUNK_S = 2, 4
L.get_model = lambda lang, stub_av=False: (FakeWhisper(), 1, "fake CPU")
FakeAudio.clips, FakeAudio.fed = [np.concatenate([speech(3.0), speech(3.0), speech(3.0), speech(2.5)])], threading.Event()

live_course = "קורס הרצאה חיה"
L.create_course(live_course)
reset()
sess = app.start("live", "he", L.run_live, "he", live_course, course=live_course)
end = time.time() + 20
while time.time() < end and not (sess.ready and app.live is not None):
    time.sleep(0.05)
FakeAudio.fed.wait(40)
time.sleep(0.5)
words = [x for _, x in app.live.all if "המרצה הסביר" in x]
check("sound becomes words: the transcription is there while the lecture runs", len(words) >= 2, [x for _, x in app.live.all][:4])

code, body = post({"where": "mini", "question": "מה הוא אמר עכשיו?"})
sent = asked()[-1] if asked() else {}
check("from the floating window: the answer comes back", code == 200 and body == "שלום לכולם", (code, body))
check("...Gemini got the words that were just transcribed, and the question",
      "המרצה הסביר משפט מספר 1" in user_text(sent) and "מה הוא אמר עכשיו?" in user_text(sent), user_text(sent)[:300])
live_dir = os.path.dirname(sess.transcript)
qa_live = os.path.join(live_dir, L.QA_NAME)
check("...and the question and answer are kept in the folder of the lecture that is running",
      os.path.isfile(qa_live) and "מה הוא אמר עכשיו?" in open(qa_live, encoding="utf-8").read(), os.listdir(live_dir))

n_asked = len(asked())
code, cx = post_ctx({"question": "מה הוא אמר עכשיו?"})
check("copy to another AI during a lecture: the question WITH the last 5 minutes of the transcript",
      code == 200 and "המרצה הסביר משפט מספר 1" in cx and "5 הדקות האחרונות" in cx and cx.endswith("השאלה שלי: מה הוא אמר עכשיו?"), cx[:300])
check("...the lines Gemini got from the floating window are in the copied text too (the same context)",
      all(l in cx for l in user_text(sent).splitlines() if l.startswith("[") and "המרצה הסביר" in l) and "המרצה הסביר" in user_text(sent), cx[:300])
check("...copying sends nothing to Gemini", len(asked()) == n_asked, (len(asked()), n_asked))
code, cx7 = post_ctx({"question": "ignored", "minutes": 7})
check("'what I missed' (7 minutes) copied: 7 minutes, the ready question, the words",
      code == 200 and "7 הדקות האחרונות" in cx7 and cx7.endswith("השאלה שלי: " + L.missed_question(7)) and "המרצה הסביר משפט מספר 1" in cx7, cx7[:300])
code, cxb = post_ctx({"question": "q", "minutes": "abc"})
check("minutes that are not a number: the usual 5", code == 200 and "5 הדקות האחרונות" in cxb and cxb.endswith("השאלה שלי: q"), cxb[:200])
code, cxm = post_ctx({"question": "q", "minutes": 900})
check("too many minutes: 30 at most", code == 200 and "30 הדקות האחרונות" in cxm, cxm[:200])

del LOG[:]
code, body = post({"where": "mini", "minutes": 7, "question": "ignored"})
check("'what I missed' (7 minutes): the ready question is sent, with the words of those minutes",
      code == 200 and asked() and L.missed_question(7) in user_text(asked()[0]) and "המרצה הסביר משפט מספר 1" in user_text(asked()[0]), (code, user_text(asked()[0])[:300] if asked() else ""))

# the quota is used up in the middle of the lecture: the answer says so, and the lecture goes on being written
for m in MODELS:
    BEHAVE[m] = "quota-min"
reader.cool.clear()
before = len(app.live.all)
code, body = post({"where": "mini", "question": "עוד שאלה"})
d = as_json(body)
check("the quota runs out during a lecture: the floating window is told (429, quota, how long to wait)",
      code == 429 and d.get("quota") is True and 0 < d.get("wait", 0) <= 60, (code, body))
check("...and the lecture is still running", app.session is sess and not sess.done, (app.session is sess, sess.done))
app.command({"action": "stop"})
sess.thread.join(30)
tr = open(sess.transcript, encoding="utf-8").read().splitlines() if os.path.isfile(sess.transcript) else []
check("...and it ends properly, with everything that was said", tr and tr[0].startswith("# תמלול הרצאה") and tr[-1].startswith("# סוף")
      and sum("המרצה הסביר" in x for x in tr) >= len(words), tr[-3:])

srv.stop()
print()
print("all passed" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)

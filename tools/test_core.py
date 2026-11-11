"""The core of Hevanti: the marks (★ / ?) and what the floating window and the settings rely on
(System/Program/live_transcribe.py). No browser needed, any OS:
  python3 tools/test_core.py"""
import json
import os
import sys
import tempfile
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


L.LIB_DIR = os.path.join(TMP, "lib")
os.makedirs(L.LIB_DIR)
C = "חשבון אינפיניטסימלי"
L.create_course(C)

# ---- a recording's marks: kept in סימונים.json in the lecture's folder ----
lec = os.path.join(L.course_dir(C), "הרצאה 1")
os.makedirs(lec)
with open(os.path.join(lec, "הרצאה 1.txt"), "w", encoding="utf-8") as f:
    f.write("[09:01:00 | +0:01:00] שלום לכולם\n[09:02:00 | +0:02:00] היום נדבר על אינטגרלים\n")


class Rec:
    def __init__(self, d, pos):
        self.dir, self.pos, self.lock, self.marks = d, pos, threading.Lock(), None


L.APP = getattr(L, "APP", None) or L.App()
rec = Rec(lec, None)
r = L.mark_recording(rec, "לא הבנתי")
check("a mark before the recording has a place: refused, nothing written", not r["ok"] and L.read_marks(lec) == [], r)
rec.pos = 125.46
r = L.mark_recording(rec, "לא הבנתי")
check("mark: saved with the place (rounded) and the kind", r["ok"] and L.read_marks(lec) == [{"t": 125.5, "kind": "לא הבנתי"}], (r, L.read_marks(lec)))
rec.pos = 300
L.mark_recording(rec, "חשוב")
kinds = [(m["t"], m["kind"]) for m in L.read_marks(lec)]
check("a second mark is added, the first stays", kinds == [(125.5, "לא הבנתי"), (300.0, "חשוב")], kinds)
check("the recording's cache is updated (the player shows it at once)", [m["kind"] for m in rec.marks] == ["לא הבנתי", "חשוב"], rec.marks)
with open(os.path.join(lec, L.MARKS_NAME), "w", encoding="utf-8") as f:
    json.dump({"marks": [{"t": 5, "kind": "חשוב"}, {"kind": "x"}, "junk", {"t": "bad"}]}, f)
check("broken entries in the marks file are ignored", [m["t"] for m in L.read_marks(lec)] == [5], L.read_marks(lec))
check("no marks file: no marks", L.read_marks(os.path.join(TMP, "nowhere")) == [])
with open(os.path.join(lec, L.MARKS_NAME), "w", encoding="utf-8") as f:
    json.dump({"marks": [{"t": 125.5, "kind": "לא הבנתי"}, {"t": 300, "kind": "חשוב"}]}, f)

# ---- a live lecture's marks: a line "[סימון: ...]" in its transcript ----
lec2 = os.path.join(L.course_dir(C), "הרצאה 2")
os.makedirs(lec2)
with open(os.path.join(lec2, "הרצאה 2.txt"), "w", encoding="utf-8") as f:
    f.write("[09:01:00 | +0:01:00] משוואה דיפרנציאלית\n[09:02:00 | +0:02:00] מפרידים משתנים\n"
            "[09:03:00 | +0:03:00] ואז עושים אינטגרציה\n[09:03:30 | +0:03:30] [סימון: לא הבנתי]\n")

marks = L.course_marks(C)
got = sorted((m["title"], m["kind"]) for m in marks)
check("course marks: all three", set(got) == {("הרצאה 1", "לא הבנתי"), ("הרצאה 1", "חשוב"), ("הרצאה 2", "לא הבנתי")} and len(got) == 3, got)
live = [m for m in marks if m["title"] == "הרצאה 2"][0]
first = sorted((m for m in marks if m["title"] == "הרצאה 1"), key=lambda m: m["t"])
check("a mark in a live transcript: what was said just before it", "אינטגרציה" in live["said"] and "מפרידים" in live["said"], live)
check("a mark in a live transcript: its time", live["t"] > 0 and live["c"], live)
check("a recording's mark: the time it was marked at", [m["t"] for m in first] == [125.5, 300], first)
check("course marks: a course without marks, or an unknown one, is empty",
      L.course_marks("קורס אחר") == [], L.course_marks("קורס אחר"))
v = L.transcript_view(first[0]["f"])
notes = [x.get("note") for x in v["lines"] if x.get("note")]
check("the transcript of a recording shows its marks as notes", "סימון: לא הבנתי" in notes and "סימון: חשוב" in notes, notes)

# ---- over HTTP: what the floating window and the app ask ----
srv = L.AppServer()
check("the local server starts", srv.start())
base = srv.url.rstrip("/")


def get(path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return r.status, r.read()


def post(d):
    q = urllib.request.Request(base + "/api/cmd", json.dumps(d).encode(), {"Content-Type": "application/json", "X-BZM": "1"})
    with urllib.request.urlopen(q, timeout=10) as r:
        return json.loads(r.read())


import urllib.parse  # noqa: E402

st, body = get("/api/marks?c=" + urllib.parse.quote(C))
d = json.loads(body)
check("/api/marks returns the course's marks", st == 200 and len(d["marks"]) == 3, d)
check("/api/marks for a missing course: empty, not an error", json.loads(get("/api/marks?c=" + urllib.parse.quote("אין"))[1])["marks"] == [])
st, body = get("/mini")
check("the floating window is served, with the ★ button (no '?') and the question box",
      st == 200 and b"markImp" in body and b"markLost" not in body and b"BZMAsk" in body)
st, body = get("/")
check("the app page has the ★ button and no 'לא הבנתי' button", st == 200 and b'id="markImp"' in body and b'id="markLost"' not in body)
# only ★ is made now: whatever kind an older page sends, a live lecture gets "חשוב"
got_kinds = []


class FakeSession:
    done, ready, kind, mark_fn = False, True, "live", staticmethod(lambda k: got_kinds.append(k))


old_session = L.APP.session
L.APP.session = FakeSession()
r1, r2 = post({"action": "mark", "kind": "lost"}), post({"action": "mark", "kind": "important"})
L.APP.session = old_session
check("a mark of an older page ('lost') is a ★ too, and so is 'important'", got_kinds == ["חשוב", "חשוב"] and r1["ok"] and r2["ok"], (got_kinds, r1, r2))
st, body = get("/ask.js")
check("the ask box script is served", st == 200 and b"setExternal" in body)
app = json.loads(get("/api/app")[1])
check("answers inside Hevanti by default: copying to other AIs is off", app["math"]["external"] is False, app["math"])
mir = json.loads(get("/api/mirror")[1])
check("copying to other AIs is off in the mirror state too", mir["external_ai"] is False, mir)
post({"action": "external_ai", "on": True})
mir = json.loads(get("/api/mirror")[1])
app = json.loads(get("/api/app")[1])
check("the settings can turn them on", mir["external_ai"] is True and app["math"]["external"] is True, (mir, app["math"]))
post({"action": "external_ai", "on": False})
check("...and off again", json.loads(get("/api/app")[1])["math"]["external"] is False)
req = urllib.request.Request(base + "/api/cmd", json.dumps({"action": "external_ai", "on": True}).encode(), {"Content-Type": "application/json"})
try:
    urllib.request.urlopen(req, timeout=10)
    refused = False
except urllib.error.HTTPError as e:
    refused = e.code in (400, 403)
check("the floating window's browser profile is on this computer (LOCALAPPDATA), not in Documents",
      L.mini_profile_dir().startswith(os.environ["LOCALAPPDATA"]) and not L.mini_profile_dir().startswith(L.DATA_DIR))
old = os.path.join(L.DATA_DIR, "mini-profile")
os.makedirs(os.path.join(old, "Default"), exist_ok=True)
open(os.path.join(old, "Default", "Cookies"), "w").close()
held = open(os.path.join(old, "lockfile"), "w")   # its browser is still running
if os.name == "nt":
    check("the old profile in Documents is kept while its browser is running", L.drop_old_mini_profile() is False and os.path.isdir(old))
held.close()
check("...and deleted once it is not", L.drop_old_mini_profile() is True and not os.path.isdir(old))
L.ERROR_LOG = os.path.join(TMP, "error_log.txt")
home = os.path.expanduser("~")
with open(L.ERROR_LOG, "w", encoding="utf-8") as f:
    f.write(f"\n--- 2026-11-05 10:00:00 (גרסה 2.10) yt ---\nOSError: cannot open {home}\\Documents\\x.txt\n")
s0 = L.load_settings().get("math")
L.save_settings(math={"key": "plain:AIzaTOPSECRET123", "on": True})
diag = json.loads(get("/api/diag")[1])
txt = diag["text"]
check("report a problem: the version, the computer and the newest error", L.VERSION in txt and "Windows" in txt and "OSError" in txt, txt[:300])
check("report a problem: never the key", "AIzaTOPSECRET123" not in txt and "plain:" not in txt and "מפתח Gemini: יש" in txt)
check("report a problem: the user's own folder name is hidden", home not in txt and "%USERPROFILE%" in txt, txt[-200:])
check("report a problem: the link opens a new GitHub issue", diag["issues"].endswith("/issues/new"))
L.save_settings(math=s0 or {})
import datetime  # noqa: E402
ln = L.LiveNow("a/b.txt", datetime.datetime.now(), course=C)
ln.add(time.time() - 20, "מה שכבר נכתב")
ln.pending_s = 14.0   # no GPU: 14 s heard, not transcribed yet, and no draft of them
old_live, L.APP.live = L.APP.live, ln
ctx = L.mini_context("מה הוא אמר עכשיו?")
check("no GPU, a question: Gemini is told the last 14 seconds may be missing", "14 השניות האחרונות עוד לא תומלל" in ctx and "מה שכבר נכתב" in ctx, ctx[-300:])
ln.set_draft("המשפט האחרון")   # with a draft (a GPU): it is there, no note
ctx = L.mini_context("מה הוא אמר עכשיו?")
check("...with a draft: the draft, and no note", "ממש עכשיו, עוד לא סופי: המשפט האחרון" in ctx and "עוד לא תומלל" not in ctx, ctx[-300:])
ln.set_draft("")
ln.pending_s = 1.0
check("...nothing missing: no note", ln.missing_note() == "")
L.APP.live = old_live
s1 = L.load_settings().get("math")
check("own instructions: none by default - the answers use only the fixed ones", L.tutor_system() == L.TUTOR_SYSTEM)
check("the answers carry their sources: the time of the transcript line, in brackets, only a time that was sent",
      "מקורות" in L.TUTOR_SYSTEM and "[00:20:44]" in L.TUTOR_SYSTEM and "אל תכתוב שעה שלא מופיעה" in L.TUTOR_SYSTEM and "לפני דקה" in L.TUTOR_SYSTEM)
r = L.math_set({"notes": "  תענה בשורה אחת.\n\nבלי נוסחאות.  "})
check("own instructions: saved (spaces tidied) and shown to the page", r["ok"] and r["math"]["notes"] == "תענה בשורה אחת. בלי נוסחאות.", r.get("math"))
sys_text = L.tutor_body({"question": "מה זה?"})["systemInstruction"]["parts"][0]["text"]
check("own instructions: added after the fixed ones, which stay (including never inventing what was said)",
      sys_text.startswith(L.TUTOR_SYSTEM) and sys_text.endswith("תענה בשורה אחת. בלי נוסחאות.") and "לעולם אל תמציא" in sys_text and "לא מבטלות את הכלל" in sys_text, sys_text[-200:])
check("own instructions: with a task for a whole lecture too", L.tutor_system(True).startswith(L.TUTOR_SYSTEM + L.TUTOR_TASK))
L.math_set({"notes": "א" * 900})
check("own instructions: at most 500 characters", len(L.math_settings()["notes"]) == L.NOTES_MAX == 500)
r = L.math_set({"notes": "   "})
check("own instructions: an empty text removes them", "notes" not in L.math_settings() and r["math"]["notes"] == "" and L.tutor_system() == L.TUTOR_SYSTEM)
L.save_settings(math=s1 or {})
L.set_language("he")
check("transcription model: Hebrew uses the Hebrew-tuned one (no small model: its Hebrew is poor)", "ivrit-ai/whisper-large-v3-turbo-ct2" in L.MODELS[0] and "small" not in L.MODELS, L.MODELS)
L.set_language("en")
check("transcription model: English uses large-v3-turbo", L.MODELS == ["large-v3-turbo"], L.MODELS)
L.set_language("he")
tsv = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n" + \
    "".join(f"5\t1\t1\t1\t1\t{i}\t0\t0\t1\t1\t{c}\tw{i}\n" for i, c in enumerate([96, 92, 90, 20, 30]))
st = L.ocr_stats(tsv)
check("slides: Tesseract's confidences are summed up", st["words"] == 5 and abs(st["mean"] - 65.6) < 0.1 and st["low"] == 0.4, st)
clean = {"words": 40, "mean": 92.0, "low": 0.03}
check("slides: clean printed text is not sent to Gemini", L.slide_needs_ai("Introduction\nThe course covers limits and series", clean, 0.2) is False)
check("slides: a formula is sent", L.slide_needs_ai("f(z) = u + iv\nu_x = v_y", clean, 0.2) is True)
check("slides: handwriting (Tesseract is unsure) is sent", L.slide_needs_ai("x 1 l", {"words": 12, "mean": 48.0, "low": 0.6}, 0.1) is True)
check("slides: a board with almost no text is sent", L.slide_needs_ai("", {"words": 0, "mean": 0.0, "low": 0.0}, 0.05) is True)
check("slides: an empty screen is not sent", L.slide_needs_ai("", {"words": 0, "mean": 0.0, "low": 0.0}, 0.0) is False)
rd = L.MathReader()
rd.order, rd.model = ["gemini-3.6-flash", "gemini-flash-latest", "gemini-flash-lite-latest"], "gemini-3.6-flash"
check("reading goes to the light model first; questions keep the strong one first",
      rd.models_to_try("k", prefer_lite=True)[0] == "gemini-flash-lite-latest" and rd.models_to_try("k")[0] == "gemini-3.6-flash")
L.log_tokens("gemini-flash-lite-latest", {"totalTokenCount": 9}, 10, True, time.time(), kind="read")
L.log_tokens("", None, 0, True, time.time(), kind="skip")
L.log_tokens("gemini-3.6-flash", {"totalTokenCount": 9}, 10, True, time.time())
L.log_tokens("gemini-3.6-flash", None, 10, False, time.time(), True)
L._USAGE["at"] = 0
ut = L.usage_today()
check("today's counts: questions, slides read, slides not sent, quota", ut == {"asks": 1, "reads": 1, "skipped": 1, "failed": 1, "quota": 1}, ut)
# ---- the keyboard shortcuts keep listening: a slow beep (a Bluetooth device) or a slow mark must not stop them ----
gate = threading.Event()
orig_mark, orig_toggle = L.PauseHotkey._mark, L.PauseHotkey._toggle
L.PauseHotkey._mark = lambda self: gate.wait(5)
L.PauseHotkey._toggle = lambda self: gate.wait(5)
t0 = time.time()
hk = L.PauseHotkey()
hk.mark()
hk.toggle()
check("hotkeys: a mark and a pause return at once (they run on their own thread, the message loop keeps listening)", time.time() - t0 < 0.5, time.time() - t0)
gate.set()
L.PauseHotkey._mark, L.PauseHotkey._toggle = orig_mark, orig_toggle
# ---- the count of marks that the small window watches ----
a0 = L.APP.mark_n if getattr(L, "APP", None) is not None else 0
check("a refused mark (nothing is running) does not count", (lambda r: r.get("ok") is False and L.APP.mark_n == a0)(L.APP.mark_moment("important")) if getattr(L, "APP", None) is not None else True)
# ---- a live question does not wait long to find the models ----
seen_timeouts = []
orig_call, orig_models, orig_cands = L.gemini_call, L.gemini_models, L.gemini_candidates
L.gemini_models = lambda key: ["gemini-flash-latest"]
L.gemini_candidates = lambda models: ["gemini-flash-latest", "gemini-flash-lite-latest"]
L.gemini_call = lambda path, key, body, timeout=None, **kw: (seen_timeouts.append(timeout), {"candidates": []})[1]
r1 = L.MathReader()
r1.restore = lambda key: False
try:
    r1.models_to_try("k", quick=True)
    quick_t = list(seen_timeouts)
    del seen_timeouts[:]
    r2 = L.MathReader()
    r2.restore = lambda key: False
    r2.models_to_try("k")
    slow_t = list(seen_timeouts)
finally:
    L.gemini_call, L.gemini_models, L.gemini_candidates = orig_call, orig_models, orig_cands
check("a live question looks for the models for PROBE_LIVE_S at most; other callers for the usual 20 s",
      quick_t and all(x == L.PROBE_LIVE_S for x in quick_t) and slow_t and all(x == 20 for x in slow_t), (quick_t, slow_t))
check("a command without the page's header is refused (another site cannot drive Hevanti)", refused)

print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.exit(1 if fails else 0)
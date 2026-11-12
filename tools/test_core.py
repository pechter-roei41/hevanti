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
_real_mail = L.REPORT_EMAIL
L.REPORT_EMAIL = "support@example.test"   # (made up: the real address is set when Hevanti has one)
diag2 = json.loads(get("/api/diag")[1])
L.REPORT_EMAIL = _real_mail
check("report a problem: the support address comes with it (when there is one), and is not inside the details", diag2.get("mail") == "support@example.test" and "support@example.test" not in diag2["text"] and diag2.get("version") == L.VERSION, diag2.get("mail"))
check("report a problem: the support address of Hevanti is the one in the program, and no personal address", L.REPORT_EMAIL == "hevanti.support@gmail.com" and "pechter" not in L.REPORT_EMAIL.lower() and diag.get("mail") == L.REPORT_EMAIL, (L.REPORT_EMAIL, diag.get("mail")))
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
# ---- the message above the floating button (Windows draws it; the picture and the place are made here, and can be checked anywhere) ----
im, tw_, th_ = L._toast_image("סומן", 1.0, False)
imd, _, _ = L._toast_image("סומן", 1.0, True)
im2, tw2, th2 = L._toast_image("סומן", 2.0, False)
chip = tuple(im.getpixel((tw_ - 17, 22))[:3])   # (inside the chip, to the side of the star)
chip_dark = tuple(imd.getpixel((tw_ - 17, 22))[:3])
check("floating-button message: a card of a sensible size, bigger on a scaled screen", 80 <= tw_ <= 140 and 36 <= th_ <= 50 and tw2 > tw_ * 1.8 and th2 > th_ * 1.8, (tw_, th_, tw2, th2))
check("floating-button message: the chip behind the star is the highlighter colour (light), and a darker one at night", chip == (247, 221, 123)
      and chip_dark == (89, 78, 37), (chip, chip_dark))
check("floating-button message: the corners are see-through (a rounded card)", im.getpixel((0, 0))[3] == 0 and im.getpixel((tw_ // 2, th_ // 2))[3] == 255)
class _Area:
    left, top, right, bottom = 0, 0, 1920, 1040
bx, by = L._mini_btn_xy(_Area, "br", 56, 12)
x1, y1 = L._toast_xy(bx, by, 56, tw_, th_, "br", _Area)
x2, y2 = L._toast_xy(bx, by, 56, tw_, th_, "tr", _Area)
x3, _ = L._toast_xy(0, by, 56, tw_, th_, "bl", _Area)
check("floating-button message: above the button for a bottom corner, below it for a top one, and never off the screen",
      y1 + th_ <= by and y2 >= by + 56 and x1 >= 0 and x1 + tw_ <= 1920 and x3 >= 0, (x1, y1, x2, y2, x3))
# ---- the floating button goes when the lecture is stopped (at once, while the last seconds are still being written) ----
class _FakeSess:
    kind, ready, done = "live", True, False
    def __init__(self):
        self.stop = threading.Event()
old_session = L.APP.session
L.APP.session = fs = _FakeSess()
try:
    L.save_settings(mini_button=True)
    before = L.mini_button_wanted()
    fs.ready = False   # (the model is still loading: the button is already there)
    loading = L.mini_button_wanted()
    fs.ready = True
    fs.stop.set()
    after = L.mini_button_wanted()
finally:
    L.APP.session = old_session
check("floating button: shown the moment a lecture starts (while the model loads too), gone the moment stop is pressed", before is True and loading is True and after is False, (before, loading, after))
L.APP.session = fs2 = _FakeSess()
try:
    fs2.stop.set()
    why_stop = L.mini_button_why()
    L.APP.session = None
    why_none = L.mini_button_why()
finally:
    L.APP.session = old_session
check("floating button: the reason it is hidden can be told (for the black window)", why_stop == "נלחצה עצירה" and why_none == "אין הרצאה", (why_stop, why_none))
# ---- the quick-start window (F1): when it opens instead of the home screen, and its commands ----
_saved_env = dict(os.environ)
os.environ.pop("BZM_NO_BROWSER", None)
os.environ["BZM_QUICK"] = "1"   # (it is Windows only: this lets the decision be checked on any OS)
_gpu = dict(L.GPU)
_sess = L.APP.session
try:
    L.APP.session = None
    L.GPU["state"] = ""
    L.save_settings(consent_ok=False, quick_start=True, math={})
    r0 = L.quick_start_wanted({"kind": "home"})
    L.save_settings(consent_ok=True)
    r1 = L.quick_start_wanted({"kind": "home"})
    L.save_settings(math={"key": L.keep_secret("AIzaQUICKTEST1234")})
    r2 = L.quick_start_wanted({"kind": "home"})
    r3 = L.quick_start_wanted(None)
    r_file = L.quick_start_wanted({"kind": "offer", "source": "x.mp4"})
    r_rec = L.quick_start_wanted({"kind": "home", "view": "rec"})
    L.GPU["state"] = "failed"
    r_gpu = L.quick_start_wanted({"kind": "home"})
    L.GPU["state"] = "installing"
    r_gpu2 = L.quick_start_wanted({"kind": "home"})
    L.GPU["state"] = ""
    L.APP.session = _FakeSess()
    r_run = L.quick_start_wanted({"kind": "home"})
    L.APP.session = None
    L.save_settings(quick_start=False)
    r_off = L.quick_start_wanted({"kind": "home"})
    L.save_settings(quick_start=True)
    os.environ["BZM_NO_BROWSER"] = "1"
    r_nb = L.quick_start_wanted({"kind": "home"})
finally:
    L.APP.session = _sess
    L.GPU.clear(); L.GPU.update(_gpu)
    os.environ.clear(); os.environ.update(_saved_env)
check("quick start: the first start (no agreement yet) is the home screen", r0[0] is False and "first start" in r0[1], r0)
check("quick start: no Gemini key - the home screen", r1[0] is False and "key" in r1[1], r1)
check("quick start: agreed, with a key, nothing running - the quick-start window (also for a second launch with no arguments)", r2 == (True, "") and r3 == (True, ""), (r2, r3))
check("quick start: a file, or the recordings view, was asked for - the home screen", r_file[0] is False and r_rec[0] is False, (r_file, r_rec))
check("quick start: the GPU install failed or is running - the home screen", r_gpu[0] is False and r_gpu2[0] is False, (r_gpu, r_gpu2))
check("quick start: something is running - the home screen", r_run[0] is False and "running" in r_run[1], r_run)
check("quick start: the student turned it off - the home screen", r_off[0] is False and "settings" in r_off[1], r_off)
check("quick start: no browser (a test, a server) - never", r_nb[0] is False, r_nb)
L.save_settings(consent_ok=False, quick_start=True)
L.APP.command({"action": "consent_seen"})
check("quick start: the page tells the tool the student agreed (kept in the settings)", L.load_settings().get("consent_ok") is True)
L.APP.command({"action": "quick_start", "on": False})
check("quick start: the setting is saved and is in what the settings page reads", L.load_settings().get("quick_start") is False and json.loads(get("/api/mirror")[1]).get("quick_start") is False)
L.APP.command({"action": "quick_start", "on": True})
code_q, body_q = get("/quick")
check("quick start: the page is served, with its title (Hevanti first) and the logo for the title bar", code_q == 200 and "<title>הבנתי · חלון התחלה מהירה</title>".encode("utf-8") in body_q and b'rel="icon"' in body_q, code_q)
check("quick start: \"close\" and \"open the app\" are harmless when no window is open (and off Windows)",
      L.APP.command({"action": "quick_close"}).get("ok") is True and L.APP.command({"action": "quick_open_app"}).get("ok") is True)
# ---- a course from the first slide (offered, never applied), and a course chosen while it records ----
import tempfile as _tf
for _c in ("אלגוריתמים", "פיזיקה"):
    L.create_course(_c)


class _Sess2:
    def __init__(self):
        self.stop, self.suggest, self.suggest_off, self.pending_course = threading.Event(), None, False, ""


def _suggestion(slide_text_value, **flags):
    d = _tf.mkdtemp()
    os.makedirs(os.path.join(d, L.SLIDES_NAME))
    open(os.path.join(d, L.SLIDES_NAME, "09-00-00.jpg"), "wb").write(b"x")
    s = _Sess2()
    for k, v in flags.items():
        setattr(s, k, v)
    old = (L.slide_text, L.SUGGEST_POLL_S)
    L.slide_text, L.SUGGEST_POLL_S = (lambda p: slide_text_value), 0.05
    try:
        L.suggest_course_from_slide(s, d, timeout_s=3)
    finally:
        L.slide_text, L.SUGGEST_POLL_S = old
    return s.suggest


sg = _suggestion("אלגוריתמים - הרצאה 3\nסיבוכיות זמן")
check("course from the first slide: a course name on it is offered, with why", sg and sg["course"] == "אלגוריתמים" and sg["why"] == "slide", sg)
check("course from the first slide: a slide with no course name offers nothing", _suggestion("ברוכים הבאים\nמבוא כללי") is None)
check("course from the first slide: nothing is offered after a 'no', or after the student chose", _suggestion("פיזיקה 1", suggest_off=True) is None and _suggestion("פיזיקה 1", pending_course="אלגוריתמים") is None)
check("course from the first slide: two courses on the slide - no guess", _suggestion("אלגוריתמים ופיזיקה") is None)
ls = L.Session("live", "he", "", L.NO_COURSE)
ls.ready = True
_sess_before = L.APP.session
L.APP.session = ls
try:
    r_set = L.APP.command({"action": "set_lecture_course", "course": "פיזיקה"})
    info1, pending1, saved1 = ls.info(), ls.pending_course, L.load_settings().get("course")
    r_same = L.APP.command({"action": "set_lecture_course", "course": L.NO_COURSE})
    info2 = ls.info()
    ls.suggest, ls.suggest_off = {"course": "אלגוריתמים", "why": "slide", "detail": ""}, False
    shown = ls.info()["suggest"]
    r_no = L.APP.command({"action": "suggest_dismiss"})
    hidden = ls.info()["suggest"]
    ls.done = True
    r_done = L.APP.command({"action": "set_lecture_course", "course": "פיזיקה"})
finally:
    L.APP.session = _sess_before
check("course while recording: the chosen course is the one shown, the lecture is marked as moving, and the course is remembered for next time",
      r_set["ok"] and pending1 == "פיזיקה" and info1["course"] == "פיזיקה" and info1["moving"] is True and info1["course_now"] == L.NO_COURSE and saved1 == "פיזיקה", (r_set, info1, saved1))
check("course while recording: choosing the course it is already in cancels the move", r_same["ok"] and info2["moving"] is False and info2["course"] == L.NO_COURSE, info2)
check("course while recording: a course offered is in the session info until the student says no", shown and shown["course"] == "אלגוריתמים" and hidden is None and r_no["ok"], (shown, hidden))
check("course while recording: no lecture running - refused in words", r_done["ok"] is False and "אין עכשיו" in r_done["error"], r_done)
# ---- F3/F4: the quick window's place, its own profile, the saved card, "open the lecture" ----
check("quick window: centred in the work area (also when the area starts away from 0,0)", L._center_xy((0, 0, 1920, 1040), 380, 440) == (770, 300) and L._center_xy((-1920, 0, 0, 1040), 380, 440) == (-1150, 300) and L._center_xy((0, 0, 300, 300), 380, 440) == (0, 0))
check("quick window: its size is small (380 x 400) and it has a browser profile of its own, in the local folder", L.QUICK_SIZE == (380, 400) and os.path.dirname(L.quick_profile_dir()) == L.LOCAL_DIR and L.quick_profile_dir() != L.mini_profile_dir())
im_c, wc_, hc_ = L._toast_image("ההרצאה נשמרה", 1.0, False, "check")
chip_c = tuple(im_c.getpixel((wc_ - 17, 22))[:3])
chip_cd = tuple(L._toast_image("ההרצאה נשמרה", 1.0, True, "check")[0].getpixel((wc_ - 17, 22))[:3])
check("saved card above the floating button: a Green Soft chip (never yellow), light and night, and a card wide enough for the words", chip_c == (220, 235, 223) and chip_cd == (37, 56, 43) and wc_ > 150, (chip_c, chip_cd, wc_))
check("open the lecture: a lecture that is not there is refused in words", L.APP.command({"action": "open_lecture", "f": "אין/כזו"}).get("ok") is False)
_lec = os.path.join(L.course_dir("אלגוריתמים"), "הרצאה לפתיחה")
os.makedirs(_lec, exist_ok=True)
open(os.path.join(_lec, "הרצאה לפתיחה.txt"), "w", encoding="utf-8").write("# x\n")
check("open the lecture: a lecture that is there is accepted (the window itself opens only on Windows)", L.APP.command({"action": "open_lecture", "f": "אלגוריתמים/הרצאה לפתיחה"}).get("ok") is True)
_ss = L.Session("live", "he", "", L.NO_COURSE)
_ss.saved = {"course": "פיזיקה", "minutes": 46, "slides": 9, "f": "פיזיקה/x"}
check("saved: the session info carries what was saved (course, minutes, slides, the lecture)", _ss.info()["saved"] == {"course": "פיזיקה", "minutes": 46, "slides": 9, "f": "פיזיקה/x"} and L.Session("live", "he").info()["saved"] is None)
check("saved: the count the floating button watches is in /api/app", "saved_n" in json.loads(get("/api/app")[1]))
# ---- the floating button: its picture (logo, X, red dot), the animation's curve and shapes, and where the window opens ----
def _near(im, x, y, pred):
    return any(pred(im.getpixel((xx, yy))) for xx in range(x - 1, x + 2) for yy in range(y - 1, y + 2))


_is_green = lambda c: abs(c[0] - 27) < 12 and abs(c[1] - 110) < 12 and abs(c[2] - 75) < 12 and c[3] == 255
_is_yellow = lambda c: c[0] > 225 and c[1] > 185 and c[2] < 120 and c[3] == 255
_is_cream = lambda c: c[0] > 215 and c[1] > 210 and c[2] > 190 and c[3] == 255
_is_white = lambda c: c[0] > 235 and c[1] > 235 and c[2] > 235 and c[3] == 255
_is_red = lambda c: abs(c[0] - 194) < 14 and abs(c[1] - 65) < 14 and abs(c[2] - 45) < 14 and c[3] == 255
b_logo = L._button_image(56, 0.0, False)
b_dot = L._button_image(56, 0.0, True, "right")
b_x = L._button_image(56, 1.0, True, "right")
b_left = L._button_image(56, 0.0, True, "left")
b_mid = L._button_image(56, 0.5, True, "right")
check("floating button: the circle is solid green (1B6E4B) with nothing round it, and the corners are see-through", _is_green(b_logo.getpixel((5, 28))) and _is_green(b_logo.getpixel((50, 28))) and b_logo.getpixel((0, 0))[3] == 0 and b_logo.getpixel((55, 55))[3] == 0 and b_logo.getpixel((28, 0))[3] > 150, [b_logo.getpixel(q) for q in ((5, 28), (0, 0), (28, 0))])
check("floating button: the logo is a thin cream line (no cream disc, no fill) with the yellow check inside", _near(b_logo, 12, 25, _is_cream) and _near(b_logo, 26, 31, _is_yellow) and _is_green(b_logo.getpixel((20, 20))) and not _near(b_logo, 28, 28, _is_cream), [b_logo.getpixel(q) for q in ((12, 25), (26, 31), (20, 20))])
check("floating button: open, the logo is gone and a white X is in its place (no yellow, no cream)", _near(b_x, 28, 28, _is_white) and _near(b_x, 20, 20, _is_white) and _near(b_x, 36, 20, _is_white) and not _near(b_x, 26, 31, _is_yellow) and not _near(b_x, 12, 25, _is_cream), [b_x.getpixel(q) for q in ((28, 28), (20, 20), (36, 20))])
check("floating button: the red dot (C2412D) is at the top, on the side of the screen's edge, and not when nothing is recorded", _near(b_dot, 45, 11, _is_red) and not _near(b_dot, 11, 11, _is_red) and _near(b_left, 11, 11, _is_red) and not _near(b_left, 45, 11, _is_red) and not _near(b_logo, 45, 11, _is_red) and _near(b_x, 45, 11, _is_red))
ring_light, ring_night = L._button_image(56, 0.0, True, "right", False).getpixel((53, 11)), L._button_image(56, 0.0, True, "right", True).getpixel((53, 11))
check("floating button: the ring round the dot is the colour of the page (paper by day, night paper at night)", ring_light[0] > 235 and ring_light[2] > 220 and ring_light[3] > 230 and ring_night[0] < 60 and ring_night[3] > 230, (ring_light, ring_night))
check("floating button: a moment of the turn is neither the logo nor the X", b_mid.tobytes() != b_logo.tobytes() and b_mid.tobytes() != b_x.tobytes())
check("floating button: it is drawn the same at 125% and 150% (a bigger picture, the same shape: green, the dot, the X)", all(_is_green(L._button_image(S_, 0.0, False).getpixel((int(S_ * 5 / 56), S_ // 2))) and _near(L._button_image(S_, 1.0, False), S_ // 2, S_ // 2, _is_white) and _near(L._button_image(S_, 0.0, True, "right"), int(S_ * 0.8), int(S_ * 0.2), _is_red) for S_ in (70, 84)))
check("floating button: the bytes for Windows are premultiplied BGRA, S x S x 4", len(L._button_rgba(56, 0.0, True)) == 56 * 56 * 4 and L._button_rgba(56, 0.0, True)[3] == 0)
ease = [L._bezier_ease(k / 20.0) for k in range(21)]
check("animation: the easing curve cubic-bezier(0.2, 0.8, 0.2, 1) starts at 0, ends at 1, never goes back, and starts fast", ease[0] == 0.0 and ease[-1] == 1.0 and all(b >= a for a, b in zip(ease, ease[1:])) and ease[2] > 0.3 and ease[10] > 0.9, ease)
g0, g1 = L._glyph_params(0.0), L._glyph_params(1.0)
check("animation: the logo turns a quarter, shrinks to 0.6 and fades out while the X turns in, grows from 0.6 to 1 and fades in",
      g0["logo"] == (0.0, 1.0, 1.0) and g0["x"][2] == 0.0 and g1["logo"][2] == 0.0 and g1["logo"][0] == -90.0 and abs(g1["logo"][1] - 0.6) < 1e-9 and g1["x"] == (0.0, 1.0, 1.0) and abs(g0["x"][1] - 0.6) < 1e-9 and g0["x"][0] == 90.0, (g0, g1))
check("animation: the window grows from the point nearest the button - nothing at the start, all of it at the end, always inside the window",
      L._grow_rect(0.0, 380, 460, 190, 460) == (190, 460, 190, 460) and L._grow_rect(1.0, 380, 460, 190, 460) == (0, 0, 380, 460) and L._grow_rect(0.5, 380, 460, 190, 460) == (95, 230, 285, 460)
      and L._grow_rect(0.0, 380, 460, -50, 900) == (0, 460, 0, 460) and all(0 <= v for v in L._grow_rect(0.3, 380, 460, 380, 0)))
AREA = (0, 0, 1920, 1040)
pos = {c: L._mini_xy_above(AREA, c, 56, 12, 380, 460, 8) for c in ("br", "bl", "tr", "tl")}
check("window place: above the button for the two bottom corners, with 8 pixels between (the button stays where it is)", pos["br"] == (1528, 440) and pos["bl"] == (12, 440) and pos["br"][1] + 460 + 8 == 908 == L._mini_btn_xy(type("A", (), {"left": 0, "top": 0, "right": 1920, "bottom": 1040}), "br", 56, 12)[1], pos)
check("window place: below the button for the two top corners, on the same side", pos["tr"] == (1528, 140) and pos["tl"] == (12, 140) and pos["tr"][1] == 76 + 56 + 8, pos)
check("window place: always inside the work area (a low screen, a second screen to the left, 150% scaling)",
      L._mini_xy_above((0, 0, 800, 400), "br", 56, 12, 380, 460, 8)[1] == 0 and L._mini_xy_above((-1920, 0, 0, 1040), "bl", 56, 12, 380, 460, 8)[0] == -1908
      and all(0 <= x <= 1920 - 570 and 0 <= y <= 1040 - 690 for x, y in (L._mini_xy_above(AREA, c, 84, 18, 570, 690, 12) for c in ("br", "bl", "tr", "tl"))))
_before_find = L._find_mini
L._find_mini = lambda u: (_ for _ in ()).throw(AssertionError("the button must not look at the small window to decide to stay"))
L.APP.session = _FakeSess()
try:
    L.save_settings(mini_button=True)
    stays = L.mini_button_wanted()
finally:
    L._find_mini = _before_find
    L.APP.session = _sess_before
check("floating button: it stays while the small window is open (the decision does not look at the window)", stays is True)
_real_anim = L._windows_animations_on
L._windows_animations_on = lambda: True   # (a build machine has Windows animations off: this checks the app's choice alone)
L.save_settings(a11y_still=False)
m_on = L._motion_allowed()
L.APP.command({"action": "a11y_still", "on": True})
m_off = L._motion_allowed()
L.APP.command({"action": "a11y_still", "on": False})
m_back = L._motion_allowed()
L._windows_animations_on = lambda: False
m_win_off = L._motion_allowed()
L._windows_animations_on = _real_anim
check("animation: motion is allowed, unless the student chose no animations and motion in the app (the app tells the tool), or Windows has its animations off",
      m_on is True and m_off is False and m_back is True and m_win_off is False, (m_on, m_off, m_back, m_win_off))
check("a command without the page's header is refused (another site cannot drive Hevanti)", refused)

print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.exit(1 if fails else 0)
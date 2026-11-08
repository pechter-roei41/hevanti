"""A recorded lecture, from the file to the player (System/Program/live_transcribe.py: run_recording, Recording,
transcribe_worker, the player page), with no model: a real WAV file of made-up speech and silence, a made-up Whisper.
It checks that the recording is cut into blocks, that the block you are watching is transcribed first, that silence costs
no call, that the lines come out in order with the right times, what the player is given (the state, the sound), what
the AI is told about where you are, that a finished recording is not transcribed twice, and - with a browser, when there
is one - that the player page shows it. Needs PyAV and faster-whisper (the way recordings are read); about 25 seconds:
  python3 tools/test_recording.py"""
import json
import os
import sys
import tempfile
import time
import urllib.request
import wave

try:
    import av  # noqa: F401
    import numpy as np
    from faster_whisper.audio import decode_audio  # noqa: F401
except ImportError:
    print("skipped: PyAV / faster-whisper not installed")
    sys.exit(1 if os.environ.get("GITHUB_ACTIONS") else 0)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp()
os.environ.update(BZM_DATA_DIR=os.path.join(TMP, "data"), LOCALAPPDATA=os.path.join(TMP, "local"), BZM_NO_BROWSER="1")
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)), flush=True)
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


SR = 16000
rng = np.random.default_rng(2)


def speech(sec):
    return (rng.normal(0, 0.15, int(sec * SR)).clip(-1, 1) * 32767).astype(np.int16)


def silence(sec):
    return np.zeros(int(sec * SR), dtype=np.int16)


# 40 seconds: speech, a short pause, speech, a long silence (a whole block of it), speech
clip = np.concatenate([speech(8), silence(3), speech(8), silence(12), speech(9)])
vids = os.path.join(TMP, "videos")
os.makedirs(vids)
wav = os.path.join(vids, "שיעור בבדיקה.wav")
with wave.open(wav, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(clip.tobytes())
DURATION = len(clip) / SR


class FakeWhisper:
    """Two sentences for every block with speech in it, at 0.5 s and at the middle of the block."""

    def __init__(self):
        self.calls = []

    def transcribe(self, audio, **kw):
        a = np.asarray(audio, dtype=np.float32)
        self.calls.append({"sec": len(a) / SR, "rms": float(np.sqrt(np.mean(a ** 2)))})
        n = len(self.calls)

        class Seg:
            pass
        out = []
        for k, st in enumerate((0.5, len(a) / SR / 2)):
            s = Seg()
            s.text, s.start = f" משפט {n}.{k + 1} ", st
            out.append(s)
        return iter(out), None


model, loads, order = FakeWhisper(), [], []


def get_model(lang, stub_av=False):
    loads.append(lang)
    time.sleep(0.8)   # (the real one takes seconds: the student is already watching)
    return model, 1, "fake CPU"


L.get_model = get_model
L._ensure_packages = lambda *a, **k: None
L.SCREEN_ENABLED = False
L.BLOCK_S = {"cpu": 12, "gpu": 12}
orig_claim = L.Recording.claim_block


def claim(self):
    i = orig_claim(self)
    order.append(i)
    return i


L.Recording.claim_block = claim
app = L.APP if getattr(L, "APP", None) is not None else L.App()
L.APP = app
srv = L.AppServer()
assert srv.start()
base = srv.url.rstrip("/")
app.url = base + "/"
C = "קורס הקלטות"
L.create_course(C)


def get(path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def post(path, d):
    q = urllib.request.Request(base + path, json.dumps(d).encode(), {"Content-Type": "application/json", "X-BZM": "1"})
    with urllib.request.urlopen(q, timeout=10) as r:
        return r.status


def wait(cond, secs=60):
    end = time.time() + secs
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False


# ---------------------------------------------------------------------------------------- the first time: a transcript
s = app.start("rec", "he", L.run_recording, wav, "he", C, title="שיעור בבדיקה", course=C)
check("the recording opens", wait(lambda: app.rec is not None and s.ready, 20), s.error)
rec = app.rec
check("it is as long as the file", abs(rec.duration - DURATION) < 1.0, (rec.duration, DURATION))
rec.set_place({"pos": 36.0, "paused": False})   # the student is already watching the end: that block goes first
check("it is done", wait(lambda: rec.complete() and rec.phase == "done", 60), (rec.phase, rec.progress(), rec.error))
blocks = rec.blocks
check("it is cut into blocks (each in a quiet moment)", len(blocks) >= 3 and abs(blocks[-1][1] - DURATION) < 1.5 and all(a[1] == b[0] for a, b in zip(blocks, blocks[1:])), blocks)
last = len(blocks) - 1
check("the part being watched is transcribed first", order and order[0] == last, (order, blocks))
check("a block of silence costs no call", all(c["rms"] > L.SILENCE_RMS for c in model.calls) and len(model.calls) < len(blocks), (len(model.calls), len(blocks), [round(c['rms'], 4) for c in model.calls]))
items = [(t, v) for t, k, v in rec.items() if k == "say"]
check("the lines are in order, inside the recording", [t for t, _ in items] == sorted(t for t, _ in items) and all(0 <= t <= DURATION for t, _ in items), items)
check("two lines for every block with speech", len(items) == 2 * len(model.calls), (len(items), len(model.calls)))
check("the transcript file: the lines with their times, and the end", os.path.isfile(rec.out_path) and L.transcript_done(rec.out_path), rec.out_path)
says, shots = L.read_transcript(rec.out_path)
check("...it reads back the same lines", [x for _, x in says] == [v for _, v in items] and all(abs(a[0] - b[0]) <= 1 for a, b in zip(says, items)), (says[:2], items[:2]))
check("the course holds it", os.path.dirname(rec.out_path).startswith(L.course_dir(C)), rec.out_path)

# ---------------------------------------------------------------------------------------- what the player and the AI get
st = json.loads(get("/api/state?rev=-1")[2])
check("the player's state: title, length, all lines, done", st["title"] == rec.stem and abs(st["duration"] - DURATION) < 1 and st["complete"]
      and len(st["lines"]) == len(items) and st["phase"] == "done", {k: st[k] for k in ("title", "duration", "complete", "phase")})
check("...the green parts of the bar cover the whole recording", st["ready"] and abs(st["ready"][-1][1] - DURATION) < 1.5, st["ready"])
check("...nothing is sent again when nothing changed", "lines" not in json.loads(get("/api/state?rev=%d" % st["rev"])[2]))
code, ctype, body = get("/media")
check("the player gets the sound (the file itself)", code == 200 and ctype.startswith("audio/") and body == open(wav, "rb").read(), (code, ctype, len(body)))
check("the player reports where it is: the server knows", post("/api/place", {"pos": 20.0, "paused": False}) == 204 and rec.pos == 20.0 and rec.playing)
now = rec.now_text(app.url + "player")
near = [v for t, v in items if 20 - L.NOW_BEFORE_S <= t <= 20.5]
check("the AI is told where the student is, and what was said around it", "מתוך" in now and near and all(v in now for v in near[-2:]), now[:400])
check("...and that the recording is the one being watched", rec.stem in now and "צפייה בהקלטה" in now, now[:200])

# ------------------------------------------------------------------------------------------------ stopping, opening again
app.command({"action": "stop"})
s.thread.join(30)
check("stopped: the last place is kept", rec.closed and os.path.isfile(rec.out_path))
before = len(model.calls)
s2 = app.start("rec", "he", L.run_recording, wav, "he", C, title="שיעור בבדיקה", course=C)
check("the same recording again: it opens", wait(lambda: app.rec is not None and app.rec is not rec and s2.ready, 20), s2.error)
rec2 = app.rec
check("...it is already transcribed: nothing is transcribed twice", rec2.complete() and len(model.calls) == before and len(loads) == 1, (before, len(model.calls), loads))
items2 = [(t, v) for t, k, v in rec2.items() if k == "say"]
check("...with the same lines (the file keeps the time to the second)", [v for _, v in items2] == [v for _, v in items]
      and all(abs(a[0] - b[0]) <= 1 for a, b in zip(items2, items)), (items2[:2], items[:2]))

# ------------------------------------------------------------------------------------------------- the player page
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
if sync_playwright:
    with sync_playwright() as p:
        b = None
        for kw in ({"channel": "msedge"}, {"channel": "chrome"}, {}):
            try:
                b = p.chromium.launch(headless=True, **kw)
                break
            except Exception:
                continue
        if b is None:
            print("SKIP the player page: no browser for Playwright")
        else:
            pg = b.new_context(viewport={"width": 1100, "height": 900}, locale="he-IL").new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(base + "/player")
            pg.wait_for_function("document.querySelectorAll('#lines li:not(.empty)').length > 0", timeout=15000)
            n = pg.evaluate("document.querySelectorAll('#lines li:not(.empty)').length")
            check("the player page: every line of the transcript is there", n >= len(items), (n, len(items)))
            check("...with the recording's name", pg.evaluate("document.querySelector('#title').textContent").strip() == rec2.stem)
            first = items[0][1]
            pg.fill("#find", first)
            pg.wait_for_timeout(500)
            shown = pg.evaluate("[...document.querySelectorAll('#lines li:not(.empty)')].filter(x => x.offsetParent !== null).length")
            check("...a search shows only the lines with the word", 1 <= shown < n, (shown, n))
            check("...no script errors", errs == [], errs)
            b.close()

print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.stdout.flush()
os._exit(1 if fails else 0)

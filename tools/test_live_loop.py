"""The live lecture loop (System/Program/live_transcribe.py, run_live) with no model, no sound card and no GPU: a made-up
speaker plays made-up speech (noise and silence, 10x faster than real time) into Hevanti, and a made-up Whisper answers.
It checks what the student relies on during a lecture: what is cut where, what is written and what is not, the last
seconds when stopping, the audio device that disconnects, the transcript that falls behind, and the GPU's drafts and
catching up. Any OS, about 40 seconds:
  python3 tools/test_live_loop.py"""
import os
import re
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.update(BZM_DATA_DIR=tempfile.mkdtemp(), LOCALAPPDATA=tempfile.mkdtemp(), BZM_NO_BROWSER="1")
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import numpy as np  # noqa: E402
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)), flush=True)
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


SR = 16000
SPEED = 10.0                     # the made-up speaker plays this many times faster than real time
rng = np.random.default_rng(1)


def speech(sec):
    return (rng.normal(0, 0.15, int(sec * SR)).clip(-1, 1) * 32767).astype(np.int16)


def silence(sec):
    return np.zeros(int(sec * SR), dtype=np.int16)


class FakeAudio:
    """The speakers, as Hevanti hears them: a clip, then the next one after a reconnect."""
    instances = []

    def __init__(self, q):
        self.q, self.gen, self.sr, self.ch, self.name, self.opened_at = q, 0, SR, 1, "test speakers", 0.0
        self.dead, self.opens, self.stop = False, 0, threading.Event()
        FakeAudio.instances.append(self)

    def open(self):
        self.gen += 1
        self.opens += 1
        self.dead = False
        clips = FakeAudio.clips
        if self.opens <= len(clips):
            threading.Thread(target=self._feed, args=(self.gen, clips[self.opens - 1]), daemon=True).start()

    def _feed(self, gen, clip):
        step = 2048
        for i in range(0, len(clip), step):
            if self.stop.is_set():
                return
            if FakeAudio.speed:
                time.sleep(step / SR / FakeAudio.speed)
            self.q.put((gen, time.time(), clip[i:i + step].tobytes()))
        FakeAudio.fed.set()

    def alive(self):
        return not self.dead

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
    """faster-whisper's WhisperModel as far as Hevanti uses it. delay: seconds per call. junk: calls that answer with
    a sound and no words (what the real model writes where there was no speech)."""

    def __init__(self, delay=0.0, junk=()):
        self.calls, self.delay, self.junk, self.n = [], delay, set(junk), 0

    def transcribe(self, audio, **kw):
        a = np.asarray(audio, dtype=np.float32)
        beam = kw.get("beam_size")
        time.sleep(self.delay)
        self.n += 1
        text = "♪ ♪" if (self.n - 1) in self.junk else f"שורה {self.n}"
        self.calls.append({"sec": len(a) / SR, "rms": float(np.sqrt(np.mean(a ** 2))), "tail": float(np.sqrt(np.mean(a[-int(0.1 * SR):] ** 2))),
                           "beam": beam, "text": text})

        class Seg:
            pass
        s = Seg()
        s.text, s.start = text, 0.0
        return iter([s]), None


L._ensure_packages = lambda *a, **k: None
L.SCREEN_ENABLED = False
L.MEDIA_STATUS = ""
L.AudioInput, L.DefaultSpeakers, L.PauseHotkey = FakeAudio, NoSpeakers, NoHotkey
L.media_status_loop = lambda: None
L.start_quick_draft = lambda slot: None   # (the Zipformer has its own test: no download and no pip here)
L.MIN_CHUNK_S, L.MAX_CHUNK_S, L.GPU_MIN_CHUNK_S, L.GPU_MAX_CHUNK_S = 2, 4, 3, 5
logged = []
real_log = L.log
L.log = lambda msg: (logged.append(str(msg)), real_log(msg))[0]
app = L.APP if getattr(L, "APP", None) is not None else L.App()
L.APP = app


def lines_of(path):
    with open(path, encoding="utf-8") as f:
        return [x.rstrip("\n") for x in f]


def run(name, clips, model, gpu=False, speed=SPEED, during=None, wait_s=40):
    """One lecture: play the clips, call during(live, audio) while it runs, stop, and return what was written."""
    FakeAudio.clips, FakeAudio.speed, FakeAudio.fed, FakeAudio.instances = clips, speed, threading.Event(), []
    del logged[:]
    L.get_model = lambda lang, stub_av=False: (model, 5 if gpu else 1, "fake GPU" if gpu else "fake CPU")
    course = "בדיקה " + name
    L.create_course(course)
    s = app.start("live", "he", L.run_live, "he", course, course=course)
    end = time.time() + 20
    while time.time() < end and not (s.ready and app.live is not None):
        time.sleep(0.05)
    live, audio = app.live, FakeAudio.instances[0]
    FakeAudio.fed.wait(wait_s)
    if during:
        during(live, audio)
    time.sleep(0.5)
    app.command({"action": "stop"})
    s.thread.join(30)
    return live, audio, lines_of(s.transcript) if s.transcript and os.path.isfile(s.transcript) else []


def spoken(lines):
    """The lines of words (not the header, the notes in [...] or the end)."""
    return [x for x in lines if x.startswith("[") and "] " in x and not x.split("] ", 1)[1].startswith("[")]


# ---------------------------------------------------------------------------------------------- A: the normal lecture
clipA = np.concatenate([speech(3.0), silence(0.5), speech(3.0), silence(0.5), silence(5.0), speech(3.0), silence(0.5), speech(2.2)])
wA = FakeWhisper(junk={1})
live, audio, tr = run("רגיל", [clipA], wA)
words = spoken(tr)
check("a lecture: a header, the words with their times, and the end", tr and tr[0].startswith("# תמלול הרצאה") and tr[-1].startswith("# סוף") and words, tr[:3])
check("the words carry a time of day and the time since the start", all(re.match(r"\[\d\d:\d\d:\d\d \| \+\d+:\d\d:\d\d\] שורה \d+$", x) for x in words), words[:3])
check("no piece of silence is sent to the model (it would only invent words)", wA.calls and all(c["rms"] > L.SILENCE_RMS for c in wA.calls), [c["rms"] for c in wA.calls])
check("5 seconds of silence cost no call", sum(c["sec"] for c in wA.calls) < len(clipA) / SR - 3, (sum(c["sec"] for c in wA.calls), len(clipA) / SR))
check("a piece is cut in a pause, not in the middle of a word", all(c["tail"] < 0.002 for c in wA.calls[:2]), [round(c["tail"], 4) for c in wA.calls])
check("a piece with sounds and no words (♪) is not written", len(words) == len(wA.calls) - 1 and all("♪" not in x for x in tr), (len(words), len(wA.calls)))
check("the last seconds are transcribed when stopping", wA.calls[-1]["sec"] > 1.5 and words and words[-1].endswith("שורה %d" % wA.n), (wA.calls[-1], words[-1:]))
check("what was said is kept for the questions (live.all)", len(live.all) >= len(words), (len(live.all), len(words)))

# ------------------------------------------------------------------------ B: stopping before the first piece is full
wB = FakeWhisper()
live, audio, tr = run("קצר", [speech(2.5)], wB)
check("stopped before a piece was full: what was heard is still written", len(spoken(tr)) == 1 and tr[-1].startswith("# סוף"), tr)

# ------------------------------------------------------------------------------------- C: the device disconnects
wC = FakeWhisper()


def disconnect(live, audio):
    audio.dead = True    # the headphones are unplugged: the loop notices after a few seconds and opens the device again
    end = time.time() + 12
    while time.time() < end and audio.opens < 2:
        time.sleep(0.1)
    FakeAudio.fed.clear()
    FakeAudio.fed.wait(15)


live, audio, tr = run("התנתקות", [speech(3.0), speech(3.0)], wC, during=disconnect, wait_s=20)
check("the device disconnects: Hevanti opens it again by itself", audio.opens == 2 and audio.gen == 2, (audio.opens, audio.gen))
check("...and says so in the transcript (a note, not a word)", any("התחברות מחדש" in x for x in tr), tr[-4:])
check("...and the lecture goes on from the new device", len(spoken(tr)) >= 2 and "# סוף" in tr[-1], tr)
check("...and tells the student", any("התחברתי מחדש" in x or "התקן השמע" in x for x in logged), logged[-4:])

# ----------------------------------------------------------------------------------------- D: the transcript falls behind
L.LAG_WARN_S = 1
wD = FakeWhisper(delay=1.2)
live, audio, tr = run("פיגור", [np.concatenate([speech(2.8), silence(0.4)] * 4)], wD, speed=20)
check("on the CPU, behind by more than the limit: a warning, and what to do", any("התמלול מאחר" in x and "המעבד" in x for x in logged), logged[-5:])
check("...and nothing is lost: the lecture is still transcribed to the end", len(spoken(tr)) >= 3 and tr[-1].startswith("# סוף"), tr)
L.LAG_WARN_S = 30

# ------------------------------------------------------------------------------- E: the GPU - drafts, and catching up
L.FAST_ON_LAG_S = 1
batches = []
L.transcribe_batch = lambda model, beam, audio16, prev: (batches.append(len(audio16) / SR), [(0.0, "קטע מהשלמת פיגור")])[1]
wE = FakeWhisper(delay=0.8)
drafts = []


def watch(live, audio):
    pass


FakeAudio.speed = 0
clipsE = [np.concatenate([speech(2.8), silence(0.4)] * 10)]     # 32 seconds, all in the queue at once: far behind
live, audio, tr = run("כרטיס מסך", clipsE, wE, gpu=True, speed=0)
check("on a GPU, far behind: everything that waited is transcribed in one go", batches and max(batches) > 5, batches)
check("...and its words are written", any("קטע מהשלמת פיגור" in x for x in tr), tr[-4:])
check("...and the transcript ends", tr and tr[-1].startswith("# סוף"))
L.FAST_ON_LAG_S = 10

# the draft of what is being said (GPU, nothing behind)
wF = FakeWhisper(delay=0.01)
seen = []


def poll(live, audio):
    pass


FakeAudio.clips, FakeAudio.speed, FakeAudio.fed, FakeAudio.instances = [speech(9.0)], 3, threading.Event(), []
del logged[:]
L.get_model = lambda lang, stub_av=False: (wF, 5, "fake GPU")
L.create_course("בדיקה טיוטה")
sF = app.start("live", "he", L.run_live, "he", "בדיקה טיוטה", course="בדיקה טיוטה")
end = time.time() + 20
while time.time() < end and not (sF.ready and app.live is not None):
    time.sleep(0.05)
liveF = app.live
end = time.time() + 15
while time.time() < end and not FakeAudio.fed.is_set():
    if liveF.draft:
        seen.append(liveF.draft)
    time.sleep(0.03)
app.command({"action": "stop"})
sF.thread.join(30)
check("on a GPU: a draft of what is being said while it is still being said", bool(seen), seen[:2])
check("...made with the fast setting, not the slow one", any(c["beam"] == 1 for c in wF.calls), [c["beam"] for c in wF.calls][:6])

print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.stdout.flush()
os._exit(1 if fails else 0)

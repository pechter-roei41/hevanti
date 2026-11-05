"""A question in the middle of a live lecture on a computer with no GPU (System/Program/live_transcribe.py): the
last seconds, heard but not transcribed yet (the transcript is written in pieces of 10-18 s), are transcribed when the
question is asked, and go into what Gemini gets. Uses the real Hebrew model on the CPU and a real lecture recording,
played into Hevanti as if from the speakers. Windows or Linux, needs the model already downloaded; slow (about a minute):
  python tools/test_live_tail.py path\\to\\clip.wav      (16 kHz mono, Hebrew speech, 40 s or more)"""
import glob
import os
import sys
import tempfile
import threading
import time
import wave

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp()
os.environ.update(BZM_DATA_DIR=os.path.join(TMP, "data"), LOCALAPPDATA=os.path.join(TMP, "local"), BZM_NO_BROWSER="1")
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import numpy as np  # noqa: E402
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)), flush=True)
    if not ok:
        fails.append(name)


if len(sys.argv) < 2 or not os.path.isfile(sys.argv[1]):
    print("SKIP no clip given")
    sys.exit(0)
snap = glob.glob(os.path.join(L.MODEL_DIR, "models--ivrit-ai--whisper-large-v3-turbo-ct2", "snapshots", "*"))
if not snap:
    print("SKIP the Hebrew model is not downloaded")
    sys.exit(0)
w = wave.open(sys.argv[1])
SOUND = w.readframes(w.getnframes())
SR = w.getframerate()


def cpu_model(lang, stub_av=False):
    from faster_whisper import WhisperModel
    L.set_language(lang)
    return WhisperModel(snap[0], device="cpu", compute_type="int8", cpu_threads=int(os.environ.get("TAIL_THREADS") or os.cpu_count())), 1, "ivrit-ai / CPU"


class FakeAudio:
    """The speakers, as Hevanti hears them: the clip, in real time."""

    def __init__(self, q):
        self.q, self.gen, self.sr, self.ch, self.name = q, 0, SR, 1, "test speakers"
        self.stop = threading.Event()

    def open(self):
        self.gen += 1
        gen, step = self.gen, 2048 * 2

        def feed():
            t0 = time.time()
            for i in range(0, len(SOUND), step):
                due = t0 + (i // 2) / SR
                time.sleep(max(0.0, due - time.time()))
                if self.stop.is_set():
                    return
                self.q.put((gen, time.time(), SOUND[i:i + step]))
        threading.Thread(target=feed, daemon=True).start()

    def alive(self):
        return True

    def close(self):
        self.stop.set()


L.get_model = cpu_model
L.AudioInput = FakeAudio
L._ensure_packages = lambda *a, **k: None
L.SCREEN_ENABLED = False
L.MEDIA_STATUS = ""
app = L.APP if getattr(L, "APP", None) is not None else L.App()
L.APP = app
C = "בדיקה"
L.create_course(C)
s = app.start("live", "he", L.run_live, "he", C, course=C)
end = time.time() + 120
while time.time() < end and not (s.ready and app.live is not None):
    time.sleep(0.2)
check("the lecture starts on the CPU", app.live is not None and app.live.tail_fn is not None)
time.sleep(32)   # 32 s of the clip: one or two pieces are written, and 5-18 s wait for the next one
live = app.live
with live.lock:
    written = " ".join(x for _, x in live.all)
pending = live.pending_s
t = time.time()
tail = live.fresh_tail()
took = time.time() - t
print(f"  written so far: {written[-160:]}\n  waiting: {pending:.1f} s\n  the last seconds, now: {tail}\n  took {took:.1f} s")
ctx = L.mini_context("מה הוא אמר עכשיו?")
print(f"  load: {live.load:.2f} s of work per second")
if tail:
    check("asked mid-lecture: the last seconds are transcribed (within the limit)", took < 20, took)
    check("...and they are not what was already written", tail[:20] not in written, (tail[:40], written[-80:]))
    check("...and Gemini gets them", f"ממש עכשיו, עוד לא סופי: {tail}" in ctx, ctx[-400:])
else:   # a computer too slow for it: no waiting, and Gemini is told the last seconds may be missing
    check("too slow here: the question does not wait", took < 2 and live.tail_slow, (took, live.tail_slow))
    check("...and Gemini is told the last seconds may be missing", "עוד לא תומלל" in ctx, ctx[-400:])
app.command({"action": "stop"})
s.thread.join(60)
print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.stdout.flush()
os._exit(1 if fails else 0)

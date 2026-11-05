"""The quick draft without a GPU (System/Program/live_transcribe.py, 2.11): during a live Hebrew lecture on the CPU,
ivrit.ai's streaming Zipformer drafts what is being said, so a question in the floating window ("what did he just
say?") has the last seconds at once. Uses the real Hebrew Whisper model on the CPU and a real lecture recording, played
into Hevanti as if from the speakers (48 kHz stereo, like real speakers). Needs the Whisper model already downloaded;
downloads the Zipformer (70 MB) and installs sherpa-onnx if missing; slow (about two minutes):
  python tools/test_quick_draft.py path\\to\\clip.wav      (16 kHz mono, Hebrew speech, 60 s or more)"""
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
mono = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
SR = 48000
SOUND = np.repeat(np.repeat(mono, 3)[:, None], 2, axis=1).astype(np.int16).tobytes()   # 48 kHz stereo
ZDIR = os.path.join(TMP, "zipformer-he")
L.zip_dir = lambda: ZDIR   # (not the student's models folder)


def cpu_model(lang, stub_av=False):
    from faster_whisper import WhisperModel
    L.set_language(lang)
    return WhisperModel(snap[0], device="cpu", compute_type="int8", cpu_threads=os.cpu_count()), 1, "ivrit-ai / CPU"


class FakeAudio:
    """The speakers, as Hevanti hears them: the clip, in real time."""

    def __init__(self, q):
        self.q, self.gen, self.sr, self.ch, self.name = q, 0, SR, 2, "test speakers"
        self.stop = threading.Event()

    def open(self):
        self.gen += 1
        gen, step = self.gen, 2048 * 4

        def feed():
            t0 = time.time()
            for i in range(0, len(SOUND), step):
                time.sleep(max(0.0, t0 + (i // 4) / SR - time.time()))
                if self.stop.is_set():
                    return
                self.q.put((gen, time.time(), SOUND[i:i + step]))
        threading.Thread(target=feed, daemon=True).start()

    def alive(self):
        return True

    def close(self):
        self.stop.set()


# the package and the model, as the app gets them the first time
L._ensure_packages([("sherpa_onnx", "sherpa-onnx")], "לטיוטה מהירה")
check("the quick draft's model downloads (the fixed version)", L.zip_download() and L.zip_ready()
      and all(os.path.getsize(os.path.join(ZDIR, f)) > 0 for f in L.ZIP_FILES))

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
while time.time() < end and not (s.ready and app.live is not None and app.live.quick_on):
    time.sleep(0.2)
live = app.live
check("a live lecture on the CPU: the quick draft runs", live is not None and live.quick_on)
t_start = time.time()
seen, lags = [], []
clip_s = len(mono) / 16000
for at in range(12, int(clip_s) - 2, 6):   # a question every 6 s
    time.sleep(max(0.0, t_start + at - time.time()))
    with live.lock:
        written, draft = " ".join(x for _, x in live.all), live.draft
    ctx = L.mini_context("מה הוא אמר עכשיו?")
    seen.append(bool(draft))
    lags.append(live.lag)
    print(f"  second {at}: waiting {live.pending_s:4.1f} s, transcript lag {live.lag:4.1f} s, draft: {draft[-70:]}")
    if draft:
        check(f"second {at}: the draft goes to Gemini at once, and no 'missing' note",
              f"ממש עכשיו, עוד לא סופי: {draft}" in ctx and "עוד לא תומלל" not in ctx, ctx[-300:])
check("a draft was there for most questions", sum(seen) >= len(seen) * 0.7, seen)
check("the transcript keeps up (Whisper is not slowed down)", max(lags) < 15, lags)
with live.lock:
    written = " ".join(x for _, x in live.all)
check("the transcript itself is still written (by Whisper)", len(written.split()) > 50, written[-200:])
app.command({"action": "stop"})
s.thread.join(60)
print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.stdout.flush()
os._exit(1 if fails else 0)

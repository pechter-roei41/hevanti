"""Slides and questions (System/Program/live_transcribe.py): a slide is kept only when it is STABLE (SlideJudge for a live
lecture, VideoSlides for a recording), a picture is taken when a question begins, and "what I missed" sends the last 3, 7
or 15 minutes. No screen, no model: made-up pictures, a made-up video. Needs numpy; the video part needs PyAV
(skipped without it, a failure on CI). About 10 seconds:
  python3 tools/test_slides.py"""
import datetime
import os
import sys
import tempfile
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


rng = np.random.default_rng(3)


def slide():
    return rng.integers(0, 256, (60, 100)).astype(np.int16)


# ---------------------------------------------------------------------------------------------- a live lecture: stable
A, B, C = slide(), slide(), slide()
j = L.SlideJudge()
t = [0.0]


def look(img):
    t[0] += 3
    return j.look(img.copy(), t[0])


check("the first look is kept", look(A) == ["cur"])
check("the same slide again: nothing", [look(A), look(A), look(A)] == [[], [], []])
outs = [look(B), look(B), look(B)]
check("a new slide is saved only when it is stable (not at once, not after one calm look)", outs == [[], [], ["cur"]], outs)
j2, t[0] = L.SlideJudge(), 0.0
j = j2
look(A)
look(A)
outs = [look(B), look(C), look(C), look(C)]
check("a slide that is gone before it settled is never saved - the next one is, when it is stable", outs == [[], [], [], ["cur"]]
      and np.array_equal(j.saved, C), outs)
j, t[0] = L.SlideJudge(), 0.0
look(A)
look(A)
outs = [look(B), look(B), look(C), look(C), look(C)]
check("a slide shown for two looks only (about 6 s) is not kept", outs[:3] == [[], [], []] and outs[-1] == ["cur"] and np.array_equal(j.saved, C), outs)
check("the stable-looks rule is the documented one (2 looks of 3 s)", L.SlideJudge.STABLE == 2 and L.SCREEN_CHECK_S == 3)

# ---------------------------------------------------------------------------------------------- a picture when a question begins
j, t[0] = L.SlideJudge(), 0.0
look(A)
look(A)
check("a question begins on the slide that is already saved: no second picture", j.snapshot(A.copy(), 20.0) is False)
check("it begins on something that is not saved yet (not stable): a picture of it", j.snapshot(B.copy(), 21.0) is True and np.array_equal(j.saved, B))
check("...and the same moment is not saved twice", j.snapshot(B.copy(), 22.0) is False and j.look(B.copy(), 24.0) == [])
check("a snapshot before any look (a fresh judge) is taken", L.SlideJudge().snapshot(A.copy(), 1.0) is True)

# the watcher: the request wakes the loop at once, and the server asks for one picture per question
w = L.ScreenWatcher(tempfile.mkdtemp(), "course/lecture", time.time(), lambda x: None)
w.request_snapshot()
t0 = time.time()
w._idle()
check("a snapshot request wakes the screen loop at once (not after the 3 s)", time.time() - t0 < 1.0 and w.snap_at > 0, time.time() - t0)
t0 = time.time()
w._idle()
check("...and without a request it waits for the next look", time.time() - t0 >= L.SCREEN_CHECK_S - 0.5, time.time() - t0)
w.stop()

app = getattr(L, "APP", None) or L.App()
L.APP = app


class Sess:
    done, kind = False, "live"

    def __init__(self, watcher):
        self.watcher = watcher


w2 = L.ScreenWatcher(tempfile.mkdtemp(), "course/lecture", time.time(), lambda x: None)
app.session = Sess(w2)
r1 = app.command({"action": "snap_question"})
r2 = app.command({"action": "snap_question"})
check("snap_question: the first key asks for a picture, the next ones (the same question) do not",
      r1 == {"ok": True} and r2.get("skipped") and w2.snap_at > 0, (r1, r2))
w2.snap_at = w2.snap_asked = 0.0
app.session = Sess(L.ScreenWatcher(tempfile.mkdtemp(), "c/l", time.time(), lambda x: None, region_fn=lambda: None))
check("snap_question: a YouTube video (its own way of taking pictures): nothing", app.command({"action": "snap_question"}) == {"ok": False})
app.session = None
check("snap_question: no lecture: nothing, no error", app.command({"action": "snap_question"}) == {"ok": False})
s_done = Sess(w2)
s_done.done = True
app.session = s_done
check("snap_question: a lecture that ended: nothing", app.command({"action": "snap_question"}) == {"ok": False})
app.session = None

# ---------------------------------------------------------------------------------------------- "what I missed": 3 / 7 / 15 minutes
now = time.time()
live = L.LiveNow("c/l.txt", datetime.datetime.now(), course="קורס")
live.all = [(now - 1000, "שורה ישנה מאוד"), (now - 600, "לפני עשר דקות"), (now - 400, "לפני שבע דקות בערך"),
            (now - 100, "לפני כמעט שתי דקות"), (now - 10, "ממש עכשיו")]
app.live, app.rec = live, None
c3, c5, c7, c15 = (L.mini_context("שאלה", m) for m in (3, 5, 7, 15))
check("3 minutes: only the last ones", "ממש עכשיו" in c3 and "כמעט שתי דקות" in c3 and "שבע דקות" not in c3 and "3 הדקות האחרונות" in c3, c3[:300])
check("5 minutes (the usual question): as before", "שבע דקות" not in c5 and "5 הדקות האחרונות" in c5 and "כמעט שתי דקות" in c5)
check("7 minutes", "שבע דקות" in c7 and "לפני עשר דקות" not in c7 and "7 הדקות האחרונות" in c7)
check("15 minutes: back to ten minutes ago, not to the start", "לפני עשר דקות" in c15 and "שורה ישנה מאוד" not in c15 and "15 הדקות האחרונות" in c15)
check("the default is 5 minutes", L.mini_context("שאלה") == c5)
q7 = L.missed_question(7)
check("the ready question names the minutes and asks for a summary", "7 הדקות" in q7 and "תסכם" in q7 and L.MISSED_MINUTES == (3, 7, 15), q7)
app.live = None

# ---------------------------------------------------------------------------------------------- a recording: stable slides only
try:
    import av  # noqa: F401
    HAVE_AV = True
except ImportError:
    HAVE_AV = False
    print("skipped: PyAV not installed (the recording part)")
    if os.environ.get("GITHUB_ACTIONS"):
        fails.append("PyAV missing on CI")
if HAVE_AV:
    import av

    def grid(seed):
        r = np.random.default_rng(seed)
        cells = r.integers(0, 256, (6, 8, 3)).astype(np.uint8)
        return np.kron(cells, np.ones((40, 40, 1), np.uint8))   # 240 x 320, blocks: survives the lossy video

    ga, gb, gc, gd = grid(11), grid(12), grid(13), grid(14)
    blend = ((ga.astype(np.int16) + gb.astype(np.int16)) // 2).astype(np.uint8)
    frames = [ga] * 10 + [blend] + [gb] * 11 + [gd] + [gb] * 7 + [gc] * 10     # A, a transition, B, one odd frame, B, C
    vp = os.path.join(tempfile.mkdtemp(), "v.mp4")
    out = av.open(vp, "w")
    st = out.add_stream("mpeg4", rate=1)
    st.width, st.height, st.pix_fmt = 320, 240, "yuv420p"
    for img in frames:
        for pk in st.encode(av.VideoFrame.from_ndarray(img, format="rgb24")):
            out.mux(pk)
    for pk in st.encode():
        out.mux(pk)
    out.close()

    class FakeRec:
        def __init__(self):
            self.shots_dir, self.shots, self.done = tempfile.mkdtemp(), [], False

        def add_shot(self, tt, name):
            self.shots.append((tt, name))

        def set_slides_done(self):
            self.done = True

    L.ocr_add = lambda *a, **k: None
    rec = FakeRec()
    vs = L.VideoSlides(vp, rec)
    vs.start()
    vs.join(60)
    times = [round(tt) for tt, _ in rec.shots]
    check("a recording: the three slides, not the transition or the odd frame", len(times) == 3 and times[0] <= 1 and 10 <= times[1] <= 12 and 29 <= times[2] <= 31, times)
    check("...each saved as a picture, and the end of the video is reported", all(os.path.isfile(os.path.join(rec.shots_dir, n)) for _, n in rec.shots) and rec.done, rec.shots)

print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.stdout.flush()
os._exit(1 if fails else 0)

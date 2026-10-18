"""Stopping a live lecture right after starting it (System/Program/live_transcribe.py). The bug of 15.10.2026: a
lecture stopped while Hevanti was still loading stayed on "stopping..." and could not be stopped. Any OS:
  python3 tools/test_stop.py"""
import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["BZM_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)))
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


# the model takes long to load (the first time it is downloaded)
loading = threading.Event()


def slow_model(lang, stub_av=False):
    loading.set()
    time.sleep(3)
    return object(), 1, "test CPU"


L.get_model = slow_model
L._ensure_packages = lambda *a, **k: None
L.SCREEN_ENABLED = False
app = L.APP if getattr(L, "APP", None) is not None else L.App()
L.APP = app
C = "פיזיקה 2"
L.create_course(C)
s = app.start("live", "he", L.run_live, "he", C, course=C)
loading.wait(10)
t = time.time()
app.command({"action": "stop", "discard": True})
check("stop while loading: done at once", s.done and time.time() - t < 1, (s.done, time.time() - t))
check("stop while loading: the page is told", app.state()["session"]["done"])
s.thread.join(10)
lectures = [n for n in os.listdir(L.course_dir(C)) if os.path.isdir(os.path.join(L.course_dir(C), n))]
check("stop while loading: no lecture folder", lectures == [], lectures)
check("a new lecture can start right after", app.start("live", "he", lambda sess, *a: None, course=C) is not None)

# a quiet live lecture keeps now_watching.txt fresh (the AI treats a file that stopped updating as a stopped lecture)
import datetime  # noqa: E402
L.LiveNow.EVERY_S, L.LiveNow.BEAT_S = 0.2, 1
ln = L.LiveNow("a/b.txt", datetime.datetime.now(), course="x")
ln.start()
time.sleep(0.6)
m1 = os.path.getmtime(L.NOW_FILE)
time.sleep(2.2)
check("live now file: rewritten while nobody speaks", os.path.getmtime(L.NOW_FILE) > m1)
ln.stop_evt.set()

print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.exit(1 if fails else 0)

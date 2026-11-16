"""Which screen is photographed when the computer has more than one (System/Program/live_transcribe.py: pick_lecture_monitor,
monitor_of_rect, capture_area, lecture_monitor): the one the lecture is on, found from the windows in view - not the main screen
only. Pure functions with made-up screens and windows, any OS, a second:
  python3 tools/test_monitor.py"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp()
os.environ.update(BZM_DATA_DIR=os.path.join(TMP, "data"), LOCALAPPDATA=os.path.join(TMP, "local"), BZM_NO_BROWSER="1")
os.environ.pop("LT_MONITOR", None)
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)[:300]), flush=True)
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300])


ONE = [{"left": 0, "top": 0, "width": 1920, "height": 1080}, {"left": 0, "top": 0, "width": 1920, "height": 1080}]
TWO = [{"left": 0, "top": 0, "width": 3840, "height": 1080}, {"left": 0, "top": 0, "width": 1920, "height": 1080},
       {"left": 1920, "top": 0, "width": 1920, "height": 1080}]
FULL2 = (1920, 0, 3840, 1080)
FULL1 = (0, 0, 1920, 1080)

check("one screen: that one", L.pick_lecture_monitor(ONE, [("Zoom Meeting", "Zoom.exe", FULL1)], 1) == 1)
check("the lecture (Zoom, full) is on the second screen -> screen 2",
      L.pick_lecture_monitor(TWO, [("Zoom Meeting", "Zoom.exe", FULL2), ("Notes", "notepad.exe", (100, 100, 700, 500))], 1) == 2)
check("a video player on screen 2 beats a small browser on screen 1",
      L.pick_lecture_monitor(TWO, [("lecture.mp4 - VLC", "vlc.exe", FULL2), ("Mail", "chrome.exe", (0, 0, 900, 700))], 1) == 2)
check("Hevanti's own window on screen 2 does not count: the lecture stays on screen 1",
      L.pick_lecture_monitor(TWO, [("הבנתי · האפליקציה", "msedge.exe", FULL2), ("Slides - PowerPoint", "POWERPNT.EXE", FULL1)], 1) == 1)
check("an AI window on screen 2 does not count",
      L.pick_lecture_monitor(TWO, [("ChatGPT - Google Chrome", "chrome.exe", FULL2), ("Teams", "ms-teams.exe", FULL1)], 1) == 1)
check("nothing in view: the screen stays as it was",
      L.pick_lecture_monitor(TWO, [], 2) == 2 and L.pick_lecture_monitor(TWO, [], 1) == 1)
check("a small window on the other screen does not make the picture jump",
      L.pick_lecture_monitor(TWO, [("Lecture - Zoom", "Zoom.exe", FULL2), ("Chat", "chrome.exe", (0, 0, 800, 600))], 2) == 2)
check("a window across both screens belongs to the one that holds most of it",
      L.monitor_of_rect(TWO, (1500, 0, 3300, 1000)) == 2 and L.monitor_of_rect(TWO, (100, 0, 2000, 1000)) == 1)

# found on a real computer (16.11.2026): the AI window fills screen 1 and hides an explorer and a browser window under it, a browser plays on screen 2
REAL = [("Claude", "claude.exe", FULL1), ("Video - Google Chrome", "chrome.exe", FULL2), ("Home - File Explorer", "explorer.exe", FULL1),
        ("Docs - Google Chrome", "chrome.exe", FULL1), ("Program Manager", "explorer.exe", (0, 0, 3840, 1080))]
check("windows hidden under the AI window do not count: the browser on screen 2 wins", L.pick_lecture_monitor(TWO, REAL, 1) == 2)
check("the same without the video: screen 1 stays (nothing to move to)", L.pick_lecture_monitor(TWO, [REAL[0], REAL[2], REAL[3]], 1) == 1)

# one window photographed: its own screen, not the main one
real = L.visible_windows
L.visible_windows = lambda: [("Lecture - Zoom", "Zoom.exe", (2000, 50, 3700, 1000))]
try:
    area, cover = L.capture_area("window", "Lecture", None, TWO[1], TWO)
finally:
    L.visible_windows = real
check("window mode: a window on screen 2 is photographed whole", area == {"left": 2000, "top": 50, "width": 1700, "height": 950}, area)
L.visible_windows = lambda: [("Lecture - Zoom", "Zoom.exe", (2000, 50, 3700, 1000))]
try:
    area_old, _ = L.capture_area("window", "Lecture", None, TWO[1])
finally:
    L.visible_windows = real
check("(without the list of screens it is cut at the main screen, as before)", area_old is None, area_old)

# the screen kept for the run, and the student's own choice
fake = {"n": 0}
L.visible_windows = lambda: [("Lecture - Zoom", "Zoom.exe", FULL2)]
try:
    L._LECTURE_MON.update(idx=0, at=0.0)
    got = L.lecture_monitor(TWO, force=True)
finally:
    L.visible_windows = real
check("lecture_monitor gives screen 2's area", got == TWO[2], got)
check("one screen: lecture_monitor gives it at once", L.lecture_monitor(ONE, force=True) == ONE[1])

print("all passed" if not fails else f"{len(fails)} failed: " + ", ".join(fails))
sys.exit(1 if fails else 0)

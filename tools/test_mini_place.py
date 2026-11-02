"""The small question window opens straight in its place (System/Program/live_transcribe.py): never at its old place
first and then jumping. Windows only, needs Edge or Chrome, and it shows the real window for a few seconds:
  python tools/test_mini_place.py"""
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

if os.name != "nt":
    print("SKIP Windows only")
    sys.exit(0)
from ctypes import wintypes  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = next((p for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe") if os.path.isfile(p)), None)
if not EXE:
    print("SKIP no Edge or Chrome")
    sys.exit(0)
TMP = tempfile.mkdtemp()
os.environ.update(BZM_DATA_DIR=os.path.join(TMP, "data"), LOCALAPPDATA=os.path.join(TMP, "local"), BZM_NO_BROWSER="1")
os.makedirs(os.environ["BZM_DATA_DIR"])
os.makedirs(os.environ["LOCALAPPDATA"])
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)))
    if not ok:
        fails.append(name)


L._browser_exe = lambda: EXE
srv = L.AppServer()
assert srv.start()
if getattr(L, "APP", None) is None:
    L.APP = L.App()
L.APP.url = srv.url.rstrip("/") + "/"
u = L._mini_user32()
if L._find_mini(u):
    print("SKIP a small window of Hevanti is already open (close it first)")
    sys.exit(0)


def chrome_windows():
    found = {}

    def each(hw, _):
        try:
            if L._is_chrome_window(u, hw):
                found[hw] = True
        except Exception:
            pass
        return True
    u.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(each), 0)
    return set(found)


def watch(fn, secs=1.0):
    """Every different rectangle the window had while visible, from the first moment it could be seen."""
    known, log, stop = chrome_windows(), [], threading.Event()
    mine = L._find_mini(u)
    known.discard(mine)

    def loop():
        L._real_pixels(u).__enter__()   # this thread too reads real pixels, like the window itself
        while not stop.is_set():
            def each(hw, _):
                try:
                    if hw not in known and L._is_chrome_window(u, hw) and u.IsWindowVisible(hw) and not u.IsIconic(hw):
                        r = wintypes.RECT()
                        u.GetWindowRect(hw, ctypes.byref(r))
                        rect = (r.left, r.top, r.right - r.left, r.bottom - r.top)
                        if rect[0] < -10000:   # (a minimized window: where Windows keeps it, not a place it was shown at)
                            return True
                        if not log or log[-1] != rect:
                            log.append(rect)
                except Exception:
                    pass
                return True
            u.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(each), 0)
            time.sleep(0.01)
    th = threading.Thread(target=loop)
    th.start()
    fn()
    time.sleep(secs)
    stop.set()
    th.join()
    return log


def target():
    w, h = L.MINI_SIZE
    return L._mini_xy_by_button(u, int(round(w * RP.scale)), int(round(h * RP.scale)))


def inside_work_area(rect):
    a = wintypes.RECT()
    u.SystemParametersInfoW(0x30, 0, ctypes.byref(a), 0)
    return rect[0] >= a.left and rect[1] >= a.top and rect[0] + rect[2] <= a.right and rect[1] + rect[3] <= a.bottom


RP = L._real_pixels(u)
RP.__enter__()
WW, HH = int(round(L.MINI_SIZE[0] * RP.scale)), int(round(L.MINI_SIZE[1] * RP.scale))


def near(a, b):
    return abs(a[0] - b[0]) <= 2 and abs(a[1] - b[1]) <= 2


# (the program itself is DPI-unaware: here the test reads the same real pixels the window has)
try:
    want = target()
    seen = watch(lambda: L.toggle_mini(show_only=True))
    check("opening: the window is seen only in its place (above the button)", len(seen) >= 1 and all(near(s[:2], want) for s in seen), (seen, want))
    check("opening: the whole window is inside the screen (also at 125% scaling)", len(seen) >= 1 and all(inside_work_area(s) for s in seen), seen)
    h = L._find_mini(u)
    L.toggle_mini(hide_only=True)
    time.sleep(0.4)
    u.MoveWindow(h, 300, 120, WW, HH, True)
    time.sleep(0.3)
    seen = watch(lambda: L.toggle_mini(show_only=True))
    check("reopening in the same session: stays where the student left it", seen and seen[0][:2] == (300, 120) and len(seen) == 1, seen)
    L.toggle_mini(hide_only=True)
    time.sleep(0.4)
    u.MoveWindow(h, 300, 120, WW, HH, True)
    time.sleep(0.3)
    L._MINI_STATE["key"] = "another session"
    seen = watch(lambda: L.toggle_mini(show_only=True))
    check("a new session: straight above the button, no jump from the old place", len(seen) >= 1 and near(seen[-1][:2], want) and len({s[:2] for s in seen}) == 1, (seen, want))
    L.toggle_mini(hide_only=True)
    time.sleep(0.4)
    u.MoveWindow(h, 5000, 5000, WW, HH, True)
    time.sleep(0.3)
    seen = watch(lambda: L.toggle_mini(show_only=True))
    check("left on no screen: pulled back above the button, no jump", len(seen) >= 1 and near(seen[-1][:2], want) and len({s[:2] for s in seen}) == 1, (seen, want))
    u.ShowWindow(h, 6)   # minimized
    time.sleep(0.6)
    L._MINI_STATE["key"] = "yet another session"
    seen = watch(lambda: L.toggle_mini(show_only=True))
    check("minimized, then opened in a new session: restored straight in its place", len(seen) >= 1 and near(seen[-1][:2], want) and len({s[:2] for s in seen}) == 1, (seen, want))
finally:
    p = L._MINI_PROC.get("proc")
    if p:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
    shutil.rmtree(TMP, ignore_errors=True)
print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.stdout.flush()
os._exit(1 if fails else 0)

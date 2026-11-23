"""The floating round button stayed on the X (and stopped drawing, the red dot too) after the small window was closed (found on a real
Windows run, 23.11.2026). The button's window procedure now logs an exception once and resets the turn, and the ten-times-a-second timer
notices an animation timer that went quiet. The button itself needs Windows and a real screen; this checks that the guards are in place.
  python3 tools/test_button_freeze.py"""
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(HERE, "System", "Program", "live_transcribe.py"), encoding="utf-8").read().replace("\r\n", "\n")
fails = []


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name, flush=True)
    if not ok:
        fails.append(name)


check("the real procedure is wrapped (callback exceptions are not forgotten)", "def _wndproc(hwnd, msg, wp, lp):" in src and "return _wndproc(hwnd, msg, wp, lp)" in src)
check("the wrapper writes the error log once", 'save_error("floating button")' in src and 'st["err_logged"]' in src)
check("the registered callback is the wrapper", "cb = proc_t(wndproc)" in src)
w = src[src.index("def wndproc(hwnd, msg, wp, lp):"):]
w = w[:w.index("def show_toast")]
check("after an exception in a timer the turn is reset and redrawn", 'st["anim_timer"] = False' in w and 'st["pt"], st["sig"] = float(st["target"]), None' in w and "KillTimer" in w)
check("a quiet animation timer is noticed by the ten-times-a-second timer", 'time.time() - st["anim_last"] > 1.5' in src)
check("every tick of the animation timer is remembered", bool(re.search(r'st\["a_t"\] = st\["anim_last"\] = now', src)))
check("starting the animation sets the same mark", bool(re.search(r'st\["a_t"\] = st\["anim_last"\] = time\.time\(\)', src)))
if fails:
    print("FAILED:", "; ".join(fails))
    sys.exit(1)
print("all passed")

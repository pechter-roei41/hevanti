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
# the hover halo (24.11.2026): the mouse messages, the leave message, the timer of the fade, and the window that has room for it
check("hover: WM_MOUSEMOVE asks for WM_MOUSELEAVE (TrackMouseEvent, TME_LEAVE) and WM_MOUSELEAVE takes the halo away",
      "msg == 0x0200 and not st[\"hover\"]" in src and "u.TrackMouseEvent" in src and "msg == 0x02A3" in src)
check("hover: the fade has its own timer (3), stopped when it arrives and when an exception happens in it",
      'msg == 0x0113 and wp == 3' in src and 'u.KillTimer(hwnd, 3)' in src and 'if wp == 3:' in w)
check("hover: with motion off the halo comes and goes at once", "hover_to" in src and "_motion_allowed()" in src[src.index("def hover_to"):src.index("def _wndproc")])
check("hover: the window is S + 2*pad, placed pad up and left, so the circle stays where it was",
      "W = S + 2 * P" in src and "u.MoveWindow(self.hwnd, x - P, y - P, W, W, True)" in src and "0, 0, W, W, None" in src)
check("hover: a hidden button forgets the halo (no WM_MOUSELEAVE comes when a window is hidden)", 'st["hover"], st["hv"], st["hv_t"] = False, 0.0, 0.0' in src)
if fails:
    print("FAILED:", "; ".join(fails))
    sys.exit(1)
print("all passed")

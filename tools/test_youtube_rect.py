"""Where Hevanti photographs the YouTube player (System/Program/live_transcribe.py: screen_rect and friends).
The bug of 14.10.2026: on a computer whose monitors have different scaling, window.screenX is in a mixed scale,
so the picture was taken beside the player - half the player, half Hevanti's own transcript - and every new line
of the transcript looked like a new slide. Any OS:  python3 tools/test_youtube_rect.py"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["BZM_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)))
    if not ok:
        fails.append(name)


# A Chrome window maximized on a 2nd monitor at 125% (real pixels 1920..3840 x 0..1032), the page 1536x737 CSS px,
# the player at CSS (40, 120) size 900x506. window.screenX would say 1536 (mixed scale) - wrong by 384 px.
win = (1920, 0, 3840, 1032)
v = {"sx": 1536, "sy": 0, "ow": 1536, "oh": 825.6, "iw": 1536, "ih": 737, "dpr": 1.25, "x": 40, "y": 120, "w": 900, "h": 506}
r = L.screen_rect(v, wins=[(0, 0, 1920, 1040), win])
page_top = 1032 - 737 * 1.25
check("the window of the page is chosen by its shape", r is not None and r["left"] >= 1920, r)
check("left edge on the player", r and abs(r["left"] - (1920 + 40 * 1.25)) <= 1, r)
check("top edge on the player", r and abs(r["top"] - (page_top + 120 * 1.25)) <= 1, r)
check("size in real pixels", r and (r["width"], r["height"]) == (1125, 632), r)
check("inside the window", r and r["left"] + r["width"] <= 3840 and r["top"] + r["height"] <= 1032, r)
check("a tiny player is not photographed", L.screen_rect(dict(v, w=100, h=60), wins=[win]) is None)
if os.name == "nt":
    check("Windows: no page window found -> no picture (no guessing)", L.screen_rect(v, wins=[]) is None)
else:
    check("not Windows: the page's own report is used", L.screen_rect(v, wins=[]) is not None)
check("not the page's shape -> not that window", L.pick_page_window(v, [(0, 0, 800, 1000)]) is None)

print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.exit(1 if fails else 0)

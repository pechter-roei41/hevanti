"""Mac test, part 1 - run with Hevanti's own Python (System/venv-mac): the Mac-only code inside the app.
Prints one JSON line: {check: [ok, detail]}. Used by tools/mac_smoke.py on a GitHub Mac."""
import json
import os
import sys

app = sys.argv[1]
out_dir = sys.argv[2]
sys.path.insert(0, os.path.join(app, "System", "Program"))
res = {}


def check(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:  # a crash is a failed check, with its reason
        ok, detail = False, f"{type(e).__name__}: {e}"
    res[name] = [bool(ok), str(detail)[:300]]


import live_transcribe as L  # noqa: E402  (main() runs only as a program)

check("is_mac", lambda: (L.IS_MAC, f"IS_MAC={L.IS_MAC}"))
check("ai_apps", lambda: (isinstance(L.find_ai_apps(), dict), L.find_ai_apps()))


def windows():
    w = L._visible_windows_mac()
    return isinstance(w, list), f"{len(w)} windows: " + ", ".join(f"{a}/{t}" for t, a, _ in w[:6])


check("window_list", windows)


def screen():
    import mss
    import numpy as np
    from PIL import Image
    with mss.mss() as s:
        mon = s.monitors[1]
        g = s.grab(mon)
    arr = np.array(g)
    Image.frombytes("RGB", g.size, g.rgb).save(os.path.join(out_dir, "screen.png"))
    L.mask_windows(arr, dict(mon))   # the Mac branch: window list from Quartz, Retina scaling
    return arr.std() > 1, f"{g.size[0]}x{g.size[1]}, contrast {arr.std():.1f} (0 = black: no permission)"


check("screenshot_and_mask", screen)


def slide():
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1280, 720), "white")
    d = ImageDraw.Draw(img)
    font = None
    for f in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial Unicode.ttf"):
        if os.path.isfile(f):
            font = ImageFont.truetype(f, 72)
            break
    font = font or ImageFont.load_default()
    d.text((120, 160), "Moment of Inertia", fill="black", font=font)
    d.text((120, 330), "מומנט התמד"[::-1], fill="black", font=font)   # (PIL draws left to right: reversed = right)
    p = os.path.join(out_dir, "slide.png")
    img.save(p)
    w = L.ocr_worker()
    if not w.setup():
        return False, f"Tesseract not ready (exe={L.find_tesseract()}, tessdata={L.tessdata_dir()})"
    text = w.read(p) or ""
    return "Inertia" in text, ("Hebrew read too: " if "מומנט" in text else "Hebrew NOT read: ") + repr(text[:120])


check("ocr", slide)
print(json.dumps(res, ensure_ascii=False))

"""Colours: (1) the CSS variables of the pages are the tokens of DESIGN.md, and (2) every colour pair the design depends on keeps its
contrast - 4.5:1 for text, 3:1 for a graphic part - in the light and the dark theme, computed from DESIGN.md (tools/contrast.py).
No browser, any OS:
  python3 tools/test_contrast.py"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contrast as C  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)[:400]), flush=True)
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


D = C.design_colors()
APP_LIGHT, APP_DARK = C.css_vars("app.html")


def col(x):
    """A colour: a token of DESIGN.md, a '#RRGGBB', or a CSS variable of app.html as 'css:--name' (light) / 'cssdark:--name' (dark)."""
    if x.startswith("#"):
        return x.upper()
    if x.startswith("css:"):
        return APP_LIGHT[x[4:]]
    if x.startswith("cssdark:"):
        return APP_DARK[x[8:]]
    return D[x]


# ---------------------------------------------------------------------------------------- 1. the pages use the tokens of DESIGN.md
for page in ("app.html", "mini.html", "player.html"):
    light, dark = C.css_vars(page)
    bad = []
    for var, (lt, dt) in C.VAR_TO_TOKEN.items():
        if var in light and lt and light[var] != D[lt]:
            bad.append((page, var, light[var], D[lt]))
        if var in dark and dt and dark[var] != D[dt]:
            bad.append((page, var, dark[var], D[dt]))
    check(f"{page}: its CSS colours are the tokens of DESIGN.md (light and dark)", not bad, bad)

# ---------------------------------------------------------------------------------------- 2. the pairs the design depends on
TEXT, GRAPHIC = 4.5, 3.0
PAIRS = [
    # (what, light foreground, light background, dark foreground, dark background, minimum)
    ("placeholder (ink-muted) on a field of paper", "ink-muted", "paper", "night-muted", "night-paper", TEXT),
    ("placeholder (ink-muted) on a sheet", "ink-muted", "sheet", "night-muted", "night-sheet", TEXT),
    ("placeholder (ink-muted) on sunk paper", "ink-muted", "sunk-paper", "night-muted", "night-sunk", TEXT),
    ("ghost button (green text) on the caution bar", "board-green", "css:--warn-bg", "night-green", "cssdark:--warn-bg", TEXT),
    ("caution text on the caution bar", "css:--warn-fg", "css:--warn-bg", "cssdark:--warn-fg", "cssdark:--warn-bg", TEXT),
]
for what, lf, lb, df, db, need in PAIRS:
    r_light, r_dark = C.ratio(col(lf), col(lb)), C.ratio(col(df), col(db))
    print(f"   {what}: light {r_light:.2f}:1, dark {r_dark:.2f}:1 (needs {need}:1)")
    check(f"contrast, light: {what}", r_light >= need, f"{r_light:.2f}")
    check(f"contrast, dark: {what}", r_dark >= need, f"{r_dark:.2f}")

print()
print("all passed" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)

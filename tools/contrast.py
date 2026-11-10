"""Colour contrast, computed (WCAG 2.x relative luminance) from the tokens of DESIGN.md and from the CSS variables of the pages - never
estimated. Used by tools/test_contrast.py, and on its own to print the numbers:
  python3 tools/contrast.py
Text needs 4.5:1, a graphic part (an icon, a check, a border that carries meaning) 3:1."""
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROG = os.path.join(HERE, "System", "Program")


def design_colors():
    """{name: '#RRGGBB'} from the front matter of DESIGN.md."""
    txt = open(os.path.join(HERE, "DESIGN.md"), encoding="utf-8").read()
    front = txt.split("---")[1]
    return {m.group(1): m.group(2).upper() for m in re.finditer(r'^\s+([a-z-]+):\s*"(#[0-9A-Fa-f]{6})"', front, re.M)}


def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hexcolor):
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def ratio(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def blend(fg, bg, alpha):
    """The colour of fg at `alpha` over bg (both '#RRGGBB')."""
    f, g = fg.lstrip("#"), bg.lstrip("#")
    out = [round(int(f[i:i + 2], 16) * alpha + int(g[i:i + 2], 16) * (1 - alpha)) for i in (0, 2, 4)]
    return "#%02X%02X%02X" % tuple(out)


def css_vars(page):
    """({var: value} of the light :root, {var: value} of the dark theme) of a page (app.html, mini.html, player.html)."""
    css = open(os.path.join(PROG, page), encoding="utf-8").read()
    light = re.search(r"^:root\{(.*?)\}", css, re.M | re.S)
    dark = re.search(r':root\[data-theme="dark"\]\{(.*?)\}', css, re.S)
    def parse(block):
        return {m.group(1): m.group(2).strip().upper() for m in re.finditer(r"(--[a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})", block.group(1))} if block else {}
    return parse(light), parse(dark)


# the CSS variable of the pages -> the token of DESIGN.md (light, dark)
VAR_TO_TOKEN = {
    "--bg": ("paper", "night-paper"), "--surface": ("sheet", "night-sheet"), "--sunk": ("sunk-paper", "night-sunk"),
    "--fg": ("ink", "night-ink"), "--muted": ("ink-muted", "night-muted"), "--line": ("hairline", "night-hairline"),
    "--accent": ("board-green", "night-green"), "--accent-soft": ("board-green-soft", "night-green-soft"),
    "--rec": ("recording-red", "night-recording"), "--mark-line": ("mark-line", "night-mark-line"), "--warn-bg": ("caution-paper", None), "--warn-fg": ("caution-ink", None),
}


if __name__ == "__main__":
    c = design_colors()
    for name, fg, bg in (("muted on paper", "ink-muted", "paper"), ("muted on sheet", "ink-muted", "sheet"), ("muted on sunk paper", "ink-muted", "sunk-paper"),
                         ("night muted on night paper", "night-muted", "night-paper"), ("night muted on night sheet", "night-muted", "night-sheet"),
                         ("night muted on night sunk", "night-muted", "night-sunk")):
        print(f"{name}: {ratio(c[fg], c[bg]):.2f}:1")

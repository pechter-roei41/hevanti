"""The folder Hevanti-Setup.exe installs (installer/hevanti.iss packs it): the app files, Hevanti's own Python
(the official embeddable Python from python.org, with site-packages on) and the icon. The release workflow then
installs the packages into that Python (on a Windows runner) and runs Inno Setup.

  python tools/build_setup_dir.py <python-3.x-embed-amd64.zip> <get-pip.py> <out folder>"""
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"__pycache__", "python"}
SKIP_EXT = (".sh",)


def policy_text():
    """What the installer shows before it installs: the privacy policy and the terms of use (PRIVACY.md and TERMS.md, the same files the repository and the website show)."""
    parts = []
    for name in ("PRIVACY.md", "TERMS.md"):
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            parts.append(f.read().strip())
    return (chr(10) * 2 + "=" * 70 + chr(10) * 2).join(parts) + chr(10)


def make_icon(path):
    """The logo (a green bubble with a short tail and a thick yellow tick) as a Windows .ico, drawn here - no image file in the repo.
    Every size is drawn on its own (8x, then smoothed down) and fills its square, so the taskbar and Start icons stay crisp."""
    from PIL import Image, ImageDraw
    green, yellow = (31, 122, 85, 255), (247, 212, 76, 255)

    def draw(S):
        k = 8
        N = S * k
        im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        u = N * 0.98 / 108   # the mark is 108 x 106 units: fill the square
        ox, oy = N * 0.01 - 6 * u, N * 0.01 + (N * 0.98 - 106 * u) / 2 - 8 * u

        def P(x, y):
            return (ox + x * u, oy + y * u)
        d.rounded_rectangle([P(6, 8), P(114, 94)], radius=24 * u, fill=green)
        d.polygon([P(68, 93), P(92, 93), P(100, 114)], fill=green)
        pts = [P(33, 52), P(52, 71), P(87, 33)]
        d.line(pts, fill=yellow, width=int(17 * u), joint="curve")
        for x, y in pts:
            d.ellipse((x - 8.5 * u, y - 8.5 * u, x + 8.5 * u, y + 8.5 * u), fill=yellow)
        return im.resize((S, S), Image.LANCZOS)
    sizes = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
    frames = [draw(n) for n in sizes]
    frames[-1].save(path, format="ICO", sizes=[(n, n) for n in sizes], append_images=frames[:-1])


def main():
    embed, get_pip, out = sys.argv[1:4]
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    for item in ("README.txt", "LICENSE", "PRIVACY.md", "TERMS.md"):
        shutil.copy2(os.path.join(ROOT, item), os.path.join(out, item))
    for d, dirs, files in os.walk(os.path.join(ROOT, "System")):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        rel = os.path.relpath(d, ROOT)
        os.makedirs(os.path.join(out, rel), exist_ok=True)
        for f in files:
            if not f.endswith(SKIP_EXT) and f != "error_log.txt":
                shutil.copy2(os.path.join(d, f), os.path.join(out, rel, f))
    py = os.path.join(out, "python")
    with zipfile.ZipFile(embed) as z:
        z.extractall(py)
    for f in os.listdir(py):
        if f.endswith("._pth"):   # let it use installed packages (off in the embeddable Python)
            p = os.path.join(py, f)
            with open(p, encoding="ascii") as h:
                body = h.read()
            with open(p, "w", encoding="ascii") as h:
                h.write(body.replace("#import site", "import site"))
    shutil.copy2(get_pip, os.path.join(py, "get-pip.py"))
    make_icon(os.path.join(out, "hevanti.ico"))
    with open(os.path.join(out, "PRIVACY.txt"), "w", encoding="utf-8-sig") as f:   # shown by the installer
        f.write(policy_text())
    print("ready:", out)


if __name__ == "__main__":
    main()

"""The folder Hevanti-Setup.exe installs (installer/hevanti.iss packs it): the app files, Hevanti's own Python
(the official embeddable Python from python.org, with site-packages on) and the icon. The release workflow then
installs the packages into that Python (on a Windows runner) and runs Inno Setup.

  python tools/build_setup_dir.py <python-3.x-embed-amd64.zip> <get-pip.py> <out folder>"""
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"__pycache__", "python", "venv-mac"}
SKIP_EXT = (".command", ".sh")


def make_icon(path):
    """The logo (a green speech bubble with a yellow tick) as a Windows .ico, drawn here - no image file in the repo."""
    from PIL import Image, ImageDraw
    big = 512
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    green, yellow = (31, 122, 85, 255), (247, 212, 76, 255)
    d.rounded_rectangle((26, 60, 486, 384), radius=60, fill=green)
    d.polygon([(330, 370), (420, 370), (432, 470)], fill=green)   # the bubble's tail
    d.line([(150, 222), (218, 290), (362, 146)], fill=yellow, width=52, joint="curve")
    for x, y in ((150, 222), (218, 290), (362, 146)):
        d.ellipse((x - 26, y - 26, x + 26, y + 26), fill=yellow)
    im.save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def main():
    embed, get_pip, out = sys.argv[1:4]
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    for item in ("README.txt", "LICENSE"):
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
    print("ready:", out)


if __name__ == "__main__":
    main()

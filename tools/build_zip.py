"""Build what students download, from the repo: the app files only, inside one folder.

  python tools/build_zip.py [out.zip]                                   Windows, Python downloaded by Install
  python tools/build_zip.py --python-zip E.zip --get-pip G.py out.zip   Windows, with its own Python inside

The Windows "embeddable" Python (python.org) goes to System/python, with site-packages turned on, so Install
only adds the packages - nobody installs Python. The GitHub release workflow builds the ZIP."""
import argparse
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = "Hevanti_v2.0"  # the folder inside the ZIP
SKIP_DIRS = {"__pycache__", "python"}   # local copies of Python, never from the working tree
SKIP_FILES = {"error_log.txt"}


def add_file(z, full, arc):
    info = zipfile.ZipInfo.from_file(full, arc)
    info.compress_type = zipfile.ZIP_DEFLATED
    with open(full, "rb") as f:
        z.writestr(info, f.read(), compresslevel=9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default=None)
    ap.add_argument("--python-zip", help="python-3.x-embed-amd64.zip from python.org (Windows)")
    ap.add_argument("--get-pip", help="get-pip.py from bootstrap.pypa.io (with --python-zip)")
    a = ap.parse_args()
    out = a.out or "Hevanti.zip"
    top = ["Hevanti.bat", "Install.bat", "README.txt", "System"]
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for item in top:
            path = os.path.join(ROOT, item)
            if os.path.isfile(path):
                add_file(z, path, f"{FOLDER}/{item}")
                n += 1
                continue
            for d, dirs, files in os.walk(path):
                dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
                for f in sorted(files):
                    if f in SKIP_FILES:
                        continue
                    full = os.path.join(d, f)
                    add_file(z, full, f"{FOLDER}/" + os.path.relpath(full, ROOT).replace(os.sep, "/"))
                    n += 1
        if a.python_zip:
            with zipfile.ZipFile(a.python_zip) as py:
                for name in py.namelist():
                    data = py.read(name)
                    if name.endswith("._pth"):   # let it use installed packages (off in the embeddable Python)
                        data = data.replace(b"#import site", b"import site")
                    z.writestr(f"{FOLDER}/System/python/{name}", data)
                    n += 1
            if a.get_pip:
                z.write(a.get_pip, f"{FOLDER}/System/python/get-pip.py")
                n += 1
    print(f"{out}: {n} files, {os.path.getsize(out) // 1024}KB")


if __name__ == "__main__":
    main()

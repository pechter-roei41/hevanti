"""Build Hevanti.zip (what students download) from the repo: the app files only, inside one folder.
Usage: python tools/build_zip.py [out.zip]"""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = "Hevanti_v2.0"  # the folder inside the ZIP
FILES = ["Hevanti.bat", "Install.bat", "README.txt", "System"]
SKIP_DIRS = {"__pycache__"}
SKIP_FILES = {"error_log.txt"}


def main(out):
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for item in FILES:
            path = os.path.join(ROOT, item)
            if os.path.isfile(path):
                z.write(path, f"{FOLDER}/{item}")
                n += 1
                continue
            for d, dirs, files in os.walk(path):
                dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
                for f in sorted(files):
                    if f in SKIP_FILES:
                        continue
                    full = os.path.join(d, f)
                    z.write(full, f"{FOLDER}/" + os.path.relpath(full, ROOT).replace(os.sep, "/"))
                    n += 1
    print(f"{out}: {n} files, {os.path.getsize(out) // 1024}KB")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "Hevanti.zip")

"""Write System/requirements.txt again: the newest wheels of Hevanti's packages for Windows and Python 3.12 (the Python that comes
with Hevanti), each with its exact version and SHA-256. The installer, the ZIP's Install.bat and the release install exactly
this file (--require-hashes), so a new release on PyPI reaches students only after it was pinned here and tested.
    python tools/pin_requirements.py            (needs the internet; changes only System/requirements.txt)"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "System", "requirements.txt")
WANTED = ["faster-whisper>=1.1", "pyaudiowpatch", "numpy", "mss", "pillow", "comtypes", "sherpa-onnx", "yt-dlp"]
HEADER = """# The Python packages of Hevanti, exactly (Windows, Python 3.12, the Python that comes with Hevanti).
# Installed with: python -m pip install -r System/requirements.txt --require-hashes --only-binary=:all:
# A package that is not exactly this file is refused (audit #25: a bad release on PyPI must not reach students by itself).
# To update: tools/pin_requirements.py (downloads the newest wheels for Windows/3.12, and writes this file again).
"""


def main():
    with tempfile.TemporaryDirectory() as d:
        subprocess.run([sys.executable, "-m", "pip", "download", "-q", "--only-binary=:all:", "--platform", "win_amd64",
                        "--python-version", "3.12", "--implementation", "cp", "-d", d] + WANTED, check=True)
        rows = []
        for f in sorted(os.listdir(d)):
            m = re.match(r"([A-Za-z0-9_.]+?)-([0-9][^-]*)-", f)
            if not m:
                continue
            with open(os.path.join(d, f), "rb") as fh:
                h = hashlib.sha256(fh.read()).hexdigest()
            rows.append(f"{m.group(1).replace('_', '-').lower()}=={m.group(2)} \\\n    --hash=sha256:{h}")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(HEADER + "\n" + "\n".join(rows) + "\n")
    print(f"{len(rows)} packages written to {OUT}")


if __name__ == "__main__":
    main()

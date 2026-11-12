"""No real key in the repository: every tracked file is searched for what a Google API key, a GitHub token or a private key
looks like. The made-up keys of the tests (tools/test_*.py) are allowed. Prints what it found and exits non-zero.
    python tools/scan_secrets.py"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOOKS = re.compile(r"AIza[0-9A-Za-z_\-]{30,}|AQ\.[0-9A-Za-z_\-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{30,}|"
                   r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
ALLOWED = re.compile(r"^tools/test_[a-z_0-9]+\.py$|^tools/scan_secrets\.py$")


def main():
    files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8").split("\0")
    hits = []
    for rel in filter(None, files):
        if ALLOWED.match(rel):
            continue
        try:
            with open(os.path.join(ROOT, rel), encoding="utf-8", errors="ignore") as f:
                for n, line in enumerate(f, 1):
                    m = LOOKS.search(line)
                    if m:
                        hits.append(f"{rel}:{n}: {m.group(0)[:8]}…")
        except OSError:
            pass
    if hits:
        print("Looks like a real key:\n" + "\n".join(hits))
        return 1
    print("no key found")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Run by the installed Python (tools/smoke_install.ps1): the installed program starts its server and serves its pages.
No model, no sound card, nothing downloaded: only what a student gets with Hevanti-Setup.exe.
  <install>\\python\\python.exe tools/smoke_server.py <install folder>"""
import os
import sys
import tempfile
import urllib.request

root = sys.argv[1]
tmp = tempfile.mkdtemp()
os.environ.update(BZM_DATA_DIR=os.path.join(tmp, "data"), LOCALAPPDATA=os.path.join(tmp, "local"), BZM_NO_BROWSER="1")
sys.path.insert(0, os.path.join(root, "System", "Program"))
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)), flush=True)
    if not ok:
        fails.append(name)


import live_transcribe as L  # noqa: E402

check("it imports from the installed folder", os.path.dirname(os.path.abspath(L.__file__)).lower().startswith(root.lower()), L.__file__)
app = L.APP if getattr(L, "APP", None) is not None else L.App()
L.APP = app
srv = L.AppServer()
check("the server starts", bool(srv.start()))
base = srv.url.rstrip("/")


def get(path):
    with urllib.request.urlopen(base + path, timeout=15) as r:
        return r.status, r.read()


VERSION_WORD = L.VERSION
for path, word in (("/", "הבנתי"), ("/player", "<"), ("/mini", "<"), ("/ask.js", "function"), ("/api/diag", VERSION_WORD)):
    try:
        code, body = get(path)
        text = body.decode("utf-8", "replace")
        check("serves " + path, code == 200 and len(body) > 100 and word in text, (code, len(body)))
    except Exception as e:  # noqa: BLE001
        check("serves " + path, False, e)

print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.stdout.flush()
os._exit(1 if fails else 0)

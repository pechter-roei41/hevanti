"""Renaming a lecture to a name so long that the path passes Windows' 260 characters (audit 16.11.2026, P1 #5): the folder move fails,
and the lecture must still be in the library with its transcript - not a folder with no transcript that the list cannot see.
Windows only (elsewhere there is no such limit) and only where long paths are off, as on most computers; about 3 seconds:
  python tools/test_long_rename.py"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if len(sys.argv) > 1 and sys.argv[1] == "child":
    sys.path.insert(0, os.path.join(HERE, "System", "Program"))
    import live_transcribe as L
    L.ERROR_LOG = os.path.join(tempfile.mkdtemp(), "error_log.txt")
    C = "קורס ארוך"
    L.create_course(C)
    lec = os.path.join(L.course_dir(C), "הרצאה")
    os.makedirs(lec)
    with open(L.lecture_txt(lec), "w", encoding="utf-8") as f:
        f.write("[09:01:00 | +0:01:00] שלום\n")
    app = L.APP if getattr(L, "APP", None) is not None else L.App()
    L.APP = app
    r = app.change_lecture("rename_lecture", {"f": C + "/הרצאה", "name": "ל" * 80})
    names = [x[1] for x in L.lecture_dirs()]
    ok_txt = os.path.isfile(L.lecture_txt(lec))
    print("RESULT", r.get("ok"), names, ok_txt)
    sys.exit(0 if (r.get("ok") is False and names == ["הרצאה"] and ok_txt) else 1)

if os.name != "nt":
    print("skipped: Windows only")
    sys.exit(0)
base = os.path.join(tempfile.mkdtemp(), "x" * 120, "y" * 20)
os.makedirs(base, exist_ok=True)
env = dict(os.environ, BZM_DATA_DIR=base, LOCALAPPDATA=os.path.join(base, "local"), BZM_NO_BROWSER="1", PYTHONUTF8="1")
p = subprocess.run([sys.executable, os.path.abspath(__file__), "child"], env=env, capture_output=True, text=True, encoding="utf-8")
out = [l for l in p.stdout.splitlines() if l.startswith("RESULT")]
if out and out[0].split()[1] == "True":
    print("skipped: this computer renamed it (long paths are on), so there is nothing to roll back")
    sys.exit(0)
print(("PASS " if p.returncode == 0 else "FAIL ") + "a rename that fails on a long path keeps the lecture and its transcript: " + (out[0] if out else p.stdout[-300:] + p.stderr[-300:]))
print("all passed" if p.returncode == 0 else "FAILED")
sys.exit(p.returncode)

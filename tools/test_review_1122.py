"""Regression tests for the two P1 findings of the review of 22.11.2026:
1. site/index.html: the "⋯" menu of the demo (hidden + inline display:flex) was always visible.
2. The helper that force-stops the profile browsers listed them AFTER its pause, so it could kill a window this run opened meanwhile
   (the prewarmed floating window).
  python3 tools/test_review_1122.py"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp()
os.environ.update(BZM_DATA_DIR=os.path.join(TMP, "data"), LOCALAPPDATA=os.path.join(TMP, "local"), BZM_NO_BROWSER="1", PYTHONUTF8="1")
os.makedirs(os.environ["LOCALAPPDATA"], exist_ok=True)
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)[:400]), flush=True)
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


# ---- 1. the landing page: an element with `hidden` stays hidden even with an inline display
site = open(os.path.join(HERE, "site", "index.html"), encoding="utf-8").read()
check("site: a global [hidden]{display:none!important} rule exists", "[hidden]{display:none!important}" in site)

try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        exe = os.environ.get("HEVANTI_TEST_CHROMIUM")
        try:
            br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch(channel="msedge")
        except Exception:
            br = pw.chromium.launch()
        for w in (1280, 320):
            pg = br.new_page(viewport={"width": w, "height": 900})
            pg.goto("file:///" + os.path.join(HERE, "site", "index.html").replace("\\", "/"))
            d0 = pg.evaluate("getComputedStyle(document.getElementById('winMenu')).display")
            pg.click("#menuBtn")
            d1 = pg.evaluate("getComputedStyle(document.getElementById('winMenu')).display")
            pg.keyboard.press("Escape")
            d2 = pg.evaluate("getComputedStyle(document.getElementById('winMenu')).display")
            check(f"site {w}px: menu hidden on load, open after the button, hidden again after Esc", (d0, d1, d2) == ("none", "flex", "none"), (d0, d1, d2))
            pg.close()
        br.close()
except ImportError:
    print("SKIP site menu in a browser: playwright is not installed")
except Exception as e:  # no browser to launch
    if os.environ.get("GITHUB_ACTIONS"):
        check("site menu in a browser", False, e)
    else:
        print("SKIP site menu in a browser:", str(e)[:200])

# ---- 2. the profile-kill helper lists first, sleeps, then stops only what it listed
ks = L._profile_kill_script([os.path.join(TMP, "profile")])
i_list, i_sleep, i_stop = ks.index("Get-CimInstance"), ks.index("Start-Sleep"), ks.index("Stop-Process")
check("kill helper: processes are listed before the pause, stopped after it", i_list < i_sleep < i_stop, ks)
check("kill helper: stops only listed ids and checks the creation time (no pid reuse)", "$old" in ks and "CreationDate" in ks and "ProcessId=$id" in ks)

if os.name == "nt":
    # a stand-in "chrome.exe" (a copy of python) whose command line holds the profile folder
    exe = os.path.join(TMP, "chrome.exe")
    prof = os.path.join(TMP, "profile")
    os.makedirs(prof, exist_ok=True)
    try:
        shutil.copy2(sys.executable, exe)
        for dll in os.listdir(os.path.dirname(sys.executable)):
            if dll.lower().startswith(("python3", "vcruntime")) and dll.lower().endswith(".dll"):
                shutil.copy2(os.path.join(os.path.dirname(sys.executable), dll), TMP)
    except OSError:
        exe = None
    procs = []
    if exe:
        def decoy():
            return subprocess.Popen([exe, "-c", "import time; time.sleep(60)", "--user-data-dir=" + prof],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        try:
            old = decoy()
            procs.append(old)
            time.sleep(1.0)
            if old.poll() is not None:
                print("SKIP kill helper run: the stand-in process does not start")
            else:
                helper = subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", L._profile_kill_script([prof])],
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
                time.sleep(0.6)
                new = decoy()       # opened while the helper pauses (the prewarmed floating window)
                procs.append(new)
                helper.wait(60)
                time.sleep(0.5)
                check("kill helper (run): the old window is stopped", old.poll() is not None)
                check("kill helper (run): a window opened during the pause survives", new.poll() is None)
        finally:
            for p in procs:
                try:
                    p.kill()
                except Exception:
                    pass
    else:
        print("SKIP kill helper run: could not copy the interpreter")


# ---- 3. P2 of the same review
app_html = open(os.path.join(HERE, "System", "Program", "app.html"), encoding="utf-8").read()
check("home: a long course name wraps in the live card (no sideways scroll at 320 px)",
      "#hlCourse{white-space:normal;overflow-wrap:anywhere" in app_html)
readme_txt = open(os.path.join(HERE, "README.txt"), encoding="utf-8").read()
check("README.txt: the 'running late' threshold names both the graphics card and the CPU case", "בלי כרטיס מסך" in readme_txt and "מאחר ביותר מ-10 שניות" not in readme_txt)
check("first-run privacy summary names the text of earlier slides", "והטקסט של השקופיות הקודמות), ושקופיות של נוסחאות" in app_html)
check("display settings: the sentence says which settings reach the small windows (zoom does not)",
      'חל רק על האפליקציה' in app_html and "וחל גם על החלון הצף ועל חלון ההתחלה המהירה" not in app_html)

# a rename whose folder move fails puts the transcript back under its old name (the rollback itself, review 22.11.2026)
import live_transcribe as L2  # noqa: E402
L.create_course("קורס החזרה")
lec = os.path.join(L.course_dir("קורס החזרה"), "הרצאה")
os.makedirs(lec, exist_ok=True)
with open(L.lecture_txt(lec), "w", encoding="utf-8") as f:
    f.write("[09:01:00 | +0:01:00] שלום" + chr(10))
app = L.APP if getattr(L, "APP", None) is not None else L.App()
L.APP = app
real_move = shutil.move


def failing_move(*a, **k):
    raise OSError("locked")


shutil.move = failing_move
try:
    r = app.change_lecture("rename_lecture", {"f": "קורס החזרה/הרצאה", "name": "שם חדש"})
finally:
    shutil.move = real_move
check("rename: a failed folder move reports the failure", r.get("ok") is False, r)
check("rename: after a failed folder move the transcript is back under its old name", os.path.isfile(os.path.join(lec, "הרצאה.txt")) and not os.path.isfile(os.path.join(lec, "שם חדש.txt")), os.listdir(lec))
check("rename: the lecture is still in the library", len(L.lecture_dirs()) == 1, L.lecture_dirs())

shutil.rmtree(TMP, ignore_errors=True)
if fails:
    print("FAILED:", "; ".join(fails))
    sys.exit(1)
print("all passed")

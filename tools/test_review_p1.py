"""Regression tests for the P0/P1 findings of the independent review of 16.11.2026.

Each check says what must be true. A check marked KNOWN means the bug is still in the code: it prints "KNOWN BUG" and
does not fail the run. When the bug is fixed the check prints "FIXED: remove known=True" - do that, so the check guards
the fix from then on. `python tools/test_review_p1.py --strict` fails on known bugs too (to see what is still open).
Any OS, a few seconds, no model, no network:
  python3 tools/test_review_p1.py"""
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp()
os.environ.update(BZM_DATA_DIR=os.path.join(TMP, "data"), LOCALAPPDATA=os.path.join(TMP, "local"), BZM_NO_BROWSER="1")
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

L.ERROR_LOG = os.path.join(TMP, "error_log.txt")   # (the real error log must not collect what these tests break on purpose)
PROG = os.path.join(HERE, "System", "Program")
STRICT = "--strict" in sys.argv
fails = []
open_bugs = []


def read(*parts):
    with open(os.path.join(HERE, *parts), encoding="utf-8") as f:
        return f.read()


def check(name, ok, detail="", known=False):
    if ok and known:
        print("FIXED: remove known=True from: " + name, flush=True)
        return
    if ok:
        print("PASS " + name, flush=True)
        return
    if known and not STRICT:
        print("KNOWN BUG " + name + ": " + str(detail)[:300], flush=True)
        open_bugs.append(name)
        return
    print("FAIL " + name + ": " + str(detail)[:400], flush=True)
    fails.append(name)
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


# ------------------------------------------------------------------------------------------------ 1. privacy wording (P0)
# The pages say "only what you ask" while earlier slides' text and slide pictures also go to Google (mini_context, MathReader).
published = {"README.txt": read("README.txt"), "app.html": read("System", "Program", "app.html"),
             "mini.html": read("System", "Program", "mini.html"), "quick.html": read("System", "Program", "quick.html")}
bad = [(f, m.group(0)) for f, t in published.items() for m in re.finditer(r"רק (?:מה )?ש(?:ו)?שואלים|רק כששואלים", t)]
check("P0 no page says Google gets 'only what you ask'", not bad, bad, known=True)

# ------------------------------------------------------------------------------------------------ 2. upload overwrites (P1)
srv = L.AppServer()
assert srv.start()
base = srv.url.rstrip("/")


def upload(name, body):
    q = urllib.request.Request(base + "/api/upload?name=" + urllib.request.quote(name), body,
                               {"X-BZM": "1", "Content-Type": "application/octet-stream"}, method="POST")
    try:
        with urllib.request.urlopen(q, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


try:
    s1, r1 = upload("Zoom recording.mp4", b"LECTURE-A-" * 10)
    p1 = r1.get("path")
    a_before = open(p1, "rb").read() if p1 and os.path.isfile(p1) else None
    s2, r2 = upload("Zoom recording.mp4", b"LECTURE-B-" * 20)
    p2 = r2.get("path")
    a_after = open(p1, "rb").read() if p1 and os.path.isfile(p1) else None
    check("P1 upload: a second recording with the same name does not replace the first",
          a_before is not None and a_after == a_before, (p1, p2, a_after[:12] if a_after else a_after), known=True)
    check("P1 upload: the second recording is whole in its own file",
          bool(p2) and p2 != p1 and os.path.isfile(p2 or "") and open(p2, "rb").read() == b"LECTURE-B-" * 20, (p1, p2), known=True)
    s3, r3 = upload("Zoom recording.mp4", b"")
    size_now = os.path.getsize(p1) if p1 and os.path.isfile(p1) else None
    check("P1 upload: an empty body does not shrink an existing recording to 0 bytes", size_now != 0, size_now, known=True)
finally:
    try:
        srv.stop()
    except Exception:
        pass

# ------------------------------------------------------------------------------------------------ 3. YouTube front-ends (P1)
check("P1 is_youtube: youtube.com / youtu.be are youtube", L.is_youtube("https://www.youtube.com/watch?v=x") and L.is_youtube("https://youtu.be/x"))
check("P1 is_youtube: a front-end of YouTube (yewtu.be, piped.video) is youtube",
      L.is_youtube("https://yewtu.be/watch?v=dQw4w9WgXcQ") and L.is_youtube("https://piped.video/watch?v=dQw4w9WgXcQ"), known=True)

# Whatever the link looks like, if yt-dlp says the video is YouTube's, site_download must refuse before it downloads anything.
attempts = []
saved = {k: getattr(L, k) for k in ("ensure_ytdlp", "_ytdlp_info", "_ytdlp_get", "problem", "show_status", "draft_clear")}
try:
    L.ensure_ytdlp = lambda upgrade=False: True
    L._ytdlp_info = lambda url: ({"title": "t", "extractor_key": "Youtube", "webpage_url": "https://www.youtube.com/watch?v=x",
                                  "formats": [], "duration": 5}, None)
    L._ytdlp_get = lambda url, *a, **k: attempts.append(url) or None
    shown = []
    L.problem = lambda t: shown.append(t)
    L.show_status = lambda *a, **k: None
    L.draft_clear = lambda *a, **k: None
    L.site_download("https://example-frontend.test/watch?v=x")
    check("P1 site_download: a link that yt-dlp resolves to YouTube is refused with no download", not attempts and L.YOUTUBE_MSG in shown,
          (attempts, shown), known=True)
finally:
    for k, v in saved.items():
        setattr(L, k, v)

# ------------------------------------------------------------------------------------------------ 4. settings: restore must keep .bak good (P1)
F = L.SETTINGS_FILE
os.makedirs(L.LOCAL_DIR, exist_ok=True)
good = {"course": "קורס בדיקה", "key": "ENCRYPTED-PLACEHOLDER"}
for p in (F, F + ".bak", F + ".corrupt"):
    if os.path.exists(p):
        os.remove(p)
for p in (F, F + ".bak"):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(good, f, ensure_ascii=False)
with open(F, "r+b") as f:
    f.truncate(15)
check("P1 settings: a cut file is restored from .bak", L.load_settings() == good)


def bak_ok():
    try:
        with open(F + ".bak", encoding="utf-8") as f:
            return json.load(f) == good
    except (OSError, ValueError):
        return False


check("P1 settings: after a restore the .bak is still the good copy (not the damaged file)", bak_ok(), open(F + ".bak", "rb").read()[:20], known=True)
with open(F, "r+b") as f:
    f.truncate(15)
check("P1 settings: a second damage still restores the key", L.load_settings() == good, L.load_settings(), known=True)
for p in (F, F + ".bak", F + ".corrupt"):
    if os.path.exists(p):
        os.remove(p)
with open(F, "w", encoding="utf-8-sig") as f:   # (a BOM written by Notepad: valid settings, not damage)
    json.dump(good, f, ensure_ascii=False)
check("P1 settings: a file with a BOM is read, not treated as damaged", L.load_settings() == good and not os.path.exists(F + ".corrupt"),
      os.path.exists(F + ".corrupt"), known=True)

# ------------------------------------------------------------------------------------------------ 5. rename that fails halfway (P1)
C = "קורס שינוי שם"
L.create_course(C)
lec = os.path.join(L.course_dir(C), "הרצאה")
os.makedirs(lec, exist_ok=True)
with open(L.lecture_txt(lec), "w", encoding="utf-8") as f:
    f.write("[09:01:00 | +0:01:00] שלום\n")
app = L.APP if getattr(L, "APP", None) is not None else L.App()
L.APP = app
real_replace = os.replace


def failing_replace(a, b, *x, **k):   # (what Windows does with a path over 260 characters: the second step fails after the folder moved)
    if str(a).endswith(".txt"):
        raise OSError("path too long")
    return real_replace(a, b, *x, **k)


os.replace = failing_replace
try:
    r = app.change_lecture("rename_lecture", {"f": C + "/הרצאה", "name": "שם חדש"})
finally:
    os.replace = real_replace
names = [os.path.basename(x) for x in L.lecture_dirs()]
check("P1 rename: a rename that fails halfway reports the failure", r.get("ok") is False, r)
check("P1 rename: after a failed rename the lecture is still in the library", len(names) == 1, names, known=True)

# ------------------------------------------------------------------------------------------------ 6. accessibility settings reach the small windows (P1)
mini, quick = published["mini.html"], published["quick.html"]


def applies(t):   # (a CSS rule for .a-contrast is not enough: the page must read the setting and set the class)
    return bool(re.search(r"a11y|classList\.(?:add|toggle)\([^)]*a-(?:contrast|read|big)", t))


check("P1 a11y: mini.html applies the saved text size / contrast / reading settings", applies(mini), known=True)
check("P1 a11y: quick.html applies the saved contrast / text size settings", applies(quick), known=True)

# ------------------------------------------------------------------------------------------------ 7. the 403 address (P1)
app_html, readme_txt = published["app.html"], published["README.txt"]
check("P1 guide: nothing tells the student to type http://127.0.0.1:8765/ by hand",
      "127.0.0.1:8765" not in app_html and "127.0.0.1:8765" not in readme_txt,
      [f for f, t in (("app.html", app_html), ("README.txt", readme_txt)) if "127.0.0.1:8765" in t], known=True)

# ------------------------------------------------------------------------------------------------ 8. the removed "?" button (P1)
check("P1 guide: the guide does not tell to press a ? button in the floating window",
      "**?**" not in app_html and not re.search(r"<b>\?</b>", app_html), known=True)
check("P1 guide: the floating window has the ★ and no ? mark button", "★" in mini and not re.search(r'id="markQ"|data-mark="\?"', mini))

print()
if open_bugs:
    print(f"{len(open_bugs)} known bug(s) still open (see the review): " + "; ".join(open_bugs))
print("all passed" if not fails else f"{len(fails)} failed: " + ", ".join(fails))
sys.exit(1 if fails else 0)

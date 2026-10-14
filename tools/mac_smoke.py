"""Mac test, part 2 - what a student does, on a GitHub Mac: after Install.command, open Hevanti.command, make a
course, play a Hebrew lecture into BlackHole, read the transcript, ask the connector. Standard library only.

  python3 tools/mac_smoke.py <the unzipped Hevanti_v2.0 folder> <folder for the results>

Writes a table to $GITHUB_STEP_SUMMARY; exits 1 when a main check fails."""
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

APP, OUT = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
os.makedirs(OUT, exist_ok=True)
PY = os.path.join(APP, "System", "venv-mac", "bin", "python")
BASE = "http://127.0.0.1:8765"
COURSE = "דינמיקה"
SPEECH = ("שלום לכולם. היום נדבר על מומנט התמד ועל החוק השני של ניוטון. "
          "מומנט ההתמד של מוט סביב הקצה שלו שווה לשליש מסה כפול אורך בריבוע. "
          "בתרגול נפתור דוגמה עם גלגלת ומסה תלויה.")
results = []   # (name, ok, detail, main)


def rec(name, ok, detail="", main=True):
    results.append((name, bool(ok), str(detail)[:400], main))
    print(("PASS " if ok else "FAIL ") + name + ": " + str(detail)[:400], flush=True)


def get(path, timeout=10):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def cmd(**d):
    req = urllib.request.Request(BASE + "/api/cmd", json.dumps(d).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-BZM": "1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


# --- what Install.command left behind
rec("install: own Python (venv)", os.access(PY, os.X_OK), PY)
td = os.path.expanduser("~/Library/Application Support/Hevanti/tessdata")
rec("install: Hebrew+English slide files", all(os.path.isfile(os.path.join(td, f"{l}.traineddata")) for l in ("heb", "eng")),
    td)
for f in ("Install.command", "Hevanti.command", "System/uninstall.command"):
    rec(f"zip: {f} runnable", os.access(os.path.join(APP, f), os.X_OK), "", main=True)

# --- the Mac code inside the app (window list, screenshot + masking, OCR, installed AI apps)
r = sh(PY, os.path.join(os.path.dirname(os.path.abspath(__file__)), "mac_inproc.py"), APP, OUT, timeout=300)
try:
    for k, (ok, detail) in json.loads(r.stdout.strip().splitlines()[-1]).items():
        rec("mac code: " + k, ok, detail, main=k not in ("screenshot_and_mask",))   # (the screen needs a permission)
except Exception:
    rec("mac code", False, (r.stdout + r.stderr)[-400:])

# --- a Claude app "installed", to see that connecting writes a working command
claude_dir = os.path.expanduser("~/Library/Application Support/Claude")
os.makedirs(claude_dir, exist_ok=True)

# --- open Hevanti.command (as a double-click does), without a browser
env = dict(os.environ, BZM_NO_BROWSER="1")
log = open(os.path.join(OUT, "hevanti_log.txt"), "w", encoding="utf-8")
proc = subprocess.Popen(["/bin/bash", os.path.join(APP, "Hevanti.command")], cwd=APP, env=env, stdout=log,
                        stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
app = None
for _ in range(90):
    try:
        app = get("/api/app")
        break
    except Exception:
        time.sleep(1)
rec("start: the app answers on 127.0.0.1:8765", app is not None, app and f"version {app.get('version')} {app.get('date')}")
if app is None:
    proc.kill()
    log.close()
else:
    rec("start: knows it is a Mac", app.get("mac") is True, f"mac={app.get('mac')}")
    s = get("/api/suggest?c=" + urllib.parse.quote("סטטיקה של גוף קשיח"))
    rec("course terms: suggestions for statics", len(s.get("terms", [])) > 10, f"{s.get('courses')} {len(s.get('terms', []))} terms")
    r = cmd(action="new_course", name=COURSE, terms=["מומנט התמד", "גלגלת", "ניוטון"])
    rec("course: create with terms", r.get("ok"), r)
    lib = get("/api/library")
    rec("course: in the library", any(c.get("name") == COURSE for c in lib.get("courses", [])),
        [c.get("name") for c in lib.get("courses", [])])

    # connect Claude, then run exactly the command it wrote
    r = cmd(action="connect", app="claude")
    cfg_p = os.path.join(claude_dir, "claude_desktop_config.json")
    try:
        srv = json.load(open(cfg_p, encoding="utf-8"))["mcpServers"]
        srv = next(v for k, v in srv.items() if "hevanti" in k.lower() or "הבנתי" in k)
        rec("connect Claude: config written", True, json.dumps(srv, ensure_ascii=False))
    except Exception as e:
        srv = None
        rec("connect Claude: config written", False, f"{r} {e}")

    def mcp(calls):
        if not srv:
            return {}
        msgs = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18",
                 "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"}]
        msgs += [{"jsonrpc": "2.0", "id": i + 1, "method": "tools/call", "params": {"name": n, "arguments": a}}
                 for i, (n, a) in enumerate(calls)]
        p = subprocess.run([srv["command"], *srv.get("args", [])], input="\n".join(json.dumps(m) for m in msgs) + "\n",
                           capture_output=True, text=True, timeout=60, env=dict(os.environ, **srv.get("env", {})))
        got = {}
        for line in p.stdout.splitlines():
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if m.get("id"):
                got[calls[m["id"] - 1][0]] = " ".join(c.get("text", "") for c in m.get("result", {}).get("content", []))
        if not got:
            got["error"] = p.stderr[-300:]
        return got

    out = mcp([("lectures", {})])
    rec("connector: lists the course", COURSE in out.get("lectures", ""), out.get("lectures") or out)

    # a live Hebrew lecture: the Mac speaks Hebrew into BlackHole
    voices = sh("say", "-v", "?").stdout
    voice = next((v for v in ("Carmit",) if v in voices), None)
    rec("audio: a Hebrew voice to play the lecture", voice is not None, voice or "no Carmit voice", main=False)
    aiff = os.path.join(OUT, "lecture.aiff")
    sh("say", *(["-v", voice] if voice else []), "-o", aiff, SPEECH if voice else
       "Today we talk about the moment of inertia and Newton's second law.")
    sw = sh("SwitchAudioSource", "-t", "output", "-s", "BlackHole 2ch")
    rec("audio: output to BlackHole", sw.returncode == 0, (sw.stdout + sw.stderr).strip())
    lang = "he" if voice else "en"
    r = cmd(action="start_live", lang=lang, course=COURSE)
    rec("live: start", r.get("ok"), r)
    text, t0, info = "", time.time(), {}
    while time.time() - t0 < 1500 and not text:   # the first time it downloads the model (~1.6GB)
        player = subprocess.Popen(["afplay", aiff])
        while player.poll() is None:
            time.sleep(2)
        try:
            st = get("/api/live?since=0")
        except Exception:
            continue
        info = st.get("info") or {}
        text = " ".join(i.get("x", "") for i in st.get("items", []) if i.get("x"))
        print(f"  {int(time.time() - t0)}s: {json.dumps(info, ensure_ascii=False)[:200]}", flush=True)
    rec("live: Hebrew transcript from BlackHole" if voice else "live: transcript from BlackHole", bool(text),
        f"{int(time.time() - t0)}s: {text[:250] or info}")
    if text:
        words = ("מומנט", "ניוטון", "גלגלת") if voice else ("inertia", "Newton")
        hit = [w for w in words if w.lower() in text.lower()]
        rec("live: course words heard right", len(hit) >= 2, hit, main=False)
        out = mcp([("now", {})])
        rec("connector: 'now' sees the live lecture", any(w.lower() in out.get("now", "").lower() for w in words),
            (out.get("now") or str(out))[:250])
    cmd(action="stop")
    time.sleep(5)
    lib = get("/api/library")
    n = sum(1 for i in lib.get("items", []) if i.get("course") == COURSE)
    rec("live: saved in the course after stop", n >= 1 or not text, f"{n} lectures in {COURSE}")
    try:
        cmd(action="quit")
    except Exception:
        pass
    try:
        proc.wait(20)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()
    errs = os.path.join(APP, "error_log.txt")
    rec("no errors written", not os.path.isfile(errs), open(errs, encoding="utf-8", errors="replace").read()[-400:]
        if os.path.isfile(errs) else "", main=False)

# --- the table
rows = ["| | check | details |", "|---|---|---|"]
for name, ok, detail, main in results:
    mark = "✅" if ok else ("❌" if main else "⚠️")
    rows.append(f"| {mark} | {name} | {detail.replace('|', '/').replace(chr(10), ' ')} |")
table = "## Hevanti on a Mac\n\n" + "\n".join(rows) + "\n"
open(os.path.join(OUT, "results.md"), "w", encoding="utf-8").write(table)
if os.environ.get("GITHUB_STEP_SUMMARY"):
    open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8").write(table)
sys.exit(1 if any(not ok and main for _, ok, _, main in results) else 0)

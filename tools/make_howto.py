#!/usr/bin/env python3
"""Hevanti how-to video: a repeatable recording on Windows.

    python tools/make_howto.py prep      # clean sandbox: library with one course, private settings folder
    python tools/make_howto.py run       # starts Hevanti on the sandbox (for a look, or for the recording)
    python tools/make_howto.py captions  # re-builds the video from the raw footage and captions.json (no re-recording)

Nothing here touches the student's own library or settings: the sandbox lives under SANDBOX
(BZM_DATA_DIR and LOCALAPPDATA point there). The Gemini key is never printed or shown on screen.
"""
import json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PROG = os.path.join(REPO, "System", "Program", "live_transcribe.py")
SANDBOX = os.environ.get("HOWTO_SANDBOX") or os.path.join(os.environ.get("TEMP", "."), "hevanti-howto")
DATA = os.path.join(SANDBOX, "data")
LOCAL = os.path.join(SANDBOX, "local")
COURSE = "חשבון אינפיניטסימלי 2"
LIB = "הקורסים שלי"

OLD_LECTURE = """# תמלול הרצאה (עברית) - התחלה 2026-11-05 10:00
[10:00:05 | +0:00:05] היום נדבר על משוואות דיפרנציאליות מסדר ראשון.
[10:01:10 | +0:01:10] משוואה ניתנת להפרדת משתנים היא משוואה שאפשר לכתוב כך שכל המשתנים של y בצד אחד וכל המשתנים של x בצד השני.
[10:03:40 | +0:03:40] [סימון: חשוב]
[10:03:45 | +0:03:45] אחרי ההפרדה מבצעים אינטגרל על שני הצדדים ומוסיפים קבוע אחד.
[10:06:20 | +0:06:20] נפתור דוגמה: y' שווה x כפול y.
"""


def prep():
    """Fresh sandbox. The private settings (consent, key) are copied from the real folder without being read."""
    for _ in range(5):
        shutil.rmtree(SANDBOX, ignore_errors=True)
        if not os.path.exists(SANDBOX):
            break
        time.sleep(1)
    lec = os.path.join(DATA, LIB, COURSE, "2026-11-05 10-00 הרצאה")
    os.makedirs(lec)
    with open(os.path.join(lec, "2026-11-05 10-00 הרצאה.txt"), "w", encoding="utf-8") as f:
        f.write(OLD_LECTURE)
    real = os.path.join(os.environ["LOCALAPPDATA"], "Hevanti")
    mine = os.path.join(LOCAL, "Hevanti")
    os.makedirs(mine)
    for name in ("settings.json", "tessdata"):
        src = os.path.join(real, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(mine, name))
        elif os.path.isfile(src):
            shutil.copy2(src, os.path.join(mine, name))
    sp = os.path.join(mine, "settings.json")
    if os.path.isfile(sp):   # light theme, the demo course, no update check; every other value (the key) stays as it is
        with open(sp, encoding="utf-8") as f:
            s = json.load(f)
        s.update(theme="light", course=COURSE, check_updates=False)
        with open(sp, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False)
    print("sandbox ready:", SANDBOX)


def _real_models():
    """The student's own models folder (the sandbox has its own LOCALAPPDATA, and must not download the models again)."""
    sys.path.insert(0, os.path.dirname(PROG))
    import live_transcribe as L   # (computed with the real LOCALAPPDATA, before env() changes it for Hevanti)
    return L.MODEL_DIR


def env():
    e = dict(os.environ, PYTHONUTF8="1", BZM_DATA_DIR=DATA, LOCALAPPDATA=LOCAL, BZM_MODEL_DIR=_real_models(), BZM_NO_TOKEN="1")   # (no secret: this tool reads the API itself)
    e.pop("BZM_NO_BROWSER", None)
    return e


def run():
    return subprocess.Popen([sys.executable, PROG, "--app"], env=env(), cwd=REPO)


# ---------------------------------------------------------------------------------------------------------------
# Recording. Footage goes to OUT/raw.mkv, the moments of every chapter to OUT/events.json.
OUT = os.environ.get("HOWTO_OUT") or os.path.join(SANDBOX, "out")
LECTURE = "https://www.youtube.com/watch?v=F1_uOZeYLVE&t=120s"   # Dvir Ross, CC BY (credit: #howcredit in app.html)
PREROLL = int(os.environ.get("HOWTO_PREROLL", "480"))   # seconds the lecture runs before the questions ("what I missed" needs minutes)
BASE = "http://127.0.0.1:8765"
FF = shutil.which("ffmpeg") or "ffmpeg"


def api(path, body=None):
    import urllib.request
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "X-BZM": "1"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


class Rec:
    def __init__(self):
        os.makedirs(OUT, exist_ok=True)
        self.events, self.t0, self.proc = {}, None, None

    def start(self):
        self.proc = subprocess.Popen([FF, "-y", "-loglevel", "error", "-f", "gdigrab", "-framerate", "25", "-draw_mouse", "1",
                                      "-offset_x", "0", "-offset_y", "0", "-video_size", "1920x1080", "-i", "desktop",
                                      "-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "19", "-b:v", "0", "-pix_fmt", "yuv420p",
                                      os.path.join(OUT, "raw.mkv")], stdin=subprocess.PIPE)
        self.t0 = time.time()

    def now(self):
        return round(time.time() - self.t0, 2)

    def mark(self, name):
        self.events[name] = self.now()
        print(f"[{self.now():7.1f}s] {name}", flush=True)

    def stop(self):
        try:
            self.proc.stdin.write(b"q")
            self.proc.stdin.flush()
        except OSError:
            pass
        self.proc.wait(timeout=60)
        ev = dict(self.events, intrusions=getattr(self, "intrusions", []))
        with open(os.path.join(OUT, "events.json"), "w", encoding="utf-8") as f:
            json.dump(ev, f, indent=1)


def shot(name):
    """A still of the screen, for checking a step (kept in OUT/shots)."""
    d = os.path.join(OUT, "shots")
    os.makedirs(d, exist_ok=True)
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "gdigrab", "-video_size", "1920x1080", "-i", "desktop", "-frames:v", "1",
                    os.path.join(d, name + ".png")])


def record():
    import howto_win as w
    from playwright.sync_api import sync_playwright
    prep()
    rec = Rec()

    rec.intrusions = []

    def pause(sec):
        """Waits, and notes (never touches) any other window that shows on the recorded screen."""
        end = time.time() + sec
        while True:
            try:
                f = w.foreign() if rec.t0 else []
            except Exception:
                f = []
            if f:
                rec.intrusions.append([rec.now(), f])
            left = end - time.time()
            if left <= 0:
                break
            time.sleep(min(1.0, left))

    hv = lec = app = None
    NOAUTO = ["--enable-automation", "--no-sandbox"]
    with sync_playwright() as pw:
        try:
            # the lecture: a full-screen window behind everything, so nothing of the student's desktop is ever filmed
            lec = pw.chromium.launch(channel="msedge", headless=False, ignore_default_args=NOAUTO,
                                     args=["--window-position=0,0", "--window-size=1536,864", "--autoplay-policy=no-user-gesture-required",
                                           "--disable-blink-features=AutomationControlled"])
            ctx = lec.new_context(no_viewport=True)
            lp = ctx.new_page()
            cdp = lec.new_browser_cdp_session()

            def lecture(at=None):
                """(Re)opens the lecture, full screen, the player filling the window. `at`: second to start from."""
                lp.goto(LECTURE if at is None else LECTURE.split("&t=")[0] + f"&t={int(at)}s")
                lp.wait_for_selector("video", timeout=30000)
                pause(3)
                for sel in ("button:has-text('Reject all')", "button:has-text('דחיית הכול')"):
                    try:
                        lp.click(sel, timeout=1200)
                    except Exception:
                        pass
                tid = ctx.new_cdp_session(lp).send("Target.getTargetInfo")["targetInfo"]["targetId"]
                wid = cdp.send("Browser.getWindowForTarget", {"targetId": tid})["windowId"]
                cdp.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"windowState": "fullscreen"}})
                lp.add_style_tag(content="#masthead-container,#secondary,#below,#guide,ytd-miniplayer,tp-yt-iron-overlay-backdrop{display:none!important}"
                                 "#movie_player{position:fixed!important;inset:0!important;width:100vw!important;height:100vh!important;z-index:99999!important;background:#000}"
                                 "body{overflow:hidden!important}")
                lp.evaluate("window.dispatchEvent(new Event('resize'))")

            def watch():
                """YouTube sometimes shows 'something went wrong' to a browser it drives: reload from where it was."""
                try:
                    if lp.evaluate("!!document.querySelector('.ytp-error') && getComputedStyle(document.querySelector('.ytp-error')).display!='none'"):
                        pos = lp.evaluate("document.querySelector('video').currentTime") or 120
                        print("lecture player error: reloading at", int(pos), flush=True)
                        lecture(pos)
                        lp.evaluate("document.querySelector('video').play()")
                except Exception as e:
                    print("watch:", e, flush=True)

            def wait_to(t):
                while rec.now() < t:
                    pause(3)
                    watch()

            lecture()
            pause(5)   # (the browser's "Esc to leave full screen" note goes away)
            lp.evaluate("document.querySelector('video').pause()")
            shot("00_lecture")
            rec.start()
            pause(2)

            # chapter 2: the quick-start window
            hv = run()
            q = w.find("חלון התחלה מהירה", timeout=60)
            assert q, "the quick-start window did not open"
            pause(1.5)
            l, t, r, b = q[3]
            rec.mark("c2")
            shot("01_quick")
            pause(2.5)
            lp.evaluate("document.querySelector('video').play()")   # the lecture starts as the student presses Start
            w.click(l + int((r - l) * 0.50), t + int((b - t) * 0.73))   # "התחל תמלול"
            pause(3)
            rec.mark("c2_end")

            # chapter 4: the lecture full screen and the round button at the edge of the screen
            pause(1.5)
            rec.mark("c4")
            btn = w.find(None, "HevantiMiniButton", timeout=10)
            shot("05_fullscreen")
            pause(5)
            rec.mark("c4_end")

            # the lecture runs: transcript, slides and "what I missed" need minutes of it
            wait_to(PREROLL - 70)

            # chapters 3 and 1: the app (tip, live page), then the key box in the settings
            app = pw.chromium.launch_persistent_context(os.path.join(SANDBOX, "edge"), channel="msedge", headless=False, no_viewport=True,
                                                        ignore_default_args=NOAUTO,
                                                        args=["--app=" + BASE + "/", "--window-size=1300,800", "--window-position=120,40"])
            ap = app.pages[0]
            pause(3)
            shot("02b_tip")
            pause(2.5)
            ap.click("#liveTipOk", timeout=5000)
            pause(0.8)
            ap.click("#runBack", timeout=5000)
            pause(1.0)
            rec.mark("c3")
            pause(10)
            shot("03_live")
            rec.mark("c3_end")
            ap.click('[data-nav="settings"]', timeout=5000)
            pause(1.2)
            rec.mark("c1")
            pause(5)
            shot("04_key")
            rec.mark("c1_end")
            app.close()
            app = None
            watch()
            wait_to(PREROLL)

            # chapter 5: click the button, write a question
            btn = w.find(None, "HevantiMiniButton", timeout=10) or btn
            l, t, r, b = btn[3]
            rec.mark("c5")
            w.click((l + r) // 2, (t + b) // 2)
            pause(2)
            mini = w.windows(lambda t, c: t.strip("‪‫‬") == "הבנתי")
            print("mini windows:", [(x[1], x[3]) for x in mini], flush=True)
            shot("06_mini")
            w.type_text("מה זה הפרדת משתנים, ואיך עושים את זה?")
            pause(0.6)
            shot("07_typed")
            w.combo("enter")
            pause(2)
            rec.mark("c5_end")

            # chapter 6: the answer
            rec.mark("c6")
            pause(26)
            shot("08_answer")
            rec.mark("c6_end")

            # chapter 7: "what did I miss" - 7 minutes
            ml, mt, mr, mb = mini[0][3]
            rec.mark("c7")
            w.click(ml + int((mr - ml) * 0.56), mt + int((mb - mt) * 0.21))
            pause(32)
            shot("09_missed")
            rec.mark("c7_end")

            # chapter 8: mark a moment with the keyboard, then close the small window with the round button
            rec.mark("c8")
            w.combo("ctrl", "alt", "m")
            pause(3)
            shot("10_marked")
            w.click((l + r) // 2, (t + b) // 2)
            pause(2.5)
            rec.mark("c8_end")
            api("/api/cmd", {"action": "stop"})
            pause(8)

            # chapters 9 and 10: the course page, the marks; chapter 11: privacy in the settings
            lp.evaluate("document.querySelector('video').pause()")
            app = pw.chromium.launch_persistent_context(os.path.join(SANDBOX, "edge"), channel="msedge", headless=False, no_viewport=True,
                                                        ignore_default_args=NOAUTO,
                                                        args=["--app=" + BASE + "/", "--window-size=1300,800", "--window-position=120,40"])
            ap = app.pages[0]
            pause(3)
            try:
                ap.click("#liveTipOk", timeout=1500)
            except Exception:
                pass
            ap.click("#courseOpen", timeout=8000)
            pause(2.5)
            rec.mark("c9")
            pause(4)
            shot("11_course")
            rec.mark("c9_end")
            ap.click('[data-ct="marks"]', timeout=5000)
            pause(1.5)
            rec.mark("c10")
            pause(4)
            shot("12_marks")
            rec.mark("c10_end")
            ap.click('[data-nav="settings"]', timeout=5000)
            pause(1)
            ap.get_by_text("פרטיות", exact=True).first.click(timeout=5000)
            pause(1.5)
            rec.mark("c11")
            pause(7)
            shot("13_privacy")
            rec.mark("c11_end")
            app.close()
            app = None
        finally:
            try:
                rec.stop()
            except Exception as e:
                print("stop rec:", e)
            for h in (app, lec):
                try:
                    h and h.close()
                except Exception:
                    pass
            if hv:
                hv.terminate()


# ---------------------------------------------------------------------------------------------------------------
# Build: raw footage + captions.json -> draft video. Re-run after changing a caption; nothing is re-recorded.
FONT = os.path.join(REPO, "System", "Program", "fonts", "SecularOne-Regular.ttf")
BAR = 120
CRF = os.environ.get("HOWTO_CRF", "24")


def _ff(*args):
    r = subprocess.run([FF, "-y", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:])


def _wrap(text, limit=46):
    """Two lines at most, broken at a space near the middle when the line is long."""
    if len(text) <= limit:
        return text
    sp = [i for i, c in enumerate(text) if c == " "]
    cut = min(sp, key=lambda i: abs(i - len(text) / 2))
    return text[:cut] + "\n" + text[cut + 1:]


def _caption_png(text, path):
    """The caption bar as a picture: the text is drawn by Chrome, so Hebrew, Latin words and numbers are in the right order."""
    from playwright.sync_api import sync_playwright
    lines = _wrap(text).split("\n")
    html = ("<meta charset=utf-8><style>@font-face{font-family:S;src:url('file:///%s')}"
            "html,body{margin:0;width:1920px;height:%dpx;background:#17261F}"
            "div{height:%dpx;display:flex;flex-direction:column;align-items:center;justify-content:center;direction:rtl;"
            "font:400 %dpx/1.15 S;color:#F6F3E9;text-align:center}</style><div>%s</div>"
            % (FONT.replace("\\", "/"), BAR, BAR, 54 if len(lines) == 1 else 44, "<br>".join(lines)))
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1920, "height": BAR})
        pg.set_content(html)
        pg.wait_for_timeout(300)
        pg.screenshot(path=path)
        b.close()


def _slide_png(path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1920, "height": 960})
        pg.goto("file:///" + os.path.join(HERE, "howto", "slide.html").replace("\\", "/"))
        pg.wait_for_timeout(600)
        pg.screenshot(path=path)
        b.close()


def build(out_name="howto_draft.mp4"):
    ev = json.load(open(os.path.join(OUT, "events.json"), encoding="utf-8"))
    bad = ev.pop("intrusions", [])
    for cid in [k for k in ev if k.endswith("_end")]:
        c0 = cid[:-4]
        hits = [(t, f) for t, f in bad if ev[c0] - 1 <= t <= ev[cid] + 1]
        if hits:
            print("WARNING: another window was on screen during", c0, ":", hits[0][1][:2])
    chapters = json.load(open(os.path.join(HERE, "howto", "captions.json"), encoding="utf-8"))["chapters"]
    raw = os.path.join(OUT, "raw.mkv")
    tmp = os.path.join(OUT, "parts")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    flat = []
    for ch in chapters:   # a chapter with "parts" is shown as several pictures of the same take, one after the other
        if "parts" in ch:
            off = 0.0
            for i, pt in enumerate(ch["parts"]):
                flat.append(dict(ch, **pt, sub=f"{ch['id']}_{i}", mode="head", off=off, parts=None))
                off += float(pt["dur"])
        else:
            flat.append(dict(ch, sub=ch["id"], off=0.0))
    parts, t_at, times = [], 0.0, []
    for ch in flat:
        cid, texts = ch["id"], ch["text"] if isinstance(ch["text"], list) else [ch["text"]]
        dur = float(ch["dur"])
        base = os.path.join(tmp, ch["sub"])
        if ch["mode"] == "slide":
            _slide_png(base + "_src.png")
            _ff("-loop", "1", "-t", str(dur), "-i", base + "_src.png", "-vf", "fps=25,format=yuv420p", "-an", base + "_body.mp4")
        else:
            a, b = ev[cid] + ch["off"], ev[cid + "_end"]
            vf_t = {"head": (a, a + dur, 1.0), "tail": (max(a, b - dur), b, 1.0), "fit": (a, b, dur / max(b - a, 0.1))}[ch["mode"]]
            x, y, w_, h_ = ch["crop"]
            vf = (f"trim=start={vf_t[0]}:end={vf_t[1]},setpts=(PTS-STARTPTS)*{vf_t[2]},crop={w_}:{h_}:{x}:{y},"
                  f"scale=1920:960:flags=lanczos,fps=25,format=yuv420p")
            _ff("-i", raw, "-vf", vf, "-t", str(dur), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", base + "_body.mp4")
        # the caption bar on top (one picture per sentence, shown in turn)
        seg = dur / len(texts)
        clip = base + "_body.mp4"
        for i, tx in enumerate(texts):
            png = f"{base}_cap{i}.png"
            _caption_png(tx, png)
        if len(texts) == 1:
            fc = "[0:v][1:v]vstack=inputs=2,format=yuv420p"
            _ff("-i", clip, "-loop", "1", "-t", str(dur), "-i", base + "_cap0.png", "-filter_complex", "[1:v]fps=25[c];[c][0:v]vstack=inputs=2,format=yuv420p",
                "-t", str(dur), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", base + ".mp4")
        else:
            ins, fcs = ["-i", clip], []
            for i in range(len(texts)):
                ins += ["-loop", "1", "-t", str(dur), "-i", f"{base}_cap{i}.png"]
            expr = "[1:v][2:v]" if len(texts) == 2 else ""
            fcs = (f"[1:v]fps=25,trim=0:{seg},setpts=PTS-STARTPTS[c0];[2:v]fps=25,trim=0:{seg},setpts=PTS-STARTPTS[c1];"
                   f"[c0][c1]concat=n=2:v=1:a=0[caps];[caps][0:v]vstack=inputs=2,format=yuv420p")
            _ff(*ins, "-filter_complex", fcs, "-t", str(dur), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", base + ".mp4")
        parts.append(base + ".mp4")
        times.append((ch["sub"], round(t_at, 1)))
        t_at += dur
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        f.write("".join(f"file '{p.replace(chr(92), '/')}'\n" for p in parts))
    out = os.path.join(OUT, out_name)
    _ff("-f", "concat", "-safe", "0", "-i", lst, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", CRF, "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", out)
    json.dump(times, open(os.path.join(OUT, "chapter_times.json"), "w"))
    fr = os.path.join(OUT, "frames")
    shutil.rmtree(fr, ignore_errors=True)
    os.makedirs(fr)
    for cid, t0 in times:   # a still of every chapter (a second in)
        _ff("-ss", str(t0 + 1.5), "-i", out, "-frames:v", "1", os.path.join(fr, cid + ".png"))
    print("draft:", out, round(os.path.getsize(out) / 1e6, 2), "MB; chapter starts:", times)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "prep":
        prep()
    elif cmd == "record":
        sys.path.insert(0, HERE)
        record()
    elif cmd == "build":
        build()
    elif cmd == "run":
        p = run()
        print("pid", p.pid)
    else:
        print(__doc__)

"""בדיקת איחור בתמלול חי: אותה הרצאה פעמיים, פעם בקטעים הקצרים (כמו קודם) ופעם בקטעים הארוכים (החדשים), ורושמת כל דקה את האיחור.

Two live runs of the same lecture on this computer, one with the old 10-18 s pieces and one with the new 20-28 s pieces, and a line for every
minute: the lag, how hard Whisper works, the CPU load and speed. It runs a separate copy of Hevanti (its own data folder, so the library and the
settings of the student are never touched), plays the file through the speakers (the sound is heard: headphones are fine) and listens to it
the way a real lecture is heard. Run it with run-lag-test.bat. About 50 minutes for 20 minutes of lecture.

  python lag_run.py [file] [minutes=20]      (LAGTEST_COOL_S: the rest between the runs, default 300 seconds)"""
import ctypes
import datetime
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PROG = os.path.join(os.path.dirname(os.path.dirname(HERE)), "System", "Program")
MODELS = os.environ.get("BZM_MODEL_DIR") or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Hevanti", "models")
URL = "http://127.0.0.1:8765"
RUNS = (("old", "קטעים קצרים (10 עד 18 שניות, כמו קודם)", {"LT_CPU_MIN_CHUNK_S": "10", "LT_CPU_MAX_CHUNK_S": "18"}),
        ("new", "קטעים ארוכים (20 עד 28 שניות, החדשים)", {}))

PLAY_PS1 = r"""Add-Type -AssemblyName presentationCore
$p = New-Object System.Windows.Media.MediaPlayer
$p.Open([uri]$args[0])
$t0 = Get-Date
while (-not $p.NaturalDuration.HasTimeSpan -and ((Get-Date) - $t0).TotalSeconds -lt 15) { Start-Sleep -Milliseconds 200 }
$dur = 0; if ($p.NaturalDuration.HasTimeSpan) { $dur = $p.NaturalDuration.TimeSpan.TotalSeconds }
$start = [double]$args[2]; $len = [double]$args[1]
if ($dur -gt 0 -and $start + $len -gt $dur) { $start = [Math]::Max(0, $dur - $len - 5) }
$p.Position = [TimeSpan]::FromSeconds($start); $p.Volume = 0.7; $p.Play()
$end = (Get-Date).AddSeconds($len)
while ((Get-Date) -lt $end) { Start-Sleep -Milliseconds 300 }
$p.Stop()
"""


class FT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_uint32), ("h", ctypes.c_uint32)]


def cpu_times():
    i, k, u = FT(), FT(), FT()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
    f = lambda x: (x.h << 32) | x.l
    return f(i), f(k) + f(u)   # (idle, all): the kernel time already holds the idle time


def cpu_speed():
    """The speed of the processor as a share of its base speed (above 100 = faster than base, below = slowed by heat or the power limit)."""
    try:
        out = subprocess.run(["typeperf", r"\Processor Information(_Total)\% Processor Performance", "-sc", "1"], capture_output=True, text=True, timeout=15).stdout
        for line in out.splitlines():
            parts = [p.strip().strip('"') for p in line.split('","')]
            if len(parts) == 2:
                try:
                    return round(float(parts[1].strip('"')))
                except ValueError:
                    pass
    except Exception:
        pass
    return None


def get(path):
    return json.load(urllib.request.urlopen(urllib.request.Request(URL + path), timeout=10))


def post(path, data):
    r = urllib.request.Request(URL + path, data=json.dumps(data).encode(), headers={"X-BZM": "1", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=20))


def live():
    try:
        return get("/api/live")
    except Exception:
        return {}


def say(text):
    print(text, flush=True)


def video_seconds(path):
    try:
        import av
        with av.open(path) as c:
            return c.duration / 1_000_000 if c.duration else 0
    except Exception:
        return 0


def one_run(label, title, extra_env, video, minutes, out_dir, player_ps1):
    data = os.path.join(out_dir, "data-" + label)
    local = os.path.join(out_dir, "local-" + label)
    shutil.rmtree(data, ignore_errors=True)
    shutil.rmtree(local, ignore_errors=True)
    os.makedirs(data)
    os.makedirs(local)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", BZM_DATA_DIR=data, LOCALAPPDATA=local, BZM_MODEL_DIR=MODELS,
               BZM_NO_BROWSER="1", BZM_NO_TOKEN="1", LT_SCREENS="0")
    for k in ("LT_CPU_THREADS", "LT_CPU_MIN_CHUNK_S", "LT_CPU_MAX_CHUNK_S", "LT_QUICK_DRAFT"):
        env.pop(k, None)
    env.update(extra_env)
    say(f"\n=== {title} ===")
    srv = subprocess.Popen([sys.executable, os.path.join(PROG, "live_transcribe.py"), "--app"], cwd=PROG, env=env,
                           stdout=open(os.path.join(out_dir, f"server-{label}.log"), "w", encoding="utf-8"), stderr=subprocess.STDOUT)
    player = None
    rows = []
    try:
        for _ in range(90):
            try:
                get("/api/app")
                break
            except Exception:
                time.sleep(1)
        else:
            say("הבנתי לא עלתה. הבדיקה נעצרת.")
            return None
        post("/api/cmd", {"action": "start_live", "lang": "he", "course": "בדיקת איחור"})
        say("טוען את מודל התמלול...")
        for _ in range(300):
            if not live().get("none", True):
                break
            time.sleep(1)
        time.sleep(45)   # the quick draft takes a short while to get ready: the lecture starts when it is
        length = minutes * 60
        if os.environ.get("LAGTEST_EXTERNAL"):   # the lecture plays somewhere else (a browser): say when to start it, and wait until its sound arrives
            with open(os.path.join(out_dir, "ready-" + label), "w") as f:
                f.write("ready")
            say("מוכן לקול: להתחיל את ההרצאה עכשיו.")
            for _ in range(180):
                if (live().get("pending") or 0) > 0 or live().get("total"):
                    break
                time.sleep(1)
            else:
                say("לא הגיע קול להבנתי. לבדוק שההרצאה מתנגנת ושהרמקולים לא מושתקים.")
                return None
        for attempt in (1, 2) if not os.environ.get("LAGTEST_EXTERNAL") else ():
            player = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", player_ps1, video, str(length + 30), "60"])
            for _ in range(40):
                if (live().get("pending") or 0) > 0 or live().get("total"):
                    break
                time.sleep(1)
            else:
                subprocess.run(["taskkill", "/PID", str(player.pid), "/T", "/F"], capture_output=True)
                player = None
                continue
            break
        if player is None and not os.environ.get("LAGTEST_EXTERNAL"):
            say("לא הגיע קול להבנתי. לבדוק שהרמקולים לא מושתקים ושההרצאה מתנגנת, ולנסות שוב.")
            return None
        say(f"ההרצאה מתנגנת. הבדיקה נמשכת {minutes} דקות. אפשר להמשיך לעבוד, אבל עדיף לא להכביד על המחשב.")
        t_start = time.time()
        i0, t0 = cpu_times()
        for minute in range(1, minutes + 1):
            while time.time() - t_start < minute * 60:
                time.sleep(1)
            i1, t1 = cpu_times()
            cpu = round(100 * (1 - (i1 - i0) / max(1, t1 - t0)))
            i0, t0 = i1, t1
            st = live()
            row = {"minute": minute, "lag": st.get("lag"), "lag_show": st.get("lag_show"), "pending": st.get("pending"), "load": st.get("load"),
                   "lines": st.get("total"), "cpu": cpu, "speed": cpu_speed()}
            rows.append(row)
            say(f"  דקה {minute:2d}: איחור {row['lag']} שניות, עבודה {row['load']} (מתחת ל-1 עומד בקצב), מעבד {cpu}%, מהירות המעבד {row['speed']}%")
            if minute == 3 and not (row["lines"] or 0):
                say("אחרי 3 דקות אין תמלול בכלל. כנראה הקול מושתק. הבדיקה נעצרת.")
                return None
        return rows
    finally:
        for p in (player, srv):
            if p is not None:
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
        time.sleep(3)


def summarize(label, title, rows):
    lags = [r["lag"] for r in rows if r["lag"] is not None]
    loads = [r["load"] for r in rows if r["load"]]
    speeds = [r["speed"] for r in rows if r["speed"]]
    late = sum(1 for r in rows if r["lag"] is not None and r["lag_show"] and r["lag"] > r["lag_show"])
    first, last = lags[: max(1, len(lags) // 4)], lags[-max(1, len(lags) // 4):]
    trend = statistics.mean(last) - statistics.mean(first)
    lines = [f"{title}",
             f"  איחור: ממוצע {statistics.mean(lags):.0f} שניות, הכי גבוה {max(lags):.0f}",
             f"  ברבע הראשון {statistics.mean(first):.0f} שניות, ברבע האחרון {statistics.mean(last):.0f} שניות: " +
             ("האיחור עולה" if trend > 3 else "האיחור יורד" if trend < -3 else "האיחור יציב"),
             f"  עבודה לכל שנייה של הרצאה (מתחת ל-1 עומד בקצב): חציוני {statistics.median(loads):.2f}" if loads else "  עבודה: אין נתון",
             f"  \"מאחר\" היה מופיע בחלון הצף ב-{late} מתוך {len(rows)} דקות"]
    if speeds:
        lines.append(f"  מהירות המעבד: בדקה הראשונה {speeds[0]}%, בסוף {speeds[-1]}%, הנמוכה ביותר {min(speeds)}%")
    return "\n".join(lines), statistics.mean(lags)


def main():
    video = sys.argv[1].strip('"') if len(sys.argv) > 1 else input("לגרור לכאן קובץ הרצאה בעברית (וידאו או שמע, לפחות 25 דקות) ולהקיש Enter: ").strip().strip('"')
    minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    cool = int(os.environ.get("LAGTEST_COOL_S") or 300)
    if not os.path.isfile(video) and not os.environ.get("LAGTEST_EXTERNAL"):
        sys.exit("הקובץ לא נמצא: " + video)
    try:
        get("/api/app")
        sys.exit("הבנתי פתוחה עכשיו. לסגור אותה (גם את החלון השחור) ולהריץ שוב.")
    except SystemExit:
        raise
    except Exception:
        pass
    dur = 0 if os.environ.get("LAGTEST_EXTERNAL") else video_seconds(video)
    if dur and dur < minutes * 60 + 90:
        say(f"שימו לב: ההקלטה קצרה ({dur / 60:.0f} דקות), ובדיקה של {minutes} דקות צריכה יותר. הבדיקה תתנגן מהסוף ותיעצר כשההקלטה נגמרת.")
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M") + (("_" + os.environ["LAGTEST_ONLY"]) if os.environ.get("LAGTEST_ONLY") else "")
    out_dir = os.path.join(HERE, "results", stamp)
    os.makedirs(out_dir, exist_ok=True)
    ps1 = os.path.join(out_dir, "play.ps1")
    with open(ps1, "w", encoding="utf-8-sig") as f:
        f.write(PLAY_PS1)
    say("מוודא שאין עוד משהו כבד פתוח... לסגור דפדפנים ותוכנות אחרות ככל האפשר. המחשב צריך להיות מחובר לחשמל.")
    results, summary = {}, [f"בדיקת איחור בתמלול חי, {stamp}", f"קובץ: {os.path.basename(video)}, {minutes} דקות לכל ריצה", ""]
    only = os.environ.get("LAGTEST_ONLY")   # "old" or "new": a single run (when the lecture can be wound back by hand between them)
    for n, (label, title, extra) in enumerate(r for r in RUNS if only in (None, "", r[0])):
        rows = one_run(label, title, extra, video, minutes, out_dir, ps1)
        if not rows:
            summary.append(f"{title}: הריצה לא הושלמה")
            break
        results[label] = rows
        with open(os.path.join(out_dir, f"{label}.csv"), "w", encoding="utf-8-sig") as f:
            f.write("minute,lag_s,lag_show_s,pending_s,work_per_second,lines,cpu_percent,cpu_speed_percent\n")
            for r in rows:
                f.write(",".join(str(r[k]) for k in ("minute", "lag", "lag_show", "pending", "load", "lines", "cpu", "speed")) + "\n")
        text, _ = summarize(label, title, rows)
        summary += [text, ""]
        if n == 0 and cool:
            say(f"\nמנוחה של {cool // 60} דקות, כדי שהמעבד יתקרר לפני הריצה השנייה...")
            time.sleep(cool)
    if len(results) == 2:
        a = statistics.mean(r["lag"] for r in results["old"] if r["lag"] is not None)
        b = statistics.mean(r["lag"] for r in results["new"] if r["lag"] is not None)
        summary.append(f"סיכום: איחור ממוצע {a:.0f} שניות בקטעים הקצרים, {b:.0f} שניות בקטעים הארוכים.")
    path = os.path.join(out_dir, "summary.txt")
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(summary) + "\n")
    say("\n" + "\n".join(summary))
    say(f"\nהתוצאות נשמרו ב: {out_dir}")
    say("לשלוח לקלוד את הקובץ summary.txt ואת שני קבצי ה-csv שבתיקייה.")


if __name__ == "__main__":
    main()

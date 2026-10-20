# -*- coding: utf-8 -*-
# הבנתי (Hevanti) - lectures, transcribed live or from a recording
# Copyright (c) 2026 Roei Pechter (רועי פכטר). MIT License, see LICENSE.txt
"""
Lecture transcription (Hebrew / English), live or recorded - run from the app page in the browser.
Hevanti.bat starts the tool and opens the app (http://127.0.0.1:8765/, this computer only).
Every lecture is one folder: "הקורסים שלי/<course>/<lecture>/" with "<lecture>.txt" and "שקופיות/".
Live: captures whatever audio the computer plays (WASAPI loopback - no microphone), transcribes it with
Whisper (ivrit.ai Hebrew model), and takes a screenshot whenever the screen changes noticeably
(new slide, new writing on the board).
Recorded: a recording (file, drag-and-drop or link) is transcribed in advance with its own times, slides
are saved from the video, and it plays in the tool's player page, which tells the tool where you are.
In both, now_watching.txt says what is happening right now, for the AI.
The black window stays open (minimized) while the tool runs; closing it stops the tool.
"""
import os
import re
import sys
import time
import queue
import threading
import datetime
import traceback
import collections
import json

import warnings
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
warnings.filterwarnings("ignore", message=".*symlinks.*")
warnings.filterwarnings("ignore", message=".*unauthenticated.*")
warnings.filterwarnings("ignore", category=DeprecationWarning)  # library notices, not for users
warnings.filterwarnings("ignore", category=FutureWarning)

try:
    import numpy as np
except Exception:  # lets "uninstall" run even if the install never finished
    np = None

VERSION = "2.1"
VERSION_DATE = "15.10.2026"
PRODUCT = "הבנתי"
GUIDE_URL = "https://claude.ai/artifact/Rho2yLpowLsxqy1Zsw6QAD"

# ---------------- settings ----------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _tool_root(d):
    """The tool folder: the script sits in System/Program (2.0), Program (1.3-1.4) or directly in it."""
    if os.path.basename(d).lower() == "program":
        d = os.path.dirname(d)
        if os.path.basename(d).lower() == "system":
            d = os.path.dirname(d)
    return d


HERE = _tool_root(SCRIPT_DIR)
IS_MAC = sys.platform == "darwin"   # the Mac version: Hevanti.command, the sound through BlackHole
SYSTEM_DIR = os.path.dirname(SCRIPT_DIR) if os.path.basename(os.path.dirname(SCRIPT_DIR)).lower() == "system" else HERE
ERROR_LOG = os.path.join(SYSTEM_DIR, "error_log.txt")
STUCK_LOG = os.path.join(SYSTEM_DIR, "loading_stuck.txt")   # written only when loading the model hangs
LIB_NAME = "הקורסים שלי"
OLD_LIB_NAMES = ("ההרצאות שלי",)   # the folder's name before 16.10.2026 - renamed on the first start
# Installed with Hevanti-Setup.exe (a Python of its own next to System\): the lectures go to Documents\הבנתי,
# not into the program's folder. From the ZIP: next to Hevanti.bat.
INSTALLED = os.path.isfile(os.path.join(HERE, "python", "python.exe"))


def _documents():
    if os.name == "nt":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(520)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:  # CSIDL_PERSONAL
                return buf.value
        except Exception:
            pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def _has_lectures(lib):
    """True when this "הקורסים שלי" folder holds at least one lecture (or a course folder)."""
    try:
        return any(not n.startswith(".") and os.path.isdir(os.path.join(lib, n)) for n in os.listdir(lib))
    except OSError:
        return False


def _earlier_library():
    """The "הקורסים שלי" (or older "ההרצאות שלי") folder an earlier copy of Hevanti (the ZIP) used, from the AI connector it set up -
    so moving to Hevanti-Setup keeps the student's lectures instead of starting with an empty library."""
    found = []
    homes = [os.environ.get("APPDATA", ""), os.path.join(os.path.expanduser("~"), ".gemini", "config"),
             os.path.join(os.path.expanduser("~"), ".gemini")]
    names = [os.path.join(homes[0], "Claude", "claude_desktop_config.json"),
             os.path.join(homes[1], "mcp_config.json"), os.path.join(homes[2], "settings.json")]
    for p in names:
        try:
            with open(p, encoding="utf-8-sig") as f:
                entry = (json.load(f).get("mcpServers") or {}).get("hevanti") or {}
            args = entry.get("args") or []
            lib = args[args.index("--lib") + 1] if "--lib" in args else ""
        except (OSError, ValueError, AttributeError, IndexError):
            continue
        if lib and os.path.basename(lib.rstrip("\\/")) in (LIB_NAME,) + OLD_LIB_NAMES and _has_lectures(lib):
            found.append(os.path.dirname(lib.rstrip("\\/")))
    return found[0] if found else None


def _data_dir():
    if os.environ.get("BZM_DATA_DIR"):
        return os.environ["BZM_DATA_DIR"]
    if not INSTALLED:
        return HERE
    # Hevanti-Setup: Documents\הבנתי - unless the student already has lectures from the ZIP version: keep using them.
    keep = os.path.join(os.environ.get("LOCALAPPDATA") or HERE, "Hevanti", "data_dir.txt")
    try:
        with open(keep, encoding="utf-8") as f:
            d = f.read().strip()
        if d and os.path.isdir(d):
            return d
    except OSError:
        pass
    d = os.path.join(_documents(), "הבנתי")
    if not any(_has_lectures(os.path.join(d, n)) for n in (LIB_NAME,) + OLD_LIB_NAMES):
        d = _earlier_library() or d
    try:
        os.makedirs(os.path.dirname(keep), exist_ok=True)
        with open(keep, "w", encoding="utf-8") as f:
            f.write(d)
    except OSError:
        pass
    return d


DATA_DIR = _data_dir()


def _lib_dir(data_dir):
    """The courses folder. Its old name "ההרצאות שלי" is renamed to "הקורסים שלי" once; if Windows will not
    rename it (a file open in it, OneDrive busy), the old folder keeps being used and the rename is tried next time."""
    new = os.path.join(data_dir, LIB_NAME)
    if os.path.isdir(new):
        return new
    for old in OLD_LIB_NAMES:
        old = os.path.join(data_dir, old)
        if os.path.isdir(old):
            try:
                os.rename(old, new)
                return new
            except OSError:
                return old
    return new


LIB_DIR = _lib_dir(DATA_DIR)   # <course>/<lecture>/<lecture>.txt + שקופיות/
NO_COURSE = "ללא קורס"
SLIDES_NAME = "שקופיות"
GLOSSARY_NAME = "מילון מונחים.txt"
STATE_NAME = ".state.json"               # a recording's progress and your place, kept in its own folder
OUT_DIR = os.path.join(HERE, "transcripts")  # the 1.x layout - moved into LIB_DIR on the first start
# ASCII-only path for the model (CTranslate2 can fail on non-English Windows paths)
MODEL_DIR = os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "whisper_models")
if IS_MAC:
    MODEL_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Hevanti", "whisper_models")
# Language: "he" or "en" - chosen on the page for each lecture
LANG, MODELS = "he", []
TARGET_SR = 16000
MIN_CHUNK_S = 10     # earliest point to cut a chunk (seconds)
MAX_CHUNK_S = 18     # latest point to cut a chunk
GPU_MIN_CHUNK_S = 15 # on a GPU: longer chunks = more context = better accuracy
GPU_MAX_CHUNK_S = 26 #   (Whisper looks at up to 30 s at once)
SILENCE_RMS = 0.0015 # chunks quieter than this are skipped
FAST_ON_LAG_S = 10   # on a GPU, falling this far behind -> fast mode (1 option per sentence instead of 5)
FAST_OFF_LAG_S = 4   # caught up for 3 pieces in a row -> back to full accuracy
FAST_MAX_SWITCHES = 2  # after this many slow-downs, stay in fast mode for the rest of the lecture
LAG_WARN_S = 30      # warn when the transcript is this far behind (at most every 2 minutes)
DRAFTS = os.environ.get("LT_DRAFTS", "1") != "0"  # GPU only: quick draft line while a piece is still being heard
DRAFT_EVERY_S = 3    # refresh the draft this often
DRAFT_MIN_S = 2      # ...once at least this much new audio is waiting
DRAFT_MAX_LOAD = 0.4   # no drafts while the real text alone keeps the GPU busy 40%+ of the time
DRAFT_MAX_SHARE = 0.25  # drafts never take more than a quarter of the time
BATCH = os.environ.get("LT_BATCH", "1") != "0"  # GPU: when behind, transcribe everything waiting in one batch
PROMPTS = {
    "he": "הרצאה באוניברסיטה, בעברית, עם מונחים מקצועיים ומילים באנגלית.",
    "en": "University lecture.",
}
PROMPT = PROMPTS["he"]
# The course's words reach the model as "hotwords" (faster-whisper 1.0.2+): a part of the prompt of their own
# (up to ~223 tokens, the first ones kept), so they are not pushed out by the last words said, which fill the
# rest. The course name comes first, then the glossary in its order, and after the first 20 terms the words
# read from the newest slides (names, terms in English) - see set_slide_words.
TERMS = ""        # an old faster-whisper without hotwords: a short glossary inside the prompt instead
TERMS_MAX = 300   # (Whisper keeps only the END of a long prompt: the glossary must leave room for the last words said)
HOT_TERMS = []    # the course name + its glossary, most important first
SLIDE_WORDS = []  # words on the newest slides of this lecture (OCR), newest first
HOT_OK = False    # set when the model loads: this faster-whisper has hotwords (also in the batched pipeline?)
HOT_OK_BATCH = False
HOT_MAX = 700     # characters - the model keeps the first ~223 tokens of them anyway
HOT_SLIDE_AT = 20  # slide words come after this many glossary terms


def set_terms(words, course=""):
    """A new lecture: the course name and its glossary, so the model writes them correctly."""
    global TERMS, HOT_TERMS, SLIDE_WORDS
    clean, seen = [], set()
    first = [course] if course and course != NO_COURSE else []
    for w in first + list(words or []):
        w = " ".join(str(w).split())[:60]
        if w and w.lower() not in seen:
            seen.add(w.lower())
            clean.append(w)
    HOT_TERMS, SLIDE_WORDS = clean, []
    out, size = [], 0
    for w in clean:
        if size + len(w) + 2 > TERMS_MAX:
            continue
        out.append(w)
        size += len(w) + 2
    TERMS = ", ".join(out)


def set_slide_words(words):
    """Words read from the slide now on the screen (newest first, at most 15 used)."""
    global SLIDE_WORDS
    have = {w.lower() for w in HOT_TERMS}
    new = [w for w in words if w and w.lower() not in have]
    SLIDE_WORDS = list(dict.fromkeys(new + SLIDE_WORDS))[:40]


def hotwords_now():
    have = {w.lower() for w in HOT_TERMS}
    items = HOT_TERMS[:HOT_SLIDE_AT] + [w for w in SLIDE_WORDS if w.lower() not in have][:15] + HOT_TERMS[HOT_SLIDE_AT:]
    out, size = [], 0
    for w in items:
        if size + len(w) + 2 > HOT_MAX:
            break
        out.append(w)
        size += len(w) + 2
    return ", ".join(out)


def hot_kw(batched=False):
    """{"hotwords": ...} for model.transcribe, when this faster-whisper has them."""
    if not (HOT_OK_BATCH if batched else HOT_OK):
        return {}
    h = hotwords_now()
    return {"hotwords": h} if h else {}


def prompt_now(batched=False):
    if (HOT_OK_BATCH if batched else HOT_OK) or not TERMS:
        return PROMPT   # the glossary goes in as hotwords
    return PROMPT + (" מונחים בקורס: " if LANG == "he" else " Terms: ") + TERMS + "."


def set_language(lang):
    global LANG, MODELS, PROMPT
    LANG = "en" if str(lang).strip().lower() == "en" else "he"
    if LANG == "en":
        MODELS = [os.environ.get("LT_MODEL", "large-v3-turbo")]  # multilingual Whisper, strong in English
    else:
        MODELS = [
            os.environ.get("LT_MODEL", "ivrit-ai/whisper-large-v3-turbo-ct2"),  # Hebrew-tuned
            "large-v3-turbo",                                                   # fallback
        ]
    PROMPT = PROMPTS[LANG]


set_language(os.environ.get("LT_LANG", "he"))
# Screen snapshots
SCREEN_ENABLED = os.environ.get("LT_SCREENS", "1") != "0"
SCREEN_DIR = os.path.join(HERE, "screenshots")
SCREEN_MONITOR = int(os.environ.get("LT_MONITOR", "1"))  # 1 = main screen
SCREEN_CHECK_S = 3       # look at the screen every 3 s
SCREEN_BIG_FRAC = 0.15   # >=15% of the screen changed = new slide / page
SCREEN_BIG_GAP_S = 5     #   ...save at most every 5 s
SCREEN_SMALL_FRAC = 0.03 # >=3% changed = new writing, small change
SCREEN_SMALL_GAP_S = 30  #   ...save at most every 30 s (avoids saving every frame of a video)
YT_SETTLE_S = 1.2        # a video: wait this long after a change before saving (a seek is reported by then)
# ------------------------------------------

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
if os.name == "nt":  # started from the installer's shortcut there is no "chcp 65001": set it here
    try:
        import ctypes as _ct
        _ct.windll.kernel32.SetConsoleOutputCP(65001)
        _ct.windll.kernel32.SetConsoleTitleW("Hevanti - הבנתי")
    except Exception:
        pass


# ---------- Hebrew in the black window ----------
# The Windows console draws every line left-to-right, so Hebrew comes out
# reversed. show() reorders each line for display only (files stay normal),
# wraps it to the window width and aligns it to the right.
_MIRROR = str.maketrans("()[]{}<>", ")(][}{><")
RTL_CONSOLE = os.environ.get("LT_RTL_CONSOLE", "1") != "0"


def _is_rtl(ch):
    return "\u0590" <= ch <= "\u05ff" or "\ufb1d" <= ch <= "\ufb4f"


def _cls(ch):
    if _is_rtl(ch):
        return "R"
    if ch.isalnum():
        return "L"
    return "N"


def visual_rtl(line):
    """Logical -> visual order for one line of mostly-Hebrew text."""
    if not any(_is_rtl(c) for c in line):
        return line
    runs = []  # [cls, text]
    for ch in line:
        c = _cls(ch)
        if runs and runs[-1][0] == c:
            runs[-1][1] += ch
        else:
            runs.append([c, ch])
    # neutrals between two LTR runs stay LTR (10:25:44, x1.5, Ctrl+C), others follow Hebrew
    for i, r in enumerate(runs):
        if r[0] == "N":
            left = runs[i - 1][0] if i > 0 else "R"
            right = runs[i + 1][0] if i + 1 < len(runs) else "R"
            r[0] = "L" if (left == "L" and right == "L") else "R"
    merged = []
    for c, t in runs:
        if merged and merged[-1][0] == c:
            merged[-1][1] += t
        else:
            merged.append([c, t])
    out = []
    for c, t in reversed(merged):
        out.append(t[::-1].translate(_MIRROR) if c == "R" else t)
    return "".join(out)


_CON_LOCK = threading.RLock()  # one writer at a time (draft line + messages from other threads)
_DRAFT_ON = False


def _con_width():
    import shutil
    return max(40, shutil.get_terminal_size((100, 30)).columns - 1)


def draft_clear():
    """Erase the draft line, if one is showing."""
    global _DRAFT_ON
    with _CON_LOCK:
        if _DRAFT_ON:
            w = _con_width()
            sys.stdout.write("\r" + " " * w + "\r")
            sys.stdout.flush()
            _DRAFT_ON = False


def show_draft(text):
    """One line, rewritten in place, with the newest words of what is being said right now."""
    global _DRAFT_ON
    with _CON_LOCK:
        w = _con_width()
        body = " ".join(text.split())
        room = w - len("טיוטה: ") - 1
        if len(body) > room:
            body = "…" + body[-(room - 1):]
        line = "טיוטה: " + body
        vis = visual_rtl(line).rjust(w) if RTL_CONSOLE else line.ljust(w)
        sys.stdout.write("\r" + vis[:w])
        sys.stdout.flush()
        _DRAFT_ON = True


def show_status(text):
    """One line, rewritten in place (progress of a recording, "you are here")."""
    global _DRAFT_ON
    try:
        APP.set_progress(text)
    except NameError:
        pass
    with _CON_LOCK:
        w = _con_width()
        line = " ".join(text.split())[:w]
        vis = visual_rtl(line).rjust(w) if RTL_CONSOLE else line.ljust(w)
        sys.stdout.write("\r" + vis[:w])
        sys.stdout.flush()
        _DRAFT_ON = True


def show(text):
    if text and not set(str(text).strip()) <= {"="}:
        try:
            APP.add_note(text)
        except NameError:
            pass  # very early, before the app exists
    with _CON_LOCK:
        draft_clear()
        if not RTL_CONSOLE or not any(_is_rtl(c) for c in text):
            print(text, flush=True)
            return
        import textwrap
        width = _con_width()
        for logical in text.split("\n"):
            for part in (textwrap.wrap(logical, width) or [""]):
                print(visual_rtl(part).rjust(width), flush=True)


def log(msg):
    show(f"[{datetime.datetime.now():%H:%M:%S}] {msg}")


def show_lines(text):
    """Line by line: Hebrew lines in reading order (show), others as they are (tracebacks)."""
    for line in str(text).rstrip("\n").split("\n"):
        if RTL_CONSOLE and any(_is_rtl(c) for c in line):
            show(line)
        else:
            print(line, flush=True)


CLOSE_MSG = "לחיצה על מקש כלשהו תסגור את החלון."


def wait_key(text=CLOSE_MSG):
    """'Press any key to close' in Hebrew (the launcher opens the tool in its own window)."""
    show(text)
    try:
        import msvcrt
        msvcrt.getch()
    except BaseException:
        pass  # no keyboard (not Windows) or Ctrl+C again - just close


def wait_enter(text):
    """input() prints its prompt raw (reversed Hebrew) - print it with show() instead."""
    show(text)
    try:
        input()
    except Exception:
        pass


def save_error(context):
    """Add the current exception to error_log.txt (for problems the tool recovers from)."""
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.datetime.now()} (גרסה {VERSION}) {context} ---\n{traceback.format_exc()}")
    except Exception:
        pass


# ---------- Windows blocking a component (Smart App Control) ----------
def is_blocked(text):
    t = str(text)
    return "Application Control" in t or "4551" in t


def smart_app_control_state():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy")
        v, _ = winreg.QueryValueEx(k, "VerifiedAndReputablePolicyState")
        return {0: "כבוי", 1: "פעיל", 2: "במצב בדיקה"}.get(int(v), str(v))
    except Exception:
        return None


def blocked_component(tb):
    import re
    found = re.findall(r"site-packages[\\/]+([A-Za-z0-9_\-]+)", tb) or re.findall(r"importing ([A-Za-z0-9_]+)", tb)
    return found[-1] if found else "לא ידוע"


def block_text(tb):
    comp = blocked_component(tb)
    sac = smart_app_control_state()
    out = [f"Windows חסם רכיב שהכלי צריך: {comp}",
           "זו הגנה של Windows בשם Smart App Control. היא פעילה כברירת מחדל במחשבים חדשים עם Windows 11,",
           "וחוסמת קבצים שעדיין אין להם מספיק \"מוניטין\" אצל מיקרוסופט, גם כשהם בטוחים."]
    if sac:
        out.append(f"מצב Smart App Control במחשב הזה: {sac}")
    out += ["מה אפשר לעשות:",
            "1. לשלוח את הקובץ error_log.txt (או צילום מסך) למי ששיתף איתך את הכלי. לפעמים אפשר לעקוף את הרכיב החסום.",
            "2. לכבות את Smart App Control: אבטחת Windows ← בקרת אפליקציות ודפדפן ← הגדרות Smart App Control ← כבוי.",
            "   במחשב מעודכן אפשר להדליק אותו שוב אחר כך באותו מקום. ההחלטה שלך."]
    return out


def explain_block(tb):
    show("=" * 60)
    for line in block_text(tb):
        show(line)
    show("=" * 60)


# ---------- audio helpers (pure numpy) ----------
def to_mono(raw_bytes, channels):
    a = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        a = a[: len(a) - len(a) % channels].reshape(-1, channels).mean(axis=1)
    return a


def resample(x, sr_in, sr_out=TARGET_SR):
    if sr_in == sr_out:
        return x.astype(np.float32)
    if sr_in % sr_out == 0:  # e.g. 48000 -> 16000: average then decimate
        k = sr_in // sr_out
        n = len(x) - len(x) % k
        return x[:n].reshape(-1, k).mean(axis=1).astype(np.float32)
    n_out = int(len(x) * sr_out / sr_in)
    return np.interp(np.linspace(0, len(x) - 1, n_out),
                     np.arange(len(x)), x).astype(np.float32)


# Windows keeps "now playing" info for media in browsers/apps (the media flyout).
# The live mode only asks whether something is playing: if it is, but no sound reaches
# the tool, the sound probably goes to other speakers - worth telling the user.
# A small PowerShell loop (signed by Microsoft, so Smart App Control allows it) prints it every 2 s.
MEDIA_PS = r"""
$ErrorActionPreference = 'SilentlyContinue'
$parent = __PARENT__
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $type) { $t = $asTaskGeneric.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType = WindowsRuntime] | Out-Null
$mgr = Await ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
if (-not $mgr) { [Console]::Out.WriteLine('error|nomanager'); [Console]::Out.Flush(); exit }
while ($true) {
  if (-not (Get-Process -Id $parent -ErrorAction SilentlyContinue)) { exit }
  $s = $mgr.GetCurrentSession()
  if ($s) {
    $pi = $s.GetPlaybackInfo()
    [Console]::Out.WriteLine(('session|{0}|{1}' -f $s.SourceAppUserModelId, $pi.PlaybackStatus))
  } else {
    [Console]::Out.WriteLine('none')
  }
  [Console]::Out.Flush()
  Start-Sleep -Milliseconds 2000
}
"""


def parse_media_line(line):
    """'session|app|Playing' -> ('session', app, 'Playing')."""
    parts = line.strip().split("|")
    if not parts or parts[0] != "session" or len(parts) < 3:
        return (parts[0] if parts else "", None, None)
    return ("session", parts[1], parts[2])


MEDIA_PROC = None
MEDIA_STATUS = None  # "Playing" / "Paused" ... of the current media in Windows, if known


def media_status_loop():
    global MEDIA_PROC, MEDIA_STATUS
    if os.name != "nt":
        return
    import base64
    import subprocess
    script = MEDIA_PS.replace("__PARENT__", str(os.getpid()))
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    try:
        MEDIA_PROC = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", creationflags=0x08000000)  # no window
    except Exception:
        return  # only the "no sound reaches the tool" hint is lost
    for line in MEDIA_PROC.stdout:
        kind, app, status = parse_media_line(line)
        MEDIA_STATUS = status if kind == "session" else None
        if kind == "error":
            return


def find_cut(buf, sr, min_s=MIN_CHUNK_S, max_s=MAX_CHUNK_S):
    """Index of the quietest 0.3 s window between min_s and max_s,
    so chunks are cut in a pause and not in the middle of a word."""
    win = int(0.3 * sr)
    lo, hi = int(min_s * sr), min(len(buf), int(max_s * sr))
    best_i, best_e = hi, None
    for i in range(lo, hi - win, win // 2):
        e = float(np.mean(buf[i:i + win] ** 2))
        if best_e is None or e < best_e:
            best_i, best_e = i + win // 2, e
    return best_i


# ---------- model ----------
def _stub_av():
    """faster-whisper imports PyAV only to decode audio files. We pass raw audio,
    and Windows Smart App Control may block PyAV's DLLs - so replace it with a stub."""
    import types
    if "av" in sys.modules:
        return  # already loaded (the real one, for recordings, or the stand-in)
    stub = types.ModuleType("av")
    stub._bzm_stub = True

    def _missing(name):
        if name.startswith("__"):
            raise AttributeError(name)
        raise ImportError("PyAV disabled (not needed for live audio)")
    stub.__getattr__ = _missing
    sys.modules["av"] = stub


def _add_nvidia_dlls():
    """install_gpu.bat installs NVIDIA's cuBLAS/cuDNN as pip packages. Their DLLs
    sit in site-packages/nvidia/*/bin, which Windows doesn't search by default."""
    import site
    roots = []
    try:
        roots += site.getsitepackages()
    except Exception:
        pass
    try:
        roots.append(site.getusersitepackages())
    except Exception:
        pass
    found = 0
    for root in roots:
        nv = os.path.join(root, "nvidia")
        if not os.path.isdir(nv):
            continue
        for pkg in os.listdir(nv):
            b = os.path.join(nv, pkg, "bin")
            if os.path.isdir(b):
                try:
                    os.add_dll_directory(b)
                except Exception:
                    pass
                os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")
                found += 1
    return found

# ---------- fast model download (parallel, resumable, with progress) ----------
# The model is one big file (about 1.6GB). Hugging Face sends it over one connection,
# which on many home connections is slow. Here it is fetched in 16MB pieces over 8
# connections at once, with a progress line, and an interrupted download resumes.
# Pure Python (no extra components). If anything fails, the normal download is used.
HF = "https://huggingface.co"
FAST_WORKERS = 8
FAST_CHUNK = 16 * 1024 * 1024
MODEL_FILES = ("config.json", "preprocessor_config.json", "model.bin", "tokenizer.json")
FALLBACK_REPOS = {"large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
                  "turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo"}


def _repo_of(name):
    if "/" in name:
        return name
    try:
        from faster_whisper.utils import _MODELS
        return _MODELS.get(name) or FALLBACK_REPOS.get(name)
    except Exception:
        return FALLBACK_REPOS.get(name)


def _http(url, headers=None, timeout=30):
    import urllib.request
    req = urllib.request.Request(url, headers=dict({"User-Agent": "Hevanti/" + VERSION}, **(headers or {})))
    return urllib.request.urlopen(req, timeout=timeout)


def _progress_line(text, end=False):
    """A progress line (model download...) - in the black window and on the page."""
    import shutil
    if text:
        try:
            APP.set_progress(text)
        except NameError:
            pass
    width = max(40, shutil.get_terminal_size((100, 30)).columns - 1)
    line = visual_rtl(text).rjust(width) if RTL_CONSOLE else text.ljust(width)
    sys.stdout.write("\r" + line[:width] + ("\n" if end else ""))
    sys.stdout.flush()


def _fmt_eta(sec):
    if sec < 60:
        return "פחות מדקה"
    mins = int(sec // 60 + 1)
    return "עוד כדקה" if mins <= 1 else f"עוד כ-{mins} דקות"


def _fetch_small(repo, rev, fname, dest):
    with _http(f"{HF}/{repo}/resolve/{rev}/{fname}") as r:
        data = r.read()
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)


def _fetch_big(repo, rev, fname, dest, size, label):
    """Download one big file in parallel pieces into dest (resumable)."""
    import json
    url = f"{HF}/{repo}/resolve/{rev}/{fname}"
    part, state_path = dest + ".part", dest + ".progress.json"
    n = (size + FAST_CHUNK - 1) // FAST_CHUNK
    done = set()
    if os.path.exists(part) and os.path.getsize(part) == size and os.path.exists(state_path):
        try:
            with open(state_path, encoding="utf-8") as f:
                st = json.load(f)
            if st.get("size") == size and st.get("chunk") == FAST_CHUNK:
                done = set(st.get("done", []))
        except Exception:
            done = set()
    if not os.path.exists(part) or os.path.getsize(part) != size:
        with open(part, "wb") as f:
            f.truncate(size)
        done = set()
    lock = threading.Lock()
    got = [sum(min(FAST_CHUNK, size - i * FAST_CHUNK) for i in done)]
    todo = queue.Queue()
    for i in range(n):
        if i not in done:
            todo.put(i)
    errors = []

    def save_state():
        tmp = state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"size": size, "chunk": FAST_CHUNK, "done": sorted(done)}, f)
        os.replace(tmp, state_path)

    def worker():
        with open(part, "r+b") as fh:
            while not errors:
                try:
                    i = todo.get_nowait()
                except queue.Empty:
                    return
                start = i * FAST_CHUNK
                end = min(size, start + FAST_CHUNK) - 1
                for attempt in range(4):
                    pos, added = start, 0
                    try:
                        with _http(url, {"Range": f"bytes={start}-{end}"}, timeout=60) as r:
                            if r.status != 206:
                                raise IOError(f"HTTP {r.status} (no ranges)")
                            while pos <= end:
                                buf = r.read(min(1 << 20, end - pos + 1))
                                if not buf:
                                    raise IOError("connection closed")
                                fh.seek(pos)
                                fh.write(buf)
                                pos += len(buf)
                                added += len(buf)
                                with lock:
                                    got[0] += len(buf)
                        with lock:
                            done.add(i)
                            save_state()
                        break
                    except Exception as e:
                        with lock:
                            got[0] -= added
                        if attempt == 3:
                            errors.append(e)
                            return
                        time.sleep(1 + attempt * 2)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(FAST_WORKERS)]
    for t in threads:
        t.start()
    t0, b0 = time.time(), got[0]
    while any(t.is_alive() for t in threads):
        time.sleep(1)
        el = max(0.5, time.time() - t0)
        rate = (got[0] - b0) / el
        pct = 100.0 * got[0] / size
        eta = _fmt_eta((size - got[0]) / rate) if rate > 1 else ""
        _progress_line(f"מוריד את {label}: {pct:.0f}% ({got[0] >> 20}/{size >> 20}MB) {rate / 1048576:.1f}MB/s {eta}")
    _progress_line(f"מוריד את {label}: {100.0 * got[0] / size:.0f}%", end=True)
    if errors:
        raise errors[0]
    if len(done) != n:
        raise IOError("download incomplete")
    os.replace(part, dest)
    try:
        os.remove(state_path)
    except OSError:
        pass


def fast_download(name):
    """Return a local folder with the model, downloading it in parallel if needed.
    Returns None when the fast path can't be used (the normal download is used then)."""
    import json
    repo = _repo_of(name)
    if not repo:
        return None
    dest_dir = os.path.join(MODEL_DIR, "fast", repo.replace("/", "__"))
    marker = os.path.join(dest_dir, ".complete")
    if os.path.exists(marker):
        return dest_dir
    label = "מודל העברית" if "ivrit" in repo else "המודל"
    try:
        with _http(f"{HF}/api/models/{repo}?blobs=true") as r:
            info = json.load(r)
        rev = info.get("sha") or "main"
        files = {s["rfilename"]: s.get("size") for s in info.get("siblings", [])}
        wanted = [f for f in files if f in MODEL_FILES or f.startswith("vocabulary.")]
        if "model.bin" not in wanted or not files.get("model.bin"):
            return None
        os.makedirs(dest_dir, exist_ok=True)
        log(f"מוריד את {label} (כ-{files['model.bin'] / 1e9:.1f}GB). פעם אחת בלבד. אם סוגרים באמצע, ההורדה ממשיכה מאותה נקודה בפעם הבאה.")
        for f in wanted:
            path = os.path.join(dest_dir, f)
            if f == "model.bin":
                if not (os.path.exists(path) and os.path.getsize(path) == files[f]):
                    _fetch_big(repo, rev, f, path, files[f], label)
            elif not os.path.exists(path):
                _fetch_small(repo, rev, f, path)
        if os.path.getsize(os.path.join(dest_dir, "model.bin")) != files["model.bin"]:
            raise IOError("size mismatch")
        with open(marker, "w", encoding="utf-8") as fm:
            json.dump({"repo": repo, "revision": rev}, fm)
        log(f"ההורדה של {label} הסתיימה.")
        return dest_dir
    except Exception as e:
        _drop_unresumable(dest_dir)
        save_error("fast download")
        log(f"ההורדה המהירה לא הצליחה ({e.__class__.__name__}: {str(e)[:120]}) - מוריד בדרך הרגילה, זה עלול לקחת יותר זמן...")
        return None


def _drop_unresumable(dest_dir):
    """After a failed fast download: keep a partial file only if part of it is really there."""
    import json
    state = os.path.join(dest_dir, "model.bin.progress.json")
    try:
        with open(state, encoding="utf-8") as f:
            if json.load(f).get("done"):
                return
    except Exception:
        pass
    for f in ("model.bin.part", "model.bin.progress.json"):
        try:
            os.remove(os.path.join(dest_dir, f))
        except OSError:
            pass


def model_path(name):
    """Where to load `name` from: an existing download, a fast download, or the name itself."""
    try:
        from faster_whisper.utils import download_model
        p = download_model(name, local_files_only=True, cache_dir=MODEL_DIR)
        if p and os.path.exists(os.path.join(p, "model.bin")):
            repo = _repo_of(name)
            if repo:  # a half-finished fast download is no longer needed
                d = os.path.join(MODEL_DIR, "fast", repo.replace("/", "__"))
                if os.path.isdir(d) and not os.path.exists(os.path.join(d, ".complete")):
                    import shutil
                    shutil.rmtree(d, ignore_errors=True)
            return p  # downloaded before (the normal way)
    except Exception:
        pass
    return fast_download(name) or name


def _cuda_libs_ok():
    """Windows: can NVIDIA's cuBLAS and cuDNN be loaded? (Mac/Linux: leave it to CTranslate2.)"""
    if os.name != "nt":
        return True
    import ctypes
    for dll in ("cublas64_12.dll", "cudnn64_9.dll"):
        try:
            ctypes.WinDLL(dll)
        except OSError:
            return False
    return True


def load_model(stub_av=True):
    if stub_av:
        _stub_av()
    global HOT_OK, HOT_OK_BATCH
    has_cuda_libs = _add_nvidia_dlls() > 0
    from faster_whisper import WhisperModel
    try:
        import inspect
        HOT_OK = "hotwords" in inspect.signature(WhisperModel.transcribe).parameters
        from faster_whisper import BatchedInferencePipeline
        HOT_OK_BATCH = "hotwords" in inspect.signature(BatchedInferencePipeline.transcribe).parameters
    except Exception:
        HOT_OK = HOT_OK_BATCH = False
    os.makedirs(MODEL_DIR, exist_ok=True)
    test = np.zeros(TARGET_SR, dtype=np.float32)
    for name in MODELS:
        try:
            path = model_path(name)
            import ctranslate2
            gpus = ctranslate2.get_cuda_device_count()
            if gpus > 0 and not _cuda_libs_ok():
                # an NVIDIA card but no cuBLAS/cuDNN (Hevanti-Setup's own Python has none until install_gpu):
                # trying the GPU then can hang for ever - straight to the CPU
                log("טיפ: יש במחשב כרטיס מסך של NVIDIA. כדי שהתמלול יהיה מהיר יותר, להריץ פעם אחת את install_gpu "
                    "(בתיקייה System של הבנתי). עד אז: על המעבד.")
                gpus = 0
            log("טוען את מודל התמלול (" + ("כרטיס מסך" if gpus > 0 else "מעבד") + ")...")
            if gpus > 0:
                err = None
                for ctype in ("float16", "int8_float16", "int8"):
                    try:
                        m = WhisperModel(path, device="cuda", compute_type=ctype,
                                         download_root=MODEL_DIR)
                        list(m.transcribe(test, language=LANG)[0])
                        return m, 5, f"{name} / GPU"
                    except Exception as e:
                        err = e
                if has_cuda_libs:
                    log(f"כרטיס מסך לא זמין ({err.__class__.__name__}) - עובד על המעבד.")
                else:
                    log("טיפ: יש במחשב כרטיס מסך של NVIDIA. כדי שהתמלול יהיה מהיר יותר, להריץ פעם אחת את install_gpu (בתיקייה Setup).")
            m = WhisperModel(path, device="cpu", compute_type="int8",
                             download_root=MODEL_DIR, cpu_threads=os.cpu_count() or 4)
            list(m.transcribe(test, language=LANG)[0])
            return m, 1, f"{name} / CPU"
        except Exception as e:
            if is_blocked(e):
                raise
            save_error(f"load {name}")
            log(f"טעינת {name} נכשלה: {e.__class__.__name__}: {str(e)[:200]}")
    raise RuntimeError("Could not load any transcription model")


USE_VAD = True


def transcribe(model, beam, audio16, prev_text):
    global USE_VAD
    prompt = prompt_now() + " " + prev_text[-150:]
    try:
        segs, _ = model.transcribe(audio16, language=LANG, beam_size=beam,
                                   vad_filter=USE_VAD, condition_on_previous_text=False,
                                   initial_prompt=prompt, **hot_kw())
        return " ".join(s.text.strip() for s in segs).strip()
    except Exception as e:
        if not USE_VAD:
            raise
        log(f"סינון שקט (VAD) לא זמין ({e.__class__.__name__}) - ממשיך בלעדיו")
        USE_VAD = False
        return transcribe(model, beam, audio16, prev_text)


_PIPE = None
_BATCH_SIZE = 8


def transcribe_batch(model, beam, audio16, prev_text):
    """Catch up: a long stretch of audio in one go - the GPU works on several 30 s windows
    at once instead of one after the other. Returns [(start in seconds, text), ...]."""
    global _PIPE, _BATCH_SIZE
    if _PIPE is None:
        from faster_whisper import BatchedInferencePipeline
        _PIPE = BatchedInferencePipeline(model)
    prompt = prompt_now(batched=True) + " " + prev_text[-150:]
    while True:
        try:
            segs, _ = _PIPE.transcribe(audio16, language=LANG, beam_size=beam, batch_size=_BATCH_SIZE,
                                       vad_filter=True, initial_prompt=prompt, **hot_kw(batched=True))
            return [(float(s.start), s.text.strip()) for s in segs]
        except Exception as e:
            if "memory" in str(e).lower() and _BATCH_SIZE > 2:
                _BATCH_SIZE //= 2  # the GPU's memory is too small for 8 at once - try fewer
                continue
            raise


# ---------- screen snapshots ----------
def _ensure_packages(pairs, what="לצילום מסך"):
    """Install missing pure-Python helpers (mss, Pillow, comtypes) on first run."""
    import importlib
    import subprocess
    missing = []
    for mod, pkg in pairs:
        try:
            importlib.import_module(mod)
        except ModuleNotFoundError:
            missing.append(pkg)
        except Exception:
            pass  # installed but blocked/broken - handled where it is used
    if missing:
        log(f"מתקין רכיבים {what} ({' '.join(missing)}) - פעם אחת בלבד...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", *missing])


def changed_fraction(a, b, thresh=25):
    """Share of (downscaled, grayscale) pixels that changed between two frames."""
    if a is None or b is None or a.shape != b.shape:
        return 1.0
    return float(np.mean(np.abs(a - b) > thresh))


# --- the AI's window and Hevanti's own windows are not the lecture ---
# With the recommended screen (the lecture on two thirds, the AI on a third) or the floating window, an answer
# being written would look like a "new slide", and the chat would end up in the saved pictures. So the windows of
# the AI apps/sites and of Hevanti that are in view are painted over (grey) before comparing and saving.
MASK_TITLE = re.compile(r"\bClaude\b|ChatGPT|Gemini|הבנתי", re.I)
MASK_EXE = {"claude", "chatgpt"}    # the program (Windows: claude.exe; Mac: the app's name)


def pick_mask_rects(wins):
    """wins: [(title, exe, (left, top, right, bottom))], the top window first. The AI/Hevanti windows that are in
    view - not one whose middle is hidden behind another window that is above it (the lecture in front)."""
    above, out = [], []
    for title, exe, rc in wins:
        l, t, r, b = rc
        if r - l < 40 or b - t < 40:
            continue
        prog = os.path.splitext(os.path.basename(str(exe or "")))[0].lower()
        if prog in MASK_EXE or MASK_TITLE.search(str(title or "")):
            cx, cy = (l + r) // 2, (t + b) // 2
            if not any(a[0] <= cx < a[2] and a[1] <= cy < a[3] for a in above):
                out.append(rc)
        else:
            above.append(rc)
    return out


def _visible_windows():
    """Windows only: the visible top-level windows with a title, the top one first: (title, exe, rect)."""
    import ctypes
    from ctypes import wintypes
    user32, dwm, k32 = ctypes.WinDLL("user32"), ctypes.WinDLL("dwmapi"), ctypes.WinDLL("kernel32")
    HWND = wintypes.HWND
    for f, args in ((user32.IsWindowVisible, [HWND]), (user32.IsIconic, [HWND]), (user32.GetWindowTextLengthW, [HWND]),
                    (user32.GetWindowTextW, [HWND, wintypes.LPWSTR, ctypes.c_int]),
                    (user32.GetWindowRect, [HWND, ctypes.POINTER(wintypes.RECT)]),
                    (user32.GetWindowThreadProcessId, [HWND, ctypes.POINTER(wintypes.DWORD)]),
                    (dwm.DwmGetWindowAttribute, [HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]),
                    (k32.OpenProcess, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]),
                    (k32.QueryFullProcessImageNameW, [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]),
                    (k32.CloseHandle, [wintypes.HANDLE])):
        f.argtypes = args
    k32.OpenProcess.restype = wintypes.HANDLE
    out = []

    def exe_of(hwnd):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = k32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf, n = ctypes.create_unicode_buffer(520), wintypes.DWORD(520)
            return os.path.basename(buf.value) if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ""
        finally:
            k32.CloseHandle(h)

    def each(hwnd, _):
        try:
            if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                return True
            cloaked = ctypes.c_int(0)   # DWMWA_CLOAKED: "visible" but not on the screen (other desktops, suspended apps)
            if dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)) == 0 and cloaked.value:
                return True
            n = user32.GetWindowTextLengthW(hwnd)
            if n <= 0:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            rc = wintypes.RECT()   # DWMWA_EXTENDED_FRAME_BOUNDS: the window as seen, in screen pixels
            if dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rc), ctypes.sizeof(rc)) != 0:
                user32.GetWindowRect(hwnd, ctypes.byref(rc))
            out.append((buf.value, exe_of(hwnd), (rc.left, rc.top, rc.right, rc.bottom)))
        except Exception:
            pass
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, wintypes.LPARAM)(each), 0)
    return out


def _visible_windows_mac():
    """Mac: the windows on the screen, the front one first: (title, app, rect in points). Needs pyobjc (Quartz);
    the titles need the "Screen Recording" permission, which the screenshots need anyway."""
    import Quartz
    infos = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements, Quartz.kCGNullWindowID)
    out = []
    for w in infos or []:
        if int(w.get("kCGWindowLayer", 0)) != 0:
            continue   # menus, the Dock, overlays
        b = w.get("kCGWindowBounds") or {}
        x, y = int(b.get("X", 0)), int(b.get("Y", 0))
        out.append((str(w.get("kCGWindowName") or ""), str(w.get("kCGWindowOwnerName") or ""),
                    (x, y, x + int(b.get("Width", 0)), y + int(b.get("Height", 0)))))
    return out


def mask_windows(arr, area, wins=None):
    """Grey out, in place, the AI/Hevanti windows that are in view inside the grabbed area (BGRA array)."""
    if wins is None:
        if IS_MAC:
            wins = _visible_windows_mac()
        elif os.name == "nt":
            wins = _visible_windows()
        else:
            return False
    h, w = arr.shape[:2]
    sx, sy = w / max(1, area.get("width", w)), h / max(1, area.get("height", h))   # a Mac's Retina: 2 pixels a point
    done = False
    for l, t, r, b in pick_mask_rects(wins):
        x0, y0 = max(0, int((l - area["left"]) * sx)), max(0, int((t - area["top"]) * sy))
        x1, y1 = min(w, int((r - area["left"]) * sx)), min(h, int((b - area["top"]) * sy))
        if x1 > x0 and y1 > y0:
            arr[y0:y1, x0:x1, :3] = 128
            done = True
    return done


# ---------- the text on the slides (OCR) ----------
# Every saved slide is read in the background with Tesseract (free, offline; Hebrew + English) into a hidden
# ".ocr.json" in the lecture's "שקופיות" folder: {"13-40-11.jpg": "the text"}. The text can be searched, goes into
# exam prep and into what is copied for an AI, and the connector gives it to the AI. The words in English on the
# slide now on the screen also help the transcription (hotwords). No Tesseract: everything works as before.
# Tesseract: "install_ocr" (Windows) or "brew install tesseract tesseract-lang" (Mac).
OCR_NAME = ".ocr.json"
OCR_MAX = 4000    # characters kept per slide
_OCR_LOCK = threading.Lock()
_OCR = None
_OCR_UI = set("""zoom mute unmute video stop start participants participant chat share screen sharing record recording
leave end meeting reactions react apps security view gallery speaker more google chrome microsoft edge teams meet
file edit home insert design slide slides page pages search settings window help tools new tab untitled powerpoint
pdf http https www com org net exit full fullscreen raise hand captions breakout rooms whiteboard notes audio camera
microphone copy paste undo redo zoomin zoomout presenter presenting youtube subscribe like playlist""".split())


def tessdata_dir():
    return os.path.join(LOCAL_DIR, "tessdata")   # Hevanti's own language files (Hebrew, English) - no admin needed


def find_tesseract():
    import shutil
    cands = [os.environ.get("HEVANTI_TESSERACT", ""), shutil.which("tesseract") or ""]
    if os.name == "nt":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", ""),
                     os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"), LOCAL_DIR):
            if base:
                cands.append(os.path.join(base, "Tesseract-OCR", "tesseract.exe"))
    else:
        cands += ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract", "/usr/bin/tesseract"]
    return next((c for c in cands if c and os.path.isfile(c)), None)


def _quiet_proc():
    """A background helper: no window, low priority, one thread (the transcription comes first)."""
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    if os.name == "nt":
        return {"creationflags": 0x08000000 | 0x00004000, "env": env}   # CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY
    return {"env": env}


def ocr_config(exe):
    """(extra args, languages) - Hevanti's tessdata when it has Hebrew, else Tesseract's own. None: no Hebrew/English."""
    import subprocess
    for extra in ([["--tessdata-dir", tessdata_dir()]] if os.path.isdir(tessdata_dir()) else []) + [[]]:
        try:
            r = subprocess.run([exe, "--list-langs", *extra], capture_output=True, timeout=30, **_quiet_proc())
        except (OSError, subprocess.SubprocessError):
            continue
        have = {ln.strip() for ln in r.stdout.decode("utf-8", "replace").splitlines()[1:]}
        langs = [x for x in ("heb", "eng") if x in have]
        if langs and (extra or "heb" in have or not os.path.isdir(tessdata_dir())):
            return extra, "+".join(langs)
    return None


def clean_ocr(text):
    out = []
    text = re.sub("[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", str(text or ""))   # direction marks
    for ln in text.splitlines():
        ln = " ".join(ln.split())
        if sum(ch.isalnum() for ch in ln) >= 2:
            out.append(ln)
    return "\n".join(out)[:OCR_MAX]


def slide_terms(text):
    """Words in English on a slide (terms, names), for the hotwords - not the screen's buttons."""
    out = []
    for m in re.finditer(r"[A-Za-z][A-Za-z'\-]{2,}(?:[ ][A-Za-z][A-Za-z'\-]{2,}){0,2}", str(text or "")):
        words = [w for w in m.group(0).split() if w.lower() not in _OCR_UI]
        if words:
            out.append(" ".join(words))
    return list(dict.fromkeys(out))[:15]


def read_ocr(slides_dir):
    try:
        with open(os.path.join(slides_dir, OCR_NAME), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def slide_text(img_path):
    return str(read_ocr(os.path.dirname(img_path)).get(os.path.basename(img_path), ""))


def _write_ocr(img_path, text):
    d = os.path.dirname(img_path)
    with _OCR_LOCK:
        data = read_ocr(d)
        data[os.path.basename(img_path)] = text
        path = os.path.join(d, OCR_NAME)
        new = not os.path.exists(path)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
        if new:
            hide_file(path)


class OcrWorker(threading.Thread):
    """Reads the slides one after the other. Old slides (from before) wait while a lecture is running."""

    def __init__(self):
        super().__init__(daemon=True)
        self.q, self.later = queue.Queue(), collections.deque()
        self.exe, self.cfg, self.ready = None, None, None

    def setup(self):
        if self.ready is None:
            self.exe = find_tesseract()
            self.cfg = ocr_config(self.exe) if self.exe else None
            self.ready = self.cfg is not None
            if not self.ready:
                log("טיפ: כדי שהבנתי תקרא את הטקסט בשקופיות (חיפוש בשקופיות, הכנה למבחן, מילים באנגלית לתמלול), "
                    "להריץ פעם אחת את install_ocr בתיקייה System.")
        return self.ready

    def read(self, path):
        import subprocess
        extra, langs = self.cfg
        r = subprocess.run([self.exe, path, "stdout", "-l", langs, "--psm", "3", *extra], capture_output=True,
                           timeout=120, **_quiet_proc())
        return clean_ocr(r.stdout.decode("utf-8", "replace")) if r.returncode == 0 else None

    def busy(self):
        s = APP.session if "APP" in globals() else None
        return s is not None and not s.done

    def run(self):
        if not self.setup():
            return
        while True:
            try:
                path, cb = self.q.get(timeout=5)
            except queue.Empty:
                if not self.later or self.busy():
                    continue
                path, cb = self.later.popleft(), None
            try:
                if os.path.isfile(path) and os.path.basename(path) not in read_ocr(os.path.dirname(path)):
                    text = self.read(path)
                    if text is not None:
                        _write_ocr(path, text)
                        if cb and text:
                            cb(text)
            except Exception:
                save_error("ocr")


def ocr_worker():
    global _OCR
    if _OCR is None:
        _OCR = OcrWorker()
        _OCR.start()
    return _OCR


def ocr_add(path, words_to_model=True):
    """A slide was just saved: read it soon; its words in English help the transcription of what follows."""
    ocr_worker().q.put((path, (lambda t: set_slide_words(slide_terms(t))) if words_to_model else None))


def ocr_backfill():
    """Slides saved before Tesseract was there: read them when no lecture is running."""
    w = ocr_worker()
    time.sleep(20)
    if not w.ready:
        return
    n = 0
    for e in library():
        sd = os.path.join(LIB_DIR, *e["f"].split("/"), SLIDES_NAME)
        if not os.path.isdir(sd):
            continue
        done = read_ocr(sd)
        for name in sorted(os.listdir(sd)):
            if name.lower().endswith((".jpg", ".png")) and name not in done:
                w.later.append(os.path.join(sd, name))
                n += 1
                if n >= 3000:
                    return


class ScreenWatcher(threading.Thread):
    """Saves into the lecture's "שקופיות" folder. The transcript says "שקופיות/<file>" (the lecture folder can
    move to another course); on_shot gets the path inside "הקורסים שלי" (what the app and Claude use)."""

    def __init__(self, lecture_dir, lecture_rel, start_ts, write_line, on_shot=None, region_fn=None):
        super().__init__(daemon=True)
        self.region_fn = region_fn    # YouTube: only the player's rectangle (None = don't look right now)
        self.session_dir = os.path.join(lecture_dir, SLIDES_NAME)
        self.lecture_rel = lecture_rel
        self.start_ts = start_ts
        self.write_line = write_line
        self.on_shot = on_shot
        self.stop_evt = threading.Event()
        self.count = 0
        self.mask_ok = True   # paint over the AI's and Hevanti's own windows (see mask_windows)

    def run(self):
        try:
            import mss
            import mss.tools
        except Exception as e:
            if is_blocked(e):
                log("Windows חסם את רכיב צילום המסך (Smart App Control) - התמלול ממשיך כרגיל, בלי צילומים")
            else:
                log(f"צילום מסך לא זמין ({e.__class__.__name__}) - התמלול ממשיך כרגיל")
            return
        try:
            from PIL import Image
        except Exception:
            Image = None
        os.makedirs(self.session_dir, exist_ok=True)
        prev, last_save = None, 0.0
        try:
            with (getattr(mss, "MSS", None) or mss.mss)() as sct:
                mons = sct.monitors
                mon = mons[SCREEN_MONITOR] if 0 < SCREEN_MONITOR < len(mons) else mons[1]
                while not self.stop_evt.is_set():
                    try:
                        area = mon
                        if self.region_fn is not None:
                            r = self.region_fn()
                            if r is None:
                                self.stop_evt.wait(SCREEN_CHECK_S)
                                continue
                            area = mon if r == "screen" else r
                        shot = sct.grab(area)
                        arr = np.frombuffer(shot.bgra, dtype=np.uint8).reshape(shot.height, shot.width, 4)
                        pixels = None   # the picture to save when windows were painted over
                        if self.region_fn is None and self.mask_ok:
                            try:
                                arr = arr.copy()
                                if mask_windows(arr, area if isinstance(area, dict) else mon):
                                    pixels = arr
                            except Exception:
                                self.mask_ok = False   # not on this computer: compare the whole screen as before
                                save_error("mask windows")
                        small = arr[::16, ::16, :3].astype(np.int16).mean(axis=2)
                        now = time.time()
                        frac = changed_fraction(small, prev)
                        gap = now - last_save
                        if (frac >= SCREEN_BIG_FRAC and gap >= SCREEN_BIG_GAP_S) or \
                           (frac >= SCREEN_SMALL_FRAC and gap >= SCREEN_SMALL_GAP_S):
                            if self.region_fn is not None:
                                # a video: the change may be a jump to another part (seek) that the page reports
                                # a moment later - look again then, and save only if this part still needs it
                                self.stop_evt.wait(YT_SETTLE_S)
                                r2 = self.region_fn()
                                if r2 is None:
                                    prev = small    # a part that already has its slides: not a new one
                                    self.stop_evt.wait(SCREEN_CHECK_S)
                                    continue
                                shot = sct.grab(mon if r2 == "screen" else r2)
                                arr = np.frombuffer(shot.bgra, dtype=np.uint8).reshape(shot.height, shot.width, 4)
                                small, now = arr[::16, ::16, :3].astype(np.int16).mean(axis=2), time.time()
                            self._save(shot, Image, mss.tools, now, pixels)
                            prev, last_save = small, now
                    except Exception as e:
                        log(f"צילום מסך נכשל פעם אחת ({e.__class__.__name__})")
                    self.stop_evt.wait(SCREEN_CHECK_S)
        except Exception as e:
            log(f"צילום מסך הופסק ({e.__class__.__name__}) - התמלול ממשיך כרגיל")

    def _save(self, shot, Image, mss_tools, now, pixels=None):
        name = datetime.datetime.fromtimestamp(now).strftime("%Y%m%d-%H-%M-%S" if self.region_fn else "%H-%M-%S")
        bgra = shot.bgra if pixels is None else pixels.tobytes()
        if Image is not None:
            name += ".jpg"
            img = Image.frombytes("RGB", shot.size, bgra, "raw", "BGRX")
            img.save(os.path.join(self.session_dir, name), "JPEG", quality=80)
        else:
            name += ".png"
            rgb = shot.rgb if pixels is None else pixels[:, :, 2::-1].tobytes()
            mss_tools.to_png(rgb, shot.size, output=os.path.join(self.session_dir, name))
        self.count += 1
        ocr_add(os.path.join(self.session_dir, name))
        rel = f"{self.lecture_rel}/{SLIDES_NAME}/{name}"
        if self.region_fn is not None:  # YouTube: the line gets the video's time (on_shot knows it)
            pos = self.on_shot(now, rel)
            self.write_line(f"[{hms(pos)}] [צילום מסך: {SLIDES_NAME}/{name}]")
            return
        self._line(now, f"[צילום מסך: {SLIDES_NAME}/{name}]")
        if self.on_shot:
            self.on_shot(now, rel)

    def _line(self, now, text):
        stamp = datetime.datetime.fromtimestamp(now).strftime("%H:%M:%S")
        elapsed = str(datetime.timedelta(seconds=int(now - self.start_ts)))
        self.write_line(f"[{stamp} | +{elapsed}] {text}")

    def stop(self):
        self.stop_evt.set()


# ---------- now_watching.txt: what is happening right now, for the AI ----------
# One small file the AI reads first, in both modes: a live lecture (the last minutes of
# what was said, a draft of what is being said right now, the newest screenshot) or a
# recording (where you are in it, what was said just before, the slide on the screen).
NOW_FILE = os.path.join(LIB_DIR, "now_watching.txt")


def write_now_file(text):
    """Replace now_watching.txt in one step (a reader never sees half a file)."""
    tmp = NOW_FILE + ".tmp"
    try:
        os.makedirs(LIB_DIR, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text.rstrip("\n") + "\n")
        os.replace(tmp, NOW_FILE)
    except OSError:
        return False  # open in another program right now - the next update writes it
    try:
        course_now_write(text)
    except Exception:
        save_error("course now")
    return True


class LiveNow(threading.Thread):
    """now_watching.txt during a live lecture."""
    KEEP_S = 300   # the last 5 minutes
    EVERY_S = 3    # rewritten at most this often (the folder is often synced to the cloud)
    BEAT_S = 30    # and at least this often while the lecture runs, even when nobody speaks

    def __init__(self, transcript_rel, start_dt, drafts=False, course=""):
        super().__init__(daemon=True)
        self.transcript_rel, self.start_dt, self.drafts, self.course = transcript_rel, start_dt, drafts, course
        self.lock = threading.Lock()
        self.lines = collections.deque()  # (time, text)
        self.shot = None                   # (time, relative path)
        self.draft = ""
        self.pending_s = 0.0               # sound heard but not transcribed yet (seconds)
        self.all = []                      # everything since the start (the page shows it)
        self.lag, self.fast, self.ended = 0.0, False, False
        self.info = {}
        self.dirty = True
        self.stop_evt = threading.Event()

    def add(self, t, text):
        with self.lock:
            self.all.append((t, text))
            self.lines.append((t, text))
            while self.lines and self.lines[0][0] < t - self.KEEP_S:
                self.lines.popleft()
            self.dirty = True

    def add_shot(self, t, rel):
        self.add(t, f"[צילום מסך: {rel}]")
        with self.lock:
            self.shot = (t, rel)

    def set_draft(self, text):
        with self.lock:
            if text != self.draft:
                self.draft, self.dirty = text, True

    def text(self):
        def clock(t):
            return datetime.datetime.fromtimestamp(t).strftime("%H:%M:%S")
        out = [f"מצב: הרצאה חיה - התמלול רץ עכשיו ({'אנגלית' if LANG == 'en' else 'עברית'})"
               + (f" | קורס: {self.course}" if self.course and self.course != NO_COURSE else ""),
               f"התחילה ב-{self.start_dt:%H:%M} | עכשיו: {datetime.datetime.now():%H:%M:%S}",
               f"תמלול מלא: {self.transcript_rel}"]
        if self.shot:
            out.append(f"צילום המסך האחרון: {self.shot[1]} (מ-{clock(self.shot[0])})")
        else:
            out.append("צילום המסך האחרון: עוד אין")
        out += ["", f"מה נאמר ב-{self.KEEP_S // 60} הדקות האחרונות:"]
        out += [f"[{clock(t)}] {x}" for t, x in sorted(self.lines, key=lambda e: e[0])] or ["(עוד לא נאמר כלום)"]
        if self.draft:
            out += ["", f"ממש עכשיו (טיוטה, עוד לא סופי): {self.draft}"]
        elif self.pending_s >= 3:
            out += ["", f"ממש עכשיו: מה שנאמר ב-{int(self.pending_s)} השניות האחרונות עוד בתמלול."]
        return "\n".join(out)

    def write(self):
        with self.lock:
            if not self.dirty:
                return
            self.dirty = False
            body = self.text()
        if not write_now_file(body):
            with self.lock:
                self.dirty = True

    def run(self):
        last = time.time()   # when the file was last written
        while not self.stop_evt.wait(self.EVERY_S):
            if time.time() - last >= self.BEAT_S:   # a quiet lecture: still say "alive" (the AI checks how fresh the file is)
                with self.lock:
                    self.dirty = True
            with self.lock:
                due = self.dirty
            self.write()
            if due:
                with self.lock:
                    wrote = not self.dirty
                if wrote:
                    last = time.time()

    def finish(self, transcript_rel):
        self.stop_evt.set()
        write_now_file(f"מצב: אין כרגע הרצאה חיה ולא צפייה בהקלטה.\n"
                       f"ההרצאה האחרונה: {transcript_rel} (הסתיימה ב-{datetime.datetime.now():%H:%M})\n")


# ---------- a YouTube video, watched inside Hevanti ----------
# YouTube's terms don't allow downloading, so the video plays in YouTube's own player (the official embed)
# inside the app, and Hevanti does what it does in a live lecture: transcribes the sound the computer plays
# and photographs the slides - only the player's part of the screen. The page reports the player's time
# every second, so each line and slide gets the VIDEO's time ([00:23:40]), and the AI knows the exact minute.
# What was already transcribed is not done again when you go back; a video can be continued another day.
YT_ID = re.compile(r"[A-Za-z0-9_-]{11}")
YT_STATE = ".youtube.json"   # in the lecture folder: which parts are transcribed, where you stopped
YT_HEAD = re.compile(r"# תמלול סרטון יוטיוב \((עברית|אנגלית)\) - (\S+) \| מזהה: ([A-Za-z0-9_-]{11})")
YT_TITLE = "# כותרת: "


def youtube_id(url):
    """A YouTube link -> (video id, start second) or (None, 0)."""
    import urllib.parse
    url = str(url or "").strip()
    if not url:
        return None, 0
    if "://" not in url:
        url = "https://" + url
    u = urllib.parse.urlsplit(url)
    host = (u.hostname or "").lower()
    q = urllib.parse.parse_qs(u.query)
    vid = None
    if host == "youtu.be" or host.endswith(".youtu.be"):
        vid = u.path.strip("/").split("/")[0]
    elif host == "youtube.com" or host.endswith(".youtube.com") or host.endswith("youtube-nocookie.com"):
        if q.get("v"):
            vid = q["v"][0]
        else:
            parts = [p for p in u.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in ("embed", "shorts", "live", "v", "e"):
                vid = parts[1]
    if not vid or not YT_ID.fullmatch(vid):
        return None, 0
    start = 0
    t = (q.get("t") or q.get("start") or [""])[0]
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?", t)
    if t and m:
        start = int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)
    return vid, start


def find_yt_lecture(course, vid):
    """The lecture folder of this video in this course, if it was started before."""
    cdir = course_dir(course)
    try:
        names = os.listdir(cdir)
    except OSError:
        return None
    for n in names:
        d = os.path.join(cdir, n)
        t = lecture_txt(d)
        if not os.path.isfile(t):
            continue
        try:
            with open(t, encoding="utf-8", errors="replace") as f:
                m = YT_HEAD.match(f.readline())
        except OSError:
            continue
        if m and m.group(3) == vid:
            return d
    return None


class Coverage:
    """Which parts of the video (seconds) are already transcribed."""

    def __init__(self, spans=None):
        self.spans = []
        for s in spans or []:
            try:
                self.add(float(s[0]), float(s[1]))
            except (TypeError, ValueError, IndexError):
                pass

    def add(self, a, b):
        if b <= a:
            return
        out = []
        for s, e in self.spans:
            if e < a - 1 or s > b + 1:
                out.append((s, e))
            else:
                a, b = min(a, s), max(b, e)
        out.append((a, b))
        self.spans = sorted(out)

    def covered(self, a, b):
        """Share of [a, b] already transcribed."""
        if b <= a:
            return 0.0
        got = sum(max(0.0, min(b, e) - max(a, s)) for s, e in self.spans)
        return got / (b - a)

    def total(self):
        return sum(e - s for s, e in self.spans)


class YtClock:
    """The player's time, as the page reports it: wall time -> video time."""
    STALE_S = 12    # no report for this long: we don't know what is playing

    def __init__(self, start=0.0):
        self.lock = threading.Lock()
        self.anchors = collections.deque(maxlen=3000)   # (wall, pos, playing, rate)
        self.page_at = 0.0
        self.region = None      # the player's rectangle on the screen (physical pixels), or None
        self.full = False       # the video is full screen
        self.visible = False
        self.title = ""
        self.duration = 0.0
        self.version = 0
        self.last_pos = float(start or 0)
        self.on_title = None

    def set(self, d):
        now = time.time()
        title = None
        with self.lock:
            self.page_at = now
            if d.get("closed"):
                self.page_at, self.visible = 0.0, False
                self.anchors.append((now, self.last_pos, False, 1.0))
                self.version += 1
                return
            try:
                pos = max(0.0, float(d.get("pos")))
            except (TypeError, ValueError):
                pos = None
            playing = bool(d.get("playing"))
            try:
                rate = min(4.0, max(0.25, float(d.get("rate") or 1)))
            except (TypeError, ValueError):
                rate = 1.0
            if pos is not None:
                last = self.anchors[-1] if self.anchors else None
                if last is None or last[2] != playing or abs(pos - self.last_pos) >= 1.5 or not playing:
                    self.version += 1
                self.anchors.append((now, pos, playing, rate))
                self.last_pos = pos
            self.visible = bool(d.get("visible", True))
            self.full = bool(d.get("full"))
            self.region = d.get("view") if not self.full else None   # (turned into screen pixels when photographing)
            try:
                self.duration = float(d.get("duration") or self.duration or 0)
            except (TypeError, ValueError):
                pass
            t = str(d.get("title") or "").strip()[:200]
            if t and t != self.title:
                self.title, title = t, t
        if title and self.on_title:
            self.on_title(title)

    def pos_at(self, wall):
        """-> (video seconds, playing) at that moment, or None if the player was not reporting."""
        with self.lock:
            for w, p, playing, rate in reversed(self.anchors):
                if w <= wall + 0.05:
                    if wall - w > self.STALE_S:
                        return None
                    return (p + (wall - w) * rate if playing else p), playing
            return None

    def now(self):
        """(position, playing, page open)."""
        with self.lock:
            alive = time.time() - self.page_at < 75
        m = self.pos_at(time.time())
        if m is None:
            return self.last_pos, False, alive
        return m[0], m[1], alive

    def rate_at(self, wall):
        with self.lock:
            for w, p, playing, rate in reversed(self.anchors):
                if w <= wall + 0.05:
                    return rate
        return 1.0

    def capture_rect(self):
        """Where to photograph: the player's rectangle, the whole screen (full screen), or None (not visible)."""
        with self.lock:
            if time.time() - self.page_at > self.STALE_S or not self.visible:
                return None
            if self.full:
                return "screen"
            view = self.region
        return screen_rect(view)


PAGE_TITLE = "הבנתי · האפליקציה"   # app.html's <title>: the browser window that shows it is named after it


def _page_windows():
    """Windows: the browser windows showing Hevanti's page, as (left, top, right, bottom) in screen pixels."""
    import ctypes
    from ctypes import wintypes
    user32, dwm = ctypes.WinDLL("user32"), ctypes.WinDLL("dwmapi")
    HWND = wintypes.HWND
    user32.GetWindowTextW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = user32.IsIconic.argtypes = [HWND]
    dwm.DwmGetWindowAttribute.argtypes = [HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    out = []

    def each(hwnd, _):
        try:
            if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
                buf = ctypes.create_unicode_buffer(300)
                user32.GetWindowTextW(hwnd, buf, 300)
                if buf.value.startswith(PAGE_TITLE):
                    rc = wintypes.RECT()   # DWMWA_EXTENDED_FRAME_BOUNDS: always real pixels, on any monitor
                    if dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rc), ctypes.sizeof(rc)) == 0:
                        out.append((rc.left, rc.top, rc.right, rc.bottom))
        except Exception:
            pass
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, wintypes.LPARAM)(each), 0)
    return out


def rect_in_window(v, win):
    """The player's rectangle from the window's real place on the screen. The page is at the bottom of the window,
    centred across it; inside it, a CSS pixel is dpr real pixels. (Correct on any monitor and at any scaling -
    unlike window.screenX, which Windows reports in a mixed scale when the monitors have different scaling.)"""
    l, t, r, b = win
    iw, ih, dpr = float(v["iw"]), float(v["ih"]), min(4.0, max(0.5, float(v.get("dpr") or 1)))
    page_l, page_t = l + max(0.0, (r - l - iw * dpr) / 2), b - ih * dpr
    x, y, w, h = float(v["x"]), float(v["y"]), float(v["w"]), float(v["h"])
    return {"left": int(round(page_l + x * dpr)), "top": int(round(page_t + y * dpr)),
            "width": int(round(w * dpr)), "height": int(round(h * dpr))}


def pick_page_window(v, wins):
    """Of the windows named like Hevanti's page, the one whose real size fits the page's report."""
    try:
        ow, oh = float(v["ow"]), float(v["oh"])
    except (KeyError, TypeError, ValueError):
        return None
    best, err = None, 0.12
    for win in wins:
        w, h = win[2] - win[0], win[3] - win[1]
        if w <= 0 or h <= 0 or ow <= 0 or oh <= 0:
            continue
        e = abs((w / h) / (ow / oh) - 1)   # the same shape (the scale of the monitor is unknown here)
        if e < err:
            best, err = win, e
    return best


def screen_rect(v, wins=None):
    """The page's report about where the player is -> a rectangle on the screen, in the screenshot's coordinates.
    Windows: from the browser window's real place (mixed-scale monitors); Mac: in points, as the screenshot is."""
    if not isinstance(v, dict):
        return None
    try:
        sx, sy = float(v["sx"]), float(v["sy"])
        ow, oh, iw, ih = float(v["ow"]), float(v["oh"]), float(v["iw"]), float(v["ih"])
        x, y, w, h = float(v["x"]), float(v["y"]), float(v["w"]), float(v["h"])
        dpr = min(4.0, max(0.5, float(v.get("dpr") or 1)))
    except (KeyError, TypeError, ValueError):
        return None
    if w < 160 or h < 90:
        return None
    if wins is None and os.name == "nt":
        try:
            wins = _page_windows()
        except Exception:
            wins = []
    win = pick_page_window(v, wins or [])
    if win is not None:
        return rect_in_window(v, win)
    if os.name == "nt":
        # the page's window was not found: a guess from window.screenX lands beside the player on monitors with
        # different scaling, and photographs Hevanti's own transcript - a "new slide" every few seconds. No picture.
        return None
    if IS_MAC:
        dpr = 1.0   # the Mac's screen coordinates are points, like window.screenX
    border = max(0.0, (ow - iw) / 2)
    top_bar = max(0.0, oh - ih - border)
    left, top = (sx + border + x) * dpr, (sy + top_bar + y) * dpr
    return {"left": int(round(left)), "top": int(round(top)), "width": int(round(w * dpr)), "height": int(round(h * dpr))}


class YtNow(LiveNow):
    """now_watching.txt (and the page's transcript) while a YouTube video plays in Hevanti. Times are the video's."""

    def __init__(self, transcript_rel, start_dt, clock, url, course="", lines=None, shots=None):
        super().__init__(transcript_rel, start_dt, drafts=False, course=course)
        self.lock = threading.RLock()   # text() runs under the lock and looks up the slide
        self.clock, self.url = clock, url
        self.yt = True
        self.rev = 0
        self.shots = sorted(shots or [])          # (video seconds, path inside הקורסים שלי)
        for t, x in sorted(lines or []):
            self.all.append((t, x))
        self.seen_version = -1

    def add(self, t, text):
        import bisect
        with self.lock:
            bisect.insort(self.all, (t, text))
            self.rev += 1
            self.dirty = True

    def add_shot(self, wall, rel):
        import bisect
        m = self.clock.pos_at(wall)
        pos = m[0] if m else self.clock.last_pos
        with self.lock:
            bisect.insort(self.shots, (pos, rel))
            self.shot = (pos, rel)
        self.add(pos, f"[צילום מסך: {rel}]")
        return pos

    def shot_near(self, pos, within):
        with self.lock:
            return any(abs(t - pos) <= within for t, _ in self.shots)

    def slide_at(self, pos):
        with self.lock:
            best = None
            for t, rel in self.shots:
                if t <= pos + 0.5:
                    best = (t, rel)
            return best

    def text(self):
        pos, playing, alive = self.clock.now()
        title = self.clock.title or "סרטון יוטיוב"
        dur = f" מתוך {hms(self.clock.duration)}" if self.clock.duration else ""
        out = [f"מצב: סרטון יוטיוב - התמלול רץ עכשיו, בנגן של הבנתי ({'אנגלית' if LANG == 'en' else 'עברית'})"
               + (f" | קורס: {self.course}" if self.course and self.course != NO_COURSE else ""),
               f"סרטון: {title} ({self.url})",
               f"אתה כאן: {hms(pos)}{dur} ({'מתנגן' if playing else 'בהשהיה'})" + ("" if alive else " - הנגן סגור"),
               f"עודכן: {datetime.datetime.now():%H:%M:%S}",
               f"תמלול מלא: {self.transcript_rel} (רק החלקים שכבר נוגנו - הבנתי מתמללת תוך כדי צפייה)"]
        sl = self.slide_at(pos)
        if sl:
            out.append(f"השקופית שעל המסך עכשיו: {sl[1]} (מ-{hms(sl[0])})")
        before = [(t, x) for t, x in self.all if pos - NOW_BEFORE_S <= t <= pos + 0.5]
        out += ["", f"מה נאמר ב-{NOW_BEFORE_S // 60} הדקות שלפני המקום שלך:"]
        out += [f"[{hms(t)}] {x}" for t, x in before] or ["(עוד אין כאן תמלול - החלק הזה עוד לא נוגן)"]
        if self.pending_s >= 3 and playing:
            out += ["", f"ממש עכשיו: מה שנאמר ב-{int(self.pending_s)} השניות האחרונות עוד בתמלול."]
        return "\n".join(out)

    def write(self):
        if self.clock.version != self.seen_version:
            self.seen_version = self.clock.version
            with self.lock:
                self.dirty = True
        super().write()

    def finish(self, transcript_rel):
        self.stop_evt.set()
        pos, _, _ = self.clock.now()
        write_now_file(f"מצב: אין כרגע הרצאה חיה ולא צפייה בהקלטה.\n"
                       f"הסרטון האחרון: {self.clock.title or self.url} - נעצר ב-{hms(pos)}. תמלול: {transcript_rel}\n")


def read_yt_lecture(ldir):
    """An existing YouTube lecture -> (lines [(sec, text)], shots [(sec, rel)], coverage, last place, title)."""
    lines, shots, title = [], [], ""
    rel = lib_rel(ldir)
    try:
        with open(lecture_txt(ldir), encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n")
                if line.startswith(YT_TITLE):
                    title = line[len(YT_TITLE):].strip()
                    continue
                m = REC_LINE.match(line)
                if not m:
                    continue
                t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
                x = m.group(4)
                sm = SHOT_RE.match(x)
                if sm:
                    r = f"{rel}/{SLIDES_NAME}/{os.path.basename(sm.group(1))}"
                    shots.append((t, r))
                    lines.append((t, f"[צילום מסך: {r}]"))
                else:
                    lines.append((t, x))
    except OSError:
        pass
    st = {}
    try:
        with open(os.path.join(ldir, YT_STATE), encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        pass
    cov = Coverage(st.get("covered") if isinstance(st, dict) else None)
    if not cov.spans:  # no state file: assume what has text is done
        for t, x in lines:
            if not x.startswith("[צילום מסך"):
                cov.add(t, t + 8)
    pos = float(st.get("pos") or 0) if isinstance(st, dict) else 0.0
    # the parts already watched for slides (the screen was checked there) - a state from before: what was
    # transcribed and a few seconds around each slide
    seen = Coverage(st.get("seen") if isinstance(st, dict) else None)
    if not seen.spans:
        for a, b in cov.spans:
            seen.add(a, b)
        for t, _rel in shots:
            seen.add(t - 3, t + 3)
    return lines, shots, cov, pos, title, seen


def save_yt_state(ldir, cov, pos, seen=None):
    path = os.path.join(ldir, YT_STATE)
    try:
        if os.path.exists(path):
            os.chmod(path, 0o666)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"covered": [[round(a, 1), round(b, 1)] for a, b in cov.spans], "pos": round(pos, 1),
                       "seen": [[round(a, 1), round(b, 1)] for a, b in (seen.spans if seen else [])]}, f)
        hide_file(path)
    except OSError:
        pass


def tidy_yt_transcript(path):
    """At the end: the lines in the video's order, one header, one title, one end mark."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            rows = f.read().splitlines()
    except OSError:
        return
    head = rows[0] if rows else ""
    title = next((r for r in rows if r.startswith(YT_TITLE)), "")
    body = []
    for i, r in enumerate(rows[1:]):
        m = REC_LINE.match(r)
        if m:
            body.append((int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)), i, r))
    body.sort()
    out = [head] + ([title] if title else []) + [r for _, _, r in body] + [f"# סוף: {datetime.datetime.now():%H:%M}"]
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        os.replace(tmp, path)
    except OSError:
        save_error("tidy youtube transcript")


# ---------- audio capture ----------
class DefaultSpeakers:
    """Asks Windows which speakers/headphones are the default right now (a cheap call),
    so switching between headphones and speakers is noticed within a second."""

    def __init__(self):
        self.ok = False
        if os.name != "nt":
            return
        try:
            import ctypes
            import comtypes
            from comtypes import GUID, IUnknown, COMMETHOD
            HRESULT = ctypes.HRESULT
            vp, ui, si = ctypes.c_void_p, ctypes.c_uint, ctypes.c_int

            class IMMDevice(IUnknown):
                _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
                _methods_ = [
                    COMMETHOD([], HRESULT, "Activate", (["in"], vp), (["in"], ui), (["in"], vp), (["out"], ctypes.POINTER(vp))),
                    COMMETHOD([], HRESULT, "OpenPropertyStore", (["in"], ui), (["out"], ctypes.POINTER(vp))),
                    COMMETHOD([], HRESULT, "GetId", (["out"], ctypes.POINTER(vp))),
                    COMMETHOD([], HRESULT, "GetState", (["out"], ctypes.POINTER(ui))),
                ]

            class IMMDeviceEnumerator(IUnknown):
                _iid_ = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
                _methods_ = [
                    COMMETHOD([], HRESULT, "EnumAudioEndpoints", (["in"], si), (["in"], ui), (["out"], ctypes.POINTER(vp))),
                    COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint", (["in"], si), (["in"], si),
                              (["out"], ctypes.POINTER(ctypes.POINTER(IMMDevice)))),
                ]

            try:
                comtypes.CoInitialize()
            except Exception:
                pass  # already initialized in this thread
            self._enum = comtypes.CoCreateInstance(GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}"),
                                                   interface=IMMDeviceEnumerator, clsctx=comtypes.CLSCTX_INPROC_SERVER)
            self._free = ctypes.windll.ole32.CoTaskMemFree
            self._free.argtypes = [vp]
            self._wstr = ctypes.wstring_at
            self.ok = self.current() is not None
        except Exception:
            self.ok = False

    def current(self):
        """Id of the default playback device, or None if Windows can't tell."""
        try:
            dev = self._enum.GetDefaultAudioEndpoint(0, 1)  # eRender, eMultimedia
            ptr = dev.GetId()
            if not ptr:
                return None
            try:
                return self._wstr(ptr)
            finally:
                self._free(ptr)
        except Exception:
            return None


class AudioInput:
    """Loopback capture of the default speakers/headphones, with reconnect.
    Each (re)connection gets a new generation number so stale audio is dropped."""

    def __init__(self, q):
        self.q = q
        self.gen = 0
        self.p = self.stream = None
        self.sr = self.ch = None
        self.name = None
        self.opened_at = 0.0

    def open(self):
        self.close()  # full PortAudio restart -> fresh device list
        if IS_MAC:
            return self._open_mac()
        import pyaudiowpatch as pyaudio
        p = pyaudio.PyAudio()
        try:
            wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            spk = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
            out_name = spk["name"]
            if not spk.get("isLoopbackDevice"):
                for lb in p.get_loopback_device_info_generator():
                    if spk["name"] in lb["name"]:
                        spk = lb
                        break
                else:
                    raise RuntimeError("לא נמצא התקן loopback לרמקולים")
            sr, ch = int(spk["defaultSampleRate"]), int(spk["maxInputChannels"])
            self.gen += 1
            gen, q = self.gen, self.q

            def cb(in_data, frame_count, time_info, status):
                q.put((gen, time.time(), in_data))
                return (in_data, pyaudio.paContinue)

            stream = p.open(format=pyaudio.paInt16, channels=ch, rate=sr, input=True,
                            input_device_index=spk["index"], frames_per_buffer=2048,
                            stream_callback=cb)
            stream.start_stream()
        except Exception:
            try:
                p.terminate()
            except Exception:
                pass
            raise
        self.p, self.stream, self.sr, self.ch, self.name = p, stream, sr, ch, out_name
        self.opened_at = time.time()

    def _open_mac(self):
        """Mac: the computer's sound cannot be recorded without a driver. It comes through BlackHole (free, open
        source), with a "Multi-Output Device" that sends the sound both to the speakers and to BlackHole."""
        import sounddevice as sd
        want = (os.environ.get("HEVANTI_AUDIO_DEVICE") or "BlackHole").lower()
        devs = sd.query_devices()
        dev = next((i for i, d in enumerate(devs) if want in str(d["name"]).lower() and d["max_input_channels"] > 0), None)
        if dev is None:
            raise RuntimeError("BlackHole not found")
        info = devs[dev]
        sr, ch = int(info["default_samplerate"]), max(1, min(2, int(info["max_input_channels"])))
        self.gen += 1
        gen, q = self.gen, self.q

        def cb(indata, frames, time_info, status):
            q.put((gen, time.time(), bytes(indata)))

        stream = sd.RawInputStream(samplerate=sr, channels=ch, dtype="int16", device=dev, blocksize=2048, callback=cb)
        stream.start()
        self.stream, self.sr, self.ch, self.name = stream, sr, ch, str(info["name"])
        self.opened_at = time.time()

    def alive(self):
        try:
            if self.stream is None:
                return False
            return bool(self.stream.active) if IS_MAC else self.stream.is_active()
        except Exception:
            return False

    def close(self):
        s = self.stream
        steps = ((lambda: s.stop(), lambda: s.close()) if IS_MAC else
                 (lambda: s.stop_stream(), lambda: s.close(), lambda: self.p.terminate()))
        for fn in steps:
            try:
                fn()
            except Exception:
                pass
        self.p = self.stream = None


# ---------- recorded lecture: all of it in advance, then a player that knows where you are ----------
# The page (or a recording dragged onto BeZmanEmet). The recording - a file, or a
# link - is transcribed with its own times ([00:12:34]), and every new slide is saved from the video
# itself. It plays in the tool's own page in the browser: the transcript follows the video, and the
# page tells the tool exactly where you are (at any playback speed), so now_watching.txt always says
# which part of the lecture you are asking about. The part you are watching is transcribed first.
LOCAL_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or HERE, "Hevanti")
if IS_MAC:
    LOCAL_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Hevanti")
OLD_LOCAL_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or HERE, "BeZmanEmet")  # 1.x
VIDEO_DIR = os.path.join(LOCAL_DIR, "videos")  # downloads: not in the tool folder, which is often synced to the cloud
CACHE_DIR = os.path.join(OLD_LOCAL_DIR, "progress")  # 1.x: unfinished transcriptions (2.0 keeps them in the lecture folder)
SETTINGS_FILE = os.path.join(LOCAL_DIR, "settings.json")
PLAYER_HTML = os.path.join(SCRIPT_DIR, "player.html")
PLAYER_PORTS = (8765, 8766, 8767, 8768, 8769, 0)  # 0 = any free port
SLIDE_LOOK_S = 1.0        # full decoding: look at one frame per second
KEYFRAME_MAX_GAP_S = 6.0  # key frames at least this often -> looking only at them is enough (much faster)
BLOCK_S = {"gpu": 300, "cpu": 90}  # transcribed in blocks of this many seconds; the one you watch goes first
AHEAD_S = 600             # ...then the next 10 minutes, and only then earlier parts
NOW_BEFORE_S = 240        # now_watching.txt: what was said in the 4 minutes before your place
NOW_AFTER_S = 30          #   ...and in the 30 seconds right after it
MEDIA_TYPES = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/mp4", ".webm": "video/webm",
               ".mkv": "video/x-matroska", ".ogv": "video/ogg", ".avi": "video/x-msvideo", ".wmv": "video/x-ms-wmv",
               ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac", ".wav": "audio/wav",
               ".ogg": "audio/ogg", ".opus": "audio/ogg", ".flac": "audio/flac", ".wma": "audio/x-ms-wma"}


def hms(t):
    t = max(0, int(t))
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def safe_stem(name):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", str(name))
    s = " ".join(s.split()).strip(" .")
    return s[:80].strip(" .") or "video"


# ---------- "הקורסים שלי": a folder per course, a folder per lecture ----------
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def clean_name(name, fallback=""):
    """A course or lecture name that is safe as a Windows folder name (no / \\ : * ? " < > |, no '..')."""
    n = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", str(name or ""))
    n = " ".join(n.split()).strip(" .")[:80].strip(" .")
    if n.upper() in _RESERVED:
        n += "_"
    return n or fallback


def course_dir(course):
    return os.path.join(LIB_DIR, clean_name(course, NO_COURSE))


def lecture_dir(course, name):
    return os.path.join(course_dir(course), clean_name(name, "הרצאה"))


def lecture_txt(d):
    return os.path.join(d, os.path.basename(d) + ".txt")


def lib_rel(path):
    return os.path.relpath(path, LIB_DIR).replace(os.sep, "/")


def hide_file(path):
    """Windows: a hidden file (the lecture folder shows only the transcript and the slides)."""
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x2)
        except Exception:
            pass


def course_names():
    try:
        names = [n for n in os.listdir(LIB_DIR) if not n.startswith(".") and os.path.isdir(os.path.join(LIB_DIR, n))]
    except OSError:
        names = []
    return sorted(names, key=lambda n: (n == NO_COURSE, n))


def lecture_dirs():
    """(course, lecture, folder) for every lecture: a folder holding "<its name>.txt"."""
    out = []
    for c in course_names():
        cd = os.path.join(LIB_DIR, c)
        try:
            names = os.listdir(cd)
        except OSError:
            continue
        for n in names:
            d = os.path.join(cd, n)
            if not n.startswith(".") and os.path.isdir(d) and os.path.isfile(lecture_txt(d)):
                out.append((c, n, d))
    return out


def lecture_from_rel(rel):
    """"<course>/<lecture>" from the page -> the lecture folder, only inside "הקורסים שלי"."""
    parts = [x for x in str(rel or "").replace("\\", "/").split("/") if x]
    if len(parts) != 2 or any(x in (".", "..") or clean_name(x) != x for x in parts):
        return None
    d = os.path.join(LIB_DIR, *parts)
    root = os.path.realpath(LIB_DIR)
    if not os.path.realpath(d).startswith(root + os.sep) or not os.path.isfile(lecture_txt(d)):
        return None
    return d


def to_recycle_bin(path):
    """Delete a folder so it can still be restored: the Windows Recycle Bin, or (if that fails / not Windows)
    a copy kept in %LOCALAPPDATA%\\Hevanti\\deleted. Returns "bin", "kept" or "" (failed)."""
    import shutil
    path = os.path.abspath(path)
    if IS_MAC:
        try:
            trash = os.path.join(os.path.expanduser("~"), ".Trash")
            shutil.move(path, os.path.join(trash, free_folder(trash, os.path.basename(path))))
            return "bin"
        except OSError:
            save_error("trash")
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class SHFILEOPSTRUCTW(ctypes.Structure):
                _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                            ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                            ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]
            # FO_DELETE, FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
            op = SHFILEOPSTRUCTW(None, 3, path + "\0", None, 0x40 | 0x10 | 0x04 | 0x400, False, None, None)
            r = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
            if r == 0 and not op.fAnyOperationsAborted and not os.path.exists(path):
                return "bin"
        except Exception:
            save_error("recycle bin")
    try:
        keep = os.path.join(LOCAL_DIR, "deleted")
        os.makedirs(keep, exist_ok=True)
        shutil.move(path, os.path.join(keep, free_folder(keep, time.strftime("%Y-%m-%d %H-%M ") + os.path.basename(path))))
        return "kept"
    except OSError:
        save_error("delete lecture")
        return ""


def free_folder(parent, name):
    """name, or "name (2)", "name (3)"... - whichever is not taken in parent."""
    for n in range(1, 1000):
        cand = name if n == 1 else f"{name} ({n})"
        if not os.path.exists(os.path.join(parent, cand)):
            return cand
    return name + " " + str(int(time.time()))


GLOSSARY_HEAD = ("# מילון המונחים של הקורס: מילה או מונח בכל שורה.\n"
                 "# התמלול משתמש בהם כדי לכתוב נכון מונחים מקצועיים, שמות ומילים באנגלית.\n"
                 "# הכי חשובים למעלה: נכנסים רק בערך 25-30 המונחים הראשונים. שורה שמתחילה ב-# לא נקראת.\n")
# Suggested terms PER COURSE (not per degree): course_terms.json, matched by the course's name - "סטטיקה של גוף
# קשיח" gets the statics list. The student adds each term with one click ("+"); nothing is added by itself.
TERMS_FILE = os.path.join(SCRIPT_DIR, "course_terms.json")
_TERMS_DB = None


def _course_key(text):
    """Compare course names without case, spaces, quotes or punctuation ("מד\"ר" = "מד ר" = "מדר")."""
    return re.sub(r"[\s\"'`\u05f3\u05f4.,:;()\[\]{}\-\u2013\u2014_/\\+&]+", "", str(text or "").lower())


def course_terms_db():
    global _TERMS_DB
    if _TERMS_DB is None:
        try:
            with open(TERMS_FILE, encoding="utf-8") as f:
                _TERMS_DB = [c for c in json.load(f).get("courses", []) if isinstance(c, dict)]
        except (OSError, ValueError):
            _TERMS_DB = []
    return _TERMS_DB


def suggest_terms(name):
    """{"courses": [the lists that fit this course name], "terms": [...]} - the best match, and a second list only
    when another part of the name fits it too ("סטטיקה וחוזק חומרים")."""
    key = _course_key(name)
    found = []
    for c in course_terms_db():
        if any(_course_key(x) and _course_key(x) in key for x in c.get("exclude", [])):
            continue
        hits = [k for k in map(_course_key, c.get("match", [])) if len(k) >= 3 and k in key]
        if hits:
            kw = max(hits, key=len)
            found.append((len(kw), kw, c))
    found.sort(key=lambda x: -x[0])
    picked = []
    for n, kw, c in found:
        if not picked or n == found[0][0] or all(kw not in k and k not in kw for _, k, _c in picked):
            picked.append((n, kw, c))
        if len(picked) == 2:
            break
    terms, seen = [], set()
    for _, _, c in picked:
        for t in c.get("terms", []):
            t = " ".join(str(t).split())[:60]
            if t and t.lower() not in seen:
                seen.add(t.lower())
                terms.append(t)
    return {"courses": [c.get("name", "") for _, _, c in picked], "terms": terms}


def glossary_path(course):
    return os.path.join(course_dir(course), GLOSSARY_NAME)


def read_glossary(course):
    try:
        with open(glossary_path(course), encoding="utf-8", errors="replace") as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    except OSError:
        return []


def glossary_text(course):
    try:
        with open(glossary_path(course), encoding="utf-8", errors="replace") as f:
            return "\n".join(ln.rstrip("\n") for ln in f if not ln.lstrip().startswith("#")).strip()
    except OSError:
        return ""


def write_glossary(course, text):
    words = [" ".join(w.split()) for w in re.split(r"[\n,،;]+", str(text or ""))]
    words = [w[:60] for w in words if w and not w.startswith("#")][:300]
    os.makedirs(course_dir(course), exist_ok=True)
    tmp = glossary_path(course) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(GLOSSARY_HEAD + "\n".join(words) + ("\n" if words else ""))
    os.replace(tmp, glossary_path(course))
    return words


def create_course(name, terms=None):
    """A new course folder, with the terms the student chose from the suggestions (or an empty glossary)."""
    name = clean_name(name)
    if not name:
        return None
    d = course_dir(name)
    os.makedirs(d, exist_ok=True)
    if not os.path.exists(glossary_path(name)):
        terms = [str(t) for t in terms if isinstance(t, str)] if isinstance(terms, list) else []
        write_glossary(name, "\n".join(terms))
    write_course_ai_files(name)
    return name


# ---------- connecting the student's AI app to Hevanti ----------
# Hevanti has no AI of its own. The student's own AI app on this computer gets a small "connector"
# (an MCP server: hevanti_mcp.py) that lets it read what is happening in the lecture right now - the last
# minutes, the slide on the screen, the whole transcript - so a question can be asked straight in the AI's
# own window. One button per app, the same for all three:
#   Claude  - Claude for desktop reads its MCP servers from claude_desktop_config.json
#   ChatGPT - ChatGPT for Windows (Codex) reads them from ~/.codex/config.toml
#   Gemini  - the Gemini app for Windows cannot use local files or connectors yet (Mac only, Sept 2026)
SUMMARY_NAME = "סיכום.txt"
MCP_SCRIPT = os.path.join(SCRIPT_DIR, "hevanti_mcp.py")
MCP_NAME = "hevanti"
AI_APPS = ("claude", "chatgpt", "gemini")


def _mcp_entry():
    return {"command": sys.executable, "args": [MCP_SCRIPT, "--lib", LIB_DIR],
            "env": {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}}


def claude_config_paths():
    """Claude for desktop's config: the usual installer, and the Microsoft Store (MSIX) copy."""
    import glob
    if IS_MAC:
        return [os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Claude",
                             "claude_desktop_config.json")]
    out = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        out.append(os.path.join(appdata, "Claude", "claude_desktop_config.json"))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        out += glob.glob(os.path.join(local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude",
                                      "claude_desktop_config.json"))
    return out


def gemini_config_path():
    """Gemini CLI's user settings (Windows and Mac alike: ~/.gemini/settings.json). Gemini CLI stopped serving
    personal Google accounts on 18.6.2026; it is still written for school/work accounts that use it."""
    home = os.environ.get("BZM_GEMINI_DIR") or os.path.join(os.path.expanduser("~"), ".gemini")
    return os.path.join(home, "settings.json")


def antigravity_config_path():
    """Antigravity CLI (agy) - Google's terminal Gemini since June 2026 - reads its MCP servers from
    ~/.gemini/config/mcp_config.json ({"mcpServers": {...}}, the same shape as Claude's)."""
    home = os.environ.get("BZM_GEMINI_DIR") or os.path.join(os.path.expanduser("~"), ".gemini")
    return os.path.join(home, "config", "mcp_config.json")


def gemini_cli_found():
    import shutil
    return bool(shutil.which("agy") or shutil.which("gemini")) or os.path.isdir(os.path.dirname(gemini_config_path()))


def gemini_connected():
    for p in (antigravity_config_path(), gemini_config_path()):
        d = _read_json(p) or {}
        if isinstance(d.get("mcpServers"), dict) and MCP_NAME in d["mcpServers"]:
            return True
    return False


def _json_servers_set(p, entry, on, name):
    d = _read_json(p)
    if d is None:
        return {"ok": False, "error": f"קובץ ההגדרות של {name} לא תקין, אז לא שיניתי אותו: {p}"}
    servers = d.get("mcpServers") if isinstance(d.get("mcpServers"), dict) else {}
    if on:
        servers[MCP_NAME] = entry
    elif MCP_NAME in servers:
        del servers[MCP_NAME]
    else:
        return {"ok": True}
    d["mcpServers"] = servers
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if os.path.exists(p):
            _backup_once(p)
        _write_text(p, json.dumps(d, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        save_error("gemini config")
        return {"ok": False, "error": f"לא הצלחתי לכתוב את ההגדרות של {name}."}
    return {"ok": True}


def gemini_set(on):
    """Antigravity CLI (agy) first, and Gemini CLI too (school/work accounts); other settings are kept."""
    a = _json_servers_set(antigravity_config_path(), _mcp_entry(), on, "Antigravity CLI")
    g = {"ok": True}
    if on or os.path.exists(gemini_config_path()):
        g = _json_servers_set(gemini_config_path(), dict(_mcp_entry(), timeout=60000), on, "Gemini CLI")
    return a if not a.get("ok") else g if not g.get("ok") else {"ok": True}


def codex_config_path():
    home = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    return os.path.join(home, "config.toml")


def _backup_once(path):
    import shutil
    bak = path + ".before-hevanti"
    if os.path.isfile(path) and not os.path.exists(bak):
        try:
            shutil.copy2(path, bak)
        except OSError:
            pass


def _read_json(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return None  # there but not readable as JSON - don't touch it


def _write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp-hevanti"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def claude_connected():
    for p in claude_config_paths():
        d = _read_json(p)
        if d and isinstance(d.get("mcpServers"), dict) and MCP_NAME in d["mcpServers"]:
            return True
    return False


def claude_installed():
    return any(os.path.isdir(os.path.dirname(p)) for p in claude_config_paths())


def claude_set(on):
    paths = [p for p in claude_config_paths() if os.path.isdir(os.path.dirname(p))]
    if on and not paths:
        return {"ok": False, "error": "לא מצאתי את Claude למחשב. להתקין אותו מ-claude.ai/download, להיכנס לחשבון, "
                                      "ואז ללחוץ שוב על \"חיבור\"."}
    for p in paths:
        d = _read_json(p)
        if d is None:
            return {"ok": False, "error": f"קובץ ההגדרות של Claude לא תקין, אז לא שיניתי אותו: {p}"}
        servers = d.get("mcpServers") if isinstance(d.get("mcpServers"), dict) else {}
        if on:
            servers[MCP_NAME] = _mcp_entry()
        elif MCP_NAME in servers:
            del servers[MCP_NAME]
        else:
            continue
        d["mcpServers"] = servers
        _backup_once(p)
        try:
            _write_text(p, json.dumps(d, ensure_ascii=False, indent=2) + "\n")
        except OSError:
            save_error("claude config")
            return {"ok": False, "error": "לא הצלחתי לכתוב את ההגדרות של Claude. לסגור את Claude ולנסות שוב."}
    return {"ok": True}


_TOML_HEAD = re.compile(r"^\s*\[mcp_servers\.(?:hevanti|\"hevanti\")\]\s*$")


def _toml_without_hevanti(text):
    """config.toml without our [mcp_servers.hevanti] table (and its sub-tables)."""
    out, skip = [], False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            skip = bool(_TOML_HEAD.match(line)) or s.startswith("[mcp_servers.hevanti.")
        if not skip:
            out.append(line)
    return "\n".join(out).rstrip("\n")


def _toml_str(s):
    s = str(s)
    if "'" not in s and "\n" not in s:
        return "'" + s + "'"  # a literal string: Windows backslashes stay as they are
    return json.dumps(s, ensure_ascii=False)


def chatgpt_connected():
    try:
        with open(codex_config_path(), encoding="utf-8-sig") as f:
            return any(_TOML_HEAD.match(line) for line in f)
    except OSError:
        return False


def chatgpt_set(on):
    path = codex_config_path()
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
    except FileNotFoundError:
        text = ""
    except OSError:
        return {"ok": False, "error": "לא הצלחתי לקרוא את ההגדרות של ChatGPT (Codex)."}
    base = _toml_without_hevanti(text)
    if on:
        e = _mcp_entry()
        block = ["[mcp_servers.hevanti]", f"command = {_toml_str(e['command'])}",
                 "args = [" + ", ".join(_toml_str(a) for a in e["args"]) + "]",
                 "env = { " + ", ".join(f"{k} = {_toml_str(v)}" for k, v in e["env"].items()) + " }"]
        new = (base + "\n\n" if base else "") + "\n".join(block) + "\n"
    else:
        if base == text.rstrip("\n"):
            return {"ok": True}
        new = base + "\n" if base else ""
    _backup_once(path)
    try:
        _write_text(path, new)
    except OSError:
        save_error("codex config")
        return {"ok": False, "error": "לא הצלחתי לכתוב את ההגדרות של ChatGPT. לסגור את ChatGPT ולנסות שוב."}
    return {"ok": True}


def connect_status():
    return {"claude": claude_connected(), "chatgpt": chatgpt_connected(), "gemini": gemini_connected(),
            "claude_found": claude_installed(), "gemini_found": gemini_cli_found()}


CONNECT_NEXT = {
    "claude": "מחובר. עכשיו לסגור את Claude למחשב לגמרי (ב-Windows גם מהאייקון ליד השעון, ב-Mac: Cmd+Q) ולפתוח אותו שוב. "
              "מהפעם הבאה אפשר פשוט לשאול אותו \"מה המרצה אמר עכשיו?\" או \"מה כתוב בשקופית?\".",
    "chatgpt": "מחובר. עכשיו לסגור את ChatGPT למחשב ולפתוח אותו שוב, לעבור למצב Codex, ולשאול שם "
               "\"מה המרצה אמר עכשיו?\". (צריך את ChatGPT ל-Windows מ-chatgpt.com/download.)",
    "gemini": "מחובר ל-Antigravity CLI (Gemini בחלון פקודות, agy). בדף של כל קורס יש \"פתיחת Gemini בקורס\": "
              "חלון פקודות נפתח בשליש המסך, כבר בתוך הקורס. בפעם הראשונה הוא שואל אם לאשר את הכלים של הבנתי - לאשר תמיד. "
              "אין עדיין Antigravity CLI? פעם אחת ב-PowerShell: irm https://antigravity.google/cli/install.ps1 | iex . "
              "(האפליקציה והאתר של Gemini עוד לא קוראים מהמחשב ב-Windows: בשבילם יש \"סנכרון לענן\".)",
}


def connect_app(app, on=True):
    app = str(app or "")
    if app not in AI_APPS:
        return {"ok": False, "error": "לא מוכר."}
    out = {"claude": claude_set, "chatgpt": chatgpt_set, "gemini": gemini_set}[app](on)
    out["status"] = connect_status()
    if out.get("ok"):
        out["next"] = CONNECT_NEXT[app] if on else "החיבור הוסר. כדי שזה ייכנס לתוקף: לסגור ולפתוח שוב את " + \
            {"claude": "Claude", "chatgpt": "ChatGPT", "gemini": "Gemini (agy)"}[app] + "."
    return out


# --- the AI apps installed on this computer: the "ChatGPT / Gemini / Claude" buttons open the app when there is one ---
# Found by their name in the Start menu (Get-StartApps): this covers Store apps, installed programs and web apps that
# were installed from the browser alike, and each is opened the way the Start menu opens it.
AI_APP_NAMES = {"claude": ("claude",), "chatgpt": ("chatgpt",), "gemini": ("gemini", "google gemini")}
_AI_APPS = {"ids": {}, "at": 0.0, "busy": False}
_AI_APPS_LOCK = threading.Lock()


def find_ai_apps():
    """{"claude": "<AppID>", ...} for the AI apps in the Start menu."""
    fake = os.environ.get("BZM_FAKE_APPS")   # tests: "claude,gemini"
    if fake is not None:
        return {a: "fake!" + a for a in fake.split(",") if a in AI_APP_NAMES}
    if IS_MAC:   # /Applications/Claude.app, ChatGPT.app, Gemini.app (also in ~/Applications)
        out = {}
        bases = ["/Applications", os.path.join(os.path.expanduser("~"), "Applications")]
        apps = [os.path.join(b, f) for b in bases if os.path.isdir(b) for f in sorted(os.listdir(b)) if f.endswith(".app")]
        for app, names in AI_APP_NAMES.items():
            hit = next((x for x in apps if os.path.basename(x)[:-4].lower() in names), None)
            if hit:
                out[app] = "mac:" + hit
        return out
    if os.name != "nt":
        return {}
    import subprocess
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
                            "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"],
                           capture_output=True, timeout=30, creationflags=0x08000000)  # CREATE_NO_WINDOW
        items = json.loads(r.stdout.decode("utf-8", "replace").strip() or "[]")
    except Exception:
        return {}
    if isinstance(items, dict):
        items = [items]
    out = {}
    for app, names in AI_APP_NAMES.items():
        for it in items if isinstance(items, list) else []:
            if isinstance(it, dict) and str(it.get("Name") or "").strip().lower() in names and it.get("AppID"):
                out[app] = str(it["AppID"])
                break
    return out


def refresh_ai_apps():
    try:
        ids = find_ai_apps()
    except Exception:
        ids = {}
    with _AI_APPS_LOCK:
        _AI_APPS.update(ids=ids, at=time.time(), busy=False)


def ai_apps_status():
    """{"claude": True, ...} - looked up again in the background every 10 minutes (an app may be installed meanwhile)."""
    with _AI_APPS_LOCK:
        stale = not _AI_APPS["busy"] and time.time() - _AI_APPS["at"] > 600
        if stale:
            _AI_APPS["busy"] = True
        ids = dict(_AI_APPS["ids"])
    if stale:
        threading.Thread(target=refresh_ai_apps, daemon=True).start()
    return {a: a in ids for a in AI_APP_NAMES}


def open_ai_app(app):
    """Open the installed app of this AI. False when it is not installed (the page then opens the website)."""
    with _AI_APPS_LOCK:
        aid = _AI_APPS["ids"].get(str(app or ""))
    if not aid:
        return False
    if aid.startswith("fake!"):
        try:
            with open(os.path.join(LOCAL_DIR, "opened_apps.txt"), "a", encoding="utf-8") as f:
                f.write(aid[5:] + "\n")
        except OSError:
            pass
        return True
    import subprocess
    try:
        if aid.startswith("mac:"):
            subprocess.Popen(["open", aid[4:]])
            return True
        subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + aid], close_fds=True)
        return True
    except OSError:
        save_error("open ai app")
        return False


def refresh_connections():
    """The Hevanti folder moved (or Python changed) since connecting: point the connections at the new place."""
    want = _mcp_entry()
    try:
        for p in claude_config_paths():
            d = _read_json(p)
            cur = d.get("mcpServers", {}).get(MCP_NAME) if d else None
            if isinstance(cur, dict) and (cur.get("command"), cur.get("args")) != (want["command"], want["args"]):
                claude_set(True)
                break
        if chatgpt_connected():
            with open(codex_config_path(), encoding="utf-8-sig") as f:
                text = f.read()
            if _toml_str(MCP_SCRIPT) not in text or _toml_str(want["command"]) not in text or _toml_str(LIB_DIR) not in text:
                chatgpt_set(True)
        for gp in (antigravity_config_path(), gemini_config_path()):
            g = (_read_json(gp) or {}).get("mcpServers") or {}
            cur = g.get(MCP_NAME) if isinstance(g, dict) else None
            if isinstance(cur, dict) and (cur.get("command"), cur.get("args")) != (want["command"], want["args"]):
                gemini_set(True)
                break
    except Exception:
        save_error("refresh connections")


# ---------- the AI of each course: Claude, ChatGPT and Gemini, each in a project of its own for the course ----------
# The student keeps one project per course in each AI (a Claude project, a ChatGPT project or Codex folder, a Gem or
# an agy window). The AI reads that course by itself - no copying and pasting of questions:
#   * apps on this computer with the connector (Claude for desktop, ChatGPT/Codex, Antigravity CLI): the tools get
#     course="<the course>". Codex and agy open the course FOLDER as their project, and read AGENTS.md there.
#   * AI websites and apps that cannot read this computer (a ChatGPT project, Gemini): "sync to the cloud" copies
#     each course's "now" file and all its transcripts into the student's Google Drive (or OneDrive) folder, which
#     those AIs read from their Drive connection, at the moment of the question.
# A project link per course and AI (saved in the course folder) makes the AI button open THAT project, on a third
# of the screen, beside the lecture.
COURSE_AI_FILE = ".hevanti_ai.json"     # {"claude": "<project link>", "chatgpt": ..., "gemini": ...}
COURSE_NOW_NAME = "now_watching.txt"     # a copy of now_watching.txt in the course folder (hidden), for that course
AI_FILE_NAMES = ("AGENTS.md", "GEMINI.md", "CLAUDE.md")   # Codex / agy, Gemini, Claude read these in a folder
AI_FILE_MARK = "<!-- hevanti course file -->"
MIRROR_DIR_NAME = "הבנתי"
AI_LINK_HOSTS = {"claude": ("claude.ai",), "chatgpt": ("chatgpt.com", "chat.openai.com"),
                 "gemini": ("gemini.google.com", "notebooklm.google.com", "notebook.google.com")}


def course_ai_md(course):
    """AGENTS.md / GEMINI.md / CLAUDE.md of a course folder: an AI that opens the folder knows the course."""
    return f"""{AI_FILE_MARK}
# הבנתי · הקורס: {course}

This folder is the course "{course}" in Hevanti (הבנתי), the student's lecture app. Each sub-folder is one lecture:
its transcript ("<lecture>.txt", with times) and its slides ("שקופיות/", pictures; ".ocr.json" = text read from them).
"now_watching.txt" here (a hidden file) says what is happening in this course right now: a live lecture, a recording
or a YouTube video, the last minutes of what was said and the slide on the screen.

LIVE LECTURE RULE (the most important one): the student often asks while a lecture is running and does not say so -
even a general question ("מה זה מומנט התמד?", "למה צריך את זה?") is probably about what the lecturer is saying right
now. So at the START of every conversation, and before answering any question on the subject of this course, call
`now` first (course="{course}"; brief=true is a cheap check). If it reports a live lecture: tie the answer to it -
what the lecturer just said (a few words and its time) and what is on the slide - e.g. "לפני דקה הוא אמר ש...".
Keep it short (3-5 lines, offer more): the student is listening. If the question has nothing to do with the last
minutes, answer normally and say so; if no lecture is running, answer normally and do not mention it. Never invent
what the lecturer said.

When the student asks about this course or about the lecture ("מה הוא אמר עכשיו?", "מה כתוב בשקופית?",
"לא הבנתי את החלק האחרון", "תכין לי מבחן תרגול"):
- Use the Hevanti tools (MCP server "hevanti") and ALWAYS pass course="{course}":
  `now` first for anything about the current lecture; `transcript` for a lecture of this course (default: the
  newest; whole_course=true for all of them - exam prep, summaries, flashcards; part=2,3... when it is long);
  `slide` for the slide at a time; `search` to find words; `moment` to find where a topic was explained (ranked,
  with time, context and slide); `lectures` for the list.
- Three ready-made requests (Claude for desktop also lists them as prompts "exam", "summary", "find_moment"):
  * "תכין מבחן דמה" - `transcript` with whole_course=true, read ALL the parts, then write ~8 questions only from
    what was taught (explanations, calculations, one trap); show only the exam, no answers. When the student
    answers: grade each (right / missing / wrong) with a score. On "פתרון": full solutions, each with its source -
    lecture and time [h:mm:ss] - where it was taught.
  * "סכם הרצאה" - the lecture (default: the open one, or the newest) in full: one paragraph on the subject, the
    topics in order with time stamps, formulas and the example solved, "what the lecturer stressed", what in the
    transcript is unclear, and 5 questions for self-check. Only what was said or shown.
  * "מצא את הרגע שבו הוא הסביר X" - `moment` with the topic (try a synonym or the English term if nothing good
    comes back), then `transcript` ~3 minutes around the best place and `slide` at that time. First line of the
    answer: the lecture and the exact time; then the explanation. If it was never said - say so, do not invent.
- Without those tools, read the files in this folder: now_watching.txt first, then the lectures' .txt files.
- Answer in Hebrew, step by step; keep technical terms in English in parentheses. The transcript is automatic:
  a word that makes no sense is probably a mis-hearing - guess it from the context and the slide.
- Do not change, move or delete any file in this folder.
"""


def write_course_ai_files(course):
    """The AI files of one course folder (only files Hevanti wrote are replaced, never the student's own)."""
    d = course_dir(course)
    if not os.path.isdir(d):
        return
    body = course_ai_md(course)
    for name in AI_FILE_NAMES:
        p = os.path.join(d, name)
        try:
            if os.path.exists(p):
                with open(p, encoding="utf-8", errors="replace") as f:
                    old = f.read()
                if not old.startswith(AI_FILE_MARK) or old == body:
                    continue
                os.chmod(p, 0o666)
            if os.name == "nt" and os.path.exists(p):   # a hidden file cannot be opened for writing - unhide first
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)
                except Exception:
                    pass
            with open(p, "w", encoding="utf-8") as f:
                f.write(body)
            hide_file(p)
        except OSError:
            save_error("course ai file")


def write_all_course_ai_files():
    for c in course_names():
        write_course_ai_files(c)


def clean_ai_link(app, url):
    """A project/Gem link of that AI, or "" (anything else is refused: the page opens it)."""
    url = str(url or "").strip()
    if not url:
        return ""
    try:
        import urllib.parse
        u = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    host = (u.hostname or "").lower()
    if u.scheme != "https" or not any(host == h or host.endswith("." + h) for h in AI_LINK_HOSTS.get(app, ())):
        return None
    return url[:500]


def course_ai_links(course):
    d = _read_json(os.path.join(course_dir(course), COURSE_AI_FILE)) or {}
    return {a: clean_ai_link(a, d.get(a)) or "" for a in AI_APPS}


def set_course_ai_link(course, app, url):
    if app not in AI_APPS:
        return {"ok": False, "error": "לא מוכר."}
    if not os.path.isdir(course_dir(course)):
        return {"ok": False, "error": "הקורס לא נמצא."}
    link = clean_ai_link(app, url)
    if link is None:
        return {"ok": False, "error": "זה לא נראה כמו קישור לפרויקט של " +
                {"claude": "Claude (claude.ai/project/...)", "chatgpt": "ChatGPT (chatgpt.com/g/...)",
                 "gemini": "Gemini (gemini.google.com/gem/...)"}[app] + "."}
    links = course_ai_links(course)
    links[app] = link
    p = os.path.join(course_dir(course), COURSE_AI_FILE)
    try:
        if os.name == "nt" and os.path.exists(p):
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)
        _write_text(p, json.dumps(links, ensure_ascii=False, indent=1) + "\n")
        hide_file(p)
    except (OSError, AttributeError):
        save_error("course ai link")
        return {"ok": False, "error": "לא הצלחתי לשמור."}
    return {"ok": True, "links": links}


def project_instructions(course, app):
    """The text to paste ONCE into the course's project (Claude project, ChatGPT project, Gem)."""
    mirror = mirror_root()
    cloud = (f'בתיקייה "{MIRROR_DIR_NAME}/{clean_name(course)}" ב-Google Drive' if mirror else
             "בתיקיית הסנכרון לענן של הבנתי (עוד לא הופעלה: \"סנכרון לענן\" בחיבור AI)")
    if app == "claude":
        return (f'הפרויקט הזה הוא הקורס "{course}". ההרצאות שלו בהבנתי (Hevanti), שמחוברת אליך בכלים של hevanti.\n'
                f'בכל שאלה על הקורס או על ההרצאה ("מה הוא אמר עכשיו?", "מה כתוב בשקופית?", "תכין מבחן תרגול"): '
                f'להשתמש בכלים של hevanti ותמיד לתת course="{course}". קודם now על מה שקורה עכשיו; transcript '
                'להרצאה של הקורס (whole_course=true לכל הקורס, part=2,3 כשארוך); slide לשקופית; search לחיפוש.\n'
                "לענות בעברית, צעד אחר צעד, מונחים מקצועיים באנגלית בסוגריים. התמלול אוטומטי: מילה מוזרה היא כנראה "
                "טעות תמלול - לנחש לפי ההקשר והשקופית.")
    return (f'הפרויקט הזה הוא הקורס "{course}". הבנתי (Hevanti), אפליקציית ההרצאות שלי, שומרת את הקורס {cloud}:\n'
            '- "עכשיו.txt": מה שקורה עכשיו בהרצאה (חיה, הקלטה או יוטיוב): הדקות האחרונות של מה שנאמר והטקסט '
            "מהשקופית שעל המסך. מתעדכן כל כמה שניות.\n"
            '- "כל ההרצאות.txt": כל ההרצאות של הקורס, מהישנה לחדשה.\n'
            "בכל שאלה על ההרצאה (\"מה הוא אמר עכשיו?\", \"לא הבנתי את החלק האחרון\") - לפתוח מחדש את הגרסה הנוכחית של "
            '"עכשיו.txt" מ-Google Drive לפני שעונים, גם אם כבר נפתח קודם בשיחה. למבחן, סיכום וכרטיסיות - '
            '"כל ההרצאות.txt".\n'
            "לענות בעברית, צעד אחר צעד, מונחים מקצועיים באנגלית בסוגריים. התמלול אוטומטי: מילה מוזרה היא כנראה "
            "טעות תמלול.")


# --- the "now" file of each course, and a copy in the cloud folder ---
_NOW_COURSE = {"name": None}
_TRANSCRIPT_LINE = re.compile(r"^תמלול מלא: (.+?)/", re.M)


def course_now_write(text):
    """now_watching.txt -> also into the folder of the course it is about. When nothing runs, the last course's
    copy says so too (an AI in that course's project must not think the lecture is still on)."""
    m = _TRANSCRIPT_LINE.search(text)
    course = clean_name(m.group(1)) if m else None
    if course:
        _NOW_COURSE["name"] = course
    elif _NOW_COURSE["name"]:
        course = _NOW_COURSE["name"]
    if not course or not os.path.isdir(course_dir(course)):
        return
    p = os.path.join(course_dir(course), COURSE_NOW_NAME)
    try:
        if os.name == "nt" and os.path.exists(p):
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text.rstrip("\n") + "\n")
        os.replace(tmp, p)
        hide_file(p)
    except (OSError, AttributeError):
        pass
    MIRROR.now_changed(course)


def find_cloud_folders():
    """Folders of Google Drive for desktop / OneDrive on this computer: [(label, path)], Google Drive first."""
    out = []
    home = os.path.expanduser("~")
    my = ("My Drive", "האחסון שלי", "Mi unidad", "Meine Ablage", "Mon Drive")
    if IS_MAC:
        import glob
        for d in sorted(glob.glob(os.path.join(home, "Library", "CloudStorage", "GoogleDrive-*"))):
            for n in my:
                if os.path.isdir(os.path.join(d, n)):
                    out.append(("Google Drive", os.path.join(d, n)))
    elif os.name == "nt":
        import string
        for letter in string.ascii_uppercase[3:]:
            for n in my:
                p = f"{letter}:\\{n}"
                try:
                    if os.path.isdir(p):
                        out.append(("Google Drive", p))
                except OSError:
                    pass
        for n in my:
            p = os.path.join(home, "Google Drive", n)
            if os.path.isdir(p):
                out.append(("Google Drive", p))
    for env in ("OneDriveConsumer", "OneDrive"):
        p = os.environ.get(env)
        if p and os.path.isdir(p) and all(p != x[1] for x in out):
            out.append(("OneDrive", p))
    return out


def mirror_root():
    """<the cloud folder>/הבנתי when "sync to the cloud" is on, else None."""
    base = load_settings().get("mirror")
    if not base or not os.path.isdir(base):
        return None
    return os.path.join(base, MIRROR_DIR_NAME)


class Mirror:
    """Copies each course's "now" file (at most every MIN_S) and all its lectures into the cloud folder."""
    MIN_S = 12

    def __init__(self):
        self.lock = threading.Lock()
        self.due = {}          # course -> time it should be written
        self.full_due = set()  # courses whose "כל ההרצאות.txt" should be rewritten
        self.last = {}
        self.evt = threading.Event()
        self.started = False

    def start(self):
        if not self.started:
            self.started = True
            threading.Thread(target=self.run, daemon=True).start()

    def now_changed(self, course):
        if mirror_root() is None:
            return
        with self.lock:
            self.due.setdefault(course, max(time.time(), self.last.get(course, 0) + self.MIN_S))
        self.evt.set()

    def lectures_changed(self, course=None):
        if mirror_root() is None:
            return
        with self.lock:
            self.full_due.update([course] if course else course_names())
        self.evt.set()

    def scan(self):
        """Courses whose lectures changed since the last look (a lecture ended, was moved, renamed or deleted)."""
        sig = {}
        for c, n, d in lecture_dirs():
            try:
                mt = os.path.getmtime(lecture_txt(d))
            except OSError:
                mt = 0
            a = sig.setdefault(c, [0, 0.0])
            a[0] += 1
            a[1] = max(a[1], mt)
        for c in course_names():
            sig.setdefault(c, [0, 0.0])
        old, self.sig = getattr(self, "sig", None), sig
        if old is None:
            return set(sig)
        return {c for c in sig if old.get(c) != sig[c]}

    def run(self):
        last_scan = 0.0
        while True:
            self.evt.wait(5)
            self.evt.clear()
            root = mirror_root()
            if root is None:
                continue
            if time.time() - last_scan > 60:
                last_scan = time.time()
                try:
                    with self.lock:
                        self.full_due |= self.scan()
                except Exception:
                    save_error("mirror scan")
            now = time.time()
            with self.lock:
                ready = [c for c, t in self.due.items() if t <= now]
                for c in ready:
                    del self.due[c]
                    self.last[c] = now
                full, self.full_due = self.full_due, set()
            for c in ready:
                self.write_now(root, c)
            for c in full:
                self.write_course(root, c)

    @staticmethod
    def _put(path, text):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                with open(path, encoding="utf-8") as f:
                    if f.read() == text:
                        return
            except OSError:
                pass
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, path)
        except OSError:
            pass   # the cloud app may hold the file for a moment - the next change writes it

    def write_now(self, root, course):
        try:
            with open(os.path.join(course_dir(course), COURSE_NOW_NAME), encoding="utf-8") as f:
                body = f.read()
        except OSError:
            return
        # the cloud copy has no pictures: the slide's text goes in instead of its file name
        def slide_text(m):
            rel = m.group(2).replace("\\", "/")
            words = ""
            try:
                with open(os.path.join(LIB_DIR, *rel.split("/")[:-1], ".ocr.json"), encoding="utf-8") as f:
                    words = str((json.load(f) or {}).get(rel.split("/")[-1], ""))
            except (OSError, ValueError, AttributeError):
                pass
            return m.group(1) + (("הטקסט שעליה:\n" + words.strip()) if words.strip() else "(תמונה, בלי טקסט שנקרא)")
        body = re.sub(r"^((?:צילום המסך האחרון|השקופית שעל המסך עכשיו): )(\S.+?\.(?:jpg|png))(?: \(.*\))?$",
                      slide_text, body, flags=re.M)
        stamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        self._put(os.path.join(root, clean_name(course), "עכשיו.txt"),
                  f"הבנתי · הקורס: {course} · עודכן: {stamp}\n\n{body.rstrip()}\n")

    def write_course(self, root, course):
        if not os.path.isdir(course_dir(course)):
            return
        try:
            text, n = course_text(course)
        except Exception:
            save_error("mirror course")
            return
        d = os.path.join(root, clean_name(course))
        self._put(os.path.join(d, "כל ההרצאות.txt"), text + "\n")
        self._put(os.path.join(d, "קרא אותי - הוראות ל-AI.txt"), project_instructions(course, "chatgpt") + "\n")


MIRROR = Mirror()


def set_mirror(path):
    """Turn "sync to the cloud" on (a folder of Google Drive / OneDrive) or off ("")."""
    path = str(path or "").strip()
    if not path:
        save_settings(mirror="")
        return {"ok": True, "mirror": ""}
    if not os.path.isdir(path):
        return {"ok": False, "error": "התיקייה לא נמצאה. צריך את Google Drive למחשב (או OneDrive) מותקן ומחובר."}
    save_settings(mirror=path)
    MIRROR.start()
    MIRROR.lectures_changed()
    for c in course_names():
        MIRROR.now_changed(c)
    return {"ok": True, "mirror": path, "folder": os.path.join(path, MIRROR_DIR_NAME)}


def mirror_status():
    return {"mirror": load_settings().get("mirror") or "", "found": [{"label": a, "path": b} for a, b in find_cloud_folders()]}


# --- the AI's window on a third of the screen, beside the lecture ---
def place_window_left_third(match, timeout=10.0):
    """Windows: move the newest window whose title matches to the left third of the main screen (the lecture
    keeps the right two thirds - the layout the guide recommends). Waits for it to appear. True when moved."""
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32")
    HWND = wintypes.HWND
    user32.GetWindowTextW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [HWND]
    user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
    user32.MoveWindow.argtypes = [HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
    user32.SetForegroundWindow.argtypes = [HWND]
    area = wintypes.RECT()
    if not user32.SystemParametersInfoW(0x30, 0, ctypes.byref(area), 0):   # SPI_GETWORKAREA: without the taskbar
        return False
    end = time.time() + timeout
    while time.time() < end:
        found = []

        def each(hwnd, _):
            try:
                if user32.IsWindowVisible(hwnd):
                    buf = ctypes.create_unicode_buffer(300)
                    user32.GetWindowTextW(hwnd, buf, 300)
                    if buf.value and match(buf.value):
                        found.append(hwnd)
            except Exception:
                pass
            return True

        user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, wintypes.LPARAM)(each), 0)
        if found:
            h = found[0]   # EnumWindows lists from the top: the one just opened or brought forward
            w = (area.right - area.left) // 3
            user32.ShowWindow(h, 9)   # SW_RESTORE: a maximized window does not move
            user32.MoveWindow(h, area.left, area.top, w, area.bottom - area.top, True)
            user32.SetForegroundWindow(h)
            return True
        time.sleep(0.4)
    return False


AI_WINDOW_TITLE = {"claude": re.compile(r"^Claude\b"), "chatgpt": re.compile(r"^ChatGPT\b|^Codex\b"),
                   "gemini": re.compile(r"Gemini|Antigravity|agy\b")}


def open_ai_app_placed(app):
    """open_ai_app, and its window on the left third (in the background: it takes a few seconds to appear)."""
    ok = open_ai_app(app)
    if ok and os.name == "nt" and load_settings().get("place_ai", True):
        rx = AI_WINDOW_TITLE.get(app)
        threading.Thread(target=place_window_left_third, args=(rx.search,), daemon=True).start()
    return ok


def open_course_terminal(course):
    """A command window inside the course folder running Gemini (Antigravity CLI, agy), on the left third."""
    d = course_dir(course)
    if not os.path.isdir(d):
        return {"ok": False, "error": "הקורס לא נמצא."}
    import shutil
    import subprocess
    title = f"Gemini - {clean_name(course)}"
    tool = "agy" if shutil.which("agy") else "gemini" if shutil.which("gemini") else None
    try:
        if IS_MAC:
            q = d.replace("\\", "\\\\").replace('"', '\\"')
            run = f'cd \\"{q}\\"; ' + (tool or "echo 'Antigravity CLI is not installed'")
            subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{run}"',
                              "-e", 'tell application "Terminal" to activate'])
        elif os.name == "nt":
            lit = d.replace("'", "''")
            missing = ("Write-Host 'Antigravity CLI (agy) is not installed yet. Install once:'; "
                       "Write-Host 'irm https://antigravity.google/cli/install.ps1 | iex'")
            ps = (f"$Host.UI.RawUI.WindowTitle = '{title.replace(chr(39), chr(39) * 2)}'; "
                  f"Set-Location -LiteralPath '{lit}'; " + (tool if tool else missing))
            subprocess.Popen(["cmd", "/c", "start", "", "powershell", "-NoExit", "-NoProfile", "-Command", ps],
                             creationflags=0x08000000)
            if load_settings().get("place_ai", True):
                threading.Thread(target=place_window_left_third, args=(lambda t: t.startswith(title),),
                                 daemon=True).start()
        else:
            return {"ok": False, "error": "לא נתמך במחשב הזה."}
    except OSError:
        save_error("open course terminal")
        return {"ok": False, "error": "לא הצלחתי לפתוח חלון פקודות."}
    return {"ok": True, "tool": tool or "", "folder": d}


def course_ai_info(course):
    """Everything the course page shows about the course's AI."""
    return {"links": course_ai_links(course), "folder": course_dir(course),
            "instructions": {a: project_instructions(course, a) for a in AI_APPS},
            "mirror": bool(mirror_root()), "mirror_folder": os.path.join(mirror_root(), clean_name(course)) if mirror_root() else ""}


# ---------- is there a newer version? (the GitHub releases of the open-source project) ----------
GITHUB_REPO = "pechter-roei41/hevanti"
RELEASES_URL = os.environ.get("BZM_RELEASES_URL") or f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def check_update():
    """A release tag looks like v2.0 or v2.0-20261014 (same number, newer build: the date tells them apart)."""
    import urllib.request
    if not load_settings().get("check_updates", True):   # turned off in "חיבור AI"
        return None
    try:
        req = urllib.request.Request(RELEASES_URL, headers={"User-Agent": "Hevanti/" + VERSION,
                                                            "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    tag = str(d.get("tag_name") or "")
    m = re.fullmatch(r"v?(\d+(?:\.\d+){0,2})(?:-(\d{4})(\d\d)(\d\d))?", tag)
    if not m:
        return None
    version, date = m.group(1), (f"{m.group(4)}.{m.group(3)}.{m.group(2)}" if m.group(2) else "")

    def key(v, dt):
        nums = tuple(int(x) for x in re.findall(r"\d+", str(v))[:3])
        nums = nums + (0,) * (3 - len(nums))
        dm = re.fullmatch(r"(\d\d)\.(\d\d)\.(\d{4})", str(dt or ""))
        return nums, (dm.group(3) + dm.group(2) + dm.group(1)) if dm else ""
    mine = key(VERSION, VERSION_DATE)
    theirs = key(version, date)
    if theirs[0] < mine[0] or (theirs[0] == mine[0] and (not theirs[1] or theirs[1] <= mine[1])):
        return None
    APP.update = {"version": version, "date": date, "url": str(d.get("html_url") or GUIDE_URL),
                  "notes": str(d.get("name") or "")[:300]}
    return APP.update


def lecture_summary(f):
    ld = lecture_from_rel(f)
    try:
        with open(os.path.join(ld, SUMMARY_NAME), encoding="utf-8") as fh:
            text = fh.read()
        return re.sub(r"^# .*\n+", "", text, count=1).strip()
    except (OSError, TypeError):
        return ""


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(**kw):
    d = load_settings()
    d.update(kw)
    try:
        os.makedirs(LOCAL_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except OSError:
        pass


OLD_LIVE_STEM = re.compile(r"(\d{4}-\d\d-\d\d)_(\d\d-\d\d)(_en)?")


def migrate_old_layout():
    """1.x kept "transcripts\\" and "screenshots\\" in the tool folder. Each lecture moves into
    "הקורסים שלי\\ללא קורס\\<lecture>\\" with its slides. Returns how many moved."""
    import shutil
    if not os.path.isdir(OUT_DIR):
        return 0
    old_shots = os.path.join(HERE, "screenshots")
    dest = course_dir(NO_COURSE)
    moved = 0
    for fn in sorted(os.listdir(OUT_DIR)):
        src = os.path.join(OUT_DIR, fn)
        if not fn.endswith(".txt") or not os.path.isfile(src):
            continue
        stem = fn[:-4]
        m = OLD_LIVE_STEM.fullmatch(stem)
        name = f"{m.group(1)} {m.group(2)} הרצאה" + (" באנגלית" if m.group(3) else "") if m else \
            (stem[:-3] if stem.endswith("_en") else stem)
        try:
            os.makedirs(dest, exist_ok=True)
            name = free_folder(dest, clean_name(name, "הרצאה"))
            d = os.path.join(dest, name)
            os.makedirs(d)
            with open(src, encoding="utf-8", errors="replace") as f:
                text = f.read()
            text = re.sub(r"\[צילום מסך: screenshots/[^\]]*/([^/\]]+)\]", "[צילום מסך: " + SLIDES_NAME + r"/\1]", text)
            with open(lecture_txt(d), "w", encoding="utf-8") as f:
                f.write(text)
            if os.path.isdir(os.path.join(old_shots, stem)):
                shutil.move(os.path.join(old_shots, stem), os.path.join(d, SLIDES_NAME))
            old_state = os.path.join(CACHE_DIR, stem + ".json")
            if os.path.isfile(old_state):
                shutil.copy2(old_state, os.path.join(d, STATE_NAME))
                hide_file(os.path.join(d, STATE_NAME))
            os.remove(src)
            moved += 1
        except OSError:
            save_error("migrate " + fn)
    for old in (OUT_DIR, old_shots):
        try:
            if os.path.isdir(old) and not os.listdir(old):
                os.rmdir(old)
        except OSError:
            pass
    _remove_quietly(os.path.join(HERE, "now_watching.txt"))
    return moved


def save_error_text(context, text):
    """Like save_error, for a problem that is not a Python exception (e.g. what a helper program said)."""
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.datetime.now()} (גרסה {VERSION}) {context} ---\n{str(text)[-4000:]}\n")
    except Exception:
        pass


class Media:
    """A recording on this computer: what the page plays, where the slides come from, what is transcribed."""

    def __init__(self, path, video="same", audio=None, title=None):
        self.path = path                                # the page plays this
        self.video = path if video == "same" else video  # slides come from this (None = sound only)
        self.audio = audio or path                      # this is transcribed
        self.title = title or os.path.splitext(os.path.basename(path))[0]


# ----- recordings from links -----
def direct_link(url):
    """Share links of Google Drive / Dropbox / OneDrive -> a link to the file itself."""
    m = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:.*&)?id=)([\w-]+)", url)
    if m:
        return f"https://drive.usercontent.google.com/download?id={m.group(1)}&export=download&confirm=t"
    low = url.lower()
    if "dropbox.com" in low:
        return re.sub(r"([?&])dl=0", r"\1dl=1", url) if "dl=0" in low else url + ("&" if "?" in url else "?") + "dl=1"
    if ("sharepoint.com" in low or "1drv.ms" in low or "onedrive.live.com" in low) and "download=1" not in low:
        return url + ("&" if "?" in url else "?") + "download=1"
    return url


def _download_name(resp, url):
    import urllib.parse
    cd = resp.headers.get("Content-Disposition") or ""
    m = re.search(r"filename\*=(?:UTF-8|utf-8)''([^;]+)", cd) or re.search(r'filename="?([^";]+)"?', cd)
    name = urllib.parse.unquote(m.group(1)) if m else urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(resp.geturl()).path))
    stem, ext = os.path.splitext(name)
    if not ext or len(ext) > 6:
        stem, ext = name or "video", ".mp4"
    return safe_stem(stem) + ext


def save_download(resp, url):
    """An open download of a file -> the file in the videos folder (with a progress line), or None."""
    os.makedirs(VIDEO_DIR, exist_ok=True)
    path = os.path.join(VIDEO_DIR, _download_name(resp, url))
    size = int(resp.headers.get("Content-Length") or 0)
    if size and os.path.isfile(path) and os.path.getsize(path) == size:
        resp.close()
        return path  # downloaded before
    part, got, t0 = path + ".part", 0, time.time()
    try:
        with resp, open(part, "wb") as f:
            while True:
                buf = resp.read(1 << 20)
                if not buf:
                    break
                f.write(buf)
                got += len(buf)
                rate = got / max(time.time() - t0, 0.1)
                if size:
                    _progress_line(f"מוריד את ההקלטה: {got * 100 // size}% ({got >> 20}/{size >> 20}MB) {_fmt_eta((size - got) / max(rate, 1))}")
                else:
                    _progress_line(f"מוריד את ההקלטה: {got >> 20}MB")
    except Exception as e:
        _progress_line("", end=True)
        problem(f"ההורדה נקטעה באמצע ({e.__class__.__name__}). להפעיל שוב.")
        return None
    _progress_line("", end=True)
    if size and got < size:
        problem("ההורדה נקטעה באמצע. להפעיל שוב.")
        return None
    os.replace(part, path)
    return path


SITE_HOSTS = ("vimeo.com", "zoom.us", "panopto", "kaltura", "facebook.com", "fb.watch",
              "dailymotion.com", "ted.com", "twitch.tv", "rumble.com", "loom.com")


# YouTube is not downloaded: its terms don't allow it. A YouTube lecture is transcribed as a live lecture
# while it plays on the screen.
YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")
YOUTUBE_MSG = ("הבנתי לא מורידה סרטונים מיוטיוב (התנאים של יוטיוב לא מתירים). אפשר לפתוח את הסרטון ביוטיוב, "
               "לבחור כאן \"הרצאה חיה\" ולנגן אותו על המסך - הבנתי תתמלל ותצלם את השקופיות תוך כדי.")


def is_youtube(url):
    import urllib.parse
    host = (urllib.parse.urlsplit(str(url)).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in YOUTUBE_HOSTS)


LINK_TITLES = {}   # link -> the recording's name, when the page knows it (the Panopto bookmark)


def fetch_link(url):
    """A link -> Media on this computer, or None (after telling the user why)."""
    m = _fetch_link(url)
    if m is not None and LINK_TITLES.get(url):
        m.title = LINK_TITLES[url]
    return m


def _fetch_link(url):
    import urllib.parse
    if is_youtube(url):
        problem(YOUTUBE_MSG)
        return None
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    is_file = parts.path.lower().endswith((".mp4", ".m4a", ".mp3", ".m4v", ".webm", ".mov", ".wav"))
    if (any(h in host for h in SITE_HOSTS) and not is_file) or parts.path.lower().endswith(".m3u8"):
        return site_download(url)   # a video site, or a stream in pieces (HLS) - yt-dlp puts it together
    try:
        resp = _http(direct_link(url), headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    except Exception as e:
        problem(f"לא הצלחתי להוריד מהקישור ({e.__class__.__name__}). לבדוק את הקישור ואת החיבור לאינטרנט.")
        return None
    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "text/html" in ctype:
        resp.close()
        return site_download(url)  # a web page, not a file - maybe a video site the downloader knows
    path = save_download(resp, url)
    return Media(path) if path else None


# Video sites (Zoom recordings, Vimeo and others - not YouTube) are downloaded with yt-dlp, an open-source
# downloader that is installed the first time it is needed. It runs as a separate program, so it can be updated and retried when a site changes.
YTDLP_AUDIO = "ba[ext=m4a]/ba/b"
YTDLP_VIDEO = "bv*[height<=720][ext=mp4]/bv*[height<=720]/b[height<=720]/bv*/b"


def ensure_ytdlp(upgrade=False):
    import importlib
    import importlib.util
    import subprocess
    if not upgrade and importlib.util.find_spec("yt_dlp"):
        return True
    if upgrade:
        show_status("מעדכן את רכיב ההורדה מאתרים (yt-dlp)...")
    else:
        log("מתקין רכיב להורדה מאתרי וידאו (yt-dlp) - פעם אחת בלבד, כ-50MB...")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "yt-dlp"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    draft_clear()
    importlib.invalidate_caches()
    if r.returncode != 0:
        save_error_text("yt-dlp install", r.stderr)
    return importlib.util.find_spec("yt_dlp") is not None


def run_ytdlp(args, password=None, on_line=None):
    """yt-dlp in its own process -> (ok, output lines)."""
    import subprocess
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-warnings", "--socket-timeout", "30"]
    if password:
        cmd += ["--video-password", password]
    p = subprocess.Popen(cmd + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         text=True, encoding="utf-8", errors="replace", env=env,
                         creationflags=0x08000000 if os.name == "nt" else 0)
    out = []
    for line in p.stdout:
        line = line.rstrip("\r\n")
        if on_line and on_line(line):
            continue
        out.append(line)
    p.wait()
    return p.returncode == 0, out


def link_problem(text):
    """What went wrong, from what yt-dlp said."""
    e = str(text).lower()
    if "passcode" in e or "password" in e:
        return "password"
    if "unsupported url" in e:
        return "unsupported"
    if "not a bot" in e:
        return "bot"
    if any(k in e for k in ("live event", "is live", "premieres in", "this live")):
        return "live"
    if any(k in e for k in ("sign in", "log in", "login", "private", "members", "cookies", "authentication",
                            "permission", "not authorized", "http error 401", "registered users", "access denied")):
        return "login"
    if any(k in e for k in ("getaddrinfo", "timed out", "connection", "network is unreachable", "name resolution")):
        return "network"
    return "other"


LINK_MESSAGES = {
    "login": "ההקלטה הזו דורשת התחברות לאתר (למשל הקלטה של קורס). אם יש באתר כפתור הורדה: להוריד את הקובץ ולגרור "
             "אותו לכאן. אם אין: לפתוח את ההקלטה באתר ולהתחיל בדף של הכלי הרצאה חיה - הכלי יתמלל אותה תוך כדי הצפייה.",
    "unsupported": "הקישור לא מוביל לסרטון שהכלי מכיר. אפשר להוריד את הקובץ ולגרור אותו לכאן.",
    "bot": "האתר חוסם כרגע הורדות מהרשת שלך (בדיקת \"לא רובוט\"). אפשר לנסות שוב בעוד כמה שעות, או לפתוח את "
           "ההקלטה באתר ולהתחיל בדף של הכלי הרצאה חיה - הכלי יתמלל אותה תוך כדי הצפייה.",
    "live": "זה שידור חי. לשידור חי מתחילים בדף של הכלי הרצאה חיה.",
    "network": "אין חיבור לאתר. לבדוק את האינטרנט ולנסות שוב.",
    "other": "לא הצלחתי להוריד מהקישור. אם יש באתר כפתור הורדה: להוריד את הקובץ ולגרור אותו לכאן. "
             "(הפרטים נשמרו ב-error_log.txt)",
}


PANOPTO_MSG = ("הקלטה בפנופטו דורשת התחברות, אז הבנתי לא יכולה להוריד אותה מהקישור. במקום זה: \"הרצאה מוקלטת\" ← "
               "\"הקלטה מפנופטו\" - גוררים פעם אחת את הכפתור לשורת הסימניות, ואז לוחצים עליו כשההקלטה פתוחה בפנופטו.")


def _ytdlp_info(url):
    """yt-dlp looks at the link: title, length, live or not. Asks for a passcode if the recording has one."""
    password, upgraded = None, False
    for _ in range(4):
        ok, out = run_ytdlp(["-J", url], password)
        if ok:
            for line in out:
                if line.startswith("{"):
                    try:
                        return json.loads(line), password
                    except ValueError:
                        break
        text = "\n".join(out)
        kind = link_problem(text)
        if kind == "password":
            draft_clear()
            password = ask_user("להקלטה יש סיסמה (קוד גישה). מה הקוד?", secret=True).strip()
            if not password:
                problem("בוטל: בלי קוד הגישה אי אפשר להוריד את ההקלטה.")
                return None, None
            continue
        if kind == "other" and not upgraded:  # sites change - a newer yt-dlp often fixes it
            upgraded = True
            ensure_ytdlp(upgrade=True)
            continue
        save_error_text("yt-dlp " + url, text)
        problem(PANOPTO_MSG if kind == "login" and "panopto" in url.lower() else LINK_MESSAGES[kind])
        return None, None
    return None, None


def _ytdlp_get(url, fmt, dest_stem, label, password):
    """Download one format -> the file, or None."""
    os.makedirs(VIDEO_DIR, exist_ok=True)
    state = {"t0": time.time()}

    def on_line(line):
        if not line.startswith("BZM|"):
            return False
        try:
            _, got, total, est = line.split("|")[:4]
            got = int(float(got)) if got not in ("", "NA", "None") else 0
            tot = total if total not in ("", "NA", "None") else est
            tot = int(float(tot)) if tot not in ("", "NA", "None") else 0
        except ValueError:
            return True
        if tot:
            rate = got / max(time.time() - state["t0"], 0.1)
            _progress_line(f"מוריד {label}: {min(100, got * 100 // tot)}% ({got >> 20}/{tot >> 20}MB) {_fmt_eta((tot - got) / max(rate, 1))}")
        return True

    ok, out = run_ytdlp(["-f", fmt, "-o", os.path.join(VIDEO_DIR, dest_stem + ".%(ext)s"),
                         "--progress", "--newline", "--progress-template",
                         "download:BZM|%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s",
                         "-O", "after_move:filepath", url], password, on_line)
    _progress_line("", end=True)
    files = [x.strip() for x in out if x.strip() and os.path.isfile(x.strip())]
    if ok and files:
        return files[-1]
    save_error_text(f"yt-dlp download {fmt} {url}", "\n".join(out))
    return None


def has_stream(path, kind):
    try:
        import av
        with av.open(path) as c:
            return len(getattr(c.streams, kind)) > 0
    except Exception:
        return False


def merge_av(video_path, audio_path, out_path):
    """Picture from one file + sound from another -> one MP4 file the browser plays.
    The streams are copied as they are (no re-encoding), so it takes seconds."""
    import av
    tmp = out_path + ".part"
    with av.open(video_path) as vin, av.open(audio_path) as ain:
        vs, aus = vin.streams.video[0], ain.streams.audio[0]
        with av.open(tmp, "w", format="mp4") as out:
            add = getattr(out, "add_stream_from_template", None)
            ov = add(vs) if add else out.add_stream(template=vs)
            oa = add(aus) if add else out.add_stream(template=aus)

            def packets(c, s):
                for p in c.demux(s):
                    if p.dts is None and p.pts is None:
                        continue  # the empty packet at the end
                    if p.dts is None:
                        p.dts = p.pts
                    yield p

            def when(p):
                return float(p.dts * p.time_base)

            gv, ga = packets(vin, vs), packets(ain, aus)
            pv, pa = next(gv, None), next(ga, None)
            while pv is not None or pa is not None:
                if pa is None or (pv is not None and when(pv) <= when(pa)):
                    pv.stream = ov
                    out.mux(pv)
                    pv = next(gv, None)
                else:
                    pa.stream = oa
                    out.mux(pa)
                    pa = next(ga, None)
    os.replace(tmp, out_path)


def site_download(url):
    """A video site (not YouTube) -> Media: sound (to transcribe) + picture up to 720p (slides, player)."""
    if is_youtube(url):
        problem(YOUTUBE_MSG)
        return None
    if not ensure_ytdlp():
        problem("לא הצלחתי להתקין את רכיב ההורדה מאתרים. לבדוק את החיבור לאינטרנט ולנסות שוב, "
             "או להוריד את הסרטון ולגרור את הקובץ לכאן.")
        return None
    show_status("בודק את הקישור...")
    info, password = _ytdlp_info(url)
    draft_clear()
    if not info:
        return None
    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]
    if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
        problem(LINK_MESSAGES["live"])
        return None
    title = info.get("title") or "video"
    stem = safe_stem(title)
    final = os.path.join(VIDEO_DIR, stem + ".mp4")
    if os.path.isfile(final):
        log(f"ההקלטה כבר הורדה בעבר: {stem}")
        return Media(final, title=title)
    log(f"מוריד: {title}" + (f" ({hms(info['duration'])})" if info.get("duration") else ""))
    fmts = info.get("formats") or []
    has_picture = any((f.get("vcodec") or "none") != "none" for f in fmts) or not fmts
    audio = _ytdlp_get(url, YTDLP_AUDIO, stem + ".sound", "את הקול", password)
    if not audio:
        problem(LINK_MESSAGES["other"])
        return None
    if has_stream(audio, "video"):  # the site has only files with both - this is the whole recording
        return Media(audio, title=title)
    if not has_picture:
        return Media(audio, video=None, title=title)
    video = _ytdlp_get(url, YTDLP_VIDEO, stem + ".picture", "את התמונה (בשביל השקופיות)", password)
    if not video:
        log("את התמונה לא הצלחתי להוריד - ממשיך רק עם הקול (בלי שקופיות).")
        return Media(audio, video=None, title=title)
    if has_stream(video, "audio"):  # the site gave one file with both
        _remove_quietly(audio)
        return Media(video, title=title)
    try:
        show_status("מחבר את הקול והתמונה לקובץ אחד...")
        merge_av(video, audio, final)
        draft_clear()
        _remove_quietly(video, audio)
        return Media(final, title=title)
    except Exception:
        draft_clear()
        save_error("merge")
        log("לא הצלחתי לחבר את הקול והתמונה. בנגן יהיה הקול, והשקופיות יופיעו כתמונות.")
        return Media(audio, video=video, title=title)


def _remove_quietly(*paths):
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass


def problem(text):
    """A reason the recording could not be opened - shown on the page too."""
    _LAST_PROBLEM[0] = text
    show(text)


def video_source(arg):
    """What the user gave (a file, or a link) -> Media on this computer, or None."""
    s = (arg or "").strip().strip('"').strip("'").strip()
    if s.lower().startswith(("http://", "https://")):
        return fetch_link(s)
    if s.lower().startswith("file:///"):
        import urllib.parse
        s = urllib.parse.unquote(s[8:])
    if os.path.isfile(s):
        return Media(os.path.abspath(s))
    problem(f"לא מצאתי את הקובץ: {s}")
    return None


def media_duration(av, path):
    with av.open(path) as c:
        if c.duration:
            return c.duration / 1_000_000
        for st in list(c.streams.audio) + list(c.streams.video):
            if st.duration and st.time_base:
                return float(st.duration * st.time_base)
    return 0.0


# ----- the transcript of a recording, built block by block -----
def transcript_done(path):
    try:
        with open(path, encoding="utf-8") as f:
            return any(line.startswith("# סוף") for line in f)
    except OSError:
        return False


SHOT_RE = re.compile(r"\[צילום מסך: (.+)\]$")
GAP_RE = re.compile(r"\(עוד לא תומלל עד \d")


def read_transcript(path):
    """A finished transcript file -> ([(t, text)], {picture name: t})."""
    says, shots = [], {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\[(\d+):(\d\d):(\d\d)\] (.*)", line.rstrip("\n"))
            if not m:
                continue
            t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            x = m.group(4)
            sm = SHOT_RE.match(x)
            if sm:
                shots[os.path.basename(sm.group(1))] = float(t)
            elif not GAP_RE.match(x):
                says.append((float(t), x))
    return says, shots


def make_blocks(n_samples, size_s, audio16=None):
    """Cut the recording into blocks of about size_s seconds - each cut in a quiet moment."""
    sr, blocks, pos = TARGET_SR, [], 0
    while pos < n_samples:
        left = n_samples - pos
        if left <= size_s * 1.3 * sr:
            cut = left
        elif audio16 is not None:
            cut = find_cut(audio16[pos:pos + int(size_s * sr) + sr], sr, size_s * 0.75, size_s)
        else:
            cut = int(size_s * sr)
        blocks.append((pos / sr, (pos + cut) / sr))
        pos += cut
    return blocks


def transcript_length(path):
    """The length written in a transcript's first line (seconds), or None."""
    try:
        with open(path, encoding="utf-8") as f:
            m = re.search(r"אורך: (\d+):(\d\d):(\d\d)", f.readline())
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else None
    except OSError:
        return None


def find_recording(stem, duration):
    """This recording, already in some course (opened before): (course, folder name) or None."""
    for course, name, d in lecture_dirs():
        if name != stem and not re.fullmatch(re.escape(stem) + r" \(\d+\)", name):
            continue
        length = transcript_length(lecture_txt(d))
        if length is not None and duration > 0 and abs(length - int(duration)) <= 2:
            return course, name
    return None


def free_stem(course, stem, duration):
    """(course, folder) for this recording. Opened before -> the same folder (in whatever course it is now).
    Another recording with the same name (two courses can both have "Lecture 1.mp4") gets "(2)", "(3)"..."""
    found = find_recording(stem, duration)
    if found:
        return found
    for n in range(1, 100):
        cand = stem if n == 1 else f"{stem} ({n})"
        d = lecture_dir(course, cand)
        if not os.path.exists(d):
            return course, cand
        length = transcript_length(lecture_txt(d))
        if length is not None and (duration <= 0 or abs(length - int(duration)) <= 2):
            return course, cand
    return course, stem


class Recording:
    """One recording: its transcript (built in blocks, the part you watch first), slides, and where you are."""

    def __init__(self, media, duration, course=""):
        self.media = media
        self.duration = float(duration or 0)
        self.course, self.stem = free_stem(clean_name(course, NO_COURSE), clean_name(media.title, "הקלטה"),
                                           self.duration)
        self.dir = lecture_dir(self.course, self.stem)
        self.out_name = self.stem + ".txt"
        self.out_path = os.path.join(self.dir, self.out_name)
        self.rel_dir = lib_rel(self.dir)
        self.rel_transcript = self.rel_dir + "/" + self.out_name
        self.shots_dir = os.path.join(self.dir, SLIDES_NAME)
        self.rel_shots = self.rel_dir + "/" + SLIDES_NAME
        self.cache_path = os.path.join(self.dir, STATE_NAME)
        self.lock = threading.RLock()
        self.save_lock = threading.Lock()  # one save at a time (the worker, the slides and the window all save)
        self.blocks, self.done, self.busy = [], set(), set()
        self.says = {}            # block -> [(t, text)], also while it is being transcribed
        self.shots = {}           # picture file name -> t
        self.slides_done = media.video is None or not SCREEN_ENABLED
        self.rev = 1              # grows whenever something new is ready (the page asks for it)
        self.phase, self.note, self.error = "start", "", None
        self.model_desc = ""
        self.pos, self.playing, self.page_at, self.resume_at = None, False, 0.0, None
        self.media_error = None
        self.saved_at = 0.0
        self.changed = False      # new text or slides since the last save (a finished transcript is never rewritten)
        self.place_changed = False  # you moved - the place is kept for next time
        self.closed = False

    # --- what is ready ---
    def complete(self):
        with self.lock:
            return bool(self.blocks) and len(self.done) == len(self.blocks)

    def finished(self):
        return self.complete() and self.slides_done

    def progress(self):
        with self.lock:
            if not self.blocks:
                return 0
            total = self.blocks[-1][1] or 1
            got = sum(e - s for i, (s, e) in enumerate(self.blocks) if i in self.done)
            return min(100, int(100 * got / total))

    def ready_ranges(self):
        with self.lock:
            out = []
            for i, (s, e) in enumerate(self.blocks):
                if i in self.done:
                    if out and abs(out[-1][1] - s) < 0.01:
                        out[-1][1] = e
                    else:
                        out.append([s, e])
            return out

    def items(self):
        """Everything in time order: (t, kind, value) - 'say' text, 'shot' picture, 'gap' end of a missing part."""
        with self.lock:
            out, gap = [], None
            for i, (s, e) in enumerate(self.blocks):
                lines = self.says.get(i, [])
                if lines and gap is not None:
                    out.append(gap)
                    gap = None
                out += [(t, "say", x) for t, x in lines]
                if i not in self.done:
                    if gap is not None and not lines:
                        gap = (gap[0], "gap", e)  # one note for neighbouring parts that are not ready
                    else:
                        if gap is not None:
                            out.append(gap)
                        gap = (lines[-1][0] + 0.01 if lines else s, "gap", e)
                elif gap is not None:
                    out.append(gap)
                    gap = None
            if gap is not None:
                out.append(gap)
            out += [(t, "shot", name) for name, t in self.shots.items()]
        order = {"say": 0, "gap": 1, "shot": 2}
        out.sort(key=lambda x: (x[0], order[x[1]]))
        return out

    # --- the transcript file + progress kept for next time ---
    def transcript_text(self):
        head = [f"# תמלול הקלטה ({'אנגלית' if LANG == 'en' else 'עברית'}) - {self.stem} | אורך: {hms(self.duration)} | "
                f"גרסה: {VERSION} | מודל: {self.model_desc or '-'}"]
        if not self.complete():
            head.append(f"# בעבודה: {self.progress()}% מוכן. חלקים שעוד לא תומללו מסומנים \"(עוד לא תומלל)\".")
        lines = []
        for t, kind, v in self.items():
            if kind == "say":
                lines.append(f"[{hms(t)}] {v}")
            elif kind == "shot":
                lines.append(f"[{hms(t)}] [צילום מסך: {SLIDES_NAME}/{v}]")
            else:
                lines.append(f"[{hms(t)}] (עוד לא תומלל עד {hms(v)})")
        tail = [f"# סוף - {len(self.shots)} צילומי מסך"] if self.finished() else []
        return "\n".join(head + lines + tail) + "\n"

    def save(self, force=False):
        with self.save_lock:
            self._save(force)

    def _save(self, force):
        with self.lock:
            if not self.blocks or not (self.changed or self.place_changed) or \
                    (not force and time.time() - self.saved_at < 2):
                return
            text = self.transcript_text() if self.changed else None
            self.saved_at, self.changed, self.place_changed = time.time(), False, False
            data = {"v": 2, "audio": os.path.abspath(self.media.audio), "path": os.path.abspath(self.media.path),
                    "video": os.path.abspath(self.media.video) if self.media.video else None,
                    "title": self.media.title, "duration": self.duration, "lang": LANG,
                    "blocks": self.blocks, "done": sorted(self.done),
                    "says": {str(i): self.says.get(i, []) for i in sorted(self.done)},
                    "shots": self.shots, "slides_done": self.slides_done, "pos": self.pos,
                    "model": self.model_desc}
        if text is not None:
            try:
                os.makedirs(self.dir, exist_ok=True)
                tmp = self.out_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(text)
                os.replace(tmp, self.out_path)
            except OSError:
                with self.lock:
                    self.changed = True  # open in another program right now - the next save writes it
        try:
            os.makedirs(self.dir, exist_ok=True)
            tmp = self.cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, self.cache_path)
            hide_file(self.cache_path)
        except OSError:
            pass

    def restore(self):
        """A finished transcript, or one that stopped in the middle -> 'done' / 'resumed' / None (start fresh)."""
        if transcript_done(self.out_path):
            try:
                says, shots = read_transcript(self.out_path)
            except OSError:
                return None
            with self.lock:
                end = max(self.duration, says[-1][0] + 1 if says else 1.0)
                self.blocks, self.done = [(0.0, end)], {0}
                self.says, self.shots, self.slides_done = {0: says}, shots, True
                self.phase = "done"
            self._load_place()
            return "done"
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            return None
        cached = float(d.get("duration") or 0)
        if self.duration <= 0:  # some files do not say how long they are
            self.duration = cached
        if d.get("lang") != LANG or abs(cached - self.duration) > 1.5 or not d.get("blocks"):
            return None
        with self.lock:
            self.blocks = [tuple(b) for b in d["blocks"]]
            self.done = set(int(i) for i in d.get("done", []))
            self.says = {int(i): [tuple(x) for x in v] for i, v in d.get("says", {}).items()}
            self.shots = {k: float(v) for k, v in d.get("shots", {}).items()}
            self.slides_done = bool(d.get("slides_done")) or self.slides_done
            self.model_desc = d.get("model") or ""
            if d.get("pos") is not None:
                self.resume_at = float(d["pos"])
        return "resumed"

    def _load_place(self):
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                p = json.load(f).get("pos")
            if p is not None:
                self.resume_at = float(p)
        except (OSError, ValueError, AttributeError):
            pass

    # --- the block worker ---
    def claim_block(self):
        """The next block to transcribe: where you are watching, then the next minutes, then the rest in order."""
        with self.lock:
            todo = [i for i in range(len(self.blocks)) if i not in self.done and i not in self.busy]
            if not todo:
                return None
            pick = todo[0]
            pos = self.pos if (self.pos is not None and time.time() - self.page_at < 60) else None
            if pos is not None:
                for i in todo:
                    s, e = self.blocks[i]
                    if e > pos - 5:
                        if s <= pos + AHEAD_S:
                            pick = i
                        break
            self.busy.add(pick)
            self.says[pick] = []
            self.rev += 1
            return pick

    def text_before(self, i):
        with self.lock:
            return " ".join(x for _, x in self.says.get(i - 1, [])) if (i - 1) in self.done else ""

    def add_say(self, i, t, text):
        with self.lock:
            self.says.setdefault(i, []).append((t, text))
            self.rev += 1
            self.changed = True

    def block_done(self, i):
        with self.lock:
            self.busy.discard(i)
            self.done.add(i)
            self.rev += 1
            self.changed = True
        self.save(force=True)

    def clear_block(self, i):
        with self.lock:
            self.says[i] = []
            self.rev += 1
            self.changed = True

    def release_block(self, i):
        with self.lock:
            self.busy.discard(i)

    def add_shot(self, t, name):
        with self.lock:
            self.shots[name] = t
            self.rev += 1
            self.changed = True
        self.save()

    def set_slides_done(self):
        with self.lock:
            self.slides_done = True
            self.rev += 1
            self.changed = True
        self.save(force=True)

    def set_phase(self, phase, note=""):
        with self.lock:
            self.phase, self.note = phase, note

    def set_note(self, note):
        self.note = note

    # --- where you are (the page reports it) ---
    def set_place(self, d):
        with self.lock:
            self.page_at = time.time()
            if d.get("closed"):
                self.page_at = 0.0
            if d.get("pos") is not None:
                try:
                    p = max(0.0, float(d["pos"]))
                    if self.pos is None or abs(p - self.pos) >= 5:
                        self.place_changed = True
                    self.pos = p
                except (TypeError, ValueError):
                    pass
            if "paused" in d:
                self.playing = not d["paused"] and not d.get("ended")
            if d.get("error"):
                self.media_error = str(d["error"])[:200]

    def page_alive(self):
        # a paused page in a background tab may check in only once a minute (browser power saving)
        return time.time() - self.page_at < 75

    def state(self, rev):
        """What the page shows (all the lines only when something changed since `rev`)."""
        with self.lock:
            st = {"rev": self.rev, "phase": self.phase, "note": self.note, "progress": self.progress(),
                  "complete": self.complete(), "slides_done": self.slides_done, "title": self.stem,
                  "duration": self.duration, "lang": LANG, "ready": self.ready_ranges(), "resume": self.resume_at,
                  "transcript": self.rel_transcript, "has_video": self.media.video is not None,
                  "plays_video": self.media.path == self.media.video}
            if rev != self.rev:
                lines = []
                for t, kind, v in self.items():
                    if kind == "say":
                        lines.append({"t": round(t, 2), "x": v})
                    elif kind == "shot":
                        lines.append({"t": round(t, 2), "img": v})
                    else:
                        lines.append({"t": round(t, 2), "gap": round(v, 2)})
                st["lines"] = lines
        return st

    def slide_at(self, pos):
        with self.lock:
            best = None
            for name, t in self.shots.items():
                if t <= pos + 0.5 and (best is None or t > best[1]):
                    best = (name, t)
            return best

    def now_text(self, url):
        """now_watching.txt while watching a recording."""
        with self.lock:
            pos, playing, alive = self.pos, self.playing, self.page_alive()
            out = [f"מצב: צפייה בהקלטה ({'אנגלית' if LANG == 'en' else 'עברית'})",
                   f"הקלטה: {self.stem} (אורך {hms(self.duration)})"]
            if pos is None:
                out.append("אתה כאן: עוד לא התחלת לצפות" + ("" if alive else f". הנגן: {url}"))
            elif alive:
                out.append(f"אתה כאן: {hms(pos)} מתוך {hms(self.duration)} ({'מתנגן' if playing else 'בהשהיה'})")
            else:
                out.append(f"אתה כאן: {hms(pos)} מתוך {hms(self.duration)} - הנגן סגור, זה המקום האחרון. לפתוח שוב: {url}")
            out.append(f"עודכן: {datetime.datetime.now():%H:%M:%S}")
            work = "" if self.complete() else f" (עדיין בעבודה: {self.progress()}% מוכן)"
            out.append(f"תמלול מלא: {self.rel_transcript}{work}")
            if self.media_error:
                out.append("שים לב: הדפדפן לא מצליח לנגן את הקובץ, אז המיקום לא ידוע. כדאי לשאול את המשתמש באיזה זמן הוא.")
            if pos is not None:
                sl = self.slide_at(pos)
                if sl:
                    out.append(f"השקופית שעל המסך עכשיו: {self.rel_shots}/{sl[0]} (מ-{hms(sl[1])})")
                start = pos - NOW_BEFORE_S
                before, after = [], []
                for t, k, v in self.items():
                    if k == "gap":  # a part that is not transcribed yet, if it overlaps the minutes around you
                        if t <= pos + 0.5 and v >= start:
                            before.append((max(t, start), k, v))
                        elif pos + 0.5 < t <= pos + NOW_AFTER_S:
                            after.append((t, k, v))
                    elif start <= t <= pos + 0.5:
                        before.append((t, k, v))
                    elif pos + 0.5 < t <= pos + NOW_AFTER_S:
                        after.append((t, k, v))

                def fmt(t, k, v):
                    if k == "shot":
                        return f"[{hms(t)}] [צילום מסך: {self.rel_shots}/{v}]"
                    if k == "gap":
                        return f"[{hms(t)}] (החלק הזה עוד בתמלול - יהיה מוכן בקרוב)"
                    return f"[{hms(t)}] {v}"
                out += ["", f"מה נאמר ב-{NOW_BEFORE_S // 60} הדקות שלפני המקום שלך:"]
                out += [fmt(*x) for x in before] or ["(עוד אין כאן טקסט)"]
                if after:
                    out += ["", "ממש אחרי המקום שלך (עוד לא שמעת):"] + [fmt(*x) for x in after]
            return "\n".join(out)


# ----- the transcription worker -----
_PIPE_REC = None


def block_segments(model, beam, piece, prompt, batched, batch_size):
    """(start in the piece, text) for each sentence. Batched = several 30 s windows at once on the GPU."""
    global _PIPE_REC
    if batched:
        if _PIPE_REC is None:
            from faster_whisper import BatchedInferencePipeline
            _PIPE_REC = BatchedInferencePipeline(model)
        segs, _ = _PIPE_REC.transcribe(piece, language=LANG, beam_size=beam, batch_size=batch_size,
                                       vad_filter=True, initial_prompt=prompt, without_timestamps=False,
                                       **hot_kw(batched=True))
    else:
        segs, _ = model.transcribe(piece, language=LANG, beam_size=beam, vad_filter=USE_VAD,
                                   condition_on_previous_text=False, initial_prompt=prompt, **hot_kw())
    for sg in segs:
        text = sg.text.strip()
        if text:
            yield float(sg.start), text


def transcribe_worker(rec, model, beam, on_gpu, audio16):
    """Transcribes the blocks one by one, the one you watch first (see Recording.claim_block)."""
    global USE_VAD
    batched, batch_size, fails = on_gpu and BATCH, 8, 0
    while not rec.closed:
        i = rec.claim_block()
        if i is None:
            return
        s, e = rec.blocks[i]
        piece = audio16[int(s * TARGET_SR):int(e * TARGET_SR)]
        prompt = (prompt_now(batched=batched) + " " + rec.text_before(i)[-150:]).strip()
        while True:
            try:
                if len(piece) >= TARGET_SR // 2 and rms(piece) >= SILENCE_RMS:
                    for st, text in block_segments(model, beam, piece, prompt, batched, batch_size):
                        rec.add_say(i, s + st, text)
                rec.block_done(i)
                fails = 0
                break
            except Exception as ex:
                rec.clear_block(i)  # half-done lines out - the block is done again from its start
                low = str(ex).lower()
                if batched and "memory" in low and batch_size > 2:
                    batch_size //= 2  # the GPU's memory is too small for that many at once
                    continue
                if batched:
                    save_error("recording batch")
                    batched = False  # one window after another from now on
                    continue
                if USE_VAD:
                    save_error("recording vad")
                    USE_VAD = False  # without the silence filter
                    continue
                rec.release_block(i)
                save_error(f"recording block {hms(s)}")
                fails += 1
                if fails >= 3:
                    rec.error = ex.__class__.__name__
                    return
                break


class VideoSlides(threading.Thread):
    """Saves a picture whenever the video shows something new (slide / board),
    with the same rules as the screenshots of a live lecture."""

    def __init__(self, path, rec):
        super().__init__(daemon=True)
        self.path, self.rec = path, rec
        self.stop_evt = threading.Event()
        self.pos, self.done, self.failed = 0.0, False, None

    def run(self):
        try:
            self._run()
            if not self.stop_evt.is_set():
                self.rec.set_slides_done()
        except Exception as e:
            self.failed = e.__class__.__name__
            save_error("video slides")
        finally:
            self.done = True

    def _keyframes_enough(self, av):
        """Do key frames come often enough (most lecture videos) to look only at them?"""
        times = []
        with av.open(self.path) as c:
            vs = c.streams.video[0]
            vs.codec_context.skip_frame = "NONKEY"
            for fr in c.decode(vs):
                if fr.time is not None:
                    times.append(float(fr.time))
                if len(times) >= 8 or (times and times[-1] > 120):
                    break
        return len(times) >= 3 and float(np.max(np.diff(times))) <= KEYFRAME_MAX_GAP_S

    def _run(self):
        import av
        with av.open(self.path) as c:
            if not c.streams.video:
                return  # sound only - nothing to see
        keyonly = self._keyframes_enough(av)
        os.makedirs(self.rec.shots_dir, exist_ok=True)
        with av.open(self.path) as c:
            vs = c.streams.video[0]
            try:
                vs.thread_type = "AUTO"
            except Exception:
                pass
            if keyonly:
                vs.codec_context.skip_frame = "NONKEY"
            ref, last_save, last_look, t = None, -1e9, -1e9, 0.0
            for fr in c.decode(vs):
                if self.stop_evt.is_set():
                    break
                if fr.time is not None:
                    t = float(fr.time)
                self.pos = t
                if t - last_look < SLIDE_LOOK_S:
                    continue
                last_look = t
                small = fr.reformat(width=max(1, fr.width // 16), height=max(1, fr.height // 16),
                                    format="gray").to_ndarray().astype(np.int16)
                frac = changed_fraction(small, ref)
                gap = t - last_save
                if (frac >= SCREEN_BIG_FRAC and gap >= SCREEN_BIG_GAP_S) or \
                   (frac >= SCREEN_SMALL_FRAC and gap >= SCREEN_SMALL_GAP_S):
                    name = hms(t).replace(":", "-") + ".jpg"
                    fr.to_image().save(os.path.join(self.rec.shots_dir, name), "JPEG", quality=80)
                    ref, last_save = small, t
                    self.rec.add_shot(t, name)
                    ocr_add(os.path.join(self.rec.shots_dir, name), words_to_model=False)

    def stop(self):
        self.stop_evt.set()


# ---------- the app: one page in the browser runs everything ----------
# BeZmanEmet.bat starts the tool and opens its page (http://127.0.0.1:8765/). From the page: a live
# lecture in Hebrew or English, a recording (file, drag-and-drop or link), the library of past lectures.
# The black window stays open, minimized: while it is on the taskbar the tool is running, and closing
# it stops everything. Only this computer can open the page.
APP_HTML = os.path.join(SCRIPT_DIR, "app.html")
ASK_JS = os.path.join(SCRIPT_DIR, "ask.js")  # the "ask the AI" box (app + player)
APP_FILE = os.path.join(LOCAL_DIR, "app.json")  # where the running tool listens - a second launch opens it
IDLE_EXIT_S = float(os.environ.get("BZM_IDLE_EXIT_S") or 15 * 60)  # nothing running, no page open -> the tool closes
RECORDING_EXTS = (".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".mpg", ".mpeg", ".ts", ".3gp",
                  ".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".flac", ".wma", ".ogv")


class Session:
    """One thing the tool does at a time: a live lecture ("live") or a recording ("rec")."""

    def __init__(self, kind, lang, title="", course=""):
        self.kind, self.lang, self.title, self.course = kind, lang, title, course
        self.stop = threading.Event()
        self.closing = None    # quick save when the black window is closed with X
        self.thread = None
        self.ready = False     # live: transcribing; rec: the recording is open in the player
        self.error = None      # what went wrong, for the page
        self.done = False
        self.started = time.time()
        self.transcript = None
        self.yt = None         # a YouTube video in Hevanti's player: {"id", "url", "start"}
        self.ready_at = None   # when it started transcribing (a stop within QUICK_STOP_S offers to delete it)
        self.discard = False   # stopped right after starting, and the student chose to delete it

    def info(self):
        return {"kind": self.kind, "lang": self.lang, "title": self.title, "course": self.course, "ready": self.ready,
                "done": self.done, "stopping": self.stop.is_set() and not self.done, "error": self.error,
                "started": self.started, "transcript": self.transcript, "yt": self.yt,
                "ready_at": self.ready_at, "discard": self.discard}


NOTE_WARN = ("אזהרה", "שגיאה", "נכשל", "לא הצלחתי", "חסם", "לא נמצא", "לא מגיע", "שים לב", "נקטעה", "נעצר")


class App:
    def __init__(self):
        self.lock = threading.RLock()
        self.model_lock = threading.Lock()
        self.session = None
        self.live = None        # LiveNow of the live session (what the live view shows)
        self.rec = None         # the Recording in the player
        self.notes = collections.deque(maxlen=300)
        self.note_seq = 0
        self.progress, self.progress_at = "", 0.0
        self.question = None    # {"id", "text", "secret"} - the page asks the user
        self.answers = {}
        self.pending = None     # a recording that arrived from outside (dragged onto Hevanti)
        self.migrated = 0       # lectures moved over from the 1.x folders on this start
        self.update = None      # a newer version, when GitHub says there is one
        self.models = {}
        self.device = ""        # "GPU" / "CPU" once a model is loaded
        self.last_seen = time.time()
        self.quit_evt = threading.Event()
        self.url = None
        self.lib_rev = 0
        self.first_view = ""
        self._connect, self._connect_at = {}, 0.0

    # --- what the page shows ---
    def add_note(self, text):
        text = str(text).strip()
        if not text:
            return
        m = re.match(r"\[(\d\d:\d\d:\d\d)\] (.*)", text, re.S)
        clock, body = (m.group(1), m.group(2)) if m else (datetime.datetime.now().strftime("%H:%M:%S"), text)
        level = "warn" if any(w in body for w in NOTE_WARN) else "info"
        with self.lock:
            self.note_seq += 1
            self.notes.append({"id": self.note_seq, "clock": clock, "text": body, "level": level})

    def set_progress(self, text):
        with self.lock:
            self.progress, self.progress_at = str(text).strip(), time.time()
            if self.rec is not None:
                self.rec.note = self.progress

    def seen(self):
        self.last_seen = time.time()

    def state(self, notes_since=0):
        with self.lock:
            s = self.session
            progress = self.progress if time.time() - self.progress_at < 8 else ""
            return {"version": VERSION, "date": VERSION_DATE, "device": self.device,
                    "session": s.info() if s else None,
                    "rec_open": self.rec is not None and s is not None and s.kind == "rec" and not s.done,
                    "progress": progress, "question": self.question, "pending": self.pending,
                    "notes": [n for n in self.notes if n["id"] > notes_since],
                    "lib_rev": self.lib_rev, "first_view": self.first_view,
                    "screens": SCREEN_ENABLED, "product": PRODUCT, "migrated": self.migrated,
                    "course": load_settings().get("course") or "", "connect": self.connect_info(), "mac": IS_MAC,
                    "ai_apps": ai_apps_status(), "update": self.update}

    def connect_info(self):
        """Which AI apps are connected (reading two small config files - at most every few seconds)."""
        now = time.time()
        if now - self._connect_at > 4:
            self._connect, self._connect_at = connect_status(), now
        return self._connect

    # --- commands from the page ---
    def start(self, kind, lang, fn, *args, title="", course="", yt=None):
        with self.lock:
            old = self.session
        if old is not None and not old.done:
            old.stop.set()
            if old.thread is not None:
                old.thread.join(180)
        sess = Session(kind, "en" if lang == "en" else "he", title, course)
        sess.yt = yt
        with self.lock:
            self.session, self.question, self.pending = sess, None, None
            if kind == "rec":
                self.live = None
            else:
                self.rec = None
        sess.thread = threading.Thread(target=self._run, args=(sess, fn) + args, daemon=True)
        sess.thread.start()
        return sess

    def _run(self, sess, fn, *args):
        try:
            fn(sess, *args)
        except KeyboardInterrupt:
            pass
        except Exception:
            tb = traceback.format_exc()
            save_error_text(f"session {sess.kind}", tb)
            sess.error = friendly_error(tb)
            log(sess.error.split("\n")[0])
        finally:
            sess.done = True
            with self.lock:
                if self.rec is not None and sess.kind == "rec":
                    self.rec = None
                self.lib_rev += 1
                if self.question is not None:
                    self.question = None

    def stop_session(self, wait=0, discard=False):
        with self.lock:
            s = self.session
        if s is not None and not s.done:
            s.discard = bool(discard)
            s.stop.set()
            if s.kind == "live" and not s.ready:
                # still loading (the model, packages): nothing was recorded yet - done now for the page, instead of
                # "stopping..." until the loading ends. run_live sees the stop when the loading ends and saves nothing.
                s.done = True
                with self.lock:
                    self.lib_rev += 1
                return
            if wait and s.thread is not None:
                s.thread.join(wait)

    def command(self, d):
        a = d.get("action")
        course = clean_name(d.get("course"), NO_COURSE)
        if a == "start_live":
            save_settings(course=course)
            self.start("live", d.get("lang"), run_live, d.get("lang"), course, course=course)
            return {"ok": True}
        if a == "start_youtube" or (a == "start_recording" and is_youtube(d.get("source") or "")):
            vid, at = youtube_id(d.get("url") or d.get("source"))
            if not vid:
                return {"ok": False, "error": "זה לא נראה כמו קישור לסרטון ביוטיוב."}
            if not at:
                ld = find_yt_lecture(course, vid)
                at = read_yt_lecture(ld)[3] if ld else 0
            save_settings(course=course)
            self.start("live", d.get("lang"), run_live, d.get("lang"), course, title="סרטון יוטיוב", course=course,
                       yt={"id": vid, "url": f"https://www.youtube.com/watch?v={vid}", "start": int(at)})
            return {"ok": True, "youtube": True}
        if a == "start_recording":
            src = str(d.get("source") or "").strip()
            if not src:
                return {"ok": False, "error": "לא נבחרה הקלטה."}
            save_settings(course=course)
            title = clean_name(str(d.get("title") or "")[:120])
            if title and src.lower().startswith(("http://", "https://")):
                LINK_TITLES[src] = title   # a name for a recording whose link says nothing (Panopto)
            self.start("rec", d.get("lang"), run_recording, src, d.get("lang"), course, title=title or display_name(src),
                       course=course)
            return {"ok": True}
        if a == "open_recording":
            media, lang, rcourse = recording_from_library(d.get("f") or "")
            if media is None:
                return {"ok": False, "view": d.get("f")}
            self.start("rec", lang, run_recording, media, lang, rcourse, title=media.title, course=rcourse)
            return {"ok": True}
        if a == "set_course":
            save_settings(course=course)
            return {"ok": True}
        if a == "new_course":
            name = create_course(d.get("name"), d.get("terms"))
            if not name:
                return {"ok": False, "error": "צריך לכתוב שם לקורס."}
            save_settings(course=name)
            with self.lock:
                self.lib_rev += 1
            return {"ok": True, "course": name}
        if a == "save_glossary":
            if not os.path.isdir(course_dir(course)):
                return {"ok": False, "error": "הקורס לא נמצא."}
            words = write_glossary(course, d.get("text"))
            with self.lock:
                self.lib_rev += 1
            return {"ok": True, "terms": len(words)}
        if a in ("move_lecture", "rename_lecture", "delete_lecture"):
            return self.change_lecture(a, d)
        if a == "delete_course":
            return self.delete_course(clean_name(d.get("course"), NO_COURSE))
        if a == "open_ai_app":
            return {"ok": open_ai_app_placed(d.get("app"))}
        if a == "course_ai_link":
            return set_course_ai_link(course, str(d.get("app") or ""), d.get("url"))
        if a == "open_course_terminal":
            return open_course_terminal(course)
        if a == "set_mirror":
            return set_mirror(d.get("path"))
        if a == "place_ai":
            save_settings(place_ai=bool(d.get("on")))
            return {"ok": True}
        if a == "check_updates":
            save_settings(check_updates=bool(d.get("on")))
            return {"ok": True}
        if a in ("connect", "disconnect"):
            out = connect_app(d.get("app"), a == "connect")
            self._connect_at = 0.0
            return out
        if a == "export_course":
            if not os.path.isdir(course_dir(course)):
                return {"ok": False, "error": "הקורס לא נמצא."}
            text, n = course_text(course)
            out = os.path.join(course_dir(course), f"{course} - כל ההרצאות.txt")
            try:
                with open(out, "w", encoding="utf-8") as f:
                    f.write(text + "\n")
            except OSError:
                return {"ok": False, "error": "לא הצלחתי לשמור את הקובץ (אולי הוא פתוח בתוכנה אחרת)."}
            open_in_explorer("course", course)
            return {"ok": True, "file": lib_rel(out), "lectures": n}
        if a == "stop":
            self.stop_session(discard=bool(d.get("discard")))
            return {"ok": True}
        if a == "answer":
            with self.lock:
                self.answers[str(d.get("id"))] = str(d.get("value") or "")
                self.question = None
            return {"ok": True}
        if a == "offer":
            src = str(d.get("source") or "")
            title = clean_name(str(d.get("name") or "")[:120]) if d.get("name") else ""
            with self.lock:
                self.pending = {"source": src, "name": title or display_name(src), "title": title} if src else None
            return {"ok": True}
        if a == "dismiss_pending":
            with self.lock:
                self.pending = None
            return {"ok": True}
        if a == "open_folder":
            open_in_explorer(d.get("what") or "tool", d.get("f"))
            return {"ok": True}
        if a == "quit":
            self.quit_evt.set()
            return {"ok": True}
        return {"ok": False, "error": "פקודה לא מוכרת"}

    def delete_course(self, name):
        """Delete a whole course folder (its lectures, slides and glossary) - to the Recycle Bin when possible."""
        if not name or name == NO_COURSE:
            return {"ok": False, "error": "\"ללא קורס\" לא נמחק: שם לכל ההרצאות שעוד לא שויכו לקורס."}
        src = course_dir(name)
        if not os.path.isdir(src):
            return {"ok": False, "error": "הקורס לא נמצא."}
        prefix = os.path.normcase(os.path.abspath(src)) + os.sep
        with self.lock:
            s = self.session
            busy = s is not None and not s.done and bool(s.transcript) and \
                os.path.normcase(os.path.abspath(s.transcript)).startswith(prefix)
        if busy:
            return {"ok": False, "error": "יש הרצאה פתוחה בקורס הזה עכשיו. אפשר למחוק אותו אחרי שעוצרים אותה."}
        where = to_recycle_bin(src)
        if not where:
            return {"ok": False, "error": "לא הצלחתי למחוק (אולי קובץ מהקורס פתוח בתוכנה אחרת)."}
        if clean_name(load_settings().get("course"), NO_COURSE) == name:
            save_settings(course=NO_COURSE)
        with self.lock:
            self.lib_rev += 1
        return {"ok": True, "where": where}

    def change_lecture(self, a, d):
        """Move a lecture to another course, rename it (its folder and its transcript file), or delete it."""
        import shutil
        src = lecture_from_rel(d.get("f"))
        if src is None:
            return {"ok": False, "error": "ההרצאה לא נמצאה."}
        with self.lock:
            s = self.session
            busy = s is not None and not s.done and s.transcript and \
                os.path.normcase(os.path.abspath(s.transcript)) == os.path.normcase(os.path.abspath(lecture_txt(src)))
        if busy:
            return {"ok": False, "error": "ההרצאה הזו פתוחה עכשיו. אפשר להעביר, לשנות שם או למחוק אחרי שעוצרים אותה."}
        if a == "delete_lecture":
            where = to_recycle_bin(src)
            if not where:
                return {"ok": False, "error": "לא הצלחתי למחוק (אולי קובץ מההרצאה פתוח בתוכנה אחרת)."}
            with self.lock:
                self.lib_rev += 1
            return {"ok": True, "where": where}
        old = os.path.basename(src)
        if a == "move_lecture":
            course = clean_name(d.get("course"), NO_COURSE)
            parent, name = course_dir(course), old
            if os.path.normcase(parent) == os.path.normcase(os.path.dirname(src)):
                return {"ok": True, "f": lib_rel(src)}
        else:
            parent, name = os.path.dirname(src), clean_name(d.get("name"))
            if not name:
                return {"ok": False, "error": "צריך לכתוב שם."}
            if name == old:
                return {"ok": True, "f": lib_rel(src)}
        try:
            os.makedirs(parent, exist_ok=True)
            name = free_folder(parent, name)
            dest = os.path.join(parent, name)
            shutil.move(src, dest)
            if name != old:
                os.replace(os.path.join(dest, old + ".txt"), lecture_txt(dest))
        except OSError:
            save_error(a)
            return {"ok": False, "error": "לא הצלחתי (אולי קובץ מההרצאה פתוח בתוכנה אחרת)."}
        with self.lock:
            self.lib_rev += 1
        return {"ok": True, "f": lib_rel(dest)}

    def emergency_close(self):
        """The black window is being closed (X): save what we have, quickly."""
        with self.lock:
            s = self.session
        if s is not None:
            s.stop.set()
            if s.closing:
                try:
                    s.closing()
                except Exception:
                    pass
        _remove_quietly(APP_FILE)


APP = App()


MISSING_PARTS = ("רכיבי התמלול לא מותקנים במחשב הזה (או שההתקנה לא הסתיימה). להריץ את Install בתיקייה של הבנתי, "
                 "לחכות ל-Installed OK, ואז לפתוח שוב את Hevanti.")


def friendly_error(tb):
    if is_blocked(tb):
        return "\n".join(block_text(tb))
    if "No module named" in tb or "ModuleNotFoundError" in tb:
        return MISSING_PARTS
    if "Could not load any transcription model" in tb:
        return ("לא הצלחתי להוריד או לטעון את מודל התמלול. לבדוק שיש חיבור לאינטרנט ולנסות שוב - "
                "ההורדה ממשיכה מאיפה שעצרה.")
    last = [x for x in tb.strip().splitlines() if x.strip()][-1:] or ["שגיאה"]
    return f"שגיאה: {last[0][:300]}\nהפרטים נשמרו בקובץ error_log.txt בתיקייה System."


def ask_user(text, secret=False):
    """A question for the user, asked on the page. Returns the answer ('' = cancelled)."""
    import uuid
    qid = uuid.uuid4().hex[:12]
    with APP.lock:
        APP.question = {"id": qid, "text": text, "secret": bool(secret)}
        sess = APP.session
    log(text)
    while not APP.quit_evt.is_set() and not (sess is not None and sess.stop.is_set()):
        with APP.lock:
            if qid in APP.answers:
                return APP.answers.pop(qid)
        time.sleep(0.2)
    with APP.lock:
        if APP.question and APP.question.get("id") == qid:
            APP.question = None
    return ""


def get_model(lang, stub_av):
    """The transcription model for this language - loaded once, kept while the tool runs."""
    global _PIPE, _PIPE_REC
    with APP.model_lock:
        set_language(lang)
        if LANG in APP.models:
            return APP.models[LANG]
        if APP.models:  # one model at a time (each takes 1-3 GB)
            APP.models.clear()
            _PIPE = _PIPE_REC = None
            import gc
            gc.collect()
        import faulthandler
        dump = None
        try:
            dump = open(STUCK_LOG, "w", encoding="utf-8")
            dump.write(f"--- {datetime.datetime.now()} (גרסה {VERSION}) loading the model took over 3 minutes - where it was: ---\n")
            dump.flush()
            faulthandler.dump_traceback_later(180, file=dump)
        except Exception:
            dump = None
        try:
            m = load_model(stub_av=stub_av)
        finally:
            if dump is not None:
                faulthandler.cancel_dump_traceback_later()
                dump.close()
        _remove_quietly(STUCK_LOG)   # loaded: nothing to report
        APP.models[LANG] = m
        APP.device = "GPU" if m[2].endswith("GPU") else "CPU"
        return m


def load_real_av():
    """PyAV for reading recordings. The live mode may have put a stand-in there (see _stub_av)."""
    mod = sys.modules.get("av")
    if mod is not None and not getattr(mod, "_bzm_stub", False):
        _av_compat(mod)
        return mod
    for k in [k for k in sys.modules if k == "av" or k.startswith("av.")]:
        del sys.modules[k]
    try:
        import av
    except Exception:
        _stub_av()  # the live mode keeps working
        raise
    _av_compat(av)
    try:
        import faster_whisper.audio as fwa
        fwa.av = av  # faster-whisper may have been loaded with the stand-in
    except Exception:
        pass
    return av


def _av_compat(av):
    """faster-whisper opens files with av.open(..., metadata_errors="ignore"), which newer PyAV (15+) no longer
    accepts ("open() got an unexpected keyword argument 'metadata_errors'"): drop it there."""
    if getattr(av.open, "_bzm", False):
        return
    real = av.open

    def open_(*a, **k):
        try:
            return real(*a, **k)
        except TypeError as e:
            if "metadata_errors" in k and "metadata_errors" in str(e):
                k.pop("metadata_errors")
                return real(*a, **k)
            raise
    open_._bzm = True
    av.open = open_


def display_name(src):
    s = str(src).strip().strip('"')
    if s.lower().startswith(("http://", "https://")):
        return s
    return os.path.splitext(os.path.basename(s))[0] or s


def open_in_explorer(what, fname=None):
    if os.name != "nt" and not IS_MAC:
        return
    paths = {"tool": DATA_DIR, "lib": LIB_DIR, "videos": VIDEO_DIR}
    p = paths.get(what, LIB_DIR)
    if what in ("file", "folder") and fname:
        d = lecture_from_rel(fname)
        if d is not None:
            p = lecture_txt(d) if what == "file" else d
    elif what == "course" and fname and clean_name(fname) == fname and os.path.isdir(course_dir(fname)):
        p = course_dir(fname)
    try:
        if what != "file":
            os.makedirs(p, exist_ok=True)
        if IS_MAC:
            import subprocess
            subprocess.Popen(["open", p])
        else:
            os.startfile(p)
    except Exception:
        save_error("open folder")


PICK_PS = r"""
Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Title = 'בחירת הקלטה'
$d.Filter = 'הקלטות (סרטון או שמע)|*.mp4;*.m4v;*.mov;*.mkv;*.webm;*.avi;*.wmv;*.mpg;*.mpeg;*.mp3;*.m4a;*.aac;*.wav;*.ogg;*.opus;*.flac;*.wma|כל הקבצים|*.*'
if ($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($d.FileName) }
"""


def pick_file():
    """Windows' own "open file" window. Returns the chosen path, or ''."""
    if os.environ.get("BZM_FAKE_PICK") is not None:  # tests
        return os.environ["BZM_FAKE_PICK"]
    if IS_MAC:
        import subprocess
        try:
            r = subprocess.run(["osascript", "-e", 'POSIX path of (choose file with prompt "בחירת הקלטה")'],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
            return (r.stdout or "").strip()
        except Exception:
            return ""
    if os.name != "nt":
        return ""
    import base64
    import subprocess
    enc = base64.b64encode(PICK_PS.encode("utf-16-le")).decode()
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-STA", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                            "-EncodedCommand", enc], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", creationflags=0x08000000)
        return (r.stdout or "").strip()
    except Exception:
        save_error("pick file")
        return ""


# ----- the library: every lecture in the transcripts folder -----
LIVE_HEAD = re.compile(r"# תמלול הרצאה \((עברית|אנגלית)\) - התחלה (\d{4}-\d\d-\d\d) (\d\d:\d\d)")
REC_HEAD = re.compile(r"# תמלול (?:הקלטה|סרטון) \((עברית|אנגלית)\) - (.+?) \| אורך: (\d+:\d\d:\d\d)")
LIVE_LINE = re.compile(r"\[(\d\d:\d\d:\d\d) \| \+(\d+):(\d\d):(\d\d)\] (.*)$")
REC_LINE = re.compile(r"\[(\d+):(\d\d):(\d\d)\] (.*)$")
_LIB_CACHE = {}


DEFAULT_LIVE_NAME = re.compile(r"(\d{4})-(\d\d)-(\d\d) (\d\d)-(\d\d) הרצאה( באנגלית)?( \(\d+\))?$")


def library_entry(d, course):
    path = lecture_txt(d)
    st = os.stat(path)
    key = (path, st.st_mtime, st.st_size)
    if key in _LIB_CACHE:
        return dict(_LIB_CACHE[key])
    name = os.path.basename(d)
    e = {"f": f"{course}/{name}", "course": course, "name": name, "kind": "other", "title": name, "lang": "he",
         "when": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"), "lines": 0, "shots": 0,
         "length": "", "complete": False, "mtime": st.st_mtime, "has_media": False, "progress": None}
    last_elapsed = None
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                line = line.rstrip("\n")
                if i == 0:
                    m = LIVE_HEAD.match(line)
                    if m:
                        e.update(kind="live", lang="en" if m.group(1) == "אנגלית" else "he",
                                 when=f"{m.group(2)} {m.group(3)}")
                        dm = DEFAULT_LIVE_NAME.match(name)
                        if dm:  # not renamed: a readable title
                            e["title"] = (f"הרצאה {dm.group(3)}.{dm.group(2)}.{dm.group(1)} {dm.group(4)}:{dm.group(5)}"
                                          + (" (אנגלית)" if dm.group(6) else "") + (dm.group(7) or ""))
                        continue
                    m = REC_HEAD.match(line)
                    if m:
                        e.update(kind="rec", lang="en" if m.group(1) == "אנגלית" else "he", length=m.group(3))
                        continue
                    m = YT_HEAD.match(line)
                    if m:
                        e.update(kind="yt", lang="en" if m.group(1) == "אנגלית" else "he", url=m.group(2))
                        dm = re.search(r"התחלה (\d{4}-\d\d-\d\d) (\d\d:\d\d)", line)
                        if dm:
                            e["when"] = f"{dm.group(1)} {dm.group(2)}"
                        e["title"] = "סרטון יוטיוב"
                        continue
                if line.startswith(YT_TITLE) and e["kind"] == "yt":
                    e["title"] = line[len(YT_TITLE):].strip() or e["title"]
                    continue
                if line.startswith("# סוף"):
                    e["complete"] = True
                    continue
                m = re.match(r"# בעבודה: (\d+)%", line)
                if m:
                    e["progress"] = int(m.group(1))
                    continue
                if "[צילום מסך:" in line:
                    e["shots"] += 1
                    continue
                m = LIVE_LINE.match(line)
                if m:
                    last_elapsed = int(m.group(2)) * 3600 + int(m.group(3)) * 60 + int(m.group(4))
                    if not m.group(5).startswith("["):
                        e["lines"] += 1
                    continue
                m = REC_LINE.match(line)
                if m and not m.group(4).startswith("("):
                    e["lines"] += 1
                    if e["kind"] == "yt":
                        last_elapsed = max(last_elapsed or 0, int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)))
    except OSError:
        pass
    if e["kind"] in ("live", "yt") and last_elapsed is not None:
        e["length"] = hms(last_elapsed)
    if e["kind"] == "rec":
        media, _, _ = recording_from_library(e["f"])
        e["has_media"] = media is not None
    _LIB_CACHE[key] = e
    return dict(e)


def library():
    out = []
    for c, n, d in lecture_dirs():
        try:
            out.append(library_entry(d, c))
        except OSError:
            pass
    out.sort(key=lambda e: e["mtime"], reverse=True)
    with APP.lock:
        s = APP.session
        cur = os.path.normcase(os.path.abspath(s.transcript)) if (s is not None and not s.done and s.transcript) else None
    for e in out:
        e["running"] = cur is not None and \
            os.path.normcase(os.path.abspath(lecture_txt(os.path.join(LIB_DIR, *e["f"].split("/"))))) == cur
    return out


def courses_info(items=None):
    """The courses for the page: name, how many lectures, the glossary's size, the newest lecture."""
    items = library() if items is None else items
    out = []
    for c in course_names():
        mine = [e for e in items if e["course"] == c]
        out.append({"name": c, "lectures": len(mine), "terms": len(read_glossary(c)),
                    "last": max((e["mtime"] for e in mine), default=0)})
    return out


_VIEW_CACHE = {}


def transcript_view(fname):
    """A lecture ("<course>/<lecture>") -> lines for the page: say / shot / gap / note, with the time to show."""
    d = lecture_from_rel(fname)
    if d is None:
        return None
    path = lecture_txt(d)
    course = os.path.basename(os.path.dirname(d))
    entry = library_entry(d, course)
    st = os.stat(path)
    try:
        ocr_m = os.path.getmtime(os.path.join(d, SLIDES_NAME, OCR_NAME))
    except OSError:
        ocr_m = 0
    key = (path, st.st_mtime, st.st_size, ocr_m)
    if key in _VIEW_CACHE:
        return {"entry": entry, "lines": _VIEW_CACHE[key]}
    lines, ocr = [], read_ocr(os.path.join(d, SLIDES_NAME)) if ocr_m else {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            m = LIVE_LINE.match(line)
            if m:
                t = int(m.group(2)) * 3600 + int(m.group(3)) * 60 + int(m.group(4))
                x, clock = m.group(5), m.group(1)
            else:
                m = REC_LINE.match(line)
                if not m:
                    continue
                t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
                x, clock = m.group(4), hms(t)
            sm = SHOT_RE.match(x)
            if sm:  # "שקופיות/<file>" in the lecture folder -> the path the page asks for
                name = os.path.basename(sm.group(1))
                lines.append({"t": t, "c": clock, "img": f"{entry['f']}/{SLIDES_NAME}/{name}",
                              **({"ocr": ocr[name]} if ocr.get(name) else {})})
            elif GAP_RE.match(x):
                lines.append({"t": t, "c": clock, "gap": x.strip("()")})
            elif x.startswith("[") and x.endswith("]"):
                lines.append({"t": t, "c": clock, "note": x.strip("[]")})
            else:
                lines.append({"t": t, "c": clock, "x": x})
    if len(_VIEW_CACHE) > 400:
        _VIEW_CACHE.clear()
    _VIEW_CACHE[key] = lines
    return {"entry": entry, "lines": lines}


_SEARCH_INDEX = None
_SEARCH_LOCK = threading.Lock()


def _search_index():
    """The search index (hevanti_search.py): a copy of the lectures' text in LOCAL_DIR, kept up to date by itself."""
    global _SEARCH_INDEX
    with _SEARCH_LOCK:
        if _SEARCH_INDEX is None:
            import hevanti_search
            _SEARCH_INDEX = hevanti_search.Index(LIB_DIR, os.path.join(LOCAL_DIR, "search.db"))
        return _SEARCH_INDEX


def search(q, course="", limit=300):
    """The lines that fit the words best, in all lectures (or one course): ranked, Hebrew prefixes and plurals
    handled, "a phrase" as written. Falls back to the plain scan if the index cannot be used."""
    try:
        res = _search_index().search(q, course=course, limit=limit)
        by = {e["f"]: e for e in library()}
    except Exception:
        save_error("search index")
        return _search_scan(q, course, limit)
    hits = []
    for h in res["hits"]:
        e = by.get(h["f"])
        if e is None:
            continue
        slide = h["kind"] == "slide"
        hits.append({"f": e["f"], "course": e["course"], "title": e["title"], "kind": e["kind"],
                     "has_media": e["has_media"], "t": h["t"], "c": h["c"],
                     "x": ("[בשקופית] " if slide else "") + h["x"],
                     **({"slide": f"{e['f']}/{SLIDES_NAME}/{h['slide']}"} if slide else {})})
    return {"hits": hits, "more": res["more"]}


def _search_scan(q, course="", limit=300):
    """Every line with these words, in all lectures (or one course). Newest lectures first."""
    words = [w for w in str(q or "").lower().split() if w]
    if not words or len("".join(words)) < 2:
        return {"hits": [], "more": False}
    hits, more = [], False
    for e in library():
        if course and e["course"] != course:
            continue
        v = transcript_view(e["f"])
        for x in (v["lines"] if v else []):
            low = (x.get("x") or x.get("ocr") or "").lower()
            if low and all(w in low for w in words):
                if len(hits) >= limit:
                    more = True
                    break
                if x.get("x"):
                    shown = x["x"][:400]
                else:   # a slide: the line of its text with the words
                    ln = next((l for l in x["ocr"].splitlines() if any(w in l.lower() for w in words)), x["ocr"])
                    shown = "[בשקופית] " + ln[:380]
                hits.append({"f": e["f"], "course": e["course"], "title": e["title"], "kind": e["kind"],
                             "has_media": e["has_media"], "t": x["t"], "c": x["c"], "x": shown,
                             **({"slide": x["img"]} if x.get("img") else {})})
        if more:
            break
    return {"hits": hits, "more": more}


def course_text(course):
    """All the lectures of a course as one text, oldest first - for exam preparation with an AI."""
    items = sorted((e for e in library() if e["course"] == course), key=lambda e: e["when"])
    parts = []
    for e in items:
        v = transcript_view(e["f"])
        if not v:
            continue
        body = [x["x"] if x.get("x") else "[טקסט בשקופית: " + x["ocr"][:1200].replace("\n", " | ") + "]"
                for x in v["lines"] if x.get("x") or x.get("ocr")]
        if body:
            parts.append(f"=== {e['title']} ({e['when']}{', אורך ' + e['length'] if e['length'] else ''}) ===\n"
                         + "\n".join(body))
    terms = read_glossary(course)
    head = (f"קורס: {course}. {len(parts)} הרצאות, תמלול אוטומטי (יכולות להיות בו טעויות תמלול). "
            "[טקסט בשקופית: ...] = מה שהיה כתוב על השקופית או על הלוח באותו רגע (נקרא אוטומטית מהתמונה).")
    if terms:
        head += "\nמונחים בקורס: " + ", ".join(terms[:60])
    return head + "\n\n" + "\n\n".join(parts), len(parts)


def recording_from_library(fname):
    """A lecture ("<course>/<lecture>") -> (Media, language, course) if the recording is still on this computer."""
    ld = lecture_from_rel(fname)
    if ld is None:
        return None, "he", NO_COURSE
    course = os.path.basename(os.path.dirname(ld))
    try:
        with open(os.path.join(ld, STATE_NAME), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None, "he", course
    lang = d.get("lang") or "he"
    path = d.get("path") or d.get("audio")
    if not path or not os.path.isfile(path):
        return None, lang, course
    video = d.get("video", "same") if "path" in d else "same"
    if video and video != "same" and not os.path.isfile(video):
        video = None
    audio = d.get("audio") if d.get("audio") and os.path.isfile(d.get("audio")) else path
    title = d.get("title") or os.path.splitext(os.path.basename(path))[0]
    return Media(path, video=video, audio=audio, title=title), lang, course


def safe_shot(rel):
    """A slide from the page ("<course>/<lecture>/שקופיות/<file>.jpg") -> the file, only inside "הקורסים שלי"."""
    rel = str(rel or "").replace("\\", "/")
    parts = [p for p in rel.split("/") if p]
    if len(parts) != 4 or parts[2] != SLIDES_NAME or any(p in (".", "..") for p in parts):
        return None
    if not re.fullmatch(r"[\w\-]+\.(jpg|png)", parts[3]) or lecture_from_rel(parts[0] + "/" + parts[1]) is None:
        return None
    p = os.path.join(LIB_DIR, *parts)
    root = os.path.realpath(LIB_DIR)
    return p if os.path.realpath(p).startswith(root + os.sep) and os.path.isfile(p) else None


def live_cover(live):
    cov = getattr(live, "cover", None)
    return cov.spans if cov is not None else []


def live_state(since):
    live = APP.live
    if live is None:
        return {"none": True}
    if getattr(live, "yt", False):
        pos, playing, alive = live.clock.now()
        with live.lock:
            out = {"yt": True, "rev": live.rev, "pending": round(live.pending_s, 1), "lag": round(live.lag, 1),
                   "info": dict(live.info), "ended": live.ended, "pos": round(pos, 1), "playing": playing,
                   "covered": [[round(a, 1), round(b, 1)] for a, b in live_cover(live)]}
            if since != live.rev:
                out["items"] = [{"t": t, "c": hms(t), **({"img": x[len("[צילום מסך: "):-1]} if x.startswith("[צילום מסך: ")
                                                         else {"x": x})} for t, x in live.all]
        return out
    with live.lock:
        items = live.all[since:]
        out = {"total": len(live.all), "since": since, "draft": live.draft, "pending": round(live.pending_s, 1),
               "lag": round(live.lag, 1), "fast": live.fast, "shot": live.shot[1] if live.shot else None,
               "info": dict(live.info), "ended": live.ended}
    out["items"] = [{"t": t, "c": datetime.datetime.fromtimestamp(t).strftime("%H:%M:%S"),
                     **({"img": x[len("[צילום מסך: "):-1]} if x.startswith("[צילום מסך: ") else {"x": x})}
                    for t, x in items]
    return out


# ----- the server -----
def _app_handler():
    import http.server
    import urllib.parse

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass  # no request lines in the black window

        def _host_ok(self):
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
            return host in ("127.0.0.1", "localhost", "::1")

        # Other websites open in the browser must not be able to use the tool (start recording the sound and
        # the screen, read transcripts, show pictures). The browser marks their requests: Sec-Fetch-Site and
        # Origin. Our own page also adds X-BZM to every command - a header other sites cannot add.
        def _site_ok(self, path):
            site = (self.headers.get("Sec-Fetch-Site") or "").lower()
            if site in ("", "none", "same-origin"):
                return True
            # a link from another site may open our page itself - nothing more (no frames, pictures, requests)
            return (self.command in ("GET", "HEAD") and self.headers.get("Sec-Fetch-Mode") == "navigate"
                    and self.headers.get("Sec-Fetch-Dest") == "document" and path in ("/", "/index.html", "/player"))

        def _post_ok(self, path):
            port = self.server.server_address[1]
            origin = (self.headers.get("Origin") or "").lower().rstrip("/")
            if origin and origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
                return False
            return path == "/api/place" or self.headers.get("X-BZM") == "1"  # where you are in a recording: harmless

        def _refuse(self):
            self.close_connection = True  # the request body (if any) is not read - don't reuse this connection
            return self._send(403, b"forbidden", "text/plain", {"Connection": "close"})

        def _send(self, code, body, ctype, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _page(self, path):
            with open(path, "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8",
                                  {"X-Frame-Options": "DENY", "Content-Security-Policy": "frame-ancestors 'none'"})

        def _file(self, path, ctype):
            size = os.path.getsize(path)
            start, end, code = 0, size - 1, 200
            m = re.match(r"bytes=(\d*)-(\d*)$", (self.headers.get("Range") or "").strip())
            if m and (m.group(1) or m.group(2)):
                if m.group(1):
                    start = int(m.group(1))
                    if m.group(2):
                        end = min(int(m.group(2)), size - 1)
                else:
                    start = max(0, size - int(m.group(2)))
                if start >= size or start > end:
                    return self._send(416, b"", "text/plain", {"Content-Range": f"bytes */{size}"})
                code = 206
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if code == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if self.command == "HEAD":
                return
            with open(path, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    buf = f.read(min(1 << 20, left))
                    if not buf:
                        break
                    self.wfile.write(buf)
                    left -= len(buf)

        def _body(self, limit=65536):
            n = min(int(self.headers.get("Content-Length") or 0), limit)
            return self.rfile.read(n) if n else b""

        def _body_json(self, limit=65536):
            try:
                d = json.loads(self._body(limit).decode("utf-8") or "{}")
                return d if isinstance(d, dict) else {}
            except ValueError:
                return {}

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            try:
                u = urllib.parse.urlsplit(self.path)
                q = urllib.parse.parse_qs(u.query)
                p = u.path
                if not self._host_ok() or not self._site_ok(p):
                    return self._refuse()

                def qint(k):
                    try:
                        return int(q.get(k, ["0"])[0])
                    except ValueError:
                        return 0
                if p in ("/", "/index.html"):
                    return self._page(APP_HTML)
                if p == "/ask.js":
                    try:
                        with open(ASK_JS, "rb") as f:
                            return self._send(200, f.read(), "text/javascript; charset=utf-8")
                    except OSError:
                        return self._send(404, b"", "text/javascript")
                if p == "/player":
                    if APP.rec is None:
                        return self._send(302, b"", "text/plain", {"Location": "/"})
                    return self._page(PLAYER_HTML)
                if p.startswith("/api/"):
                    APP.seen()
                if p == "/api/app":
                    return self._json(APP.state(qint("notes")))
                if p == "/api/live":
                    return self._json(live_state(qint("since")))
                if p == "/api/library":
                    items = library()
                    return self._json({"items": items, "courses": courses_info(items)})
                if p == "/api/search":
                    return self._json(search(q.get("q", [""])[0], clean_name(q.get("c", [""])[0])))
                if p == "/api/course":
                    c = clean_name(q.get("c", [""])[0])
                    if not c or not os.path.isdir(course_dir(c)):
                        return self._json({"none": True}, 404)
                    return self._json({"name": c, "glossary": glossary_text(c), "ai": course_ai_info(c)})
                if p == "/api/mirror":
                    return self._json(dict(mirror_status(), place_ai=load_settings().get("place_ai", True),
                                           check_updates=load_settings().get("check_updates", True)))
                if p == "/api/suggest":
                    return self._json(suggest_terms(q.get("c", [""])[0][:120]))
                if p == "/api/course_text":
                    c = clean_name(q.get("c", [""])[0])
                    if not c or not os.path.isdir(course_dir(c)):
                        return self._json({"none": True}, 404)
                    text, n = course_text(c)
                    return self._json({"text": text, "lectures": n, "chars": len(text)})
                if p == "/api/transcript":
                    v = transcript_view(q.get("f", [""])[0])
                    if v:
                        v = dict(v, summary=lecture_summary(q.get("f", [""])[0]))
                    return self._json(v if v else {"none": True}, 200 if v else 404)
                if p == "/api/slide_text":
                    f = safe_shot(q.get("p", [""])[0]) if q.get("p") else None
                    n = q.get("n", [""])[0]
                    if not f and APP.rec is not None and re.fullmatch(r"[\w\-]+\.(jpg|png)", n or ""):
                        f = os.path.join(APP.rec.shots_dir, n)
                    return self._json({"text": slide_text(f) if f else ""})
                if p == "/shot":
                    f = safe_shot(q.get("p", [""])[0])
                    if f:
                        return self._file(f, "image/jpeg" if f.endswith(".jpg") else "image/png")
                    return self._send(404, b"not found", "text/plain")
                rec = APP.rec
                if p == "/api/state":
                    if rec is None:
                        return self._json({"none": True}, 404)
                    rec.page_at = time.time()
                    return self._json(rec.state(qint("rev")))
                if p == "/media" and rec is not None:
                    ext = os.path.splitext(rec.media.path)[1].lower()
                    return self._file(rec.media.path, MEDIA_TYPES.get(ext, "application/octet-stream"))
                if p.startswith("/shots/") and rec is not None:
                    name = urllib.parse.unquote(p[7:])
                    if re.fullmatch(r"[\w\-]+\.(jpg|png)", name) and os.path.isfile(os.path.join(rec.shots_dir, name)):
                        return self._file(os.path.join(rec.shots_dir, name), "image/jpeg" if name.endswith(".jpg") else "image/png")
                return self._send(404, b"not found", "text/plain")
            except (ConnectionError, OSError):
                pass  # the browser stopped reading (it does that all the time while seeking)

        def do_POST(self):
            try:
                u = urllib.parse.urlsplit(self.path)
                p = u.path
                if not self._host_ok() or not self._site_ok(p) or not self._post_ok(p):
                    return self._refuse()
                APP.seen()
                if p == "/api/upload":
                    return self._json(self._upload(urllib.parse.parse_qs(u.query).get("name", [""])[0]))
                d = self._body_json()  # always read it: the connection is reused
                if p == "/api/place":
                    rec, live = APP.rec, APP.live
                    if d.get("yt") and live is not None and getattr(live, "clock", None) is not None:
                        live.clock.set(d)
                    elif rec is not None and not d.get("yt"):
                        rec.set_place(d)
                    return self._send(204, b"", "text/plain")
                if p == "/api/cmd":
                    return self._json(APP.command(d))
                if p == "/api/pick":
                    return self._json({"path": pick_file()})
                return self._send(404, b"not found", "text/plain")
            except (ConnectionError, OSError):
                pass

        def _upload(self, name):
            """A recording dragged onto the page: the browser sends the file, it is kept in the videos folder."""
            size = int(self.headers.get("Content-Length") or 0)
            stem, ext = os.path.splitext(os.path.basename(name or "recording"))
            ext = ext.lower() if ext.lower() in RECORDING_EXTS else ".mp4"
            os.makedirs(VIDEO_DIR, exist_ok=True)
            path = os.path.join(VIDEO_DIR, safe_stem(stem) + ext)
            if size and os.path.isfile(path) and os.path.getsize(path) == size:
                left = size
                while left > 0:  # read it anyway (the browser is sending it), keep the copy we have
                    buf = self.rfile.read(min(1 << 20, left))
                    if not buf:
                        break
                    left -= len(buf)
                return {"path": path}
            part, left = path + ".part", size
            with open(part, "wb") as f:
                while left > 0:
                    buf = self.rfile.read(min(1 << 20, left))
                    if not buf:
                        break
                    f.write(buf)
                    left -= len(buf)
            if left:
                _remove_quietly(part)
                return {"path": "", "error": "ההעלאה נקטעה באמצע. לנסות שוב."}
            os.replace(part, path)
            return {"path": path}

    return Handler


class AppServer:
    """The page on http://127.0.0.1:<port>/ - only this computer can open it."""

    def __init__(self):
        self.httpd, self.url = None, None

    def start(self):
        import http.server
        import socket
        import socketserver
        handler = _app_handler()

        class Server(http.server.ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = os.name != "nt"  # on Windows this would let two programs share a port

            def server_bind(self):
                if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                socketserver.TCPServer.server_bind(self)  # (skips a slow name lookup of the computer)
                self.server_name, self.server_port = "127.0.0.1", self.server_address[1]

        for port in PLAYER_PORTS:
            try:
                self.httpd = Server(("127.0.0.1", port), handler)
                break
            except OSError:
                continue
        if self.httpd is None:
            return False
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        try:
            os.makedirs(LOCAL_DIR, exist_ok=True)
            with open(APP_FILE, "w", encoding="utf-8") as f:
                json.dump({"url": self.url, "pid": os.getpid(), "version": VERSION}, f)
        except OSError:
            pass
        return True

    def stop(self):
        try:
            if self.httpd is not None:
                self.httpd.shutdown()
                self.httpd.server_close()
        except Exception:
            pass


def console_show():
    """The black window starts minimized - bring it up when it has something to say (an error, the address)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def open_browser(url):
    if os.environ.get("BZM_NO_BROWSER") == "1":
        return False
    import webbrowser
    try:
        return webbrowser.open(url)
    except Exception:
        return False


_CLOSE_HANDLERS = []


def on_window_close(fn):
    """Closing the black window with X ends the tool within seconds (no Ctrl+C) - fn() gets to save first."""
    if os.name != "nt":
        return
    try:
        import ctypes
        proto = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)

        def handler(event):
            if event in (2, 5, 6):  # window closed, log off, shut down
                try:
                    fn()
                except Exception:
                    pass
            return 0  # Windows (and Ctrl+C) carry on as usual

        h = proto(handler)
        _CLOSE_HANDLERS.append(h)  # must stay alive
        ctypes.windll.kernel32.SetConsoleCtrlHandler(h, True)
    except Exception:
        pass


# ----- a recording -----
def run_recording(sess, source, lang, course=""):
    """A recording (file, link, or Media from the library): transcribe it (where you watch first) and play it."""
    set_language(lang)
    try:
        av = load_real_av()  # reads the recording (the live mode does not need it)
    except Exception:
        tb = traceback.format_exc()
        save_error_text("PyAV", tb)
        sess.error = ("\n".join(block_text(tb)) if is_blocked(tb) else
                      "רכיב קריאת ההקלטות (PyAV) לא נטען. להריץ שוב את install בתיקייה Setup.") + \
            "\nבינתיים אפשר לנגן את ההקלטה בנגן אחר ולהשתמש בהרצאה חיה."
        return
    if SCREEN_ENABLED:
        _ensure_packages([("PIL", "pillow")], "לשמירת השקופיות")
    media = source if isinstance(source, Media) else video_source(source)
    if sess.stop.is_set():
        return
    if not media:
        sess.error = last_problem() or "לא הצלחתי לפתוח את ההקלטה."
        return
    try:
        duration = media_duration(av, media.audio)
        if media.video is not None and media.video == media.path and not has_stream(media.path, "video"):
            media.video = None  # a sound recording
    except Exception:
        save_error("open recording")
        sess.error = "לא הצלחתי לפתוח את הקובץ. אולי הוא לא קובץ סרטון או שמע, או שהוא פגום."
        return
    rec = Recording(media, duration, course)
    set_terms(read_glossary(rec.course), rec.course)
    resumed = rec.restore()
    sess.title, sess.transcript, sess.course = rec.stem, rec.out_path, rec.course
    log(f"הקלטה: {rec.stem} ({hms(rec.duration)})")
    if resumed == "done":
        log(f"ההקלטה הזו כבר תומללה: {rec.rel_transcript}")
    elif resumed == "resumed":
        log(f"ממשיך את התמלול מאיפה שנעצר ({rec.progress()}% כבר מוכן).")
    with APP.lock:
        APP.rec = rec
        APP.lib_rev += 1
    sess.ready = True
    player_url = (APP.url or "") + "player"

    def closing():
        rec.closed = True
        rec.save(force=True)
        where = f"המקום האחרון בהקלטה: {hms(rec.pos)}\n" if rec.pos is not None else ""
        write_now_file(f"מצב: לא צופים עכשיו בהקלטה.\nההקלטה האחרונה: {rec.stem}\n"
                       f"{where}תמלול מלא: {rec.rel_transcript}\n")
    sess.closing = closing

    slides, worker, said_done, last_now = None, None, False, (None, 0.0)
    try:
        if not rec.complete():
            loaded = {}

            def load():  # the model loads while the sound is being read (saves time)
                try:
                    loaded["m"] = get_model(lang, stub_av=False)
                except BaseException as e:
                    loaded["e"] = e
            loader = threading.Thread(target=load, daemon=True)
            loader.start()
            rec.set_phase("audio", "קורא את הקול מההקלטה...")
            show_status("קורא את הקול מההקלטה...")
            from faster_whisper.audio import decode_audio
            audio16 = decode_audio(media.audio, sampling_rate=TARGET_SR)
            draft_clear()
            if rec.duration <= 0:
                rec.duration = len(audio16) / TARGET_SR
            if loader.is_alive():
                rec.set_phase("model", "טוען את מודל התמלול...")
                log("טוען את מודל התמלול... (כמה שניות)")
            while loader.is_alive():
                loader.join(0.5)
            if "e" in loaded:
                raise loaded["e"]
            model, beam, model_desc = loaded["m"]
            on_gpu = model_desc.endswith("GPU")
            rec.model_desc = model_desc
            if not rec.blocks:
                rec.blocks = make_blocks(len(audio16), BLOCK_S["gpu" if on_gpu else "cpu"], audio16)
            rec.set_phase("work")
            worker = threading.Thread(target=transcribe_worker, args=(rec, model, beam, on_gpu, audio16), daemon=True)
            worker.start()
            log(f"מתמלל את ההקלטה{' על כרטיס המסך' if on_gpu else ''} - החלק שאתה צופה בו קודם. "
                "אפשר כבר לצפות ולשאול על מה שמוכן.")
        else:
            rec.set_phase("done")
        if not rec.slides_done and media.video:
            slides = VideoSlides(media.video, rec)
            slides.start()
        started, start_pct = time.time(), rec.progress()
        while not sess.stop.is_set():
            busy = (worker is not None and worker.is_alive()) or (slides is not None and not slides.done)
            if not busy and not said_done:
                said_done = True
                draft_clear()
                if rec.error:
                    rec.set_phase("error", "התמלול נעצר בגלל שגיאה (הפרטים ב-error_log.txt). מה שכבר מוכן נשמר.")
                    log("התמלול נעצר באמצע בגלל שגיאה (הפרטים ב-error_log.txt). מה שכבר תומלל נשמר.")
                elif rec.complete():
                    rec.set_phase("done")
                    rec.save(force=True)
                    if worker is not None or slides is not None:
                        log(f"התמלול מוכן: {rec.rel_transcript} ({len(rec.shots)} צילומי מסך).")
                    with APP.lock:
                        APP.lib_rev += 1
                if slides is not None and slides.failed:
                    log(f"צילומי המסך מההקלטה נעצרו ({slides.failed}). התמלול עצמו תקין.")
            pos = rec.pos
            where = f"אתה כאן: {hms(pos)} מתוך {hms(rec.duration)}" if pos is not None else "הנגן מחכה בדפדפן"
            if busy:
                pct = rec.progress()
                eta = ""
                if pct - start_pct >= 3:
                    eta = _fmt_eta((time.time() - started) * (100 - pct) / (pct - start_pct))
                head = f"מתמלל: {pct}% {eta}".strip() if worker is not None and worker.is_alive() else "שומר שקופיות מההקלטה"
                show_status(f"{head} | {where}")
            else:
                show_status(where)
            # now_watching.txt: when you moved, paused/played, or new text arrived (at most every 2 s)
            sig = (None if pos is None else int(pos // 3), rec.playing, rec.page_alive(), rec.rev)
            prev, since = last_now[0], time.time() - last_now[1]
            flip = prev is not None and (sig[1], sig[2]) != (prev[1], prev[2])  # played/paused, player closed/opened
            if sig != prev and (since >= 2 or flip) or since >= 30:
                if write_now_file(rec.now_text(player_url)):
                    last_now = (sig, time.time())
            sess.stop.wait(0.5)
    finally:
        draft_clear()
        rec.closed = True
        if slides is not None:
            slides.stop()
        rec.save(force=True)
        if not rec.finished() and rec.blocks:
            log(f"נשמר מה שתומלל עד עכשיו ({rec.progress()}%): {rec.rel_transcript}. "
                "בפעם הבאה עם אותה הקלטה התמלול ימשיך מאותה נקודה.")
        closing()


_LAST_PROBLEM = [""]


def last_problem():
    p, _LAST_PROBLEM[0] = _LAST_PROBLEM[0], ""
    return p


# ----- starting the tool -----
_INSTANCE = None  # keeps the "already running" marker alive while the tool runs


def another_window_open():
    """True if the tool is already running (two copies = double work, slower)."""
    global _INSTANCE
    if IS_MAC:
        try:
            import fcntl
            os.makedirs(LOCAL_DIR, exist_ok=True)
            _INSTANCE = open(os.path.join(LOCAL_DIR, ".running"), "w")
            fcntl.flock(_INSTANCE, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return False
        except OSError:
            return True
    if os.name != "nt":
        return os.environ.get("BZM_FAKE_RUNNING") == "1"
    try:
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        _INSTANCE = k32.CreateMutexW(None, False, "Local\\Hevanti_app")
        return ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return False


def running_url():
    """The page of a tool that is already running, if it answers."""
    try:
        with open(APP_FILE, encoding="utf-8") as f:
            url = json.load(f).get("url")
    except (OSError, ValueError):
        return None
    if not url:
        return None
    for _ in range(6):
        try:
            with _http(url + "api/app", timeout=2) as r:
                if r.status == 200:
                    return url
        except Exception:
            time.sleep(0.5)
    return None


def post_json(url, obj):
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(obj).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "X-BZM": "1"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def initial_action(argv, env):
    """What the launcher asked for. BeZmanEmet.bat passes --app; the 1.3 start files may still be in the folder."""
    source = next((a for a in argv if not a.startswith("--")), None)
    app_mode = "--app" in argv
    lang = "en" if (env.get("LT_LANG") or "").strip().lower() == "en" else "he"
    if source:
        if app_mode or env.get("LT_ASK_LANG") == "1":
            return {"kind": "offer", "source": source}
        return {"kind": "rec", "source": source, "lang": lang}
    if app_mode:
        return {"kind": "home"}
    if (env.get("LT_MODE") or "").lower() == "video":
        return {"kind": "home", "view": "rec"}
    return {"kind": "live", "lang": lang}   # start_Hebrew / start_English from 1.3


def main():
    log(f"{PRODUCT} - גרסה {VERSION} ({VERSION_DATE})")
    act = initial_action(sys.argv[1:], os.environ)
    if another_window_open():
        url = running_url()
        if url:
            try:
                if act["kind"] == "offer":
                    post_json(url + "api/cmd", {"action": "offer", "source": act["source"]})
                elif act["kind"] == "rec":
                    post_json(url + "api/cmd", {"action": "start_recording", "source": act["source"], "lang": act["lang"]})
            except Exception:
                save_error("forward")
            open_browser(url + ("#rec" if act.get("view") == "rec" else ""))
            log(f"{PRODUCT} כבר פועלת. פתחתי שוב את האפליקציה בדפדפן: {url}")
            return "forwarded"
        log("שים לב: נראה שהכלי כבר פתוח בחלון אחר (אולי גרסה ישנה). כדאי לסגור אותו - שני חלונות מתמללים פעמיים.")
    server = AppServer()
    if not server.start():
        raise RuntimeError("לא הצלחתי לפתוח את האפליקציה (כל הפורטים 8765-8769 תפוסים).")
    APP.url = server.url
    on_window_close(APP.emergency_close)
    os.makedirs(LIB_DIR, exist_ok=True)
    try:
        APP.migrated = migrate_old_layout()
    except Exception:
        save_error("migrate")
    if APP.migrated:
        log(f"{APP.migrated} הרצאות מגרסה קודמת הועברו לתיקייה \"{LIB_NAME}\\{NO_COURSE}\". אפשר להעביר אותן לקורסים.")
    threading.Thread(target=check_update, daemon=True).start()
    threading.Thread(target=refresh_connections, daemon=True).start()
    threading.Thread(target=write_all_course_ai_files, daemon=True).start()   # also courses made before 2.1
    MIRROR.start()
    threading.Thread(target=ocr_backfill, daemon=True).start()
    with _AI_APPS_LOCK:
        _AI_APPS["busy"] = True
    threading.Thread(target=refresh_ai_apps, daemon=True).start()
    last = clean_name(load_settings().get("course"), NO_COURSE)
    if act["kind"] == "live":
        APP.start("live", act["lang"], run_live, act["lang"], last, course=last)
    elif act["kind"] == "rec":
        APP.start("rec", act["lang"], run_recording, act["source"], act["lang"], last, title=display_name(act["source"]),
                  course=last)
    elif act["kind"] == "offer":
        APP.pending = {"source": act["source"], "name": display_name(act["source"])}
    APP.first_view = act.get("view", "")
    if not open_browser(server.url + ("#rec" if act.get("view") == "rec" else "")) and \
            os.environ.get("BZM_NO_BROWSER") != "1":
        console_show()  # no browser opened: the address is written in this window
    show("=" * 50)
    show(f"{PRODUCT} פועלת. האפליקציה נפתחה בדפדפן. אם לא נפתחה: {server.url}")
    show("החלון הזה הוא הסימן שהאפליקציה פועלת. אפשר למזער אותו. סגירה שלו עוצרת אותה.")
    show("=" * 50)
    try:
        while not APP.quit_evt.wait(1.0):
            s = APP.session
            idle = s is None or s.done
            if idle and time.time() - APP.last_seen > IDLE_EXIT_S:
                log(f"האפליקציה סגורה ושום דבר לא רץ כבר {max(1, round(IDLE_EXIT_S / 60))} דקות - {PRODUCT} נסגרה. כדי לפתוח שוב: Hevanti.")
                break
    except KeyboardInterrupt:
        draft_clear()
        log("עוצר...")
    APP.stop_session(wait=180)
    server.stop()
    _remove_quietly(APP_FILE)
    with APP.lock:
        s = APP.session
    if s is None or s.kind != "rec":
        try:
            now_text = open(NOW_FILE, encoding="utf-8").read() if os.path.exists(NOW_FILE) else ""
            if not now_text or "הרצאה חיה - התמלול רץ" in now_text or "סרטון יוטיוב - התמלול רץ" in now_text:
                write_now_file(f"מצב: {PRODUCT} סגורה - אין כרגע הרצאה חיה ולא צפייה בהקלטה.\n")
        except OSError:
            pass
    return "closed"


def rms(x):
    return float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0


def run_live(sess, lang, course=""):
    """A live lecture: whatever the computer plays is transcribed (and the screen photographed) until sess.stop."""
    set_language(lang)
    course = clean_name(course, NO_COURSE)
    set_terms(read_glossary(course), course)
    log("טוען... (כמה שניות)")
    os.makedirs(course_dir(course), exist_ok=True)
    if SCREEN_ENABLED:
        _ensure_packages([("mss", "mss"), ("PIL", "pillow")])
    if os.name == "nt":
        _ensure_packages([("comtypes", "comtypes")], "למעבר בין אוזניות לרמקולים")
    if IS_MAC:
        _ensure_packages([("sounddevice", "sounddevice")], "להקלטת הקול של המחשב")
    if sess.stop.is_set():
        return   # stopped while loading: no lecture folder
    model, beam, model_desc = get_model(lang, stub_av=True)
    if sess.stop.is_set():
        log("ההרצאה בוטלה לפני שהתחילה - לא נשמר כלום.")
        return
    on_gpu = model_desc.endswith("GPU")
    min_s, max_s = (GPU_MIN_CHUNK_S, GPU_MAX_CHUNK_S) if on_gpu else (MIN_CHUNK_S, MAX_CHUNK_S)
    q = queue.Queue()
    audio = AudioInput(q)
    told = False
    while not sess.stop.is_set():
        try:
            audio.open()
            break
        except Exception as e:
            if is_blocked(e) or isinstance(e, ImportError):
                raise
            if not told:
                if IS_MAC:
                    log("לא מצאתי את BlackHole - בלעדיו Mac לא נותן להקליט את הקול של המחשב. ההתקנה וההגדרה (פעם אחת) "
                        "כתובות ב-README, בחלק \"Mac\". ממשיך לנסות...")
                else:
                    log(f"לא נמצא התקן שמע פעיל ({e.__class__.__name__}). לחבר רמקולים או אוזניות - ממשיך לנסות...")
                told = True
            sess.stop.wait(5)
    if sess.stop.is_set():
        return
    sr, ch, dev = audio.sr, audio.ch, audio.name
    speakers = DefaultSpeakers()
    speakers_id = speakers.current() if speakers.ok else None

    start = datetime.datetime.now()
    yt = getattr(sess, "yt", None)   # a YouTube video in Hevanti's player (else: a live lecture)
    ldir, old = None, ([], [], Coverage(), 0.0, "", Coverage())
    if yt:
        ldir = find_yt_lecture(course, yt["id"])  # started before: continue in the same lecture
        if ldir:
            old = read_yt_lecture(ldir)
    if ldir is None:
        name = free_folder(course_dir(course), f"{start:%Y-%m-%d %H-%M} " + ("יוטיוב" if yt else "הרצאה")
                           + (" באנגלית" if LANG == "en" and not yt else ""))
        ldir = os.path.join(course_dir(course), name)
    os.makedirs(ldir, exist_ok=True)
    cover, seen = old[2], old[5]   # transcribed / watched for slides (video seconds)
    path = lecture_txt(ldir)
    lecture_rel = lib_rel(ldir)
    transcript_rel = lecture_rel + "/" + os.path.basename(path)
    write_lock = threading.Lock()

    def write_line(line):
        with write_lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    lang_he = 'אנגלית' if LANG == 'en' else 'עברית'
    if yt and os.path.isfile(path):
        pass  # continuing a video: its header is there
    elif yt:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"# תמלול סרטון יוטיוב ({lang_he}) - {yt['url']} | מזהה: {yt['id']} | התחלה {start:%Y-%m-%d %H:%M}"
                    f" | גרסה: {VERSION} | מודל: {model_desc}" + (f" | קורס: {course}" if course != NO_COURSE else "") + "\n")
    else:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"# תמלול הרצאה ({lang_he}) - התחלה {start:%Y-%m-%d %H:%M} | גרסה: {VERSION} | מודל: {model_desc} | התקן: {dev}"
                    + (f" | קורס: {course}" if course != NO_COURSE else "")
                    + ("" if SCREEN_ENABLED else " | בלי צילומי מסך") + "\n")

    if yt:
        clock = YtClock(yt.get("start") or old[3])
        clock.title = old[4]

        def got_title(t):
            write_line(YT_TITLE + t)
            sess.title = t
            with APP.lock:
                APP.lib_rev += 1
        clock.on_title = got_title
        now_file = YtNow(transcript_rel, start, clock, yt["url"], course=course, lines=old[0], shots=old[1])
        now_file.cover = cover
        if old[4]:
            sess.title = old[4]
    else:
        clock = None
        now_file = LiveNow(transcript_rel, start, drafts=DRAFTS and on_gpu, course=course)
    now_file.info.update(transcript=transcript_rel, device=dev, gpu=on_gpu, course=course, f=lecture_rel,
                         lang=LANG, started=start.strftime("%H:%M"), started_ts=start.timestamp())
    sess.transcript = path
    with APP.lock:
        APP.live = now_file
        APP.lib_rev += 1
    now_file.start()
    threading.Thread(target=media_status_loop, daemon=True).start()
    watcher = None
    if SCREEN_ENABLED:
        last_look = [None]

        def yt_area():
            """Where to photograph the video - nothing while it is paused (the player's controls appear when the
            mouse is over it - not a new slide), nor in a part already watched for slides. Watching marks the part
            since the last look as watched: a slide that changed in it was seen (and saved) then."""
            pos, playing, _alive = clock.now()
            if not playing:
                last_look[0] = None
                return None
            already = seen.covered(pos - 2, pos + 2) > 0.9 or \
                (cover.covered(pos - 2, pos + 2) > 0.9 and now_file.shot_near(pos, 20))
            before, last_look[0] = last_look[0], pos
            if before is not None and 0 <= pos - before <= 8:
                seen.add(before, pos)
            else:
                seen.add(pos - 0.5, pos + 0.5)
            return None if already else clock.capture_rect()
        watcher = ScreenWatcher(ldir, lecture_rel, start.timestamp(), write_line, now_file.add_shot,
                                region_fn=yt_area if yt else None)
        watcher.start()
    else:
        log("צילום מסך כבוי - רק תמלול")
    ended = [False]

    def closing():
        """Write the end of the transcript (once): when stopping, or when the window is closed with X."""
        if ended[0]:
            return
        ended[0] = True
        if sess.discard and not (yt and old[0]):
            # stopped right after starting, and the student chose to delete it (a video watched before is kept)
            import shutil
            now_file.finish(transcript_rel)
            shutil.rmtree(ldir, ignore_errors=True)
            log("ההרצאה נמחקה (נעצרה מיד אחרי שהתחילה).")
            with APP.lock:
                APP.lib_rev += 1
            return
        if yt and not old[0] and not now_file.all:
            # nothing was played (e.g. the owner doesn't allow playing the video outside YouTube): no empty lecture
            import shutil
            now_file.finish(transcript_rel)
            shutil.rmtree(ldir, ignore_errors=True)
            with APP.lock:
                APP.lib_rev += 1
            return
        if yt:
            save_yt_state(ldir, cover, clock.now()[0], seen)
            tidy_yt_transcript(path)
        else:
            write_line(f"# סוף: {datetime.datetime.now():%H:%M}")
        now_file.finish(transcript_rel)
    sess.closing = closing
    if yt:
        log(f"מוכן לתמלול {'באנגלית' if LANG == 'en' else 'בעברית'}. הסרטון מתנגן בנגן של הבנתי - "
            "מה שמתנגן בו מתומלל, ושקופיות נשמרות מהחלק של הנגן במסך.")
    else:
        log(f"מוכן לתמלול {'באנגלית' if LANG == 'en' else 'בעברית'}{' (על כרטיס המסך)' if on_gpu else ''}. תפעיל את ההרצאה.")
    sess.ready_at = time.time()
    sess.ready = True

    blocks, n, t0 = [], 0, None
    inflight = []  # the sound being transcribed right now - done again if Ctrl+C stops it in the middle
    state = {"prev_text": "", "fast": False, "calm": 0, "fast_count": 0, "warned_at": 0.0,
             "draft_at": 0.0, "draft_cost": 0.0, "load": 0.0, "lag": 0.0, "batch_ok": True}
    drafts_on = DRAFTS and on_gpu and not yt
    saved_at = [time.time()]

    def draft(buf, buf_sr):
        """Quick draft of the piece that is still being heard (GPU only, never written to the transcript)."""
        try:
            if rms(buf[-3 * buf_sr:]) < SILENCE_RMS:
                return  # nothing is being said right now
            t1 = time.time()
            text = transcribe(model, 1, resample(buf, buf_sr), state["prev_text"])
            state["draft_cost"] = time.time() - t1
            if text:
                show_draft(text)
                now_file.set_draft(text)
        except Exception:
            pass  # a draft is optional; the final text still comes

    def draft_fits():
        """A draft only when the GPU has time to spare - it must never make the real text late."""
        return (not state["fast"] and state["load"] < DRAFT_MAX_LOAD and state["lag"] < FAST_OFF_LAG_S
                and time.time() - state["draft_at"] >= max(DRAFT_EVERY_S, state["draft_cost"] / DRAFT_MAX_SHARE))

    def say(line_t, text, dur=None):
        """One finished line: into the transcript, the window and now_watching.txt."""
        if yt:
            m = clock.pos_at(line_t)
            if m is None or not m[1]:
                return  # the player was not playing - this sound is not the video's
            a = m[0]
            b = a + (dur or 6.0) * clock.rate_at(line_t)
            if cover.covered(a, b) > 0.5:
                return  # watched again: already transcribed
            e = clock.pos_at(line_t + (dur or 6.0))
            if e is not None and abs(e[0] - b) > 1.5 and cover.covered(max(0.0, e[0] - 2), e[0]) > 0.5:
                return  # a jump inside this piece, to a part already transcribed: its sound is mostly a repeat
            cover.add(a, b)
            state["prev_text"] = (state["prev_text"] + " " + text)[-400:]
            write_line(f"[{hms(a)}] {text}")
            show(f"[{hms(a)}] {text}")
            now_file.add(a, text)
            if time.time() - saved_at[0] > 30:
                saved_at[0] = time.time()
                save_yt_state(ldir, cover, clock.now()[0], seen)
            return
        state["prev_text"] = (state["prev_text"] + " " + text)[-400:]
        stamp = datetime.datetime.fromtimestamp(line_t).strftime("%H:%M:%S")
        elapsed = str(datetime.timedelta(seconds=int(max(0, line_t - start.timestamp()))))
        write_line(f"[{stamp} | +{elapsed}] {text}")
        show(f"[{stamp}] {text}")
        now_file.add(line_t, text)

    def handle_chunk(chunk, chunk_t, chunk_sr, heard_until=None):
        """Transcribe one piece of audio and write it out (the final text replaces the draft line).
        heard_until: when the newest sound we already have arrived - the delay is measured from there
        (not from the end of this piece: waiting for a piece to fill up is not being late)."""
        if len(chunk) < chunk_sr or rms(chunk) < SILENCE_RMS:
            draft_clear()
            now_file.set_draft("")
            return
        t1 = time.time()
        text = transcribe(model, 1 if state["fast"] else beam, resample(chunk, chunk_sr), state["prev_text"])
        busy = (time.time() - t1) / (len(chunk) / chunk_sr)  # share of the time the real text needs
        state["load"] = busy if state["load"] == 0 else 0.5 * state["load"] + 0.5 * busy
        lag = time.time() - (heard_until or chunk_t + len(chunk) / chunk_sr)
        state["lag"] = now_file.lag = lag
        track_lag(lag)
        now_file.fast = state["fast"]
        now_file.set_draft("")
        if not text:
            draft_clear()
            return
        say(chunk_t, text, len(chunk) / chunk_sr)
        warn_lag(lag)

    def track_lag(lag):
        """On a GPU: drop to fast mode while behind, return to full accuracy once caught up."""
        if beam <= 1:
            return
        if not state["fast"] and lag > FAST_ON_LAG_S:
            state["fast"], state["calm"] = True, 0
            state["fast_count"] += 1
            if state["fast_count"] == 1:
                log("התמלול מתחיל לאחר - עובר למצב מהיר (קצת פחות מדויק) עד שהוא מדביק את הקצב.")
            note("מצב מהיר")
        elif state["fast"] and state["fast_count"] < FAST_MAX_SWITCHES:
            state["calm"] = state["calm"] + 1 if lag < FAST_OFF_LAG_S else 0
            if state["calm"] >= 3:
                state["fast"] = False
                note("דיוק מלא")

    def warn_lag(lag):
        if lag > LAG_WARN_S and time.time() - state["warned_at"] > 120:
            state["warned_at"] = time.time()
            if beam > 1:
                log(f"אזהרה: התמלול מאחר ב-{lag:.0f} שניות, גם על כרטיס המסך ובמצב מהיר. "
                    "כדאי לסגור תוכנות כבדות (משחקים, עריכת וידאו, הרבה לשוניות בדפדפן).")
            else:
                log(f"אזהרה: התמלול מאחר ב-{lag:.0f} שניות. הכלי עובד על המעבד, והוא איטי מדי במחשב הזה. "
                    "יש כרטיס מסך של NVIDIA? לעדכן את הדרייבר שלו, להפעיל מחדש את המחשב ולהריץ install_gpu (בתיקייה Setup). "
                    "אין? לסגור תוכנות כבדות, ובמחשב נייד לחבר למטען.")

    def handle_backlog(buf, buf_t, buf_sr):
        """The transcript is behind: everything that waited is transcribed in one batch on the GPU.
        Returns False if that did not work (then the caller does it piece by piece, as usual)."""
        if rms(buf) < SILENCE_RMS:
            draft_clear()
            return True
        t1 = time.time()
        try:
            parts = transcribe_batch(model, 1 if state["fast"] else beam, resample(buf, buf_sr), state["prev_text"])
        except Exception:
            save_error("batch")
            state["batch_ok"] = False  # not possible on this computer - back to one piece at a time
            return False
        dur = len(buf) / buf_sr
        busy = (time.time() - t1) / dur
        state["load"] = busy if state["load"] == 0 else 0.5 * state["load"] + 0.5 * busy
        lag = time.time() - (buf_t + dur)
        state["lag"] = now_file.lag = lag
        note(f"השלמת פיגור: {dur:.0f} שניות בבת אחת")
        draft_clear()
        now_file.set_draft("")
        for start_s, text in parts:
            if text:
                say(buf_t + start_s, text)
        track_lag(lag)
        warn_lag(lag)
        return True

    def in_pieces(buf, buf_t, buf_sr):
        """Transcribe a long stretch piece by piece (the normal way)."""
        pos = 0
        while pos < len(buf):
            inflight[:] = [(buf[pos:], buf_t + pos / buf_sr, buf_sr)]
            left = len(buf) - pos
            c = find_cut(buf[pos:], buf_sr, min_s, max_s) if left > max_s * buf_sr else left
            handle_chunk(buf[pos:pos + c], buf_t + pos / buf_sr, buf_sr)
            pos += c
        inflight.clear()

    def note(line):
        if yt:
            return  # the video's transcript has only the video's times
        now = time.time()
        stamp = datetime.datetime.fromtimestamp(now).strftime("%H:%M:%S")
        elapsed = str(datetime.timedelta(seconds=int(now - start.timestamp())))
        write_line(f"[{stamp} | +{elapsed}] [{line}]")

    def reconnect(reason, loud):
        """Reopen the audio device (new default device, after sleep, after an error)."""
        nonlocal blocks, n, t0, sr, ch
        if n > 0:  # transcribe what we already have before switching
            handle_chunk(np.concatenate(blocks), t0, sr)
        blocks, n, t0 = [], 0, None
        old = audio.name
        try:
            audio.open()
        except Exception as e:
            if not state.get("down"):
                log(f"{reason} - אין כרגע התקן שמע פעיל ({e.__class__.__name__}). לחבר רמקולים או אוזניות - ממשיך לנסות...")
                state["down"] = True
            return False
        sr, ch = audio.sr, audio.ch
        was_down = state.pop("down", False)
        if was_down:
            log(f"התחברתי שוב להתקן השמע: {audio.name}. התמלול ממשיך.")
            note(f"התקן שמע: {audio.name}")
        elif audio.name != old:
            log(f"התקן השמע הוחלף: {audio.name}. התמלול ממשיך ממנו.")
            note(f"התקן שמע: {audio.name}")
        elif loud:
            log(f"{reason} - התחברתי מחדש ל: {audio.name}. התמלול ממשיך.")
            note(f"התחברות מחדש: {reason}")
        return True

    last_audio = time.time()
    last_loop = time.time()
    last_reconnect = time.time()
    last_default_check = time.time()
    warned_silent = False
    def finish_tail():
        """Don't lose the last seconds: the piece that was in the middle, what was heard, what still waits."""
        if sess.discard:
            return   # it is being deleted: nothing to finish
        log("עוצר... (מתמלל את השניות האחרונות)")
        now_file.info["stopping"] = True
        try:
            rest = list(inflight)
            more = [np.concatenate(blocks)] if n > 0 else []
            first_t = t0
            while True:
                try:
                    g2, t2, d2 = q.get_nowait()
                except queue.Empty:
                    break
                if g2 == audio.gen:
                    if first_t is None:
                        first_t = t2
                    more.append(to_mono(d2, ch))
            if more:
                rest.append((np.concatenate(more), first_t, sr))
            for buf, bt, bsr in rest:
                in_pieces(buf, bt, bsr)
        except KeyboardInterrupt:
            pass  # Ctrl+C again: stop right now
        except Exception:
            save_error("last seconds")

    try:
        while not sess.stop.is_set():
            now = time.time()
            # ---- watchdog: keep listening after sleep / device change / errors ----
            if now - last_loop > 20:
                reconnect("המחשב חזר ממצב שינה", True); last_reconnect = now; last_audio = now
            elif not audio.alive() and now - last_reconnect > 3:
                reconnect("התקן השמע התנתק", True); last_reconnect = now; last_audio = now
            elif MEDIA_STATUS == "Playing" and now - last_audio > 8 and now - last_reconnect > 15:
                # something is playing but no sound reaches us -> the sound went to another device
                reconnect("משהו מתנגן אבל לא מגיע סאונד", False); last_reconnect = now
                if not warned_silent and now - last_audio > 40:
                    log("לא מגיע סאונד למרות שמשהו מתנגן. לבדוק שההרצאה לא מושתקת ושהסאונד יוצא מהרמקולים/האוזניות של המחשב.")
                    warned_silent = True
            elif now - last_audio > 45 and now - last_reconnect > 45:
                reconnect("בדיקה שקטה", False); last_reconnect = now
            elif speakers.ok and now - last_default_check >= 1.0:
                # the user picked other speakers/headphones -> follow them right away
                last_default_check = now
                cur = speakers.current()
                if cur and cur != speakers_id:
                    reconnect("התקן השמע הוחלף", False); last_reconnect = now; last_audio = now
                    speakers_id = speakers.current() or cur
            if speakers.ok and last_reconnect == now:
                speakers_id = speakers.current() or speakers_id  # reconnected for another reason
            last_loop = now
            try:
                g, t, data = q.get(timeout=0.5)
            except queue.Empty:
                g = None
            if g is None or g != audio.gen:  # nothing new, or audio from a device we already left
                continue
            last_audio = time.time(); warned_silent = False
            a = to_mono(data, ch)
            if t0 is None:
                t0 = t
            blocks.append(a)
            n += len(a)
            now_file.pending_s = n / sr
            if n < max_s * sr:
                if drafts_on and n >= DRAFT_MIN_S * sr and q.qsize() < 8 and draft_fits():
                    state["draft_at"] = time.time()
                    draft(np.concatenate(blocks), sr)
                continue

            buf = np.concatenate(blocks)
            if on_gpu and BATCH and state["batch_ok"] and q.qsize() * len(a) >= max_s * sr:
                # behind by more than a whole piece: take everything that is waiting and do it in one go
                more = [buf]
                while True:
                    try:
                        g2, _, d2 = q.get_nowait()
                    except queue.Empty:
                        break
                    if g2 == audio.gen:
                        more.append(to_mono(d2, ch))
                buf = np.concatenate(more)
                tail = min(len(buf), int(max_s * sr))
                cut = len(buf) - tail + find_cut(buf[-tail:], sr, 0.5, max_s)  # keep the last words for the next piece
                back_t = t0
                blocks, n, t0 = [buf[cut:]], len(buf) - cut, t0 + cut / sr
                inflight[:] = [(buf[:cut], back_t, sr)]
                if not handle_backlog(buf[:cut], back_t, sr):
                    in_pieces(buf[:cut], back_t, sr)
                inflight.clear()
                last_loop = time.time()
                continue
            cut = find_cut(buf, sr, min_s, max_s)
            chunk, rest = buf[:cut], buf[cut:]
            chunk_t = t0
            blocks, n, t0 = [rest], len(rest), t0 + cut / sr

            inflight[:] = [(chunk, chunk_t, sr)]
            handle_chunk(chunk, chunk_t, sr, heard_until=t + len(a) / sr)
            inflight.clear()
            last_loop = time.time()  # transcribing can take a while - that is not "sleep"
    except KeyboardInterrupt:
        finish_tail()
    else:
        finish_tail()
    finally:
        audio.close()
        if MEDIA_PROC is not None:
            try:
                MEDIA_PROC.terminate()
            except Exception:
                pass
        if watcher is not None:
            watcher.stop()
            log(f"צילומי מסך שנשמרו: {watcher.count}")
        closing()
        now_file.ended = True
        if not os.path.isdir(ldir):
            sess.transcript = None
        else:
            log(f"נשמר: {path}")


# ---------- uninstall (uninstall.bat) ----------
TOOL_PKGS = ["faster-whisper", "ctranslate2", "pyaudiowpatch", "mss", "nvidia-cublas-cu12", "nvidia-cudnn-cu12",
             "yt-dlp", "yt-dlp-ejs", "deno"]
SHARED_PKGS = ["onnxruntime", "av", "tokenizers", "huggingface-hub", "pillow", "comtypes"]


def _ask(question):
    show(question + "   (Y = כן, N = לא)")
    try:
        return input("> ").strip().lower() in ("y", "yes", "כ", "כן")
    except Exception:
        return False


def _size_gb(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total / 1024 ** 3


def uninstall():
    import shutil
    import subprocess
    show(f"הסרת \"{PRODUCT}\" (גרסה {VERSION})")
    if not _ask(f"להסיר את {PRODUCT} מהמחשב?"):
        show("בוטל. לא נמחק כלום.")
        return
    for app_name, done in (("Claude", claude_set(False) if claude_connected() else None),
                           ("ChatGPT", chatgpt_set(False) if chatgpt_connected() else None),
                           ("Gemini CLI", gemini_set(False) if gemini_connected() else None)):
        if done is not None:
            show(f"החיבור של הבנתי הוסר מ-{app_name}" + ("" if done.get("ok") else " (לא הצליח - לנתק ידנית בהגדרות שלו)"))
    if os.path.isdir(MODEL_DIR):
        gb = _size_gb(MODEL_DIR)
        shutil.rmtree(MODEL_DIR, ignore_errors=True)
        show(f"נמחקו מודלי התמלול ({gb:.1f}GB) מ- {MODEL_DIR}")
    show("מסיר את רכיבי Python של הכלי...")
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", *TOOL_PKGS])
    if _ask("להסיר גם ספריות כלליות שהכלי התקין (" + ", ".join(SHARED_PKGS) + ")? אם יש לך תוכנות Python אחרות, עדיף לבחור N."):
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", *SHARED_PKGS])
    for local in (LOCAL_DIR, OLD_LOCAL_DIR):
        if os.path.isdir(local):
            gb = _size_gb(local)
            if gb < 0.01 or _ask(f"למחוק גם הקלטות שהורדו מקישורים או נגררו לאפליקציה ({gb:.1f}GB, ב-{local})?"):
                shutil.rmtree(local, ignore_errors=True)
                show("ההקלטות שהורדו נמחקו.")
    for d, label in ((LIB_DIR, "ההרצאות שלך (תמלולים ושקופיות)"), (OUT_DIR, "התמלולים הישנים"),
                     (SCREEN_DIR, "צילומי המסך הישנים")):
        if os.path.isdir(d) and os.listdir(d):
            if _ask(f"למחוק גם את {label}? הם יימחקו לתמיד. ({d})"):
                shutil.rmtree(d, ignore_errors=True)
                show(f"{label} נמחקו.")
            else:
                show(f"{label} נשארו בתיקייה.")
    try:
        os.remove(ERROR_LOG)
    except OSError:
        pass
    show("סיום.")
    show(f"מה שנשאר לעשות ידנית: למחוק את התיקייה של {PRODUCT} בסייר הקבצים.")
    show("Python עצמו נשאר. אם לא צריך אותו לשום דבר אחר: הגדרות ← אפליקציות ← Python ← הסרה.")


if __name__ == "__main__":
    if "--disconnect-ai" in sys.argv:   # Hevanti-Setup's uninstaller: take Hevanti out of the AI apps, quietly
        for _app in AI_APPS:
            try:
                connect_app(_app, False)
            except Exception:
                pass
        sys.exit(0)
    if "--uninstall" in sys.argv:
        try:
            uninstall()
        except Exception:
            show_lines(traceback.format_exc())
        print()
        wait_enter("Enter לסגירה...")
        sys.exit(0)
    try:
        result = main()
        if result == "forwarded":
            time.sleep(2)  # the page of the running tool opens - this window closes by itself
        sys.exit(0)
    except KeyboardInterrupt:  # Ctrl+C before the tool was ready
        show("נעצר.")
        time.sleep(1)
        sys.exit(0)
    except Exception:
        console_show()  # the window started minimized - the user must see this
        tb = traceback.format_exc()
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.datetime.now()} (גרסה {VERSION}) ---\n{tb}")
        if is_blocked(tb):
            explain_block(tb)
        elif "No module named" in tb:
            show(MISSING_PARTS)
        else:
            show_lines(tb)
            print()
            if "Could not load any transcription model" in tb:
                show("לא הצלחתי להוריד או לטעון את מודל התמלול. לבדוק שיש חיבור לאינטרנט ולהפעיל שוב - ההורדה ממשיכה מאיפה שעצרה.")
        print()
        show("שגיאה. הפרטים נשמרו בקובץ error_log.txt")
        wait_key()

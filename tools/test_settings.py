"""Saving the settings and the Gemini key (System/Program/live_transcribe.py): the file is written whole or not at all, a damaged
file is never taken for "no settings" quietly (the key and every choice would be gone), two threads saving at once lose nothing,
and a key that cannot be encrypted is not saved. Any OS, a few seconds:
  python3 tools/test_settings.py"""
import json
import os
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp()
os.environ["BZM_DATA_DIR"] = os.path.join(TMP, "data")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "local")
os.environ["BZM_NO_BROWSER"] = "1"
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)[:400]), flush=True)
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


F = L.SETTINGS_FILE
said = []
real_log = L.log
L.log = lambda msg: (said.append(str(msg)), real_log(msg))[0]
L.ERROR_LOG = os.path.join(TMP, "error_log.txt")


def error_log():
    return open(L.ERROR_LOG, encoding="utf-8").read() if os.path.isfile(L.ERROR_LOG) else ""


# ------------------------------------------------------------------------------------------ 1. a normal save
check("no file yet: no settings", L.load_settings() == {})
check("a save says it worked", L.save_settings(theme="dark", course="פיזיקה") is True)
check("...and is read back", L.load_settings() == {"theme": "dark", "course": "פיזיקה"}, L.load_settings())
L.save_settings(theme="light")
check("a save changes only what it is given", L.load_settings() == {"theme": "light", "course": "פיזיקה"}, L.load_settings())
check("no temporary file is left", not os.path.exists(F + ".tmp"), os.listdir(os.path.dirname(F)))
check("the last good file is kept as .bak", json.load(open(F + ".bak", encoding="utf-8")) == {"theme": "dark", "course": "פיזיקה"})

# ------------------------------------------------------------------------------------------ 2. a crash in the middle of a save
good = open(F, encoding="utf-8").read()
real_replace = os.replace


def broken_replace(a, b):
    raise OSError("the computer went off")


L.os.replace = broken_replace
try:
    ok = L.save_settings(theme="dark")
finally:
    L.os.replace = real_replace
check("the save cannot finish: it says so, and the old file is whole", ok is False and open(F, encoding="utf-8").read() == good, ok)
check("...and says so in error_log.txt", "save settings" in error_log(), error_log()[-200:])
if os.path.exists(F + ".tmp"):
    os.remove(F + ".tmp")

# ------------------------------------------------------------------------------------------ 3. a damaged file, with a good copy
L.save_settings(math={"key": "dpapi:SECRET", "ask": True})
with open(F, "w", encoding="utf-8") as f:
    f.write('{"math": {"key": "dpapi:SEC')   # cut in the middle, as a crash would leave it
del said[:]
d = L.load_settings()
check("a damaged file: the last good copy is used, not 'no settings'", d.get("theme") == "light" and d.get("course") == "פיזיקה", d)
check("...the damaged file is kept beside it", os.path.isfile(F + ".corrupt") and "dpapi:SEC" in open(F + ".corrupt", encoding="utf-8").read())
check("...and the student is told", any("פגום" in x and "שחזרתי" in x for x in said), said)
check("...and error_log.txt says it", "settings damaged" in error_log(), error_log()[-300:])
check("...and the file on disk is whole again", json.load(open(F, encoding="utf-8")) == d)

# ------------------------------------------------------------------------------------------ 4. a damaged file, no good copy
os.remove(F + ".bak")
with open(F, "w", encoding="utf-8") as f:
    f.write("not json at all")
del said[:]
d = L.load_settings()
check("a damaged file and no good copy: empty, but not quietly", d == {} and any("פגום" in x and "אין העתק תקין" in x for x in said), (d, said))
check("...the damaged file is kept", open(F + ".corrupt", encoding="utf-8").read() == "not json at all")
check("a save over it works (the damaged file is already kept)", L.save_settings(theme="dark") is True and L.load_settings() == {"theme": "dark"})

# ------------------------------------------------------------------------------------------ 5. a file that cannot be read now
real_open = open
calls = {"n": 0}


def locked_open(path, *a, **k):
    if str(path) == F:
        calls["n"] += 1
        raise PermissionError("in use by another program")
    return real_open(path, *a, **k)


import builtins  # noqa: E402
builtins.open = locked_open
try:
    saved = L.save_settings(theme="light")
finally:
    builtins.open = real_open
check("a file held by another program: nothing is saved (an empty start would erase everything)", saved is False and calls["n"] >= 2, (saved, calls))
check("...and it was not changed", L.load_settings() == {"theme": "dark"}, L.load_settings())

# ------------------------------------------------------------------------------------------ 6. two threads save at once
L.save_settings(seed="x")
stop, bad = threading.Event(), []


def reader():
    while not stop.is_set():
        d = L.load_settings()
        if d.get("seed") != "x":
            bad.append(dict(d))
            return


def writer(name):
    for i in range(150):
        L.save_settings(**{name: i})


rd = threading.Thread(target=reader)
ws = [threading.Thread(target=writer, args=(n,)) for n in ("a", "b", "c")]
rd.start()
for w in ws:
    w.start()
for w in ws:
    w.join(60)
stop.set()
rd.join(10)
final = L.load_settings()
check("three threads saving at once: every one's last value is there", all(final.get(n) == 149 for n in "abc") and final.get("seed") == "x", final)
check("...and the file was never seen half written or empty", not bad, bad[:1])
check("...and it is valid JSON", isinstance(json.load(open(F, encoding="utf-8")), dict))

# ------------------------------------------------------------------------------------------ 7. the key
secret = L.keep_secret("AQ.fake-key")
check("the key is kept in a form that reads back", L.read_secret(secret) == "AQ.fake-key", secret)
check("an empty key is kept as nothing", L.keep_secret("   ") == "")

real_dpapi, real_flag = L._dpapi, L.DPAPI_REQUIRED
L.DPAPI_REQUIRED = True


def no_dpapi(data, protect):
    raise OSError("DPAPI")


L._dpapi = no_dpapi
try:
    err = None
    try:
        L.keep_secret("AQ.fake-key")
    except L.SecretError as e:
        err = str(e)
    check("the encryption fails: the key is not kept, with a clear message", err is not None and "לא הצלחתי להצפין את המפתח" in err, err)
    L.save_settings(math={})
    probed = []
    real_probe = L.MathReader.probe
    L.MathReader.probe = lambda self, key: probed.append(key) or "gemini-x"
    try:
        r = L.math_set({"key": "AQ.fake-key", "ask": True})
    finally:
        L.MathReader.probe = real_probe
    check("saving a key when it cannot be encrypted: refused, with the message", r.get("ok") is False and "לא הצלחתי להצפין את המפתח" in r.get("error", ""), r)
    check("...nothing is saved, not even in plain text", "key" not in L.math_settings() and "AQ.fake" not in open(F, encoding="utf-8").read(), L.math_settings())
    check("...and the key is not sent to Google", probed == [], probed)
finally:
    L._dpapi, L.DPAPI_REQUIRED = real_dpapi, real_flag

# ------------------------------------------------------------------------------------------ 8. a save that cannot be done is told
real_open2 = open


def locked_open2(path, *a2, **k):
    if str(path) == F or str(path) == F + ".tmp":
        raise PermissionError("in use by another program")
    return real_open2(path, *a2, **k)


del said[:]
before_n = L._SAVE_FAIL["n"]
builtins.open = locked_open2
try:
    saved = L.save_settings(theme="light")
    r = L.math_set({"notes": "תענה בשורה אחת"})
    state_during = L.APP.state() if getattr(L, "APP", None) is not None else {}
finally:
    builtins.open = real_open2
check("a save that cannot be done: the student is told in Hebrew, in the window", saved is False and any(L.SAVE_FAIL_MSG in x for x in said), (saved, said))
check("...the message says 'could not save, try again'", "לא הצלחתי לשמור" in L.SAVE_FAIL_MSG and "לנסות שוב" in L.SAVE_FAIL_MSG, L.SAVE_FAIL_MSG)
check("a command that saves (the instructions) answers with the same message, not 'ok'", r.get("ok") is False and r.get("error") == L.SAVE_FAIL_MSG, r)
check("...and every page is told: save_failed in what the app polls (a count, so each failure is shown once)",
      L._SAVE_FAIL["n"] >= before_n + 2 and (L.save_failed_public() or {}).get("msg") == L.SAVE_FAIL_MSG, (L._SAVE_FAIL, L.save_failed_public()))
check("...it is in the app's state", (state_during.get("save_failed") or {}).get("msg") == L.SAVE_FAIL_MSG if state_during else True, state_during.get("save_failed"))
L._SAVE_FAIL["at"] = 0.0
check("...and it is shown only for a minute", L.save_failed_public() is None)

# ------------------------------------------------------------------------------------------ 9. deleting the key deletes every copy of it
KEY2 = "AQ.deleteme-secret-key-0123456789"
STORED2 = L.keep_secret(KEY2)   # (DPAPI gives different bytes on every call: this one value is what is written everywhere below)
L.save_settings(theme="dark", math={"key": STORED2, "ask": True})
L.save_settings(course="פיזיקה")                       # (this save makes the last good copy, .bak, from a file that has the key)
L.probe_cache_write(KEY2, ["gemini-x"])
with open(F + ".corrupt", "w", encoding="utf-8") as f:
    f.write(json.dumps({"math": {"key": STORED2}}))
with open(F + ".tmp", "w", encoding="utf-8") as f:
    f.write(json.dumps({"math": {"key": STORED2}}))
stored = L.math_settings().get("key")
check("before: the key is in the settings, in the last good copy, in a damaged copy and in an unfinished write",
      all(stored in real_open2(x, encoding="utf-8").read() for x in (F, F + ".bak", F + ".corrupt", F + ".tmp")) and os.path.isfile(L._probe_cache_path()))


def files_with(text):
    hits = []
    for root, _dirs, names in os.walk(os.path.dirname(F)):
        for n in names:
            try:
                if text in real_open2(os.path.join(root, n), encoding="utf-8", errors="replace").read():
                    hits.append(n)
            except OSError:
                pass
    return hits


r = L.math_set({"key": ""})
check("'delete the key' worked", r.get("ok") is True and not L.math_settings().get("key"), r)
check("...the key is in no file of Hevanti's folder (not the settings, not the last good copy, not the damaged copy, not a write that did not finish)",
      not files_with(stored) and not files_with("AQ.deleteme"), (files_with(stored), os.listdir(os.path.dirname(F))))
check("...the models check (it holds a mark of the key) is gone too", not os.path.exists(L._probe_cache_path()))
check("...the last good copy is made again from the settings as they are now, so it can still be restored from",
      os.path.isfile(F + ".bak") and json.load(real_open2(F + ".bak", encoding="utf-8")) == json.load(real_open2(F, encoding="utf-8")))
check("...and the other settings stayed", L.load_settings().get("theme") == "dark" and L.load_settings().get("course") == "פיזיקה", L.load_settings())

# replacing the key: the old one does not stay in a copy either
KEY3 = "AQ.the-new-key-9876543210-abcdef"
STORED2B = L.keep_secret(KEY2)
L.save_settings(math={"key": STORED2B, "ask": True})
L.save_settings(course="כימיה")
real_probe2 = L.MathReader.probe
L.MathReader.probe = lambda self, key: "gemini-x"
try:
    r = L.math_set({"key": KEY3})
finally:
    L.MathReader.probe = real_probe2
check("a new key replaces the old one: the old key is in no file", r.get("ok") is True and not files_with(STORED2B) and not files_with("AQ.deleteme"), (r, files_with("AQ.deleteme")))
check("...and the new one is saved", L.read_secret(L.math_settings().get("key")) == KEY3)

# ------------------------------------------------------------------------------------------ 10. "report a problem" never carries a key, or the copy
with open(L.ERROR_LOG, "a", encoding="utf-8") as f:
    f.write("\n--- test ---\nrequest failed key=AQ.leaked-in-a-log-0123456789abcdef and AIzaSyA-leaked-google-key-0123456789 and dpapi:AAAABBBBCCCCDDDD== and plain:AQ.something-else-1234567890\n")
with open(F + ".bak", "a", encoding="utf-8") as f:
    f.write("\nBAK-ONLY-MARKER")
rep_text = L.diag_text()
check("the report has no Google key, no saved key, whatever the log held",
      all(x not in rep_text for x in ("AQ.leaked", "AIzaSyA-leaked", "dpapi:AAAA", "plain:AQ.something", KEY3)), rep_text[-600:])
check("...it says where it took them out", "מפתח הוסר" in rep_text)
check("...and it does not read the last good copy", "BAK-ONLY-MARKER" not in rep_text)
check("...but it still says whether there is a key, and the version", "מפתח Gemini: יש" in rep_text and L.VERSION in rep_text, rep_text[:300])

# ------------------------------------------------------------------------------------------ 11. the uninstall
import inspect  # noqa: E402
src = inspect.getsource(L.uninstall)
check("the uninstall deletes the settings and the key BEFORE it asks about the recordings (so 'no' does not leave the key)",
      "remove_settings_files()" in src and src.index("remove_settings_files()") < src.index("for local in (LOCAL_DIR, OLD_LOCAL_DIR)"), src[:200])
for x in L.settings_secret_files():
    with open(x, "a", encoding="utf-8") as f:
        f.write("x")
L.remove_settings_files()
check("...and it removes every file that can hold the key", not any(os.path.exists(x) for x in L.settings_secret_files()), [x for x in L.settings_secret_files() if os.path.exists(x)])
iss = open(os.path.join(HERE, "installer", "hevanti.iss"), encoding="utf-8").read()
check("the installer's uninstall deletes the settings and every copy (settings.json*, the models check) from %LOCALAPPDATA%\\Hevanti",
      'Name: "{localappdata}\\Hevanti\\settings.json*"' in iss and 'gemini_models.json' in iss, iss[iss.index("[UninstallDelete]"):][:400])

print()
print("all passed" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)

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

print()
print("all passed" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)

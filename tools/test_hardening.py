"""Small hardening fixes from the review (16.11.2026): a lecture text that is too long is cut where it matters and the answer says so,
a request that is too big is refused (not an empty question), Gemini models of one version are ordered by what follows it, a network
that interferes with the secure connection is named, and a wait is measured with a clock that a change of the computer's time cannot
move. Any OS, a few seconds, no network:
  python3 tools/test_hardening.py"""
import json
import os
import re
import ssl
import sys
import tempfile
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp()
os.environ.update(BZM_DATA_DIR=os.path.join(TMP, "data"), LOCALAPPDATA=os.path.join(TMP, "local"), BZM_NO_BROWSER="1")
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

L.ERROR_LOG = os.path.join(TMP, "error_log.txt")
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)[:300]), flush=True)
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300])


# ---- a context that is too long (#19)
big = "a" * (L.CONTEXT_LIMIT - 10) + "START-OF-END" + "b" * 100
txt, cut = L.fit_context("short", False)
check("a short context is not touched", txt == "short" and cut is False)
txt, cut = L.fit_context(big, False)
check("a question keeps the END of a too long context (the last minutes) and says it was cut", cut and len(txt) == L.CONTEXT_LIMIT and txt.endswith("b" * 100), (cut, len(txt)))
txt, cut = L.fit_context(big, True)
check("a whole-lecture task keeps the START", cut and len(txt) == L.CONTEXT_LIMIT and txt.startswith("a"), (cut, len(txt)))
d = {"context": big, "question": "q"}
L.tutor_body(d)
check("tutor_body marks the cut for the answer to say", d.get("_cut") is True)
src = open(os.path.join(HERE, "System", "Program", "live_transcribe.py"), encoding="utf-8").read()
check("the answer starts with a line that says the lecture was cut", "ההרצאה ארוכה מאוד, ולכן נשלח רק" in src)

srv = L.AppServer()
assert srv.start()
base = srv.url.rstrip("/")
try:
    q = urllib.request.Request(base + "/api/ask", b"x" * ((8 << 20) + 10), {"X-BZM": "1", "Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(q, timeout=20)
        code = 200
    except urllib.error.HTTPError as e:
        code = e.code
    except OSError:
        code = -1   # (the server closed the connection while we were still sending: also not an empty question)
    check("a question body over 8MB is refused, not answered as an empty question", code in (413, -1), code)
finally:
    srv.stop()

# ---- model order (#22)
names = ["models/gemini-2.5-flash-002", "models/gemini-2.5-flash-001", "models/gemini-3-flash", "models/gemini-2.5-flash-preview-09-2025", "models/gemini-flash-latest"]
got = L.gemini_candidates(names)
check("the newest version first, a release before a preview", got[0] == "gemini-flash-latest" and got[1] == "gemini-3-flash" and got.index("gemini-2.5-flash-002") < got.index("gemini-2.5-flash-preview-09-2025"), got)
check("of one version the later number comes first (002 before 001)", got.index("gemini-2.5-flash-002") < got.index("gemini-2.5-flash-001"), got)

# ---- a network in the way (#22)
e_ssl = urllib.error.URLError(ssl.SSLCertVerificationError("CERTIFICATE_VERIFY_FAILED"))
m = L._net_error(e_ssl)
check("a certificate problem is named, not 'no internet'", m is not None and "מתערבת" in str(m), m)
check("a plain connection failure stays 'no connection'", L._net_error(urllib.error.URLError(OSError("unreachable"))) is None)
check("a proxy that asks for a sign-in (407) is named", "פרוקסי" in str(L._gemini_http_error(urllib.error.HTTPError("u", 407, "Proxy Authentication Required", {}, None))))

# ---- a clock that does not jump (#16)
waits = re.findall(r"end = time\.(\w+)\(\) \+", src)
check("waits with an end time use the monotonic clock", waits and all(w == "monotonic" for w in waits), set(waits))

print("all passed" if not fails else f"{len(fails)} failed: " + ", ".join(fails))
sys.exit(1 if fails else 0)

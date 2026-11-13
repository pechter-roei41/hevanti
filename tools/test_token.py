"""The secret of a run (audit 12.11.2026, #27): the pages and what they show are given only to a browser that came with the secret.
No browser needed (http.client).   python3 tools/test_token.py"""
import http.client
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp()
os.environ.update(BZM_DATA_DIR=os.path.join(TMP, "data"), LOCALAPPDATA=os.path.join(TMP, "local"), BZM_NO_BROWSER="1", PYTHONUTF8="1")
os.makedirs(os.path.join(TMP, "data", "הקורסים שלי", "פיזיקה 1", "הרצאה"))
os.makedirs(os.environ["LOCALAPPDATA"])
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)[:300]))
    if not ok:
        fails.append(name)


srv2 = L.AppServer()
assert srv2.start()
srv = L.AppServer()   # (started second: the file of the running tool is its)
assert srv.start()
port = srv.httpd.server_address[1]
L.REQUIRE_TOKEN[port] = True
tok = srv.token
check("the secret is long and different in each server", len(tok) >= 24 and srv2.token != tok)
srv2.stop()


def get(path, cookie=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    h = {"Host": f"127.0.0.1:{port}"}
    if cookie is not None:
        h["Cookie"] = "bzm=" + cookie
    h.update(headers or {})
    c.request("GET", path, headers=h)
    r = c.getresponse()
    body = r.read()
    out = (r.status, dict(r.getheaders()), body)
    c.close()
    return out


for path in ("/", "/mini", "/quick", "/player"):
    st, hd, body = get(path)
    check(f"a page without the secret: {path} is refused", st == 403 and "הבנתי נפתחת רק מהקיצור" in body.decode("utf-8"), (st, body[:80]))
for path in ("/api/app", "/api/library", "/api/live", "/api/diag", "/api/transcript?f=x", "/shot", "/shots/a.jpg", "/media"):
    st, hd, body = get(path)
    check(f"what the pages show, without the secret: {path} is refused", st == 403, st)
st, hd, body = get("/api/app", cookie="not-the-secret")
check("a wrong secret in the cookie is refused", st == 403, st)
st, hd, body = get(f"/?bzm=wrong")
check("a wrong secret in the address is refused", st == 403, st)
st, hd, body = get(f"/mini?bzm={tok}")
cookie = hd.get("Set-Cookie", "")
check("the right secret in the address: the cookie is set (HttpOnly, only for us) and the address goes on without it",
      st == 302 and hd.get("Location") == "/mini" and f"bzm={tok}" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie, (st, hd))
st, hd, body = get(f"/?bzm={tok}&x=1")
check("...other parts of the address are kept", st == 302 and hd.get("Location") == "/?x=1", hd.get("Location"))
for path in ("/", "/mini", "/quick", "/api/app", "/api/library", "/api/diag"):
    st, hd, body = get(path, cookie=tok)
    check(f"with the cookie: {path} is served", st == 200 and len(body) > 20, st)
for path in ("/ask.js", "/katex.js"):
    st, hd, body = get(path)
    check(f"what holds nothing of the student (no secret needed): {path}", st == 200, st)
st, hd, body = get("/api/app", cookie=tok, headers={"Host": "evil.example"})
check("another host name is refused even with the secret (DNS rebinding)", st == 403, st)
st, hd, body = get("/api/app", cookie=tok, headers={"Sec-Fetch-Site": "cross-site"})
check("another site is refused even with the secret", st == 403, st)

# the commands (POST) need the cookie too
def post(path, body, cookie=None, bzm=True):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    h = {"Host": f"127.0.0.1:{port}", "Content-Type": "application/json"}
    if bzm:
        h["X-BZM"] = "1"
    if cookie is not None:
        h["Cookie"] = "bzm=" + cookie
    c.request("POST", path, body=json.dumps(body), headers=h)
    r = c.getresponse()
    out = (r.status, r.read())
    c.close()
    return out


check("a command without the cookie is refused, even with X-BZM", post("/api/cmd", {"action": "nothing"})[0] == 403)
check("a command with a wrong cookie is refused", post("/api/cmd", {"action": "nothing"}, cookie="x")[0] == 403)
check("a command with the cookie but without X-BZM is refused", post("/api/cmd", {"action": "nothing"}, cookie=tok, bzm=False)[0] == 403)
check("a command with the cookie and X-BZM goes through", post("/api/cmd", {"action": "nothing"}, cookie=tok)[0] == 200)
check("where you are in a recording needs the cookie too", post("/api/place", {"pos": 1}, bzm=False)[0] == 403 and post("/api/place", {"pos": 1}, cookie=tok, bzm=False)[0] in (200, 204))

# the address a window is opened with
link = L.make_link("http://127.0.0.1:8765/", "TOK")
check("the address of a window: the secret goes before the #fragment",
      link("") == "http://127.0.0.1:8765/?bzm=TOK" and link("mini") == "http://127.0.0.1:8765/mini?bzm=TOK"
      and link("#t=%D7%90") == "http://127.0.0.1:8765/?bzm=TOK#t=%D7%90" and link("#rec") == "http://127.0.0.1:8765/?bzm=TOK#rec")
check("no secret (a test server): the plain address", L.make_link("http://x/", "")("mini") == "http://x/mini")

# a second start finds the running one: from app.json, with the secret
app_json = L.APP_FILE
with open(app_json, encoding="utf-8") as f:
    info = json.load(f)
check("the running tool's file holds its address and secret (in the student's own folder)", info.get("token") == tok and info.get("url") == srv.url, info)
found = L.running_url()
check("a second start finds the running tool and gets the secret", found == (srv.url, tok), found)
info["token"] = "wrong"
with open(app_json, "w", encoding="utf-8") as f:
    json.dump(info, f)
orig_sleep = L.time.sleep
L.time.sleep = lambda s: None
check("a wrong secret in that file: the tool is not taken for the running one", L.running_url() is None)
L.time.sleep = orig_sleep

srv.stop()
print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.exit(1 if fails else 0)

"""The quiet motion of version 2.22, in a real browser: the selected shape of the top tabs and of a choice group slides to the new place
(glideGroup), a mark made now is drawn like a highlighter (sweepLine), and the saved card of the floating window draws its check.
Each one must (a) end in the finished look, (b) stop with the system setting and with "no animations and motion", (c) never break the
page when it cannot be measured. Needs Playwright and Edge or Chrome; skips when missing.
  python3 tools/test_motion.py"""
import json
import os
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP playwright is not installed")
    sys.exit(0)
TMP = tempfile.mkdtemp()
os.environ["BZM_DATA_DIR"] = os.path.join(TMP, "data")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "local")
os.environ["BZM_NO_BROWSER"] = "1"
os.makedirs(os.environ["BZM_DATA_DIR"])
os.makedirs(os.environ["LOCALAPPDATA"])
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)))
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


srv = L.AppServer()
assert srv.start()
url = srv.url.rstrip("/")


def cmd(body):
    req = urllib.request.Request(url + "/api/cmd", data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "X-BZM": "1"})
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def launch(p):
    for kw in ({"channel": "msedge"}, {"channel": "chrome"}, {}):
        try:
            return p.chromium.launch(headless=True, **kw)
        except Exception:
            continue
    return None


# where the selected shape is, and where the glide is (both relative to the group; the glide may still be moving)
GEOM = """(sel) => { const box = document.querySelector(sel), g = box.querySelector(':scope > .glide'),
    cur = box.querySelector('[aria-current="page"],[aria-selected="true"],[aria-pressed="true"]');
  if (!g || !cur) return null;
  const gt = getComputedStyle(g).transform, m = gt && gt !== 'none' ? new DOMMatrix(gt) : null;
  return {on: box.classList.contains('glide-on'), x: m ? m.m41 : 0, y: m ? m.m42 : 0, w: parseFloat(getComputedStyle(g).width), h: parseFloat(getComputedStyle(g).height),
          cx: cur.offsetLeft, cy: cur.offsetTop, cw: cur.offsetWidth, ch: cur.offsetHeight, curBg: getComputedStyle(cur).backgroundColor,
          gBg: getComputedStyle(g).backgroundColor, tr: getComputedStyle(g).transitionDuration}; }"""


def at(gm):
    return gm and all(abs(gm[a] - gm[b]) < 1.5 for a, b in (("x", "cx"), ("y", "cy"), ("w", "cw"), ("h", "ch")))


with sync_playwright() as p:
    b = launch(p)
    if b is None:
        print("SKIP no browser for Playwright")
        sys.exit(0)

    def page(motion="no-preference", scheme="light", path="/", w=1100):
        pg = b.new_context(viewport={"width": w, "height": 900}, locale="he-IL", reduced_motion=motion, color_scheme=scheme).new_page()
        pg.errs = []
        pg.on("pageerror", lambda e: pg.errs.append(str(e)))
        pg.goto(url + path)
        pg.wait_for_timeout(1200)
        pg.evaluate("document.querySelectorAll('.modal').forEach(m => { if (m.id !== 'consent') m.hidden = true })")
        return pg

    # ---- the top tabs ----
    for scheme in ("light", "dark"):
        pg = page(scheme=scheme)
        g = pg.evaluate(GEOM, ".nav")
        check(f"top tabs, {scheme}: the glide sits under the current tab and the tab leaves its own background to it", g and g["on"] and at(g) and g["curBg"] == "rgba(0, 0, 0, 0)", g)
        check(f"top tabs, {scheme}: the glide has the sunk-paper look of the selected tab ('where am I', never green)", g and g["gBg"] != "rgba(0, 0, 0, 0)")
        pg.click('[data-nav="courses"]')
        pg.wait_for_timeout(120)
        mid = pg.evaluate(GEOM, ".nav")
        pg.wait_for_timeout(500)
        end = pg.evaluate(GEOM, ".nav")
        check(f"top tabs, {scheme}: after the click it slides (still on its way a moment later) and ends exactly under the new tab",
              mid and end and not at(mid) and at(end) and mid["tr"] != "0s", (mid, end))
        for tab in ("how", "settings", "home"):
            pg.click(f'[data-nav="{tab}"]')
            pg.wait_for_timeout(450)
            check(f"top tabs, {scheme}: '{tab}' ends under its tab", at(pg.evaluate(GEOM, ".nav")), pg.evaluate(GEOM, ".nav"))
        check(f"top tabs, {scheme}: no script errors", pg.errs == [], pg.errs)
        pg.context.close()

    # ---- motion off: the system setting, and the app's own switch ----
    pg = page(motion="reduce")
    pg.click('[data-nav="courses"]')
    pg.wait_for_timeout(60)
    g = pg.evaluate(GEOM, ".nav")
    check("system motion off: the glide jumps (no transition) and is already under the new tab", at(g) and g["tr"] == "0s", g)
    pg.context.close()
    pg = page()
    pg.evaluate("document.documentElement.classList.add('a-still')")
    pg.click('[data-nav="how"]')
    pg.wait_for_timeout(60)
    g = pg.evaluate(GEOM, ".nav")
    check("'no animations and motion' in the app: the glide jumps and is already under the new tab", at(g) and g["tr"] == "0s", g)
    pg.context.close()

    # ---- a narrow window: the tabs wrap onto their own row, the glide still follows ----
    pg = page(w=360)
    pg.click('[data-nav="settings"]')
    pg.wait_for_timeout(450)
    check("360px: the tabs wrap and the glide ends under the current tab", at(pg.evaluate(GEOM, ".nav")), pg.evaluate(GEOM, ".nav"))
    check("360px: nothing scrolls sideways", pg.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
    pg.context.close()

    # ---- a choice group: the language of a recording (home), and a group that is hidden ----
    pg = page()
    pg.click("#recTile")   # (the language of a recording is chosen in the panel this tile opens)
    pg.wait_for_timeout(500)
    LANG = ".seg:has([data-lang])"
    g = pg.evaluate(GEOM, LANG)
    check("choice group: the glide sits under the chosen button, soft green with the green edge", g and g["on"] and at(g) and g["curBg"] == "rgba(0, 0, 0, 0)", g)
    pg.evaluate("document.querySelector('.seg [data-lang=en]').click()")
    pg.wait_for_timeout(450)
    check("choice group: choosing the other one ends the glide under it, and only one button is chosen",
          at(pg.evaluate(GEOM, LANG)) and pg.evaluate("document.querySelectorAll('.seg [data-lang][aria-pressed=true]').length") == 1)
    hidden = pg.evaluate("""() => { const z = document.querySelector('#a11yZoom'); return {glide: !!z.querySelector(':scope > .glide'), on: z.classList.contains('glide-on'),
        bg: getComputedStyle(z.querySelector('[aria-pressed=true]') || z.querySelector('button')).backgroundColor, w: z.offsetWidth}; }""")
    check("a group that is not on screen cannot be measured: it does nothing, the button keeps its own soft green", hidden["w"] == 0 and not hidden["on"] and hidden["bg"] != "rgba(0, 0, 0, 0)", hidden)
    pg.evaluate("document.querySelector('[data-nav=settings]').click()")
    pg.wait_for_timeout(300)
    pg.evaluate("document.querySelectorAll('#setTabs > *').forEach(x => { if (/נגישות/.test(x.textContent)) x.click() })")
    pg.wait_for_timeout(600)
    g = pg.evaluate(GEOM, "#a11yZoom")
    check("...and when it is shown (settings, accessibility) the glide appears under the chosen button", g and g["on"] and at(g), g)
    pg.evaluate("document.querySelector('#a11yZoom [data-v=\"1.25\"]') && document.querySelector('#a11yZoom [data-v=\"1.25\"]').click()")
    pg.wait_for_timeout(500)
    g = pg.evaluate(GEOM, "#a11yZoom")
    check("...and it follows a choice made there (zoom changes the sizes: the glide is measured again)", g and at(g), g)
    check("choice group: no script errors", pg.errs == [], pg.errs)
    pg.context.close()

    # ---- a mark made now ----
    SWEEP = """(fresh) => {
      const ol = document.createElement('ol'); ol.className = 'lines'; ol.id = 'probe'; document.body.appendChild(ol);
      appendLine(ol, {t: 1, c: '00:01', x: 'שורה לפני הסימון'}, fresh);
      appendLine(ol, {t: 2, c: '00:02', x: 'שורה אחרת'}, fresh);
      appendLine(ol, {t: 3, c: '00:03', x: '[סימון: חשוב]'}, fresh);
      const lis = [...ol.children];
      return lis.map(l => ({cls: l.className, anim: getComputedStyle(l).animationName, star: !!l.querySelector('.mstar'),
                            starAnim: l.querySelector('.mstar') ? getComputedStyle(l.querySelector('.mstar')).animationName : ''})); }"""
    BAND = """() => { const probe = document.createElement('i'); probe.style.background = 'var(--mark-line)'; document.body.appendChild(probe);
      const band = getComputedStyle(probe).backgroundColor; probe.remove();
      return [...document.querySelectorAll('#probe li')].map(l => { const s = getComputedStyle(l);
        return {band: s.backgroundColor === band || (s.backgroundImage.indexOf('linear-gradient') >= 0 && s.backgroundSize.split(' ')[0] === '100%' && s.backgroundColor === 'rgba(0, 0, 0, 0)'), cls: l.className}; }); }"""
    for scheme in ("light", "dark"):
        pg = page(scheme=scheme)
        r = pg.evaluate(SWEEP, True)
        check(f"a mark made now, {scheme}: the line before it and the mark row are drawn (the band sweeps), the ★ pops",
              "sweep" in r[1]["cls"] and "marked" in r[1]["cls"] and "sweep" in r[2]["cls"] and r[1]["anim"] == "hv-sweep" and r[1]["starAnim"] == "hv-pop", r)
        check(f"a mark made now, {scheme}: the line before the one marked is left alone", r[0]["cls"] == "" and r[0]["anim"] == "none", r)
        pg.wait_for_timeout(1500)
        done = pg.evaluate(BAND)
        check(f"a mark made now, {scheme}: when it is over, the class is gone and both lines are the plain highlighter band",
              all("sweep" not in x["cls"] for x in done) and done[1]["band"] and done[2]["band"] and not done[0]["band"], done)
        check(f"a mark made now, {scheme}: no script errors", pg.errs == [], pg.errs)
        pg.context.close()
    pg = page()
    r = pg.evaluate(SWEEP, False)
    check("a lecture that is opened (not made now): the marks are the finished band, nothing is drawn", all("sweep" not in x["cls"] and x["anim"] == "none" for x in r) and "marked" in r[1]["cls"], r)
    pg.context.close()
    for why, setup, motion in (("system motion off", "", "reduce"), ("app motion off", "document.documentElement.classList.add('a-still')", "no-preference")):
        pg = page(motion=motion)
        pg.evaluate(setup or "0")
        r = pg.evaluate(SWEEP, True)
        band = pg.evaluate(BAND)
        check(f"a mark made now, {why}: no animation, and the band is already the whole line", r[1]["anim"] == "none" and r[1]["starAnim"] == "none" and band[1]["band"] and band[2]["band"], (r, band))
        pg.context.close()

    # ---- the real way a mark arrives in a lecture that is running: pollLive, with a made-up /api/live ----
    batches = [
        {"items": [{"t": 1, "c": "00:01", "x": "שורה ראשונה"}, {"t": 2, "c": "00:02", "x": "שורה שנייה"}, {"t": 3, "c": "00:03", "x": "[סימון: חשוב]"}], "total": 3},
        {"items": [{"t": 4, "c": "00:04", "x": "שורה שלישית"}, {"t": 5, "c": "00:05", "x": "המרצה אומר משהו חשוב"}, {"t": 6, "c": "00:06", "x": "[סימון: חשוב]"}], "total": 6},
    ]

    def live_route(route):
        since = int(route.request.url.split("since=")[-1].split("&")[0] or 0)
        d = dict(batches[0] if since == 0 else batches[1] if since == 3 else {"items": [], "total": 6})
        d.update({"pending": 0, "draft": "", "ended": False, "info": {"started_ts": 0}, "lag": 0})
        route.fulfill(status=200, content_type="application/json", body=json.dumps(d))

    pg = b.new_context(viewport={"width": 1100, "height": 900}, locale="he-IL").new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.route("**/api/live*", live_route)
    pg.goto(url + "/#live")
    pg.wait_for_timeout(700)
    pg.evaluate("document.querySelectorAll('.modal').forEach(m => { if (m.id !== 'consent') m.hidden = true })")
    first = pg.evaluate("[...document.querySelectorAll('#liveLines li')].map(l => l.className)")
    check("a lecture that is running, first look: what was already said (with a mark) is the finished band, nothing is drawn",
          len(first) == 3 and all("sweep" not in c for c in first) and "mark" in first[2] and "marked" in first[1], first)
    seen = []
    for _ in range(14):   # (a poll is every second: catch the moment the new mark comes in)
        pg.wait_for_timeout(120)
        seen.append(pg.evaluate("[...document.querySelectorAll('#liveLines li')].map(l => l.className)"))
        if any("sweep" in c for c in seen[-1]):
            break
    now = seen[-1]
    check("...a mark that comes in while it runs: the line before it and the mark row are drawn", len(now) == 6 and "sweep" in now[4] and "marked" in now[4] and "sweep" in now[5], now)
    check("...and the old mark is not drawn again", "sweep" not in now[1] and "sweep" not in now[2], now)
    pg.wait_for_timeout(1500)
    done = pg.evaluate("[...document.querySelectorAll('#liveLines li')].map(l => l.className)")
    check("...and later the class is gone and both marks are the same finished band", all("sweep" not in c for c in done) and "marked" in done[4] and "marked" in done[1], done)
    check("a lecture that is running: no script errors", pg.errs == [], pg.errs)
    pg.context.close()

    # ---- the small window: the saved card and the mark ----
    st = L.load_settings().get("a11y_still")
    app = json.loads(urllib.request.urlopen(url + "/api/app", timeout=10).read())
    check("/api/app tells the small window whether motion is off", app.get("still") is bool(st) or app.get("still") == bool(st), app.get("still"))
    SAVED = """() => { sawLive = true; savedGone = ''; drawSaved({done: true, saved: {f: 'c/t', course: 'קורס', minutes: 12, slides: 3}});
      const t = document.querySelector('#saved .tick'), path = t.querySelector('svg path');
      return {shown: !document.querySelector('#saved').hidden, svg: !!path, dash: path ? getComputedStyle(path).strokeDasharray : '', anim: getComputedStyle(t).animationName,
              drawAnim: path ? getComputedStyle(path).animationName : '', stroke: path ? getComputedStyle(path).stroke : '', ink: getComputedStyle(t).color,
              text: document.querySelector('#saved').textContent.indexOf('ההרצאה נשמרה בהצלחה') >= 0}; }"""
    for scheme in ("light", "dark"):
        pg = page(scheme=scheme, path="/mini")
        r = pg.evaluate(SAVED)
        check(f"small window, {scheme}: the saved card has a check that draws itself in the green chip", r["shown"] and r["svg"] and r["anim"] == "hv-pop" and r["drawAnim"] == "hv-draw" and r["stroke"] == r["ink"] and r["text"], r)
        pg.evaluate("toast(MARKED)")
        sa = pg.evaluate("getComputedStyle(document.querySelector('#toast .star')).animationName")
        check(f"small window, {scheme}: the ★ of the mark message pops once", sa == "hv-pop", sa)
        check(f"small window, {scheme}: no script errors", pg.errs == [], pg.errs)
        pg.context.close()
    pg = page(motion="reduce", path="/mini")
    r = pg.evaluate(SAVED)
    check("small window, system motion off: the check is just there (finished, not hidden mid-draw)", r["shown"] and r["svg"] and r["anim"] == "none" and r["drawAnim"] == "none", r)
    pg.context.close()
    # the app's "no animations and motion" reaches the small window through /api/app
    cmd({"action": "a11y_still", "on": True})
    pg = page(path="/mini")
    pg.wait_for_timeout(2500)
    check("small window: 'no animations and motion' chosen in the app is applied there", pg.evaluate("document.documentElement.classList.contains('a-still')"))
    r = pg.evaluate(SAVED)
    check("...and then the check is just there", r["shown"] and r["svg"] and r["anim"] == "none" and r["drawAnim"] == "none", r)
    pg.context.close()
    cmd({"action": "a11y_still", "on": False})
    pg = page(path="/mini")
    pg.wait_for_timeout(2500)
    check("small window: with the switch off again, the class is gone", not pg.evaluate("document.documentElement.classList.contains('a-still')"))
    pg.context.close()
    b.close()

srv.stop() if hasattr(srv, "stop") else None
print("")
print("all passed" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)

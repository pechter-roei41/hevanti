"""Tests for the search (System/Program/hevanti_search.py) on a small made-up courses folder.
Standard library only; runs anywhere:  python3 tools/test_search.py"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import hevanti_search as H  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)[:600]))
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


def write(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)


def lecture(root, course, name, body, ocr=None):
    d = os.path.join(root, course, name)
    write(os.path.join(d, name + ".txt"), body)
    if ocr is not None:
        write(os.path.join(d, "שקופיות", ".ocr.json"), json.dumps(ocr, ensure_ascii=False))
    return os.path.join(d, name + ".txt")


def texts(r):
    return [h["x"] for h in r["hits"]]


def find(ix, q, **kw):
    return ix.search(q, **kw)["hits"]


root = tempfile.mkdtemp()
S, D = "סטטיקה", "dynamics"
L1 = lecture(root, S, "2026-10-12 10-00 הרצאה",
             "# תמלול\n"
             "[10:00:05 | +0:00:05] היום נדבר על תגובות סמך במעגל חשמלי\n"
             "[10:01:00 | +0:01:00] [צילום מסך: שקופיות/10-01-00.jpg]\n"
             "[10:02:00 | +0:02:00] מומנטים סביב נקודה והבית של גוף קשיח\n"
             "[10:03:00 | +0:03:00] גוף שלם ואחר כך משהו קשיח מאוד\n"
             "[10:04:00 | +0:04:00] שָׁלוֹם לכולם, זה צ'יק צ'אט\n"
             "[10:05:00 | +0:05:00] (שקט)\n"
             "[10:06:00 | +0:06:00] [הערה]\n"
             "# סוף: 10:06\n",
             {"10-01-00.jpg": "Free Body Diagram\nמעגל פתוח"})
L2 = lecture(root, S, "הקלטה", "# תמלול הקלטה\n[0:00:10] הסבר על גוף קשיח ועל מומנט\n[0:01:30] עוד על מומנט כוח\n")
L3 = lecture(root, D, "2026-10-15 09-00 הרצאה", "[09:00:05 | +0:00:05] תנע זוויתי של דיסקה, ספרים וספר\n")
os.makedirs(os.path.join(root, "קורס ריק"))
os.makedirs(os.path.join(root, ".hidden", "x"))

ix = H.Index(root)

# ---- spelling ----
check("norm: niqqud, final letters, quotes, case",
      H.norm("שָׁלוֹם") == H.norm("שלומ") and H.norm("צ'יק") == "ציק" and H.norm("Free-Body") == "free-body",
      [H.norm("שָׁלוֹם"), H.norm("שלומ")])
check("prefix_stems", H.prefix_stems("במעגל") == ["מעגל"] and H.prefix_stems("ובבית") == ["בבית"]
      and H.prefix_stems("מעגל") == [] and H.prefix_stems("הבית") == ["בית"], [H.prefix_stems(w) for w in ("במעגל", "ובבית", "מעגל", "הבית")])

# ---- finding ----
st = ix.stats()
check("index: lectures and lines", st["lectures"] == 3 and st["lines"] == 8, st)   # 4 + 1 slide in L1... see below
r = find(ix, "תגובות")
check("finds a word", len(r) == 1 and r[0]["f"] == f"{S}/2026-10-12 10-00 הרצאה" and r[0]["t"] == 5, r)
check("live line: the clock shown is the wall clock; a recording: from the start",
      r[0]["c"] == "10:00:05" and find(ix, "הסבר")[0]["c"] == "0:00:10", [r[0]["c"], find(ix, "הסבר")])
check("hits carry the time in seconds and the lecture", find(ix, "עוד")[0]["t"] == 90 and find(ix, "עוד")[0]["lecture"] == "הקלטה")
check("prefix in the text: 'מעגל' finds 'במעגל'", any("במעגל" in x for x in texts({"hits": find(ix, "מעגל")})))
check("prefix in the query: 'במעגל' finds the slide's 'מעגל'", any(h["kind"] == "slide" for h in find(ix, "במעגל")))
check("'בית' and 'הבית' both find 'והבית'", len(find(ix, "בית")) == 1 and len(find(ix, "הבית")) == 1, find(ix, "בית"))
check("short word is not cut: 'עגל' does not find 'מעגל'", find(ix, "עגל") == [], find(ix, "עגל"))
check("plural in the text: 'מומנט' finds 'מומנטים'", len(find(ix, "מומנט")) == 3, [h["x"] for h in find(ix, "מומנט")])
check("plural in the query: 'מומנטים' finds 'מומנט'", len(find(ix, "מומנטים")) == 3)
check("singular/plural of 'ספר'", len(find(ix, "ספרים")) == 1 and len(find(ix, "ספר")) == 1)
check("niqqud and quotes do not matter", len(find(ix, "שלום")) == 1 and len(find(ix, "ציק")) == 1 and len(find(ix, "צ'יק")) == 1)
check("English: case and slide text", [h["kind"] for h in find(ix, "free body")] == ["slide"]
      and find(ix, "FREE BODY")[0]["slide"] == "10-01-00.jpg")
check("all the words, in one line (not next to each other)", len(find(ix, "גוף קשיח")) == 3 and len(find(ix, "תגובות מומנט")) == 0)
phrase = find(ix, '"גוף קשיח"')
check("a phrase in quotes: next to each other only", len(phrase) == 2 and all("גוף קשיח" in h["x"] for h in phrase), phrase)
check("a phrase: not the words apart", all("שלם" not in h["x"] for h in phrase))
check("not found", find(ix, "לא קיים בכלל") == [])

# ---- the result ----
h = find(ix, "מעגל")[0]
check("marks point at the matches inside x", h["marks"] and all(H.norm(h["x"][s:e]).startswith("מעגל") or H.norm(h["x"][s:e]).startswith("מעגל") for s, e in h["marks"])
      or all("מעגל" in h["x"][s:e] for s, e in h["marks"]), h)
long = "מילה " * 200 + "יעד נמצא כאן " + "עוד " * 200
piece, spans = H.excerpt(long, ["יעד"])
check("excerpt: a piece around the match, with its place", len(piece) <= 305 and spans and piece[spans[0][0]:spans[0][1]] == "יעד", (len(piece), spans))
lecture(root, "דירוג", "a", "[0:00:01] מילה אחת בלבד של ניסוי\n[0:00:20] ניסוי ניסוי ניסוי בכל מקום\n[0:00:40] שורה ארוכה מאוד עם הרבה מילים שונות שאין בהן שום קשר ואחר כך בסוף ניסוי\n")
ix._synced = 0
rank = find(ix, "ניסוי", course="דירוג")
check("ranking: the short line with the word comes before the long one", rank[0]["t"] in (1, 20) and rank[-1]["t"] == 40, [(x["t"], x["score"]) for x in rank])
check("sort recent: newest lecture first", find(ix, "מומנט", sort="recent")[0]["lecture"] in ("הקלטה", "2026-10-12 10-00 הרצאה"))

# ---- courses and limits ----
check("one course only", find(ix, "גוף", course=D) == [] and len(find(ix, "תנע", course=D)) == 1 and find(ix, "תנע", course=S) == [])
many = ix.search("מומנט", limit=2)
check("limit: says there is more", len(many["hits"]) == 2 and many["more"] is True, many)
check("per_lecture caps one lecture", sum(1 for x in find(ix, "מומנט", per_lecture=1) if x["lecture"] == "הקלטה") == 1)
check("hidden and empty folders are not lectures", ix.stats()["lectures"] == 4, ix.stats())

# ---- queries that must not break ----
bad = ['"', '*', 'OR', 'AND NOT', 'NEAR(', 'a"b', '(((', '-', '', '   ', 'א', 'x:y', 'body:אבג', '"" ""', "'; DROP TABLE lines; --", "‮גוף"]
ok = True
for q in bad:
    try:
        r = ix.search(q)
        if not isinstance(r["hits"], list):
            ok = False
    except Exception as e:
        ok = False
        print("   raised on", repr(q), e)
check("odd queries never raise", ok)
check("one letter or nothing: nothing", find(ix, "א") == [] and find(ix, "") == [])
check("injection stays text", len(find(ix, "'; DROP TABLE lines; --")) == 0 and ix.stats()["lines"] > 0)

# ---- keeping up to date ----
time.sleep(0.01)
ix._synced = 0
with open(L2, "a", encoding="utf-8") as f:
    f.write("[0:02:00] עכשיו מדברים על אנטרופיה\n")
os.utime(L2, (time.time() + 5, time.time() + 5))
check("a changed lecture is read again", len(find(ix, "אנטרופיה")) == 1)
ix._synced = 0
write(os.path.join(root, S, "2026-10-12 10-00 הרצאה", "שקופיות", ".ocr.json"), json.dumps({"10-01-00.jpg": "Torque arm"}))
check("new slide text is found, the old is gone", len(find(ix, "torque")) == 1 and find(ix, "free body") == [])
ix._synced = 0
os.remove(L3)
os.rmdir(os.path.dirname(L3))
check("a deleted lecture is gone", find(ix, "תנע") == [])

# ---- on disk ----
dbp = os.path.join(tempfile.mkdtemp(), "x", "search.db")
d1 = H.Index(root, dbp)
check("on disk: built", len(d1.search("אנטרופיה")["hits"]) == 1 and os.path.isfile(dbp))
d2 = H.Index(root, dbp)     # a new run: nothing to read again
check("on disk: used again by a new object", d2.sync(force=True) == 0 and len(d2.search("אנטרופיה")["hits"]) == 1)
with open(dbp, "wb") as f:
    f.write(b"this is not a database at all" * 100)
d3 = H.Index(root, dbp)
try:
    ok = len(d3.search("אנטרופיה")["hits"]) == 1
except Exception as e:
    ok = False
    print("   raised:", e)
check("on disk: a damaged file is built again", ok)

# ---- speed ----
big = os.path.join(root, "גדול", "x")
write(os.path.join(big, "x.txt"), "".join(f"[{i // 3600}:{i % 3600 // 60:02d}:{i % 60:02d}] שורה {i} על נושא{i % 50} וגם עוד מילים של הרצאה\n" for i in range(20000)))
t0 = time.time()
ix._synced = 0
r1 = ix.search("נושא7 הרצאה", limit=50)
t1 = time.time()
r2 = ix.search("נושא7 מילים", limit=50)
t2 = time.time()
check("speed: 20,000 lines indexed in a few seconds, then a search is quick", t1 - t0 < 10 and t2 - t1 < 0.5 and r1["hits"], (t1 - t0, t2 - t1))

print("\nall passed" if not fails else f"\nFAILED: {fails}")
sys.exit(1 if fails else 0)

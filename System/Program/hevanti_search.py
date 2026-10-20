# -*- coding: utf-8 -*-
"""Hevanti (הבנתי) search - (c) 2026 Roei Pechter. MIT License, see LICENSE.txt

Full-text search over everything Hevanti saved: what was said in every lecture and the text read from the slides.
SQLite FTS5 (built into Python) - standard library only, nothing to install.

What it does that a plain "does the line contain the word" scan does not:
  * ranking: the lines that fit best come first (bm25), not just the newest lecture;
  * Hebrew: niqqud, final letters (ם/מ), quotes inside words (צ'יק) and ־ do not matter; "הבית" finds "בית" and
    "בבית" finds "בית" (and the other way round); "מומנטים" finds "מומנט" and "מומנט" finds "מומנטים";
  * "a phrase in quotes" has to appear as written; several words have to appear in the same line;
  * a short piece of the line around the match, with the places to mark.

Two ways to use it: a file on disk that is kept up to date (the app: Index(root, path)), or in memory
(the AI connector, which must not write anything: Index(root, ":memory:")). It only READS the lectures folder.
The index is a copy: if it is deleted or damaged it is simply built again."""
import json
import os
import re
import sqlite3
import threading
import time

SLIDES = "שקופיות"
OCR_NAME = ".ocr.json"
SCHEMA = 2                      # a different number in an old file -> built again
LIVE_LINE = re.compile(r"\[(\d\d:\d\d:\d\d) \| \+(\d+):(\d\d):(\d\d)\] (.*)$")
REC_LINE = re.compile(r"\[(\d+):(\d\d):(\d\d)\] (.*)$")
SHOT = re.compile(r"\[צילום מסך: (.+)\]$")
OCR_MAX = 4000

_MARKS = re.compile("[\u0591-\u05bd\u05bf-\u05c7\u200e\u200f\u202a-\u202e\u2066-\u2069]")  # niqqud, direction marks
_DROP = str.maketrans("", "", "'\"`\u2019\u2018\u05f3\u05f4")       # quotes inside words: צ'יק, ת"א
_FINAL = str.maketrans("ךםןףץ", "כמנפצ")                            # final letters -> regular
_TOKEN = re.compile(r"\w+")
_HEB = re.compile(r"[\u05d0-\u05ea]+$")


def norm(text):
    """One spelling for comparing: no niqqud, no quotes inside words, lower case, regular letters."""
    t = str(text or "").replace("\u05be", " ")                         # maqaf joins words
    return _MARKS.sub("", t).translate(_DROP).lower().translate(_FINAL)


def tokens(text):
    return _TOKEN.findall(norm(text))


def _strip_ok(w):
    """The Hebrew one-letter prefixes (the, and, in, to, from, that...). ה/ו from 4 letters, the others from 5, so
    that a short word that merely starts with such a letter (מעגל) is not cut."""
    if not _HEB.match(w):
        return False
    return (w[0] in "הו" and len(w) >= 4) or (w[0] in "בכלמש" and len(w) >= 5)


def prefix_stems(w):
    """'במעגל' -> ['מעגל'], 'ובבית' -> ['בבית', 'בית']: the word without its prefix letters (at most two)."""
    out, cur = [], w
    for _ in range(2):
        if not _strip_ok(cur):
            break
        cur = cur[1:]
        out.append(cur)
    return out


def _forms(w):
    """The spellings a typed word is looked for under: itself, without a plural ending, without a prefix letter.
    (w is already normal: the final ם is מ.)"""
    exact = [w]
    for suf in ("ימ", "ות"):   # ים, after the final letter became regular
        if w.endswith(suf) and len(w) - 2 >= 3 and _HEB.match(w):
            exact.append(w[:-2])
    return exact, prefix_stems(w)


def _q(tok):
    return '"' + tok + '"'


def build_query(text):
    """What the person typed -> (an FTS5 query, the spellings to mark). (None, []) when there is nothing to look for."""
    clauses, marks = [], []
    for phrase, word in re.findall(r'"([^"]+)"|(\S+)', str(text or "")):
        toks = [t for t in tokens(phrase or word) if len(t) >= 2]
        if not toks:
            continue
        if len(toks) > 1:               # "a b c" or yt-dlp: next to each other
            clauses.append("body:" + _q(" ".join(toks)) + " *")
            marks.append(toks[-1])
            marks.extend(toks[:-1])
            continue
        exact, stripped = _forms(toks[0])
        alts = []
        for f in exact:
            alts += ["body:" + _q(f) + " *", "stems:" + _q(f) + " *"]
        for s in stripped:
            alts.append("body:" + _q(s) + " *")
        clauses.append("(" + " OR ".join(alts) + ")")
        marks.extend(exact + stripped)
    if not clauses:
        return None, []
    return " AND ".join(clauses), list(dict.fromkeys(marks))


def _body(text):
    toks = tokens(text)
    return " ".join(toks), " ".join(s for t in toks for s in prefix_stems(t))


def _matches(tok, marks):
    t = norm(tok)
    if any(t.startswith(m) for m in marks):
        return True
    return any(s.startswith(m) for s in prefix_stems(t) for m in marks)


def excerpt(text, marks, width=300):
    """(a piece of the text around the first match, [[start, end], ...] of the matches in it)."""
    text = " ".join(_MARKS.sub("", str(text or "")).split())
    spans = [(m.start(), m.end()) for m in _TOKEN.finditer(text) if _matches(m.group(0), marks)]
    if not spans:
        return text[:width], []
    start = max(0, spans[0][0] - width // 3)
    if start:
        cut = text.find(" ", start)         # do not start in the middle of a word
        start = cut + 1 if 0 <= cut < spans[0][0] else start
    end = min(len(text), start + width)
    piece = text[start:end]
    lead = "…" if start else ""
    piece = lead + piece + ("…" if end < len(text) else "")
    shift = start - len(lead)
    return piece, [[s - shift, e - shift] for s, e in spans if s >= start and e <= end][:8]


def hms(t):
    t = int(max(0, t))
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def parse_lecture(path):
    """A lecture's transcript -> [(seconds from the start, text, None, clock) | (seconds, None, 'file.jpg', clock)],
    by time. The clock is the time to show: the wall clock of a live lecture, else h:mm:ss from the start."""
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line.startswith("#"):
                    continue
                m = LIVE_LINE.match(line)
                if m:
                    t, x, clock = int(m.group(2)) * 3600 + int(m.group(3)) * 60 + int(m.group(4)), m.group(5), m.group(1)
                else:
                    m = REC_LINE.match(line)
                    if not m:
                        continue
                    t, x = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)), m.group(4)
                    clock = hms(t)
                s = SHOT.match(x)
                if s:
                    out.append((t, None, os.path.basename(s.group(1).replace("\\", "/")), clock))
                elif x.startswith("(") or x.startswith("[") or not x.strip():
                    continue            # a gap, a note
                else:
                    out.append((t, x.strip(), None, clock))
    except OSError:
        pass
    out.sort(key=lambda e: e[0])
    return out


def _read_ocr(slides_dir):
    try:
        with open(os.path.join(slides_dir, OCR_NAME), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _stat(path):
    try:
        st = os.stat(path)
        return f"{st.st_mtime_ns}:{st.st_size}"
    except OSError:
        return "-"


class Index:
    def __init__(self, root, path=":memory:"):
        self.root = os.path.abspath(root)
        self.path = path
        self._lock = threading.RLock()
        self._mem = None
        self._synced = 0.0
        self._ready = False

    # ---- the database ----
    def _open(self):
        if self.path == ":memory:":
            if self._mem is None:
                self._mem = sqlite3.connect(":memory:", check_same_thread=False)
                self._mem.row_factory = sqlite3.Row
            return self._mem
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        db = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        db.row_factory = sqlite3.Row
        return db

    def _close(self, db):
        if db is not self._mem:
            db.close()

    def _create(self, db):
        db.executescript("""
            DROP TABLE IF EXISTS lines; DROP TABLE IF EXISTS lectures; DROP TABLE IF EXISTS meta;
            CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
            CREATE TABLE lectures(id INTEGER PRIMARY KEY, f TEXT UNIQUE, course TEXT, name TEXT, mtime REAL, sig TEXT);
            CREATE VIRTUAL TABLE lines USING fts5(body, stems, x UNINDEXED, lec UNINDEXED, t UNINDEXED,
                slide UNINDEXED, clock UNINDEXED, tokenize = 'unicode61 remove_diacritics 0', prefix = '2 3 4');
        """)
        db.execute("INSERT INTO meta VALUES('schema', ?)", (str(SCHEMA),))
        db.commit()

    def _prepare(self, db):
        try:
            ok = db.execute("SELECT v FROM meta WHERE k='schema'").fetchone()
            if ok is None or ok[0] != str(SCHEMA):
                raise sqlite3.Error("old schema")
            db.execute("SELECT count(*) FROM lines").fetchone()
        except sqlite3.Error:
            self._create(db)

    # ---- keeping it up to date ----
    def _lectures(self):
        """[(course, lecture, folder, transcript)] - a folder holding '<its name>.txt', in a course folder."""
        out = []
        try:
            courses = sorted(os.listdir(self.root))
        except OSError:
            return out
        for c in courses:
            cd = os.path.join(self.root, c)
            if c.startswith(".") or not os.path.isdir(cd):
                continue
            try:
                names = os.listdir(cd)
            except OSError:
                continue
            for n in names:
                d = os.path.join(cd, n)
                t = os.path.join(d, n + ".txt")
                if os.path.isfile(t):
                    out.append((c, n, d, t))
        return out

    def sync(self, force=False):
        """Reads what changed since last time (a lecture that is running is read again, it is small)."""
        with self._lock:
            if not force and self._ready and time.time() - self._synced < 2:
                return 0
            db = self._open()
            try:
                try:
                    self._prepare(db)
                except sqlite3.DatabaseError:
                    if db is self._mem:
                        raise
                    db.close()          # the file is damaged (or not ours): it is only a copy - build it again
                    for suffix in ("", "-journal", "-wal", "-shm"):
                        try:
                            os.remove(self.path + suffix)
                        except OSError:
                            pass
                    db = self._open()
                    self._prepare(db)
                known = {r["f"]: (r["id"], r["sig"]) for r in db.execute("SELECT id, f, sig FROM lectures")}
                seen, changed = set(), 0
                for c, n, d, t in self._lectures():
                    f = f"{c}/{n}"
                    seen.add(f)
                    slides = os.path.join(d, SLIDES)
                    sig = _stat(t) + "|" + _stat(os.path.join(slides, OCR_NAME))
                    if f in known and known[f][1] == sig:
                        continue
                    self._load(db, known.get(f), f, c, n, t, slides, sig)
                    changed += 1
                for f, (lid, _) in known.items():
                    if f not in seen:
                        db.execute("DELETE FROM lines WHERE lec = ?", (lid,))
                        db.execute("DELETE FROM lectures WHERE id = ?", (lid,))
                        changed += 1
                db.commit()
                self._synced, self._ready = time.time(), True
                return changed
            finally:
                self._close(db)

    def _load(self, db, old, f, course, name, transcript, slides, sig):
        try:
            mtime = os.path.getmtime(transcript)
        except OSError:
            mtime = 0.0
        if old:
            lid = old[0]
            db.execute("DELETE FROM lines WHERE lec = ?", (lid,))
            db.execute("UPDATE lectures SET course=?, name=?, mtime=?, sig=? WHERE id=?", (course, name, mtime, sig, lid))
        else:
            lid = db.execute("INSERT INTO lectures(f, course, name, mtime, sig) VALUES (?,?,?,?,?)",
                             (f, course, name, mtime, sig)).lastrowid
        ocr = _read_ocr(slides)
        rows = []
        for t, x, shot, clock in parse_lecture(transcript):
            if x is None:
                x, slide = str(ocr.get(shot, ""))[:OCR_MAX], shot      # a slide: its text, if it was read
                if not x.strip():
                    continue
            else:
                slide = None
            body, stems = _body(x)
            if body:
                rows.append((body, stems, x, lid, t, slide, clock))
        db.executemany("INSERT INTO lines(body, stems, x, lec, t, slide, clock) VALUES (?,?,?,?,?,?,?)", rows)

    # ---- searching ----
    def search(self, query, course="", limit=50, sort="best", per_lecture=0):
        """{"hits": [...], "more": bool}. A hit: f ('<course>/<lecture>'), course, lecture, t (seconds), c (the time to show), kind
        ('say' | 'slide'), x (a piece of the line), marks ([[start, end]] in x), slide (file name, slides only),
        score. sort: 'best' (the best fit first) or 'recent' (the newest lecture first, in order of time)."""
        match, marks = build_query(query)
        if match is None:
            return {"hits": [], "more": False}
        self.sync()
        with self._lock:
            db = self._open()
            try:
                sql = ("SELECT l.f, l.course, l.name, l.mtime, m.x, m.t, m.slide, m.clock, m.r FROM "
                       "(SELECT lec, t, x, slide, clock, bm25(lines, 10.0, 4.0) AS r FROM lines WHERE lines MATCH ?) m "
                       "JOIN lectures l ON l.id = m.lec")
                args = [match]
                if course:
                    sql += " WHERE l.course = ?"
                    args.append(course)
                sql += " ORDER BY m.r LIMIT ?"
                args.append(2000 if sort == "recent" else max(limit * 4, 200) if per_lecture else limit + 1)
                try:
                    rows = db.execute(sql, args).fetchall()
                except sqlite3.OperationalError:
                    return {"hits": [], "more": False}           # a query FTS5 cannot read
            finally:
                self._close(db)
        if sort == "recent":
            rows = sorted(rows, key=lambda r: (-r["mtime"], r["t"]))
        else:
            rows = sorted(rows, key=lambda r: (round(r["r"], 1), -r["mtime"], r["t"]))
        hits, count = [], {}
        for r in rows:
            if per_lecture and count.get(r["f"], 0) >= per_lecture:
                continue
            count[r["f"]] = count.get(r["f"], 0) + 1
            if len(hits) >= limit:
                return {"hits": hits, "more": True}
            piece, spans = excerpt(r["x"], marks)
            hit = {"f": r["f"], "course": r["course"], "lecture": r["name"], "t": int(r["t"]), "c": r["clock"],
                   "kind": "slide" if r["slide"] else "say", "x": piece, "marks": spans,
                   "score": round(-r["r"], 2)}
            if r["slide"]:
                hit["slide"] = r["slide"]
            hits.append(hit)
        return {"hits": hits, "more": False}

    def stats(self):
        self.sync()
        with self._lock:
            db = self._open()
            try:
                return {"lectures": db.execute("SELECT count(*) FROM lectures").fetchone()[0],
                        "lines": db.execute("SELECT count(*) FROM lines").fetchone()[0]}
            finally:
                self._close(db)

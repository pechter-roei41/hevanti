# -*- coding: utf-8 -*-
"""Hevanti (הבנתי) connector - (c) 2026 Roei Pechter. MIT License, see LICENSE.txt

A small MCP server (Model Context Protocol, over stdin/stdout) that lets the student's own AI app - Claude for
desktop, ChatGPT/Codex - read what Hevanti saved: what is happening in the lecture right now, the slide on the
screen, any transcript, and search in all of them. It only reads files in the "הקורסים שלי" folder; it changes
nothing and sends nothing anywhere by itself. Hevanti adds it to the AI app's settings ("חיבור" in the app).

Run by the AI app as:  python hevanti_mcp.py --lib "<path to הקורסים שלי>"
Standard library only (Pillow is used when it is there, to make big screenshots smaller)."""
import base64
import io
import json
import os
import re
import sys

VERSION = "2.1"
NOW_NAME = "now_watching.txt"
SLIDES = "שקופיות"
GLOSSARY = "מילון מונחים.txt"
OCR_NAME = ".ocr.json"     # the text Hevanti read from each slide (when Tesseract is installed)
MAX_TEXT = 90_000          # characters of transcript in one answer
PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")

LIVE_LINE = re.compile(r"\[(\d\d:\d\d:\d\d) \| \+(\d+):(\d\d):(\d\d)\] (.*)$")
REC_LINE = re.compile(r"\[(\d+):(\d\d):(\d\d)\] (.*)$")
SHOT = re.compile(r"\[צילום מסך: (.+)\]$")
NOW_SLIDE = re.compile(r"^(?:צילום המסך האחרון|השקופית שעל המסך עכשיו): (.+?\.(?:jpg|png))(?: \(|$)", re.M)
NOW_TRANSCRIPT = re.compile(r"^תמלול מלא: (.+?\.txt)", re.M)

INSTRUCTIONS = (
    "Hevanti (הבנתי) is the student's lecture app on this computer. It transcribes live lectures, recorded "
    "lectures and YouTube videos (Hebrew or English) and saves every new slide/board as a picture. "
    "Whenever the user asks about the lecture, the lecturer, 'what he just said', the slide or the board "
    "(e.g. 'מה הוא אמר עכשיו?', 'מה כתוב בשקופית?', 'לא הבנתי את החלק האחרון'), call `now` FIRST: it returns "
    "what is happening right now (live, or the exact minute in a recording/video), the last minutes of the "
    "transcript and the slide on the screen. Use `transcript` for more context or another lecture, `slide` for "
    "the slide at a given time, `search` to find where something was said, `lectures` for the list. "
    "Answer in the user's language (usually Hebrew), step by step, and keep technical terms in English in "
    "parentheses. The transcript is automatic: a word that makes no sense is probably a mis-hearing - guess from "
    "the context. Ignore ads. "
    "COURSES: every lecture belongs to a course (a folder). When the conversation is about one course - e.g. a "
    "project whose instructions name a Hevanti course, or a folder that is a course folder - pass that course's "
    "name as `course` to every tool, so only its lectures are used. `transcript` with `whole_course: true` "
    "returns all the lectures of a course (in parts) for exam preparation, summaries and flashcards.")

TOOLS = [
    {"name": "now",
     "description": "What is happening in the lecture RIGHT NOW: live lecture or the user's exact place in a "
                    "recording/YouTube video, the transcript of the last minutes, and the picture of the slide "
                    "on the screen. Call this first for any question about the current lecture.",
     "inputSchema": {"type": "object", "properties": {
         "course": {"type": "string", "description": "the course this conversation is about (optional)"}},
         "additionalProperties": False}},
    {"name": "transcript",
     "description": "The transcript of a lecture (default: the one open now, or the newest). Optional time range "
                    "in minutes from the start (for a recording/video: its own time). With `course`: the newest "
                    "lecture of that course; with `whole_course: true`: all its lectures, oldest first, in parts.",
     "inputSchema": {"type": "object", "properties": {
         "lecture": {"type": "string", "description": "'<course>/<lecture>' as listed by `lectures`, or part of its name"},
         "course": {"type": "string", "description": "only lectures of this course"},
         "whole_course": {"type": "boolean", "description": "all the lectures of `course` (exam prep, summary)"},
         "part": {"type": "integer", "description": "with whole_course: which part (1, 2, ...) when it is long"},
         "from_min": {"type": "number", "description": "start, minutes from the beginning"},
         "to_min": {"type": "number", "description": "end, minutes from the beginning"}},
         "additionalProperties": False}},
    {"name": "slide",
     "description": "The picture of the slide/board that was on the screen at a given time of a lecture "
                    "(default: the lecture open now, at the current moment).",
     "inputSchema": {"type": "object", "properties": {
         "lecture": {"type": "string", "description": "'<course>/<lecture>' or part of its name"},
         "course": {"type": "string", "description": "only lectures of this course"},
         "at": {"type": "string", "description": "time in the lecture, like '23:40' or '1:05:10'"}},
         "additionalProperties": False}},
    {"name": "search",
     "description": "Find where words were said - or written on a slide - in all lectures (or one course). "
                    "Returns lecture, time and line.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "course": {"type": "string"}},
         "required": ["query"], "additionalProperties": False}},
    {"name": "lectures",
     "description": "The courses and their lectures (newest first), and each course's glossary of terms "
                    "(with `course`: only that course, with the terms themselves).",
     "inputSchema": {"type": "object", "properties": {
         "course": {"type": "string", "description": "only this course"}}, "additionalProperties": False}},
]


class Lib:
    def __init__(self, root):
        self.root = os.path.abspath(root)

    def inside(self, path):
        real, root = os.path.realpath(path), os.path.realpath(self.root)
        return real == root or real.startswith(root + os.sep)

    def lectures(self):
        """[(course, lecture, dir, transcript, mtime)] newest first."""
        out = []
        try:
            courses = sorted(os.listdir(self.root))
        except OSError:
            return out
        for c in courses:
            cd = os.path.join(self.root, c)
            if not os.path.isdir(cd) or c.startswith("."):
                continue
            for n in os.listdir(cd):
                d = os.path.join(cd, n)
                t = os.path.join(d, n + ".txt")
                if os.path.isfile(t):
                    out.append((c, n, d, t, os.path.getmtime(t)))
        out.sort(key=lambda x: x[4], reverse=True)
        return out

    def course_of(self, wanted):
        """The course folder meant by `wanted` (exact name, ignoring case, or part of it), or None."""
        wanted = str(wanted or "").strip().replace("\\", "/").strip("/").lower()
        if not wanted:
            return None
        try:
            names = [x for x in os.listdir(self.root) if not x.startswith(".") and os.path.isdir(os.path.join(self.root, x))]
        except OSError:
            names = []
        for n in names:
            if n.lower() == wanted:
                return n
        hits = [n for n in names if wanted in n.lower() or n.lower() in wanted]
        return min(hits, key=len) if hits else None

    def now_course(self, body=None):
        """The course of what is happening now (from the transcript path in now_watching.txt), or None."""
        m = NOW_TRANSCRIPT.search(self.now_text() if body is None else body)
        if not m:
            return None
        return m.group(1).replace("\\", "/").split("/")[0] or None

    def now_text(self):
        try:
            with open(os.path.join(self.root, NOW_NAME), encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def find(self, name, course=None):
        """A lecture by '<course>/<lecture>', by part of its name, or (no name) the one open now / the newest -
        only in `course` when it is given."""
        items = self.lectures()
        if course:
            items = [it for it in items if it[0] == course]
        name = str(name or "").strip().replace("\\", "/").strip("/")
        if not name:
            m = NOW_TRANSCRIPT.search(self.now_text())
            if m:
                rel = m.group(1).replace("\\", "/")
                d = os.path.dirname(os.path.join(self.root, *rel.split("/")))
                for it in items:
                    if os.path.normcase(it[2]) == os.path.normcase(d):
                        return it
            return items[0] if items else None
        low = name.lower()
        for it in items:
            if f"{it[0]}/{it[1]}".lower() == low:
                return it
        for it in items:
            if low in f"{it[0]}/{it[1]}".lower():
                return it
        return None


def secs(text):
    """'23:40' / '1:05:10' / '95' (minutes) -> seconds."""
    text = str(text or "").strip()
    if not text:
        return None
    parts = text.split(":")
    try:
        if len(parts) == 1:
            return float(parts[0]) * 60
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    out = 0.0
    for n in nums:
        out = out * 60 + n
    return out


def hms(t):
    t = int(max(0, t))
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def read_lines(path):
    """The transcript -> [(seconds from the start, text)], shots as ('shot', file)."""
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n")
                m = LIVE_LINE.match(line)
                if m:
                    t, x = int(m.group(2)) * 3600 + int(m.group(3)) * 60 + int(m.group(4)), m.group(5)
                else:
                    m = REC_LINE.match(line)
                    if not m:
                        continue
                    t, x = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)), m.group(4)
                out.append((t, x))
    except OSError:
        pass
    out.sort(key=lambda e: e[0])
    return out


def image_content(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        if im.width > 1600 or len(data) > 900_000:
            im = im.convert("RGB")
            im.thumbnail((1600, 1600))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=80)
            data, mime = buf.getvalue(), "image/jpeg"
    except Exception:
        if len(data) > 3_000_000:
            return None
    return {"type": "image", "data": base64.b64encode(data).decode("ascii"), "mimeType": mime}


def text(t):
    return {"type": "text", "text": t}


def ocr_of(path):
    """The text read from this slide picture, or ""."""
    try:
        with open(os.path.join(os.path.dirname(path), OCR_NAME), encoding="utf-8") as f:
            d = json.load(f)
        return str(d.get(os.path.basename(path), "")) if isinstance(d, dict) else ""
    except (OSError, ValueError):
        return ""


def slide_path(lecture_dir, root, rel):
    rel = rel.replace("\\", "/")
    return os.path.join(lecture_dir, *rel.split("/")) if rel.startswith(SLIDES + "/") else os.path.join(root, *rel.split("/"))


def glossary_words(course_dir):
    try:
        with open(os.path.join(course_dir, GLOSSARY), encoding="utf-8") as f:
            return [w.strip() for w in f.read().splitlines() if w.strip() and not w.startswith("#")]
    except OSError:
        return []


def rows_of(lib, lecture_dir, lines, a=None, b=None, ocr_max=500):
    """Transcript lines as text rows; a slide line carries the text read from it."""
    out = []
    for t, x in lines:
        if (a is not None and t < a) or (b is not None and t > b):
            continue
        m = SHOT.match(x)
        if not m:
            out.append(f"[{hms(t)}] {x}")
            continue
        words = ocr_of(slide_path(lecture_dir, lib.root, m.group(1)))
        out.append(f"[{hms(t)}] [שקופית: {m.group(1)}]" +
                   (" כתוב עליה: " + words.replace("\n", " | ")[:ocr_max] if words else ""))
    return out


class Server:
    def __init__(self, lib):
        self.lib = lib

    def _course(self, args):
        """(course folder or None, error text or None) for the optional `course` argument."""
        wanted = str(args.get("course") or "").strip()
        if not wanted:
            return None, None
        c = self.lib.course_of(wanted)
        if c:
            return c, None
        try:
            names = sorted(x for x in os.listdir(self.lib.root)
                           if not x.startswith(".") and os.path.isdir(os.path.join(self.lib.root, x)))
        except OSError:
            names = []
        return None, (f"אין בהבנתי קורס בשם \"{wanted}\". הקורסים שיש: " + (", ".join(names) or "(עוד אין)") +
                      ". אם זה הקורס הנכון בשם אחר - להשתמש בשם כפי שהוא כאן.")

    # --- tools ---
    def tool_now(self, args):
        course, err = self._course(args)
        if err:
            return [text(err)]
        body = self.lib.now_text()
        if not body.strip():
            return [text("הבנתי לא פועלת כרגע, או שעוד לא התחילה הרצאה (אין now_watching.txt). "
                         "אפשר להשתמש ב-`lectures` וב-`transcript` להרצאות שכבר נשמרו.")]
        out = []
        cur = self.lib.now_course(body)
        if course and cur and cur != course:
            out.append(text(f"שימו לב: מה שקורה עכשיו בהבנתי שייך לקורס \"{cur}\", לא לקורס \"{course}\" "
                            "שהשיחה הזו עליו. אם השאלה על ההרצאה שרצה עכשיו - הנה היא. אם על הקורס הזה - "
                            f"`transcript` עם course=\"{course}\" מביא את ההרצאה האחרונה שלו."))
        elif course and not cur:
            newest = self.lib.find(None, course)
            out.append(text("כרגע לא רצה הרצאה. " + (f"ההרצאה האחרונה בקורס \"{course}\": {newest[0]}/{newest[1]} "
                            "(`transcript` מביא אותה)." if newest else f"בקורס \"{course}\" עוד אין הרצאות שמורות.")))
        out.append(text(body))
        m = NOW_SLIDE.search(body)
        if m:
            p = os.path.join(self.lib.root, *m.group(1).replace("\\", "/").split("/"))
            if self.lib.inside(p):
                img = image_content(p)
                if img:
                    out += [text("השקופית שעל המסך:"), img]
                words = ocr_of(p)
                if words:
                    out.append(text("הטקסט שנקרא מהשקופית (אוטומטי, יכולות להיות טעויות):\n" + words))
        return out

    def whole_course(self, course, part):
        items = sorted((it for it in self.lib.lectures() if it[0] == course), key=lambda it: it[4])
        if not items:
            return [text(f"בקורס \"{course}\" עוד אין הרצאות שמורות.")]
        blocks = []
        for c, n, d, path, _ in items:
            lines = read_lines(path)
            body = "\n".join(rows_of(self.lib, d, lines, ocr_max=300))
            if not body:
                continue
            head = f"=== {n} ==="
            while len(body) > MAX_TEXT:   # a very long lecture is split on a line
                cut = body.rfind("\n", 0, MAX_TEXT)
                cut = cut if cut > 0 else MAX_TEXT
                blocks.append(head + "\n" + body[:cut])
                body, head = body[cut:].lstrip("\n"), f"=== {n} (המשך) ==="
            blocks.append(head + "\n" + body)
        parts, cur = [], ""
        for b in blocks:
            if cur and len(cur) + len(b) + 2 > MAX_TEXT:
                parts.append(cur)
                cur = ""
            cur = (cur + "\n\n" + b) if cur else b
        if cur:
            parts.append(cur)
        if not parts:
            return [text(f"בקורס \"{course}\" יש הרצאות, אבל עוד בלי תמלול.")]
        try:
            k = min(len(parts), max(1, int(part or 1)))
        except (TypeError, ValueError):
            k = 1
        terms = glossary_words(os.path.join(self.lib.root, course))
        head = (f"קורס: {course} | {len(items)} הרצאות, מהישנה לחדשה | חלק {k} מתוך {len(parts)}" +
                (f" (את שאר החלקים: part={k + 1}..{len(parts)})" if len(parts) > 1 else "") +
                "\nתמלול אוטומטי: מילה שנשמעת מוזרה היא כנראה טעות תמלול." +
                ("\nמונחים בקורס: " + ", ".join(terms[:80]) if terms else ""))
        return [text(head + "\n\n" + parts[k - 1])]

    def tool_transcript(self, args):
        course, err = self._course(args)
        if err:
            return [text(err)]
        if args.get("whole_course"):
            if not course:
                return [text("whole_course צריך גם course (שם הקורס). `lectures` מראה את הקורסים.")]
            return self.whole_course(course, args.get("part"))
        it = self.lib.find(args.get("lecture"), course)
        if not it:
            return [text("לא מצאתי הרצאה כזו" + (f" בקורס \"{course}\"" if course else "") +
                         ". `lectures` מראה את כל ההרצאות.")]
        c, n, d, path, _ = it
        lines = read_lines(path)
        a, b = args.get("from_min"), args.get("to_min")
        a = float(a) * 60 if isinstance(a, (int, float)) else None
        b = float(b) * 60 if isinstance(b, (int, float)) else None
        rows = rows_of(self.lib, d, lines, a, b)
        head = f"הרצאה: {c}/{n} | {len(lines)} שורות" + (f" | מ-{hms(a)}" if a is not None else "") + \
               (f" עד {hms(b)}" if b is not None else "")
        body = "\n".join(rows)
        if len(body) > MAX_TEXT:
            body = body[:MAX_TEXT] + f"\n... (ארוך מדי - לבקש שוב עם from_min/to_min, למשל {int((a or 0) / 60) + 40} והלאה)"
        words = glossary_words(os.path.dirname(d))
        terms = ("\nמונחים בקורס: " + ", ".join(words[:80])) if words else ""
        return [text(head + terms + "\n\n" + (body or "(אין שורות בטווח הזה)"))]

    def tool_slide(self, args):
        course, err = self._course(args)
        if err:
            return [text(err)]
        if not args.get("lecture") and not args.get("at"):
            body = self.lib.now_text()
            m = NOW_SLIDE.search(body)
            if m and (not course or self.lib.now_course(body) == course):
                p = os.path.join(self.lib.root, *m.group(1).replace("\\", "/").split("/"))
                img = image_content(p) if self.lib.inside(p) else None
                if img:
                    words = ocr_of(p)
                    return [text("השקופית שעל המסך עכשיו: " + m.group(1)), img] + \
                        ([text("הטקסט שנקרא מהשקופית (אוטומטי):\n" + words)] if words else [])
        it = self.lib.find(args.get("lecture"), course)
        if not it:
            return [text("לא מצאתי הרצאה כזו" + (f" בקורס \"{course}\"" if course else "") + ".")]
        at = secs(args.get("at"))
        best = None
        for t, x in read_lines(it[3]):
            m = SHOT.match(x)
            if m and (at is None or t <= at + 1):
                best = (t, m.group(1))
        if not best:
            return [text("אין שקופית שמורה עד הזמן הזה בהרצאה הזו.")]
        p = slide_path(it[2], self.lib.root, best[1])
        img = image_content(p) if self.lib.inside(p) else None
        if not img:
            return [text("קובץ השקופית לא נמצא.")]
        words = ocr_of(p)
        return [text(f"השקופית מ-{hms(best[0])} ({it[0]}/{it[1]}):"), img] + \
            ([text("הטקסט שנקרא מהשקופית (אוטומטי):\n" + words)] if words else [])

    def tool_search(self, args):
        words = [w for w in str(args.get("query") or "").lower().split() if w]
        if not words:
            return [text("צריך מילה לחפש.")]
        course, err = self._course(args)
        if err:
            return [text(err)]
        hits = []
        for c, n, d, path, _ in self.lib.lectures():
            if course and c != course:
                continue
            for t, x in read_lines(path):
                m = SHOT.match(x)
                body = ocr_of(slide_path(d, self.lib.root, m.group(1))) if m else x
                if body and all(w in body.lower() for w in words):
                    if m:
                        ln = next((l for l in body.splitlines() if any(w in l.lower() for w in words)), body)
                        hits.append(f"{c}/{n} [{hms(t)}] [בשקופית {m.group(1)}] {ln[:300]}")
                    else:
                        hits.append(f"{c}/{n} [{hms(t)}] {x}")
                    if len(hits) >= 60:
                        break
            if len(hits) >= 60:
                break
        return [text("\n".join(hits) if hits else "לא נמצא.")]

    def tool_lectures(self, args):
        course, err = self._course(args)
        if err:
            return [text(err)]
        # every course folder is listed, also a course with no lecture yet (a folder with only its glossary)
        by = {}
        for c, n, d, path, mt in self.lib.lectures():
            by.setdefault(c, []).append(n)
        try:
            courses = sorted(x for x in os.listdir(self.lib.root)
                             if not x.startswith(".") and os.path.isdir(os.path.join(self.lib.root, x)))
        except OSError:
            courses = []
        courses = sorted(set(courses) | set(by))
        if course:
            courses = [course]
        if not courses:
            return [text("עוד אין קורסים ולא הרצאות שמורות בתיקיית הקורסים שלי.")]
        out = []
        for c in courses:
            words = glossary_words(os.path.join(self.lib.root, c))
            lectures = by.get(c, [])
            out.append(f"קורס {c} ({len(lectures)} הרצאות, {len(words)} מונחים במילון):")
            out += [f"  {c}/{n}" for n in lectures] or ["  (עוד אין הרצאות שמורות בקורס הזה)"]
            if course and words:
                out.append("  מונחים: " + ", ".join(words[:120]))
        return [text("\n".join(out))]

    # --- the protocol ---
    def handle(self, msg):
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            want = (msg.get("params") or {}).get("protocolVersion")
            return {"protocolVersion": want if want in PROTOCOLS else PROTOCOLS[1],
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "hevanti", "title": "הבנתי", "version": VERSION},
                    "instructions": INSTRUCTIONS}
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": TOOLS}
        if method == "tools/call":
            p = msg.get("params") or {}
            fn = getattr(self, "tool_" + str(p.get("name")), None)
            if fn is None or p.get("name") not in [t["name"] for t in TOOLS]:
                raise KeyError("unknown tool")
            try:
                return {"content": fn(p.get("arguments") or {}), "isError": False}
            except Exception as e:
                return {"content": [text(f"שגיאה בקריאת הקבצים של הבנתי: {e.__class__.__name__}")], "isError": True}
        if mid is None:
            return None  # a notification (initialized, cancelled...) - nothing to answer
        raise LookupError(method)


def main():
    args = sys.argv[1:]
    lib = None
    if "--lib" in args and args.index("--lib") + 1 < len(args):
        lib = args[args.index("--lib") + 1]
    if not lib:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        lib = next((os.path.join(root, n) for n in ("הקורסים שלי", "ההרצאות שלי") if os.path.isdir(os.path.join(root, n))),
                   os.path.join(root, "הקורסים שלי"))
    if not os.path.isdir(lib) and os.path.basename(lib.rstrip("\\/")) == "ההרצאות שלי":
        lib = os.path.join(os.path.dirname(lib.rstrip("\\/")), "הקורסים שלי")   # renamed by Hevanti since connecting
    server = Server(Lib(lib))
    out = sys.stdout.buffer
    for raw in sys.stdin.buffer:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw.decode("utf-8"))
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            if not isinstance(msg, dict):
                continue
            mid = msg.get("id")
            try:
                res = server.handle(msg)
                if mid is None:
                    continue
                reply = {"jsonrpc": "2.0", "id": mid, "result": res if res is not None else {}}
            except KeyError:
                reply = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": "unknown tool"}}
            except LookupError:
                if mid is None:
                    continue
                reply = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found"}}
        out.write(json.dumps(reply, ensure_ascii=False).encode("utf-8") + b"\n")
        out.flush()


if __name__ == "__main__":
    main()

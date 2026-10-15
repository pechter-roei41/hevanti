"""Tests for the AI connector (System/Program/hevanti_mcp.py) on a small made-up "ההרצאות שלי" folder.
Standard library only; runs anywhere:  python3 tools/test_mcp.py"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MCP = os.path.join(HERE, "System", "Program", "hevanti_mcp.py")
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)[:600]))
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):   # shown on the run's page (annotations)
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


def write(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)


def make_lib(root):
    s, d = "סטטיקה של גוף קשיח", "דינמיקה"
    write(os.path.join(root, s, "מילון מונחים.txt"), "# header\nמומנט\nתגובת סמך\n")
    write(os.path.join(root, d, "מילון מונחים.txt"), "תנע זוויתי\n")
    os.makedirs(os.path.join(root, "קורס ריק"))
    l1 = os.path.join(root, s, "2026-10-12 10-00 הרצאה")
    write(os.path.join(l1, "2026-10-12 10-00 הרצאה.txt"),
          "[10:00:05 | +0:00:05] היום נדבר על תגובות סמך\n[10:01:00 | +0:01:00] [צילום מסך: שקופיות/10-01-00.jpg]\n"
          "[10:02:00 | +0:02:00] מומנט סביב נקודה A\n")
    write(os.path.join(l1, "שקופיות", ".ocr.json"), json.dumps({"10-01-00.jpg": "Free body diagram"}))
    l2 = os.path.join(root, s, "2026-10-14 10-00 הרצאה")
    write(os.path.join(l2, "2026-10-14 10-00 הרצאה.txt"), "[10:00:05 | +0:00:05] מסבך ומוטות\n")
    l3 = os.path.join(root, d, "2026-10-15 09-00 הרצאה")
    write(os.path.join(l3, "2026-10-15 09-00 הרצאה.txt"), "[09:00:05 | +0:00:05] תנע זוויתי של דיסקה\n")
    os.utime(os.path.join(l1, "2026-10-12 10-00 הרצאה.txt"), (1, 1000))
    os.utime(os.path.join(l2, "2026-10-14 10-00 הרצאה.txt"), (1, 2000))
    os.utime(os.path.join(l3, "2026-10-15 09-00 הרצאה.txt"), (1, 3000))
    write(os.path.join(root, "now_watching.txt"),
          f"מצב: הרצאה חיה - התמלול רץ עכשיו (עברית) | קורס: {d}\nתמלול מלא: {d}/2026-10-15 09-00 הרצאה/"
          "2026-10-15 09-00 הרצאה.txt\nצילום המסך האחרון: עוד אין\n\nמה נאמר:\n[09:00:05] תנע זוויתי של דיסקה\n")


def call(root, calls):
    msgs = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}]
    for i, (name, args) in enumerate(calls):
        msgs.append({"jsonrpc": "2.0", "id": 10 + i, "method": "tools/call", "params": {"name": name, "arguments": args}})
    inp = "\n".join(json.dumps(m, ensure_ascii=False) for m in msgs) + "\n"
    r = subprocess.run([sys.executable, MCP, "--lib", root], input=inp.encode("utf-8"), capture_output=True, timeout=60)
    out = {}
    for line in r.stdout.decode("utf-8").splitlines():
        m = json.loads(line)
        out[m["id"]] = m
    return out


def body(res):
    return "\n".join(c.get("text", "") for c in res["result"]["content"] if c.get("type") == "text")


with tempfile.TemporaryDirectory() as tmp:
    root = os.path.join(tmp, "ההרצאות שלי")
    make_lib(root)
    S, D = "סטטיקה של גוף קשיח", "דינמיקה"
    r = call(root, [
        ("lectures", {}),                                   # 10
        ("lectures", {"course": "סטטיקה"}),                  # 11
        ("now", {"course": S}),                              # 12
        ("now", {"course": D}),                              # 13
        ("transcript", {"course": S}),                       # 14
        ("transcript", {"course": S, "whole_course": True}),  # 15
        ("search", {"query": "מומנט", "course": S}),         # 16
        ("search", {"query": "תנע", "course": S}),           # 17
        ("now", {"course": "אלגברה"}),                       # 18
        ("transcript", {"whole_course": True}),             # 19
        ("search", {"query": "free body"}),                 # 20
        ("transcript", {"course": "קורס ריק", "whole_course": True}),  # 21
    ])
    tools = {t["name"]: t for t in r[1]["result"]["tools"]}
    check("tools list has course everywhere",
          all("course" in tools[n]["inputSchema"]["properties"] for n in ("now", "transcript", "slide", "search", "lectures")))
    check("instructions mention courses", "course" in r[0]["result"]["instructions"])
    check("lectures: all courses, also an empty one", all(x in body(r[10]) for x in (S, D, "קורס ריק")), body(r[10]))
    check("lectures: one course by part of its name, with its terms",
          S in body(r[11]) and D not in body(r[11]) and "תגובת סמך" in body(r[11]), body(r[11]))
    check("now: warns when the running lecture is of another course", "שייך לקורס" in body(r[12]) and D in body(r[12]), body(r[12]))
    check("now: no warning in the right course", "שימו לב" not in body(r[13]) and "תנע זוויתי" in body(r[13]), body(r[13]))
    check("transcript: newest lecture of the course", "2026-10-14" in body(r[14]) and "מסבך" in body(r[14]), body(r[14]))
    b = body(r[15])
    check("whole course: both lectures, oldest first, with slide text",
          b.find("2026-10-12") < b.find("2026-10-14") and "Free body diagram" in b and "תנע" not in b and "חלק 1 מתוך 1" in b, b)
    check("search: only in the course", "מומנט סביב" in body(r[16]) and body(r[17]) == "לא נמצא.", body(r[16]) + body(r[17]))
    check("unknown course: says which courses exist", "אין בהבנתי קורס" in body(r[18]) and S in body(r[18]), body(r[18]))
    check("whole_course needs a course", "צריך גם course" in body(r[19]), body(r[19]))
    check("search finds slide text", "בשקופית" in body(r[20]), body(r[20]))
    check("whole course of an empty course", "עוד אין הרצאות" in body(r[21]), body(r[21]))

    # a long course is split into parts
    big = os.path.join(root, S, "2026-10-13 10-00 ארוכה")
    write(os.path.join(big, "2026-10-13 10-00 ארוכה.txt"),
          "".join(f"[10:{i // 60 % 60:02d}:{i % 60:02d} | +0:{i // 60 % 60:02d}:{i % 60:02d}] " + "מילה " * 40 + "\n"
                  for i in range(1200)))
    r = call(root, [("transcript", {"course": S, "whole_course": True}),
                    ("transcript", {"course": S, "whole_course": True, "part": 2})])
    b1, b2 = body(r[10]), body(r[11])
    check("long course: in parts", "חלק 1 מתוך" in b1 and "חלק 2 מתוך" in b2 and "part=2" in b1, b1[:300])
    check("long course: parts within the limit", len(b1) < 95_000 and len(b2) < 95_000, (len(b1), len(b2)))

    # --- "find the moment": ranked places with time, context and the slide of that time ---
    r = call(root, [("moment", {"query": "מומנט נקודה", "course": S}),                 # 10
                    ("moment", {"query": "תנע זוויתי"}),                                # 11 (another course)
                    ("moment", {"query": "free body"}),                                # 12 (text on a slide)
                    ("moment", {"query": "ננומטר", "course": S}),                       # 13 (nowhere)
                    ("moment", {"query": ""}),                                         # 14
                    ("moment", {"query": "מומנט", "course": "אלגברה"})])               # 15
    check("moment: finds the place with its time", "בזמן 0:02:00" in body(r[10]) and "מומנט סביב נקודה A" in body(r[10]), body(r[10]))
    check("moment: carries the slide of that time", "Free body diagram" in body(r[10]), body(r[10]))
    check("moment: all the courses when none is given", D in body(r[11]) and "תנע זוויתי של דיסקה" in body(r[11]), body(r[11]))
    check("moment: a word written on a slide", "0:01:00" in body(r[12]), body(r[12]))
    check("moment: nothing found - says so, suggests other words", "לא מצאתי" in body(r[13]) and "מילה אחרת" in body(r[13]), body(r[13]))
    check("moment: empty query", "צריך נושא" in body(r[14]), body(r[14]))
    check("moment: unknown course", "אין בהבנתי קורס" in body(r[15]), body(r[15]))

    # the best place first, and two places of one lecture far from each other are both returned
    far = os.path.join(root, S, "2026-10-16 10-00 ארוכה")
    write(os.path.join(far, "2026-10-16 10-00 ארוכה.txt"),
          "[10:00:10 | +0:00:10] נדבר על מומנט התמד\n[10:00:20 | +0:00:20] מומנט ההתמד של גליל הוא חצי מסה בריבוע רדיוס\n"
          "[10:10:00 | +0:10:00] עכשיו משהו אחר לגמרי\n[10:30:00 | +0:30:00] שוב מומנט התמד של קורה\n")
    r = call(root, [("moment", {"query": "מומנט התמד של גליל", "course": S}),
                    ("moment", {"query": "מומנט התמד", "lecture": "2026-10-16"})])
    b = body(r[10])
    check("moment: best place first", b.find("בזמן 0:00:10") != -1 and "חצי מסה" in b, b)
    b = body(r[11])
    check("moment: two far places of one lecture", "0:00:10" in b and "0:30:00" in b and "עכשיו משהו אחר" not in b, b)

    # --- ready-made requests as MCP prompts ---
    msgs = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "id": 1, "method": "prompts/list"},
            {"jsonrpc": "2.0", "id": 2, "method": "prompts/get", "params": {"name": "exam", "arguments": {"course": "סטטיקה", "count": "12"}}},
            {"jsonrpc": "2.0", "id": 3, "method": "prompts/get", "params": {"name": "summary", "arguments": {"course": S, "lecture": "10-12"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "prompts/get", "params": {"name": "find_moment", "arguments": {"topic": "מומנט התמד"}}},
            {"jsonrpc": "2.0", "id": 5, "method": "prompts/get", "params": {"name": "nothing", "arguments": {}}}]
    rr = subprocess.run([sys.executable, MCP, "--lib", root], input=("\n".join(json.dumps(m, ensure_ascii=False) for m in msgs) + "\n").encode("utf-8"),
                        capture_output=True, timeout=60)
    P = {}
    for line in rr.stdout.decode("utf-8").splitlines():
        m = json.loads(line)
        P[m["id"]] = m

    def ptext(i):
        return P[i]["result"]["messages"][0]["content"]["text"]
    check("prompts: capability announced", "prompts" in P[0]["result"]["capabilities"])
    check("prompts: the three requests are listed",
          [p["name"] for p in P[1]["result"]["prompts"]] == ["exam", "summary", "find_moment"])
    check("prompt exam: the course name is resolved and the count used",
          f"'{S}'" in ptext(2) and "12 questions" in ptext(2) and "whole_course=true" in ptext(2), ptext(2))
    check("prompt summary: the lecture is passed on", "lecture='10-12'" in ptext(3), ptext(3))
    check("prompt find_moment: the topic is used, no course is allowed", "מומנט התמד" in ptext(4) and "`moment`" in ptext(4), ptext(4))
    check("prompts: an unknown one is an error", "error" in P[5])

print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.exit(1 if fails else 0)

"""Tests for "the AI of each course" inside the app (System/Program/live_transcribe.py), on a made-up library:
the course folder's AGENTS.md / GEMINI.md / CLAUDE.md, project links, the course's "now" file, the cloud copy,
the Gemini (Antigravity CLI) connection and the connector reading the course folder. Any OS:
  python3 tools/test_course_ai.py"""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tmp = tempfile.mkdtemp()
os.environ["BZM_DATA_DIR"] = os.path.join(tmp, "data")
os.environ["BZM_GEMINI_DIR"] = os.path.join(tmp, "gemini")
os.environ["LOCALAPPDATA"] = os.path.join(tmp, "local")
os.environ["HOME"] = os.environ["USERPROFILE"] = os.path.join(tmp, "home")
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)[:500]))
    if not ok:
        fails.append(name)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


C = "סטטיקה של גוף קשיח"
name = L.create_course(C, ["מומנט", "תגובת סמך"])
cd = L.course_dir(C)
check("new course", name == C and os.path.isdir(cd))
for n in L.AI_FILE_NAMES:
    p = os.path.join(cd, n)
    check(f"{n} written", os.path.isfile(p) and f'course="{C}"' in read(p) and read(p).startswith(L.AI_FILE_MARK))

# the student's own AGENTS.md is never replaced; Hevanti's own one is updated
with open(os.path.join(cd, "AGENTS.md"), "w", encoding="utf-8") as f:
    f.write("my own rules\n")
L.write_course_ai_files(C)
check("student's own AGENTS.md kept", read(os.path.join(cd, "AGENTS.md")) == "my own rules\n")
with open(os.path.join(cd, "GEMINI.md"), "w", encoding="utf-8") as f:
    f.write(L.AI_FILE_MARK + "\nold\n")
L.write_course_ai_files(C)
check("Hevanti's old GEMINI.md updated", f'course="{C}"' in read(os.path.join(cd, "GEMINI.md")))
check("course list ignores the AI files", L.course_names() == [C], L.course_names())

# project links: only that AI's own https site
for app, url, good in [("claude", "https://claude.ai/project/0199abc", True),
                       ("chatgpt", "https://chatgpt.com/g/g-p-68abc-statics/project", True),
                       ("gemini", "https://gemini.google.com/gem/abc123", True),
                       ("claude", "https://evil.example/claude.ai", False),
                       ("chatgpt", "javascript:alert(1)", False),
                       ("gemini", "http://gemini.google.com/gem/x", False)]:
    r = L.set_course_ai_link(C, app, url)
    check(f"link {app} {'accepted' if good else 'refused'}: {url[:40]}", bool(r.get("ok")) == good, r)
links = L.course_ai_links(C)
check("links saved per course", links["claude"].endswith("0199abc") and links["gemini"].endswith("abc123"), links)
check("link removed with an empty one", L.set_course_ai_link(C, "gemini", "")["links"]["gemini"] == "")
check("link for a missing course refused", not L.set_course_ai_link("אין כזה", "claude", "https://claude.ai/project/1").get("ok"))

info = L.course_ai_info(C)
check("instructions name the course", all(C in info["instructions"][a] for a in L.AI_APPS))
check("Claude's instructions use the tools with course", f'course="{C}"' in info["instructions"]["claude"])
check("cloud instructions name the Drive files", "עכשיו.txt" in info["instructions"]["chatgpt"])

# the course's "now" file follows now_watching.txt
lec = f"{C}/2026-10-15 10-00 הרצאה"
os.makedirs(os.path.join(L.LIB_DIR, *lec.split("/"), "שקופיות"), exist_ok=True)
with open(os.path.join(L.LIB_DIR, *lec.split("/"), "שקופיות", ".ocr.json"), "w", encoding="utf-8") as f:
    json.dump({"10-01-00.jpg": "Free body diagram\nΣM = 0"}, f)
body = (f"מצב: הרצאה חיה - התמלול רץ עכשיו (עברית) | קורס: {C}\nתמלול מלא: {lec}/2026-10-15 10-00 הרצאה.txt\n"
        f"צילום המסך האחרון: {lec}/שקופיות/10-01-00.jpg (מ-10:01:00)\n\nמה נאמר:\n[10:01:02] מומנט סביב A\n")
L.write_now_file(body)
cnow = os.path.join(cd, L.COURSE_NOW_NAME)
check("course now file written", os.path.isfile(cnow) and "מומנט סביב A" in read(cnow))
L.write_now_file("מצב: אין כרגע הרצאה חיה ולא צפייה בהקלטה.\n")
check("course now file says the lecture ended", "אין כרגע" in read(cnow), read(cnow)[:200])
L.write_now_file(body)

# cloud copy (a folder standing for Google Drive)
drive = os.path.join(tmp, "My Drive")
os.makedirs(drive)
check("no cloud copy before it is turned on", L.mirror_root() is None)
r = L.set_mirror(drive)
check("cloud on", r.get("ok") and L.mirror_root() == os.path.join(drive, "הבנתי"), r)
with open(os.path.join(L.LIB_DIR, *lec.split("/"), "2026-10-15 10-00 הרצאה.txt"), "w", encoding="utf-8") as f:
    f.write("[10:01:02 | +0:01:02] מומנט סביב A\n")
L.MIRROR.now_changed(C)
L.MIRROR.lectures_changed(C)
now_cloud = os.path.join(drive, "הבנתי", C, "עכשיו.txt")
all_cloud = os.path.join(drive, "הבנתי", C, "כל ההרצאות.txt")
for _ in range(40):
    if os.path.isfile(now_cloud) and os.path.isfile(all_cloud):
        break
    time.sleep(0.5)
check("cloud: now file", os.path.isfile(now_cloud) and "מומנט סביב A" in read(now_cloud))
check("cloud: slide text instead of a picture", os.path.isfile(now_cloud) and "Free body diagram" in read(now_cloud)
      and ".jpg" not in read(now_cloud), read(now_cloud) if os.path.isfile(now_cloud) else "")
check("cloud: all lectures", os.path.isfile(all_cloud) and "מומנט סביב A" in read(all_cloud))
check("cloud: instructions file", os.path.isfile(os.path.join(drive, "הבנתי", C, "קרא אותי - הוראות ל-AI.txt")))
check("cloud off", L.set_mirror("").get("ok") and L.mirror_root() is None)
check("cloud: a missing folder is refused", not L.set_mirror(os.path.join(tmp, "nope")).get("ok"))

# Gemini: Antigravity CLI's config (and Gemini CLI's, for school accounts); other servers kept
os.makedirs(os.path.dirname(L.antigravity_config_path()), exist_ok=True)
with open(L.antigravity_config_path(), "w", encoding="utf-8") as f:
    json.dump({"mcpServers": {"other": {"command": "x"}}}, f)
r = L.gemini_set(True)
ag = json.load(open(L.antigravity_config_path(), encoding="utf-8"))
check("Gemini: Antigravity config written", r.get("ok") and "hevanti" in ag["mcpServers"] and "other" in ag["mcpServers"], ag)
check("Gemini: connected", L.gemini_connected())
L.gemini_set(False)
ag = json.load(open(L.antigravity_config_path(), encoding="utf-8"))
check("Gemini: disconnected, other server kept", "hevanti" not in ag["mcpServers"] and "other" in ag["mcpServers"], ag)
check("Gemini: not connected", not L.gemini_connected())

# the connector, reading this library with the course
msgs = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "now", "arguments": {"course": "סטטיקה"}}}]
p = subprocess.run([sys.executable, L.MCP_SCRIPT, "--lib", L.LIB_DIR],
                   input=("\n".join(json.dumps(m, ensure_ascii=False) for m in msgs) + "\n").encode(),
                   capture_output=True, timeout=60)
res = {json.loads(x)["id"]: json.loads(x) for x in p.stdout.decode().splitlines()}
txt = " ".join(c.get("text", "") for c in res[1]["result"]["content"] if c.get("type") == "text")
check("connector: now in the course, no warning", "מומנט סביב A" in txt and "שימו לב" not in txt, txt[:300])

print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.exit(1 if fails else 0)

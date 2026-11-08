"""Which course is the lecture about to start? (System/Program/live_transcribe.py: guess_course) - from the title of a window
on the screen, else from the weekly schedule (the same weekday and hour in earlier weeks). Only a suggestion: the page selects
it and says why. Any OS, a second:
  python3 tools/test_course_guess.py"""
import datetime
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.update(BZM_DATA_DIR=tempfile.mkdtemp(), LOCALAPPDATA=tempfile.mkdtemp(), BZM_NO_BROWSER="1")
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)))
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


PROB, FUNC, DYN = "מבוא להסתברות וסטטיסטיקה", "פונקציות מרוכבות", "דינמיקה של גוף קשיח"
courses = [PROB, FUNC, DYN, "Linear Algebra"]

# ---- the title of a window ----
check("the words that tell a course apart: no 'של', no one-letter prefix", L._course_stems(DYN) == ["דינמיקה", "גוף", "קשיח"]
      and L._course_stems(PROB) == ["הסתברות", "סטטיסטיקה"], (L._course_stems(DYN), L._course_stems(PROB)))
g = L.guess_by_title(["Chrome", "Zoom - הרצאה בפונקציות מרוכבות 3"], courses)
check("a window with the course's name (words with a prefix: 'בפונקציות')", g == (FUNC, "Zoom - הרצאה בפונקציות מרוכבות 3"), g)
check("'הסתברות וסטטיסטיקה' in a title is the course 'מבוא להסתברות וסטטיסטיקה'", L.guess_by_title(["הסתברות וסטטיסטיקה - תרגול 4"], courses)[0] == PROB)
check("a long name (3 words): two of them are enough", L.guess_by_title(["גוף קשיח - הרצאה"], courses)[0] == DYN)
check("a name in English, any case", L.guess_by_title(["Zoom: linear ALGEBRA 101"], courses)[0] == "Linear Algebra")
check("one word of a two-word name is not enough", L.guess_by_title(["מרוכבות בלבד"], courses) is None)
check("two courses fit equally (words, not the whole name): no guess", L.guess_by_title(["מרוכבות ופונקציות", "גוף קשיח דינמיקה"], courses) is None)
check("...but the whole name of one beats the words of another", L.guess_by_title(["פונקציות מרוכבות", "גוף קשיח דינמיקה"], courses)[0] == FUNC)
check("nothing on the screen fits: no guess", L.guess_by_title(["Chrome", "Spotify", "מחשבון"], courses) is None)
check("a course with no distinctive word is skipped (not an error)", L.guess_by_title(["כל דבר"], ["של", "קורס"]) is None)

# ---- the weekly schedule ----
now = datetime.datetime(2026, 11, 15, 11, 20)   # a Sunday


def live(course, when, kind="live"):
    return {"kind": kind, "course": course, "when": when}


sched = [live(PROB, "2026-11-01 11:04"), live(PROB, "2026-11-08 11:36"), live(FUNC, "2026-11-08 16:00"), live(DYN, "2026-11-09 11:10")]
check("two earlier Sundays at about this hour: that course", L.guess_by_schedule(sched, now) == (PROB, 2), L.guess_by_schedule(sched, now))
check("a single earlier lecture is not a schedule", L.guess_by_schedule([live(PROB, "2026-11-08 11:36")], now) is None)
check("two courses equally often: no guess", L.guess_by_schedule(sched + [live(FUNC, "2026-11-01 11:00"), live(FUNC, "2026-11-08 11:00")], now) is None)
check("a lecture today, another weekday, another hour or not a live one is not counted",
      L.guess_by_schedule([live(PROB, "2026-11-15 11:04"), live(PROB, "2026-11-09 11:04"), live(PROB, "2026-11-01 16:30"),
                           live(PROB, "2026-11-01 11:04", kind="rec"), live(PROB, "2026-11-08 11:04", kind="yt")], now) is None)
check("a lecture of no course, or with a broken date, is ignored", L.guess_by_schedule(
    [live(L.NO_COURSE, "2026-11-01 11:04"), live(L.NO_COURSE, "2026-11-08 11:04"), live(PROB, "garbage"), live(PROB, None)], now) is None)

# ---- both together ----
g = L.guess_course(titles=["Zoom - דינמיקה של גוף קשיח"], now=now, entries=sched, courses=courses)
check("the window wins over the schedule", g["course"] == DYN and g["why"] == "title" and "דינמיקה" in g["detail"], g)
g = L.guess_course(titles=["Chrome"], now=now, entries=sched, courses=courses)
check("no window fits: the schedule, saying how often and when", g["course"] == PROB and g["why"] == "schedule" and "2 הרצאות" in g["detail"]
      and "יום ראשון" in g["detail"] and "11:00" in g["detail"], g)
check("nothing fits: nothing", L.guess_course(titles=["Chrome"], now=now, entries=[], courses=courses) == {})
check("no courses (or only 'no course'): nothing", L.guess_course(titles=["פונקציות מרוכבות"], now=now, entries=sched, courses=[]) == {}
      and L.guess_course(titles=["x"], now=now, entries=sched, courses=[L.NO_COURSE]) == {})
check("a course that was deleted is not suggested by the schedule", L.guess_course(titles=[], now=now, entries=sched, courses=[FUNC]) == {})

# ---- over the command the page sends ----
L.APP = getattr(L, "APP", None) or L.App()
L.create_course(FUNC)
L.create_course(DYN)
L.window_choices = lambda: [{"title": "Teams | פונקציות מרוכבות", "app": "ms-teams"}]
r = L.APP.command({"action": "guess_course"})
check("the page's command returns the suggestion", r.get("ok") and r.get("course") == FUNC and r.get("why") == "title", r)
L.window_choices = lambda: (_ for _ in ()).throw(RuntimeError("no windows here"))
r = L.APP.command({"action": "guess_course"})
check("a failing window list is not an error: just no guess", r.get("ok") and not r.get("course"), r)

print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.exit(1 if fails else 0)

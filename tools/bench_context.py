"""How much lecture text can one question carry? Measures Gemini on THIS computer with the student's saved key.
  python tools/bench_context.py lecture.txt [--pos MIN] [--question TEXT] [--model NAME] [--no-repeat]
`lecture.txt` is a lecture transcript of the library ("[09:01:00 | +0:01:00] text" lines, or "[00:20:44] text").
For the last 5 minutes, the last 30 minutes and the whole lecture up to --pos (default: the end) it sends one real question
and prints: characters, tokens Gemini counted, seconds until the answer starts (the app gives up after GEMINI_START_S),
seconds for the whole answer, tokens it served from its cache (the second send of each size) and any quota error.
It makes 3 requests (6 without --no-repeat) of the key's free quota. The key is read like the app reads it and never printed.
For the developer; not part of the app."""
import argparse
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

_ELAPSED = re.compile(r"^\[[\d:]+\s*\|\s*\+(\d+):(\d{2}):(\d{2})\]\s*(.+)$")
_PLAIN = re.compile(r"^\[(\d{1,2}):(\d{2}):(\d{2})\]\s*(.+)$")
DEFAULT_QUESTION = "מה ההבדל בין מה שהוסבר קודם לבין מה שנאמר עכשיו? תסביר בקצרה את המושג המרכזי."


def read_lines(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            m = _ELAPSED.match(raw.strip()) or _PLAIN.match(raw.strip())
            if m:
                h, mi, s, text = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4).strip()
                if text:
                    out.append((h * 3600 + mi * 60 + s, text))
    return out


def build_context(lines, pos, minutes, question):
    lo = 0 if minutes is None else pos - minutes * 60
    part = [(t, x) for t, x in lines if lo <= t <= pos + 0.5]
    span = "מתחילת ההרצאה" if minutes is None else f"של {minutes} הדקות האחרונות"
    head = f"אני עכשיו ב-{L.hms(pos)} מההרצאה.\nזה התמלול האוטומטי {span} (יכולות להיות בו טעויות תמלול):\n\n"
    return head + "".join(f"[{L.hms(t)}] {x}\n" for t, x in part) + "\nהשאלה שלי: " + question, len(part)


def body_for(context):
    return {"systemInstruction": {"parts": [{"text": L.tutor_system(False, "")}]},
            "contents": [{"role": "user", "parts": [{"text": context}]}], "generationConfig": {"temperature": 0.3}}


def send(key, model, body, start_timeout):
    usage, info, out = {}, {}, []
    t0, first = time.monotonic(), None
    try:
        for piece in L.gemini_stream(key, model, body, usage, timeout=start_timeout, info=info):
            if first is None:
                first = time.monotonic() - t0
            out.append(piece)
    except L.MathError as e:
        return {"error": str(e), "quota": e.kind == "quota", "wait": e.wait, "first": first}
    return {"first": first, "total": time.monotonic() - t0, "usage": usage, "text": "".join(out), "warn": info.get("warn", "")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lecture")
    ap.add_argument("--pos", type=float, help="the place of the question, minutes from the start (default: the end)")
    ap.add_argument("--question", default=DEFAULT_QUESTION)
    ap.add_argument("--model", help="a model name (default: the first the key can use, as the app picks)")
    ap.add_argument("--no-repeat", action="store_true", help="send each size once (the cache is then not measured)")
    ap.add_argument("--pause", type=float, default=15.0, help="seconds between two requests (default 15)")
    ap.add_argument("--start-timeout", type=float, default=90.0, help="how long to wait for the answer to start (default 90)")
    a = ap.parse_args()
    lines = read_lines(a.lecture)
    if not lines:
        sys.exit("no transcript lines found in " + a.lecture)
    pos = a.pos * 60 if a.pos is not None else lines[-1][0]
    key = os.environ.get("GEMINI_API_KEY") or L.read_secret(L.math_settings().get("key"))
    if not key:
        sys.exit("no Gemini key: save it in Hevanti's settings, or set GEMINI_API_KEY")
    model = a.model
    if not model:
        names = L.gemini_candidates(L.gemini_models(key))
        if not names:
            sys.exit("the key has no usable Gemini model")
        model = names[0]
    print(f"lecture: {len(lines)} lines, {L.hms(lines[-1][0])} long; question at {L.hms(pos)}; model: {model}")
    print(f"the live question gives up after {L.GEMINI_START_S} s without a first word\n")
    print(f"{'size':<14}{'lines':>6}{'chars':>9}{'tokens':>9}{'first(s)':>10}{'total(s)':>10}{'cached':>9}  note")
    first_run = True
    for label, minutes in (("last 5 min", 5), ("last 30 min", 30), ("whole lecture", None)):
        ctx, n = build_context(lines, pos, minutes, a.question)
        body = body_for(ctx)
        for rep in (1,) if a.no_repeat else (1, 2):
            if not first_run:
                time.sleep(a.pause)
            first_run = False
            r = send(key, model, body, a.start_timeout)
            name = label + ("" if a.no_repeat else f" #{rep}")
            if "error" in r:
                print(f"{name:<14}{n:>6}{len(ctx):>9}{'-':>9}{'-':>10}{'-':>10}{'-':>9}  ERROR{' (quota)' if r['quota'] else ''}: {r['error']}")
                if r["quota"]:
                    print("   the free quota stopped it: that is itself the measurement for this size")
                    break
                continue
            u = r["usage"]
            note = "would be abandoned by the app" if r["first"] is not None and r["first"] > L.GEMINI_START_S else ""
            note = (note + " " + r["warn"]).strip()
            print(f"{name:<14}{n:>6}{len(ctx):>9}{u.get('promptTokenCount', '?'):>9}{r['first'] or 0:>10.1f}{r['total']:>10.1f}"
                  f"{u.get('cachedContentTokenCount', 0):>9}  {note}")
    print("\nRead it: 'first' is what the student waits before the first word; 'cached' above 0 on the second send means Gemini")
    print("reused the beginning (cheaper, faster). Run it on a lecture of 60-90 minutes, once at the end and once with --pos 30.")


if __name__ == "__main__":
    main()

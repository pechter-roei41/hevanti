"""Does a longer piece of sound cost less work per second of lecture on the CPU? (Whisper always works on a 30 s window, so a 12 s piece pays for 30.)
Standalone: it runs with the Python of an installed Hevanti.

  & "$env:LOCALAPPDATA\\Programs\\Hevanti\\python\\python.exe" bench_chunks.py "C:\\path\\to\\lecture.mp4" [seconds=180] [start=60] [rounds=2]

It cuts the same stretch of the file into pieces the way a live lecture does (find_cut, a pause between the shortest and the longest piece),
once for each pair of lengths, in turns (A B C A B C ...) so a computer that slows down with heat does not favour one of them, and prints:
  work/audio  = seconds of work for one second of lecture (below 1.0 keeps up live; lower is better)
  words/work  = words written for each second of work (the same work buys more speech when this is higher)"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROG = os.path.join(os.path.dirname(HERE), "System", "Program")
if not os.path.isdir(PROG):
    PROG = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Hevanti", "System", "Program")
sys.path.insert(0, PROG)
import numpy as np  # noqa: E402
import live_transcribe as L  # noqa: E402
from faster_whisper import WhisperModel, decode_audio  # noqa: E402

SR = 16000
CONFIGS = (("A  10-18 s (today)", 10, 18), ("B  15-26 s", 15, 26), ("C  20-28 s", 20, 28))


def pieces(audio, min_s, max_s):
    """The pieces a live lecture would make: it waits until max_s of sound is there, then cuts at the quietest 0.3 s between min_s and max_s."""
    out, buf = [], audio
    while len(buf) >= max_s * SR:
        cut = L.find_cut(buf, SR, min_s, max_s)
        out.append(buf[:cut])
        buf = buf[cut:]
    if len(buf) >= SR:
        out.append(buf)
    return out


def run(model, parts):
    prev, words, t0 = "", 0, time.time()
    for p in parts:
        text = L.transcribe(model, 1, p, prev) or ""
        words += len(text.split())
        prev = text or prev
    return time.time() - t0, words


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 180.0
    start = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
    rounds = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    audio = decode_audio(sys.argv[1], sampling_rate=SR)[int(start * SR):int((start + secs) * SR)]
    real = len(audio) / SR
    L.set_language("he")
    model, beam, desc = L.get_model("he", stub_av=False)
    print(f"{desc}, {real:.0f}s of audio from second {start:.0f}, {os.cpu_count()} logical processors, {rounds} rounds", flush=True)
    if not desc.endswith("CPU"):
        sys.exit("This measures the CPU: this computer would use its graphics card.")
    L.transcribe(model, 1, audio[:SR], "")   # the first call is always slower
    plan = {name: pieces(audio, lo, hi) for name, lo, hi in CONFIGS}
    for name, parts in plan.items():
        lens = [len(p) / SR for p in parts]
        print(f"{name}: {len(parts)} pieces, {min(lens):.1f}-{max(lens):.1f} s, average {sum(lens) / len(lens):.1f} s", flush=True)
    res = {name: [] for name, _, _ in CONFIGS}
    for r in range(rounds):
        for name, _, _ in CONFIGS:
            work, words = run(model, plan[name])
            res[name].append((work / real, words / work))
            print(f"round {r + 1}  {name}: work/audio {work / real:.2f}   words/work {words / work:.2f}", flush=True)
    print("\naverage of the rounds:")
    for name, _, _ in CONFIGS:
        w = sum(x[0] for x in res[name]) / rounds
        wd = sum(x[1] for x in res[name]) / rounds
        print(f"  {name}: work/audio {w:.2f}   words/work {wd:.2f}")


if __name__ == "__main__":
    main()

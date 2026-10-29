"""Transcription speed on THIS computer, the way the live lecture does it (the same model, the same settings).
Run it on a student-like laptop with a minute or more of lecture audio or video (any format Hevanti reads):
  python tools/bench_transcribe.py lecture.mp4 [seconds=90] [chunk=15]
It prints how many seconds of work one second of lecture costs (below 1.0 = keeps up live; the lower, the better),
and what to expect. For the developer; not part of the app."""
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    total = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0
    chunk = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
    from faster_whisper import decode_audio
    audio = decode_audio(path, sampling_rate=L.TARGET_SR)
    audio = audio[:int(total * L.TARGET_SR)]
    secs = len(audio) / L.TARGET_SR
    print(f"{secs:.0f}s of audio, chunks of {chunk:.0f}s, {os.cpu_count()} CPU threads")
    t0 = time.time()
    model, beam, label = L.load_model()
    print(f"model: {label}, beam {beam}, loaded in {time.time() - t0:.1f}s")
    prev, done, spent, worst = "", 0.0, 0.0, 0.0
    step = int(chunk * L.TARGET_SR)
    for i in range(0, len(audio), step):
        piece = audio[i:i + step]
        t = time.time()
        text = L.transcribe(model, beam, piece, prev)
        took = time.time() - t
        spent += took
        done += len(piece) / L.TARGET_SR
        worst = max(worst, took / (len(piece) / L.TARGET_SR))
        prev = text
        print(f"  {done:5.0f}s  took {took:5.1f}s  x{took / (len(piece) / L.TARGET_SR):.2f}  {text[:50]}")
    rtf = spent / max(done, 1)
    print(f"\nspeed: x{rtf:.2f} (worst chunk x{worst:.2f}) - {label}")
    if rtf < 0.6:
        print("OK: keeps up with a live lecture with room to spare.")
    elif rtf < 0.9:
        print("TIGHT: keeps up, but a hard stretch (fast speech, a slow moment of the computer) will lag.")
    else:
        print("TOO SLOW for live on this computer: it falls behind. Needs a smaller model or record-then-transcribe.")


if __name__ == "__main__":
    main()

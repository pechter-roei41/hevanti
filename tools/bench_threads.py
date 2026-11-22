"""Does fewer CPU threads transcribe faster on THIS computer? (a laptop with fast and slow cores may). Standalone: it runs with the
Python of an installed Hevanti, no other file of the repository is needed:

  & "$env:LOCALAPPDATA\\Programs\\Hevanti\\python\\python.exe" bench_threads.py "C:\\path\\to\\lecture.mp4" [seconds=90]

It transcribes the first seconds of the file the way a live lecture does on a CPU (the Hebrew model, int8, beam 1, pieces of 15 s) once
for each number of threads, and prints how many seconds of work one second of lecture costs. Below 1.0 keeps up live; lower is better."""
import os
import sys
import time

PROG = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Hevanti", "System", "Program")
if os.path.isdir(PROG):
    sys.path.insert(0, PROG)
import live_transcribe as L  # noqa: E402
from faster_whisper import WhisperModel, decode_audio  # noqa: E402

SR = 16000


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0
    audio = decode_audio(sys.argv[1], sampling_rate=SR)[:int(secs * SR)]
    real = len(audio) / SR
    print(f"{real:.0f}s of audio, {os.cpu_count()} logical processors")
    path = L.model_path("ivrit-ai/whisper-large-v3-turbo-ct2")
    for n in (12, 8, 6, 4):
        if n > (os.cpu_count() or 4):
            continue
        m = WhisperModel(path, device="cpu", compute_type="int8", cpu_threads=n)
        list(m.transcribe(audio[:SR], language="he", beam_size=1)[0])   # warm-up: the first call is always slower
        t0 = time.time()
        for i in range(0, len(audio), 15 * SR):
            segs, _ = m.transcribe(audio[i:i + 15 * SR], language="he", beam_size=1, vad_filter=True)
            list(segs)
        print(f"{n} threads: {(time.time() - t0) / real:.2f}  (below 1.0 keeps up live)", flush=True)
        del m


if __name__ == "__main__":
    main()

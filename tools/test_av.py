"""Reading a recording with a new PyAV (15+): faster-whisper still passes metadata_errors=, which PyAV dropped
(the bug of 15.10.2026 with a Panopto recording). Needs PyAV and faster-whisper (skipped without them):
  python3 tools/test_av.py"""
import os
import sys
import tempfile
import wave

try:
    import av  # noqa: F401
    import numpy as np
    from faster_whisper.audio import decode_audio
except ImportError:
    print("skipped: PyAV / faster-whisper not installed")
    sys.exit(0)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["BZM_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

p = os.path.join(tempfile.mkdtemp(), "t.wav")
with wave.open(p, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(16000)
    w.writeframes((np.sin(np.arange(16000) / 5) * 3000).astype(np.int16).tobytes())
L.load_real_av()
L.load_real_av()   # twice: wrapped once
n = len(decode_audio(p, sampling_rate=16000))
print(("PASS" if n == 16000 else "FAIL") + f" a recording is read (PyAV {av.__version__}): {n} samples")
sys.exit(0 if n == 16000 else 1)

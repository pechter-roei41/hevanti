# Hevanti (הבנתי)

Open-source (MIT) lecture companion for Israeli university students on Windows. It transcribes lectures on the student's computer (Hebrew or English), saves a picture of every new slide, and has two core features: a small always-on-top question window (Ctrl+Alt+Q) and one-click marks (★ / ?; Ctrl+Alt+M). Answers come from Gemini through the student's own free API key. There is no Hevanti server.

Read these before larger changes:
- `PRODUCT.md`: who it is for and what it is
- `DESIGN.md`: visual system ("The Open Notebook")
- `DECISIONS.md`: what was decided and why (Hebrew). Add every new decision there, with a date.
- `README.md`: features, privacy, file map

## Principles (do not break without asking)

- **No server, no AI of our own, no key of ours.** The student's own Gemini key, or copy to their AI app. The key is stored encrypted (Windows DPAPI).
- **Privacy:** transcripts and screenshots stay on the computer. The app listens on `127.0.0.1` only. Nothing leaves without a student action. Cloud sync is off by default.
- **Must work on an ordinary laptop:** no discrete GPU, little memory. No default local AI model.
- **Hebrew first, right-to-left.** UI and in-app guide in Hebrew; README and code comments in English.
- **YouTube:** play in the official player inside the app. Never download.
- **Listen to the computer's audio only, not the microphone.**
- **Screenshots:** if the Hevanti window cannot be located (DWM frame), do not capture. Never guess.

## Layout

- `System/Program/live_transcribe.py`: the whole computer side (transcription, screenshots, local server, courses, YouTube, AI). Very large single file.
- `System/Program/app.html`, `player.html`, `mini.html`: the app, the recording player, the floating window. `ask.js`: the ask box. `katex/`, `fonts/`: bundled.
- `System/Program/hevanti_mcp.py`: MCP server, standard library only.
- `System/Program/course_terms.json`: suggested glossary terms per course.
- `System/VERSION.txt`: release notes per version (Hebrew). Update with each version.
- `Install.bat`, `System/get_python.ps1`, `System/install_ocr.*`: Windows setup. `installer/hevanti.iss`, `tools/build_setup_dir.py`, `tools/build_zip.py`: packaging.
- `tools/test_*.py`: tests.

## Testing

Plain Python scripts, no pytest. CI (`.github/workflows/tests.yml`) runs them on Windows and Linux with `numpy` and `pillow`:

```
python -m pip install numpy pillow
python tools/test_core.py
python tools/test_mcp.py
python tools/test_course_ai.py
```

See the workflow for the full list. `test_core_ui.py` needs Playwright and Edge, so it runs on Windows only. `test_av.py` also needs `av` and `faster-whisper`. Run the relevant `tools/test_*.py` after every change. Most of the code was written with AI, so tests matter. A real run on a Windows computer is needed before a release.

## Conventions

- Set `PYTHONUTF8=1` when running tests (Hebrew text, Windows).
- Follow `DESIGN.md` for any UI change (colors, light and dark, accessibility options: size, contrast, no motion, screen reader).
- User-visible Hebrew strings should read as natural Israeli Hebrew.
- Local lecture folders (`הקורסים שלי/`, `ההרצאות שלי/`), `transcripts/`, `screenshots/` are never committed. `.claude/`, `.agents/`, `.codex/` are also ignored.
- Bump the version in `System/VERSION.txt` and the app when releasing.

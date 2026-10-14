# Hevanti (הבנתי)

**Everything the lecturer said, and an answer to everything you didn't understand.** A free, open-source lecture companion for students on Windows (and Mac, in beta).

Hevanti writes down everything said in the lecture, in Hebrew or English, and saves a picture of every slide and board. You listen instead of copying, and you can ask an AI exactly about the moment you missed.

- **Live lecture:** Zoom, a broadcast, or anything playing on your computer. Transcription runs on your computer.
- **Recorded lecture:** a file or a link (Drive, Dropbox, OneDrive, a Zoom recording). A player synced with the transcript.
- **YouTube video:** plays in YouTube's official player inside Hevanti (no download), and is transcribed while you watch, with the video's timestamps.
- **Courses:** a folder per course, a glossary that improves transcription, and search across everything that was said. Type a course name (for example "סטטיקה של גוף קשיח", rigid-body statics) and Hevanti suggests terms for that course; one click on **+** adds a term to the glossary. Suggestions are per course, not per degree: 55 common courses so far, in [`course_terms.json`](System/Program/course_terms.json).
- **Better transcription of terms and names:** the course name and its glossary reach the model as *hotwords* with a budget of their own, so the last words said never push them out, and English terms and names read from the slide on the screen join them.
- **Reading the slides (OCR):** every saved slide is read with [Tesseract](https://github.com/tesseract-ocr/tesseract) (Hebrew and English, offline). Search covers the slides too, their text goes into exam prep and into what is copied for an AI, and a connected AI gets it with the picture.
- **Exam prep:** a practice exam, a summary, flashcards and a formula sheet from all the lectures of a course (with the slides' text).
- **Recommended layout:** the lecture on two thirds of the screen, the AI on one third. Hevanti greys out the AI's window and its own windows in its screenshots, so an answer being written is never saved as a "new slide" and your chat stays out of the pictures.
- **Connect AI:** one button connects Claude for desktop, ChatGPT (Codex) or Gemini CLI to Hevanti through a small MCP server. Then you ask them directly in their own window, for example "What is he saying now?", and they read the last minutes and the slide themselves. The AI sees every course, including courses with no lectures yet.
- **Floating window:** a small window that stays on top of the lecture: a question box at the top, then what is being said now, then the latest slide.
- **Without a connection:** ChatGPT, Gemini or Claude with one click. The question is copied together with the last five minutes, and the AI's desktop app opens if it is installed (found in the Windows Start menu); otherwise its website opens on a third of the screen. Another click brings the same window back, so the conversation goes on.
- **How to use:** a one-minute animated walkthrough inside the app (the "איך משתמשים?" button), drawn with the app's own parts rather than a video file.

## Download and install

**Windows:** download `Hevanti.zip` from the [latest release](https://github.com/pechter-roei41/hevanti/releases/latest), extract it, double-click `Install`, then `Hevanti`. No Python to install: the ZIP comes with the official embeddable Python, and `Install` only adds the packages (and, if you agree, Tesseract for reading slides).

**Mac (beta, not yet tested on a real Mac):** download `Hevanti-Mac.zip`, right-click `Install.command` > Open (once), then open `Hevanti.command`. `Install.command` gets its own Python with [uv](https://docs.astral.sh/uv/) (no admin password). A Mac cannot record its own sound without a virtual audio device, so Hevanti listens through [BlackHole](https://existential.audio/blackhole/) (free); the one-time setup is in `README.txt`.

Full guide (Hebrew): [the Hevanti guide](https://claude.ai/artifact/Rho2yLpowLsxqy1Zsw6QAD)

## Privacy

- Transcripts and screenshots stay on your computer. The app only listens on `127.0.0.1`.
- There is no Hevanti server. The connector (`hevanti_mcp.py`) only reads files from the "ההרצאות שלי" (My Lectures) folder, and only when your AI asks for them. What your AI reads is sent to its provider like any other conversation with it.

## How it is built

| File | What it does |
|---|---|
| `System/Program/live_transcribe.py` | Everything on the computer side: transcription ([faster-whisper](https://github.com/SYSTRAN/faster-whisper) with the Hebrew model from [ivrit.ai](https://huggingface.co/ivrit-ai)), screenshots, the local server, courses, YouTube and the AI connection |
| `System/Program/app.html` | The app (opens in the browser) |
| `System/Program/player.html` | The player for recorded lectures |
| `System/Program/ask.js` | The "ask AI" box |
| `System/Program/hevanti_mcp.py` | The AI connector (MCP server, standard library only): `now`, `transcript`, `slide`, `search`, `lectures` |
| `System/Program/course_terms.json` | Suggested glossary terms per course, matched by the course name. Corrections and new courses are welcome |
| `Install.bat`, `System/get_python.ps1`, `System/install_ocr.*` | Windows setup: the packages into Hevanti's own Python, and Tesseract with the Hebrew and English language files |
| `Install.command`, `Hevanti.command` | Mac setup and start |
| `tools/build_zip.py` | Builds `Hevanti.zip` (with the embeddable Python) and `Hevanti-Mac.zip` |

New version: push a tag such as `v2.0-20261014` (same number, new build) or `v2.1`. GitHub Actions builds both ZIPs and attaches them to a release, and the app tells students that an update is available.

Code signing: the scripts are not signed yet, so Windows shows "Windows protected your PC" once. The plan is a signed installer through the free [SignPath Foundation](https://signpath.org/) program for open-source projects.

## Contributing and issues

Found a bug? [Open an issue](https://github.com/pechter-roei41/hevanti/issues) with a screenshot and `System\error_log.txt`. Pull requests are welcome, and a good first one is adding your course to `course_terms.json`: its name, the words its name may contain (`match`), and 20-30 terms, most important first.

## License

[MIT](LICENSE) © 2026 Roei Pechter. Third-party models and libraries are downloaded from their own sources and are subject to their own licenses. Lectures and slides belong to whoever created them: use them for personal study, according to your institution's policy.

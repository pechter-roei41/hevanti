# Hevanti (הבנתי)

**Everything the lecturer said, and an answer to everything you didn't understand.** A free, open-source lecture companion for students on Windows.

Hevanti writes down everything said in the lecture, in Hebrew or English, and saves a picture of every slide and board. You listen instead of copying, and you can ask an AI exactly about the moment you missed.

- **Live lecture:** Zoom, a broadcast, or anything playing on your computer. Transcription runs on your computer.
- **Recorded lecture:** a file or a link (Drive, Dropbox, OneDrive, a Zoom recording). A player synced with the transcript.
- **YouTube video:** plays in YouTube's official player inside Hevanti (no download), and is transcribed while you watch, with the video's timestamps.
- **Courses:** a folder per course, a glossary that improves transcription, and search across everything that was said. Type a course name (for example "סטטיקה של גוף קשיח", rigid-body statics) and Hevanti suggests terms for that course; one click on **+** adds a term to the glossary. Suggestions are per course, not per degree: 55 common courses so far, in [`course_terms.json`](System/Program/course_terms.json).
- **Exam prep:** a practice exam, a summary, flashcards and a formula sheet from all the lectures of a course.
- **Recommended layout:** the lecture on two thirds of the screen, the AI on one third. Hevanti greys out the AI's window and its own windows in its screenshots, so an answer being written is never saved as a "new slide" and your chat stays out of the pictures.
- **Connect AI:** one button connects Claude or ChatGPT on Windows to Hevanti through a small MCP server. Then you ask them directly in their own window, for example "What is he saying now?", and they read the last minutes and the slide themselves. The AI sees every course, including courses with no lectures yet.
- **Floating window:** a small window that stays on top of the lecture: a question box at the top, then what is being said now, then the latest slide.
- **Without a connection:** ChatGPT, Gemini or Claude with one click. The question is copied together with the last five minutes, and the AI's desktop app opens if it is installed (found in the Windows Start menu); otherwise its website opens on a third of the screen. Another click brings the same window back, so the conversation goes on.
- **How to use:** a one-minute animated walkthrough inside the app (the "איך משתמשים?" button), drawn with the app's own parts rather than a video file.

## Download and install

1. Download `Hevanti.zip` from the [latest release](https://github.com/pechter-roei41/hevanti/releases/latest) and extract it.
2. Install [Python 3.14](https://www.python.org/downloads/windows/) (tick **Add python.exe to PATH**).
3. Double-click `Install`, then double-click `Hevanti`.

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
| `tools/build_zip.py` | Builds `Hevanti.zip` |

New version: push a tag such as `v2.0-20261014` (same number, new build) or `v2.1`. GitHub Actions builds the ZIP and attaches it to a release, and the app tells students that an update is available.

## Contributing and issues

Found a bug? [Open an issue](https://github.com/pechter-roei41/hevanti/issues) with a screenshot and `System\error_log.txt`. Pull requests are welcome, and a good first one is adding your course to `course_terms.json`: its name, the words its name may contain (`match`), and 20-30 terms, most important first.

## License

[MIT](LICENSE) © 2026 Roei Pechter. Third-party models and libraries are downloaded from their own sources and are subject to their own licenses. Lectures and slides belong to whoever created them: use them for personal study, according to your institution's policy.

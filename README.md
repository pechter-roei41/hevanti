# Hevanti (הבנתי)

**Everything the lecturer said, and an answer to everything you didn't understand.** A free, open-source lecture companion for students on Windows.

Hevanti writes down everything said in the lecture, in Hebrew or English, and saves a picture of every slide and board. You listen instead of copying, and you can ask an AI exactly about the moment you missed.

- **Live lecture:** Zoom, a broadcast, or anything playing on your computer. Transcription runs on your computer.
- **Answers inside Hevanti, free (2.2):** an "answer here" button in every question box. With the student's own free Gemini API key (Google AI Studio, no credit card) Hevanti asks Gemini for you and writes the answer under the question as it arrives, using the last minutes of the lecture and the slide on the screen. No Hevanti server, no cost for the student or for us. The key is stored encrypted (Windows DPAPI). The page talks to Hevanti on your computer, which talks to Google; which Gemini model answers is probed on every start, so a retired or busy model does not break it. Without a key, everything works as before (copy to ChatGPT / Gemini / Claude).
- **After the lecture (2.2):** one click for a summary, flashcards, a mock exam, a formula sheet, or an explanation of the moments you marked ("לא הבנתי" / "חשוב", also Ctrl+Alt+M). Every question and answer is kept in the lecture's folder (`שאלות ותשובות.md`).
- **Formulas and handwriting (2.2, optional, off):** with the same key, each saved slide can be read by Gemini, with formulas as LaTeX.
- **Smarter screenshots (2.2):** capture the whole screen, one window (a window that pops over it is mosaicked) or a part of the screen; pause with Ctrl+Alt+P; mosaic fixed areas; delete screenshots for good. A video of the lecturer, a clock or a playing clip no longer counts as a "slide change"; the full board is kept before it is erased.
- **Accessibility (2.2):** text and interface size, reading spacing, high contrast, no motion, screen-reader announcements, big captions in the floating window.- **Recorded lecture:** a file or a link (Drive, Dropbox, OneDrive, a Zoom recording). A player synced with the transcript.
- **YouTube video:** plays in YouTube's official player inside Hevanti (no download), and is transcribed while you watch, with the video's timestamps.
- **Courses:** a folder per course in "הקורסים שלי" (created with the course), a course page with four tabs (lectures, the course's AI, exam prep, glossary), a glossary that improves transcription, and search across everything that was said. Type a course name (for example "סטטיקה של גוף קשיח", rigid-body statics) and Hevanti suggests terms for that course; one click on **+** adds a term to the glossary. Suggestions are per course, not per degree: 55 common courses so far, in [`course_terms.json`](System/Program/course_terms.json).
- **Better transcription of terms and names:** the course name and its glossary reach the model as *hotwords* with a budget of their own, so the last words said never push them out, and English terms and names read from the slide on the screen join them.
- **Reading the slides (OCR):** every saved slide is read with [Tesseract](https://github.com/tesseract-ocr/tesseract) (Hebrew and English, offline). Search covers the slides too, their text goes into exam prep and into what is copied for an AI, and a connected AI gets it with the picture.
- **Panopto recordings:** Panopto needs a sign-in, so a bookmark (dragged once from "הרצאה מוקלטת") runs on the Panopto page where you are signed in, asks Panopto's own `DeliveryInfo.aspx` for the recording's file (as [Panopto-Video-DL](https://github.com/Panopto-Video-DL/Panopto-Video-DL-browser) does) and sends it to Hevanti, which downloads and transcribes it. For your own use only, under your institution's rules.
- **Exam prep:** a practice exam, a summary, flashcards and a formula sheet from all the lectures of a course (with the slides' text).
- **Recommended layout:** the lecture on two thirds of the screen, the AI on one third. Hevanti greys out the AI's window and its own windows in its screenshots, so an answer being written is never saved as a "new slide" and your chat stays out of the pictures.
- **Connect AI:** one button connects Claude for desktop, ChatGPT (Codex) or Gemini (Antigravity CLI, `agy`) to Hevanti through a small MCP server. Then you ask them directly in their own window, for example "What is he saying now?", and they read the last minutes and the slide themselves. The AI sees every course, including courses with no lectures yet.
- **The AI of each course:** one project per course in each AI, set up once on the course page. Every connector tool takes a `course`, so the AI in a course's project reads only that course. Each course folder holds `AGENTS.md` / `GEMINI.md` / `CLAUDE.md`, so Codex or `agy` opened in the folder knows the course by itself; Claude projects get their instructions with one "copy" click. A saved project link makes the course's AI buttons open that project, and the AI's window moves to the left third of the screen, beside the lecture.
- **Sync to the cloud (optional, off by default):** for AIs that cannot read your computer (a ChatGPT project, a Gem, Gemini Notebook), each course's "now" file (every ~12 seconds) and all its transcripts are copied into your own Google Drive or OneDrive folder, where those AIs read them through their Drive connection.
- **Floating window:** a small window that stays on top of the lecture: a question box at the top, then what is being said now, then the latest slide.
- **Without a connection:** ChatGPT, Gemini or Claude with one click. The question is copied together with the last five minutes, and the AI's desktop app opens if it is installed (found in the Windows Start menu); otherwise its website opens on a third of the screen. Another click brings the same window back, so the conversation goes on.
- **How to use:** a one-minute animated walkthrough inside the app (the "איך משתמשים?" button), drawn with the app's own parts rather than a video file.

## Download and install

**Windows:** download `Hevanti-Setup.exe` from the [latest release](https://github.com/pechter-roei41/hevanti/releases/latest) and run it. It installs for your user only (no administrator), with its own Python and every package inside; your lectures are kept in `Documents\הבנתי`. The same app as a folder: `Hevanti.zip` - extract it, double-click `Install`, then `Hevanti`.


Full guide (Hebrew): [the Hevanti guide](https://claude.ai/artifact/Rho2yLpowLsxqy1Zsw6QAD)

## Privacy

- Transcripts and screenshots stay on your computer. The app only listens on `127.0.0.1`.
- There is no Hevanti server. If you turn on Answer here, what you ask (the question, the last minutes of the transcript and the current slide) is sent to Google's Gemini API with your own key; with Formulas and handwriting, every saved slide too. The connector (`hevanti_mcp.py`) only reads files from the "הקורסים שלי" (My Lectures) folder, and only when your AI asks for them. What your AI reads is sent to its provider like any other conversation with it.
- "Sync to the cloud" is off until you turn it on; then your transcripts are copied to your own Google Drive / OneDrive.
- **Responsibility:** Hevanti is provided s is, without warranty of any kind (see [LICENSE](LICENSE)). Using it, including recording, transcribing and saving lectures and slides, is entirely the user's responsibility. **Each user must check the rules of their own institution and lecturer before using it.** The author and contributors are not liable for its use. Full policy: [CODE_SIGNING.md](CODE_SIGNING.md#privacy).

## How it is built

| File | What it does |
|---|---|
| `System/Program/live_transcribe.py` | Everything on the computer side: transcription ([faster-whisper](https://github.com/SYSTRAN/faster-whisper) with the Hebrew model from [ivrit.ai](https://huggingface.co/ivrit-ai)), screenshots, the local server, courses, YouTube and the AI connection |
| `System/Program/app.html` | The app (opens in the browser) |
| `System/Program/player.html` | The player for recorded lectures |
| `System/Program/ask.js` | The "ask AI" box |
| `System/Program/hevanti_mcp.py` | The AI connector (MCP server, standard library only): `now`, `transcript`, `slide`, `search`, `moment` (where a topic was explained), `lectures`, plus the prompts `exam`, `summary`, `find_moment` |
| `System/Program/course_terms.json` | Suggested glossary terms per course, matched by the course name. Corrections and new courses are welcome |
| `Install.bat`, `System/get_python.ps1`, `System/install_ocr.*` | Windows setup: the packages into Hevanti's own Python, and Tesseract with the Hebrew and English language files |
| `tools/build_zip.py` | Builds `Hevanti.zip` (with the embeddable Python) |
| `installer/hevanti.iss`, `tools/build_setup_dir.py` | `Hevanti-Setup.exe` (Inno Setup): per-user, its own Python with the packages inside |
| `tools/test_*.py` | Tests run on every push (`.github/workflows/tests.yml`) |
| `DECISIONS.md` | What was decided and why (Hebrew) |

New version: push a tag such as `v2.0-20261014` (same number, new build) or `v2.1`. GitHub Actions builds both ZIPs and attaches them to a release, and the app tells students that an update is available.

Code signing: see [Code signing policy](#code-signing-policy).

## Contributing and issues

Found a bug? [Open an issue](https://github.com/pechter-roei41/hevanti/issues) with a screenshot and `System\error_log.txt`. Pull requests are welcome, and a good first one is adding your course to `course_terms.json`: its name, the words its name may contain (`match`), and 20-30 terms, most important first.

## Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io), certificate by [SignPath Foundation](https://signpath.org) (applied for; until approved, Windows shows "Windows protected your PC" once).

- What is signed: `Hevanti-Setup.exe`, built from the tagged commit by the public [release workflow](.github/workflows/release.yml). Nothing built on a personal computer is signed.
- Committers and reviewers: [Roei Pechter](https://github.com/pechter-roei41). Approvers: [Roei Pechter](https://github.com/pechter-roei41).
- Privacy: this program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it. Details: [CODE_SIGNING.md](CODE_SIGNING.md#privacy).

## License

[MIT](LICENSE) © 2026 Roei Pechter. Third-party models and libraries are downloaded from their own sources and are subject to their own licenses. Lectures and slides belong to whoever created them: use them for personal study, according to your institution's policy.

# Hevanti (הבנתי)

**Ask during the lecture, mark what you didn't understand.** An open-source lecture companion for students on Windows.

> **Beta.** Hevanti is still being tested, and things may change or break. If something does not work, use "Report a problem" at the bottom of the home screen (or open an [issue](https://github.com/pechter-roei41/hevanti/issues)).

Hevanti writes down everything said in the lecture, in Hebrew or English, while it runs on your computer. Its core is two things:

- **The floating window.** A small button with the Hevanti logo sits at the edge of the screen (or press Ctrl+Alt+Q). It opens a small always-on-top window, also over a full-screen lecture: type a question, press Enter, and the answer is written under it, based on what the lecturer said in the last minutes and the slide on the screen. Formulas are drawn with KaTeX.
- **The marks.** One click on ★ ("important") or ? ("didn't understand"), also Ctrl+Alt+M, marks the moment without stopping to listen. After the lecture, the "my marks" tab of the lecture and of the course lists every mark with what was said just before it, jumps to that moment in the transcript, and can ask an AI to explain them all.

Everything else supports these two.

## Also in Hevanti

- **Live, recorded and YouTube lectures:** Zoom, a broadcast or anything playing on your computer; a file or a link (Drive, Dropbox, OneDrive, Zoom, Panopto through a bookmark); a YouTube video in YouTube's own player. Recordings open in a player synced with the transcript.
- **Answers inside Hevanti:** with the student's own free Gemini API key (Google AI Studio, no credit card). No Hevanti server. The key is stored encrypted (Windows DPAPI). Without a key, a question can be copied with the last five minutes to ChatGPT, Gemini or Claude in one click; with a key, those buttons stay hidden unless you turn them on in Settings, Advanced.
- **Slides:** a picture of every new slide or board, read offline with [Tesseract](https://github.com/tesseract-ocr/tesseract); with your own Gemini key, formulas and handwriting are read by Gemini as LaTeX (on by default once a key is saved; slides that are not clearly plain printed text (formulas, handwriting, pictures) are sent to Google - plain printed text is read on your computer; it can be turned off in Settings). Capture the whole screen, one window or a part of it, pause it, mosaic areas, delete pictures for good.
- **After the lecture:** one click for a summary, a mock exam or a formula sheet (and an explanation of the moments you marked). Every question and answer is kept in the lecture's folder (`שאלות ותשובות.md`).
- **Courses:** a folder per course in "הקורסים שלי", a course page (lectures, marks, and the syllabus and glossary that improve transcription: the course name and its terms are given to the model as hotwords), search across everything that was said, and suggested terms for 55 common courses ([`course_terms.json`](System/Program/course_terms.json)) that improve transcription.
- **Connect your own AI:** a small MCP server lets Claude for desktop, ChatGPT (Codex) or Gemini (`agy`) read the lecture themselves ("what is he saying now?"). Optional cloud sync copies transcripts to your own Google Drive or OneDrive for AIs that cannot read your computer.
- **Accessibility:** text and interface size, reading spacing, high contrast, no motion, screen-reader announcements, a keyboard-friendly floating window.
- **How to use:** a one-minute video inside the app (the "איך משתמשים?" button). What changed in each version: [`System/VERSION.txt`](System/VERSION.txt).

## Download and install

**Windows:** download `Hevanti-Setup.exe` from the [latest release](https://github.com/pechter-roei41/hevanti/releases/latest) and run it. It installs for your user only (no administrator), with its own Python and every package inside; your lectures are kept in `Documents\הבנתי`. The same app as a folder: `Hevanti.zip` - extract it, double-click `Install`, then `Hevanti`.


**Virus scan:** [`Hevanti-Setup.exe` 2.10 on VirusTotal](https://www.virustotal.com/gui/file/d0ff70d455d65493815d328eeb56486892ebb950556d05517db851b9bafc5a04/detection): none of the 62 engines that scanned it flagged it as malicious (6 could not process the file type and 6 timed out). SHA-256: `d0ff70d455d65493815d328eeb56486892ebb950556d05517db851b9bafc5a04`. The installer is not signed yet, so Windows may still show "Windows protected your PC" once. A scan describes one exact file; later releases are scanned again.

Full guide (Hebrew): [the Hevanti guide](https://claude.ai/artifact/Rho2yLpowLsxqy1Zsw6QAD)

## Privacy

- Transcripts and screenshots stay on your computer. The app only listens on `127.0.0.1`.
- There is no Hevanti server. Once you save your own Gemini key, two things go to Google's Gemini API: when you ask (Answer here), the question, the last minutes of the transcript, the text of earlier slides and the current slide; and, because reading formulas and handwriting is on by default with a key, every new slide picture that is saved. The second can be turned off in Settings, under the key. The connector (`hevanti_mcp.py`) only reads files from the "הקורסים שלי" (My Lectures) folder, and only when your AI asks for them. What your AI reads is sent to its provider like any other conversation with it.
- "Sync to the cloud" is off until you turn it on; then your transcripts are copied to your own Google Drive / OneDrive.
- **Responsibility:** Hevanti is provided as is, without warranty of any kind (see [LICENSE](LICENSE)). Using it, including recording, transcribing and saving lectures and slides, is entirely the user's responsibility. **Each user must check the rules of their own institution and lecturer before using it.** The author and contributors are not liable for its use. Full policy: [CODE_SIGNING.md](CODE_SIGNING.md#privacy).

## How it is built

| File | What it does |
|---|---|
| `System/Program/live_transcribe.py` | Everything on the computer side: transcription ([faster-whisper](https://github.com/SYSTRAN/faster-whisper) with the Hebrew model from [ivrit.ai](https://huggingface.co/ivrit-ai)), screenshots, the local server, courses, YouTube and the AI connection |
| `System/Program/app.html` | The app (opens in the browser) |
| `System/Program/player.html` | The player for recorded lectures |
| `System/Program/mini.html` | The small always-on-top question window (Ctrl+Alt+Q) |
| `System/Program/media/howto.mp4` | The explainer video on the how-to page (key, lecture, floating window, marks, course page). The lecture in it is ["פתרון משוואה דיפרנציאלית מסדר ראשון בעזרת הפרדת משתנים"](https://www.youtube.com/watch?v=F1_uOZeYLVE) by Dvir Ross, licensed [CC BY](https://creativecommons.org/licenses/by/3.0/); a short silent excerpt is shown with Hevanti's window over it |
| `System/Program/fonts/` | The two fonts of the app, Secular One and Assistant (SIL Open Font License, the licences are in the folder) |
| `System/Program/katex/` | [KaTeX](https://katex.org) (MIT), draws the formulas in the answers |
| `System/Program/ask.js` | The "ask AI" box |
| `System/Program/hevanti_mcp.py` | The AI connector (MCP server, standard library only): `now`, `transcript`, `slide`, `search`, `moment` (where a topic was explained), `lectures`, plus the prompts `exam`, `summary`, `find_moment` |
| `System/Program/course_terms.json` | Suggested glossary terms per course, matched by the course name. Corrections and new courses are welcome |
| `Install.bat`, `System/get_python.ps1`, `System/install_ocr.*` | Windows setup: the packages into Hevanti's own Python, and Tesseract with the Hebrew and English language files |
| `tools/build_zip.py` | Builds `Hevanti.zip` (with the embeddable Python) |
| `installer/hevanti.iss`, `tools/build_setup_dir.py` | `Hevanti-Setup.exe` (Inno Setup): per-user, its own Python with the packages inside |
| `tools/test_*.py` | Tests run on every push (`.github/workflows/tests.yml`); `test_core.py` and `test_core_ui.py` cover the core: the marks, the first-time consent, the ask box and the floating window |
| `DECISIONS.md` | What was decided and why (Hebrew) |

New version: push a tag such as `v2.0-20261014` (same number, new build) or `v2.1`. GitHub Actions builds both ZIPs and attaches them to a release, and the app tells students that an update is available.

Code signing: see [Code signing policy](#code-signing-policy).

## Contributing and issues

Found a bug? [Open an issue](https://github.com/pechter-roei41/hevanti/issues) with a screenshot and `System\error_log.txt`. Pull requests are welcome, and a good first one is adding your course to `course_terms.json`: its name, the words its name may contain (`match`), and 20-30 terms, most important first.

## Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io), certificate by [SignPath Foundation](https://signpath.org) (the first application was declined for lack of proof of users; the project will apply again once it has them. Until then the installer is not signed and Windows shows "Windows protected your PC" once).

- What is signed: `Hevanti-Setup.exe`, built from the tagged commit by the public [release workflow](.github/workflows/release.yml). Nothing built on a personal computer is signed.
- Committers and reviewers: [Roei Pechter](https://github.com/pechter-roei41). Approvers: [Roei Pechter](https://github.com/pechter-roei41).
- Privacy: Hevanti runs on your computer and sends information to other systems only in the cases listed in the [privacy policy](CODE_SIGNING.md#privacy-policy): your question to Google's Gemini with your own key, the model download, the update check and the page fonts.

## License

[MIT](LICENSE) © 2026 Roei Pechter. Third-party models and libraries are downloaded from their own sources and are subject to their own licenses. Lectures and slides belong to whoever created them: use them for personal study, according to your institution's policy.

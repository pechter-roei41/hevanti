# Hevanti (הבנתי)

Open-source (MIT) lecture companion for Israeli university students, Windows only. Beta (currently 2.17).

It transcribes a lecture on the student's computer (Hebrew or English, live or recorded), saves a picture of every new slide, and has two core features:
- **The floating window** (`mini.html`, Ctrl+Alt+Q, or the round button at the screen edge): always on top, also over a full-screen lecture. Type a question, get an answer based on the last minutes and the slide on screen. Three "what did I miss" buttons (3, 7, 15 minutes).
- **Marks:** one click on ★ (or Ctrl+Alt+M) marks the moment. Each mark is listed later with what was said just before it, and opens 8 seconds earlier (`MARK_LEAD_S`).

Answers come from Gemini, called straight from the student's computer with the student's own free API key. There is no Hevanti server, no AI of our own and no key of ours.

Read before larger changes:
- `PRODUCT.md`: users, purpose, positioning
- `DESIGN.md`: visual system ("The Open Notebook": cream paper, white cards, one green action, yellow only for marks and the logo)
- `DECISIONS.md`: what was decided and why (Hebrew, dated). **Add every new decision there.** It is the project's memory.
- `README.md`: features, privacy, file map
- `docs/distribution.md`: how it is spread. `docs/real-lecture-test.md`: the manual checklist before each release.
- `CODE_SIGNING.md`: signing and release policy (SignPath application was declined for lack of users; the installer is unsigned for now)

## Principles (do not break without asking Roei)

- **No server, no AI of our own.** Gemini through the student's key (stored encrypted, Windows DPAPI), or copy the question to the student's own AI app. A paid AI subscription does not give API quota, so subscribers work through their app, not through the key.
- **Privacy:** transcripts and screenshots stay on the computer. The server listens on `127.0.0.1` only, and commands need the page's `X-BZM: 1` header (another site cannot drive Hevanti). Nothing leaves without a student action. Cloud sync is off by default. No telemetry. "Report a problem" only shows text to copy (no key, no transcripts, no user name).
- **Works on an ordinary laptop:** no discrete GPU, little memory. No local AI model by default. Without a GPU, a small ivrit.ai Zipformer drafts what is being said right now (Hebrew live only).
- **Do not promise a price.** No "free" claims about Hevanti itself (decided 8.11.2026). Descriptions of Google's free key and quota are fine.
- **Do not invent what the lecturer said.** The tutor instructions say so, and the student's personal instructions (up to 500 characters) cannot override it.
- **Hebrew first, right-to-left.** UI and in-app guide in Hebrew; README, code comments and this file in English.
- **YouTube:** play in the official player inside the app. Never download.
- **Audio:** the computer's output only (WASAPI loopback), never the microphone.
- **Screenshots:** if the Hevanti window cannot be located (DWM frame), do not capture. Never guess. AI windows and Hevanti's own windows are painted grey so an answer is not saved as a slide.
- **Windows only** (decided 29.10.2026). No other platforms.
- **Liability:** provided as is. Each user checks their institution's and lecturer's rules. We keep no list of what is allowed where.
- **Most of the code was written with AI,** so tests and a real run before a release matter.

## How it runs

- `Hevanti.bat` (or the installed shortcut) starts `System/Program/live_transcribe.py --app`, which serves the app at `http://127.0.0.1:8765/` and opens it in Edge or Chrome app mode (`--app=`). A minimized black window stays open; closing it stops Hevanti. Nothing starts recording until the student presses a button.
- Server: standard-library HTTP server in `live_transcribe.py` (`AppServer`, `App`). The page talks to `/api/...`. One page runs everything.
- Transcription: faster-whisper with `ivrit-ai/whisper-large-v3-turbo-ct2`. Models go to `%PUBLIC%\whisper_models`. NVIDIA GPU is detected at start and offered as a one-time install; CPU otherwise. Course name and glossary terms are given to the model as hotwords.
- Slides: `ScreenWatcher` and `SlideJudge`. A slide is saved only when stable (live: about 6 seconds without movement), plus one picture when the student starts typing a question. OCR offline with Tesseract; formulas and handwriting go to Gemini as LaTeX, only for slides that are not clearly plain printed text.
- Gemini: the model that answers is picked by what responds today (checked once a day, cached in `gemini_models.json`, with the key's mark, not the key). Model names change often. Quota: a model that hit it rests a minute. Each question is logged without its content in `tokens.jsonl` under `%LOCALAPPDATA%\Hevanti`.
- Lecture sources: live (Hebrew or English), recorded (file, drag and drop, link; Panopto and others), YouTube (official player, `YtClock`/`YtNow`). Recordings play in `player.html`, which reports the position back.

## Where things live

- Data: installed with `Hevanti-Setup.exe` → `Documents\הבנתי` (an earlier ZIP library is kept if found); ZIP → next to `Hevanti.bat`. `BZM_DATA_DIR` overrides. Local state (browser profile of the floating window, usage counts, `data_dir.txt`) → `%LOCALAPPDATA%\Hevanti`.
- Library: `הקורסים שלי/<course>/<lecture>/` with `<lecture>.txt`, `שקופיות/`, and `שאלות ותשובות.md`. Per course: syllabus, glossary, and hidden `AGENTS.md`, `GEMINI.md`, `CLAUDE.md` for AI apps. `now_watching.txt` says what is happening right now. (Older name: `ההרצאות שלי`, renamed on first start.)
- Errors: `System/error_log.txt`; `System/loading_stuck.txt` only if loading the model hangs.

## Layout

- `System/Program/live_transcribe.py` (~9,300 lines): the whole computer side. Sections are marked with `# ----------` comments: settings, audio, model, QuickDraft, screenshots, OCR, MathReader (Gemini reads slides), the tutor, ScreenWatcher, YouTube, courses, AI connection, floating window and button, update check, recordings, the app and server, library, course guessing, `main`.
- `System/Program/app.html` (the app: top tabs בית · הקורסים שלי · איך משתמשים · הגדרות; views for live, YouTube, a saved lecture, a course), `mini.html` (floating window), `player.html` (recording player), `ask.js` (the ask box, shared). `media/howto.mp4` and its poster, `fonts/` (Secular One, Assistant, OFL), `katex/` (formulas).
- Settings page tabs (`SET_TABS` in `app.html`): תשובות · צילום וטשטוש · נגישות · מתקדם · פרטיות.
- `System/Program/hevanti_mcp.py`: MCP server, standard library only. Tools `now`, `transcript`, `slide`, `search`, `moment`, `lectures`; prompts `exam`, `summary`, `find_moment`. Every tool takes `course`. Claude for desktop, Codex and `agy` connect to it. Optional cloud sync (Google Drive / OneDrive) for AIs that cannot read the computer.
- `System/Program/course_terms.json`: suggested glossary per course name (55 courses).
- `System/VERSION.txt`: release notes in Hebrew, newest first. Setup and removal: `Install.bat`, `System/get_python.ps1`, `System/install_ocr.*`, `System/install_gpu.bat`, `System/uninstall.bat`.
- Packaging: `tools/build_zip.py`, `tools/build_setup_dir.py`, `installer/hevanti.iss` (Inno Setup). Workflows: `tests.yml`, `release.yml` (tag `v*` builds the ZIP and the installer), `installer-smoke.yml` (installs on a clean Windows runner).
- Design files for the Impeccable tool: `.impeccable/config.json`, `design.json` (shared). Private ones are ignored.

## The in-app guide ("איך משתמשים")

It lives in `app.html`, section `#vHow`, and is also published as an online artifact (`GUIDE_URL` in `live_transcribe.py`). Parts: video, חיבור לתשובות, בהרצאה, אחרי ההרצאה, מראה ונגישות, פרטיות, משהו לא עובד. The video has clickable chapters (`#howChapters`, timestamps in `data-t`) and credits Dvir Ross (CC BY). **When a feature, a button, a shortcut or a setting changes, update the guide, the README, `PRODUCT.md` and `VERSION.txt` in the same change.** The video must be re-recorded if the flow it shows changes. Keep the app's wording simple and in Hebrew, with as little English as possible.

Shortcuts (global, registered with `RegisterHotKey`): Ctrl+Alt+Q floating window, Ctrl+Alt+M mark ★, Ctrl+Alt+P pause screenshots (transcription continues).

## Testing

Plain Python scripts, no pytest. Each prints `all passed` or the failures and exits non-zero. Set `PYTHONUTF8=1` (Hebrew, Windows).

```
python -m pip install numpy pillow
python tools/test_core.py
python tools/test_mcp.py
python tools/test_course_ai.py
```

`.github/workflows/tests.yml` runs these on Windows and Linux: `test_core`, `test_mcp`, `test_course_ai`, `test_quota`, `test_youtube_rect`, `test_stop`, `test_panopto`, `test_live_loop`, `test_recording`, `test_course_guess`, `test_slides`, plus `test_av` (needs `av` and `faster-whisper`). `test_core_ui.py` needs Playwright and Edge, so it runs on Windows only.

Not in CI, run by hand on Windows: `test_mini_place.py` (opens a real window, needs Edge or Chrome), `test_quick_draft.py` (needs the Whisper model and a 60 s Hebrew clip), `bench_transcribe.py` (is transcription fast enough for live on this computer: below 1 means yes), `smoke_server.py` and `smoke_install.ps1` (an installed copy).

Tests cover logic, not a real lecture. Before a release, run `docs/real-lecture-test.md` on a real Windows computer. Run the relevant `tools/test_*.py` after every change and add a test for each bug fixed. If you touch the screenshots, the live loop, the marks or the floating window, say what you could and could not check without Windows.

## Conventions

- Follow `DESIGN.md` for any UI change: light and dark themes, and the accessibility options (text size, high contrast, no motion, screen reader, keyboard-friendly floating window).
- A change to the floating window must be checked at the screen edge, on a full-screen lecture, and with mixed display scaling.
- Be careful with Gemini quota: a new automatic call costs the student's free quota. Prefer the lite model for reading slides, and keep question context to the last 5 minutes.
- User-visible Hebrew should read as natural Israeli Hebrew.
- Never commit lecture folders (`הקורסים שלי/`, `ההרצאות שלי/`), `transcripts/`, `screenshots/`, `System/python/`, `mini-profile/`, or `.claude/`, `.agents/`, `.codex/`.
- Commits: short English subject. Releases are tags `v*` on `main`.

## Releasing a version

The version number is in several places; change them together:
1. `VERSION` and `VERSION_DATE` in `System/Program/live_transcribe.py` (the update check compares against the latest GitHub release, so never go below the current number).
2. `installer/hevanti.iss` (the comment line and `AppVersion`).
3. `System/VERSION.txt` (new "מה חדש" block on top, and the header line and date).
4. `README.txt` (the beta line).
5. README's VirusTotal line (version, link, hash) only after a new scan of the new installer.
6. A dated entry in `DECISIONS.md` for any decision behind the release.

Then run the tests, do the real-lecture checklist, and tag `v<version>`.

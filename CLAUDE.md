# Hevanti (הבנתי)

Open-source (MIT) lecture companion for Israeli university students, Windows only. Beta (currently 2.21: it holds 2.20 too, which was never released apart; the GitHub release v2.19 was published on 11.11.2026 from `main` at `b0e1dd5` (the tag `v2.19`; the history was rewritten on 12.11.2026, so older commit hashes quoted elsewhere no longer exist)).

It transcribes a lecture on the student's computer (Hebrew or English, live or recorded), saves a picture of every new slide, and has two core features:
- **The floating window** (`mini.html`, Ctrl+Alt+Q, or the round button at the screen edge, which stays while the window is open and turns to an X that closes it): always on top, also over a full-screen lecture. Type a question, get an answer based on the last minutes and the slide on screen. Three "what did I miss" buttons (3, 7, 15 minutes).
- **Marks:** one click on ★ (or Ctrl+Alt+M) marks the moment. Each mark is listed later with what was said just before it, and opens 8 seconds earlier (`MARK_LEAD_S`).

Answers come from Gemini, called straight from the student's computer with the student's own free API key. There is no Hevanti server, no AI of our own and no key of ours.

Read before larger changes:
- `PRODUCT.md`: users, purpose, positioning
- `DESIGN.md`: visual system ("The Open Notebook": cream paper, white cards, one green action, yellow only for marks and the logo)
- **Private notes, not in this repository (since 12.11.2026):** `TASKS.md` and `DECISIONS.md` live only on Roei's computer, in `C:\Users\רועי\hevanti-private\` (outside every repo, so they are never pushed). Read them from there; if that folder is not among the session's folders, ask Roei to add it. Never copy them into the repo, a worktree or a PR, and never quote their content in a commit message, PR text or public file.
  - `TASKS.md`: open work, split between Roei's tasks (what Claude cannot do) and Claude's. **Update it whenever a task opens or closes.**
  - `DECISIONS.md`: what was decided and why (Hebrew, dated). **Add every new decision there.** It is the project's memory.
  - The same folder holds `backup/` (git bundles and copies from before the files left the history). `.gitignore` lists both names, so a stray copy in the repo folder is never committed.
- `README.md`: features, privacy, file map
- `docs/distribution.md`: how it is spread. `docs/real-lecture-test.md`: the manual checklist before each release.
- `CODE_SIGNING.md`: signing and release policy (SignPath application was declined for lack of users; the installer is unsigned for now)

## Working copy and what goes to GitHub (since 12.11.2026)

- The repository was moved on 12.11.2026 (same name `pechter-roei41/hevanti`, clean history; the old one is the private `hevanti-old`, to be deleted by Roei). Work only in `hevanti-new`. Older folders (`hevanti-repo`, `hevanti-floating`, `hevanti-tasks`, `hevanti-untrack`) hold the old history: never push from them. Commit hashes from before that date no longer exist.
- **Push (in a branch and a PR):** code, tests, pages, `VERSION.txt`, `README.md`, `PRODUCT.md`, `DESIGN.md`, `CLAUDE.md`, `docs/`, `site/`.
- **Never push or put in a PR, commit message or public text:** `TASKS.md`, `DECISIONS.md` and anything copied or quoted from them (prices, plans for a paid product); lecture folders; keys. Roei's personal e-mail address must not appear in commits: commit with the GitHub no-reply address (`git config user.email` in this repository is set for that).
- Update the private `TASKS.md` and `DECISIONS.md` (see the first list above) as before: they are the project's memory, only not in the repository.
- Pushing is Roei's call; open a PR, do not merge or force-push without asking.

## Principles (do not break without asking Roei)

- **Settings and the key are saved whole or not at all.** `save_settings` writes a temporary file, then replaces, under one lock; a damaged `settings.json` is kept as `.corrupt` and the last good `.bak` is used, never read as "no settings" quietly. On Windows a key that cannot be encrypted (DPAPI) is **not saved** (`SecretError`, "לא הצלחתי להצפין את המפתח"); never add a quiet fall back to plain text.
- **No server, no AI of our own.** Gemini through the student's key (stored encrypted, Windows DPAPI), or copy the question to the student's own AI app. A paid AI subscription does not give API quota, so subscribers work through their app, not through the key.
- **Privacy:** transcripts and screenshots stay on the computer. The server listens on `127.0.0.1` only, and commands need the page's `X-BZM: 1` header (another site cannot drive Hevanti). Nothing leaves without a student action. Cloud sync is off by default. No telemetry. "Report a problem" only shows text to copy (no key, no transcripts, no user name); the student sends it themselves, in a GitHub issue, or in an e-mail when `REPORT_EMAIL` is set (a mail window opens and the text is on the clipboard: Hevanti sends nothing). `REPORT_EMAIL` is the support address of Hevanti (hevanti.support@gmail.com); if it is ever empty, no e-mail option is shown.
- **Works on an ordinary laptop:** no discrete GPU, little memory. No local AI model by default. Without a GPU, a small ivrit.ai Zipformer drafts what is being said right now (Hebrew live only).
- **Colour is computed, not estimated.** Colours come from `DESIGN.md`; `tools/contrast.py` and `tools/test_contrast.py` check that the pages use those tokens and that every pair keeps 4.5:1 (text) or 3:1 (graphic), light and dark. Add a pair there for any new colour combination. **One solid-green control per screen** ("answer here" on the live and lecture screens; the lecture card on home); the others are ghost buttons. Yellow is only the ★ mark (the star, and the `mark-line` band behind a marked transcript line) and the logo check; the `now-line` is the line being played or opened.
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

- `Hevanti.bat` (or the installed shortcut) starts `System/Program/live_transcribe.py --app`, which serves the app at `http://127.0.0.1:8765/` and opens it in Edge or Chrome app mode (`--app=`). What opens first: the quick-start window (`quick.html`, a small window in the middle of the screen with its own browser profile, titled "הבנתי · חלון התחלה מהירה" with the logo: course, or a new one made there, kind of lecture, "Start" runs the transcript in the background, "Open the app" shows the home screen) when `quick_start_wanted()` says so (Windows, the student agreed once, there is a key, no GPU install running or failed, nothing running, not turned off in the settings, no file or view asked for); otherwise the home screen, and the black window says why. A lecture that started with no course offers the course named on its first slide (`suggest_course_from_slide`, local Tesseract, offered in the small window and the live view, never applied by itself); the course of a recording lecture can be changed (`set_lecture_course`), and the lecture folder moves there when it is saved (`run_live`, after the end of the transcript is written). A minimized black window stays open; closing it stops Hevanti. Nothing starts recording until the student presses a button.
- Server: standard-library HTTP server in `live_transcribe.py` (`AppServer`, `App`). The page talks to `/api/...`. One page runs everything.
- Transcription: faster-whisper with `ivrit-ai/whisper-large-v3-turbo-ct2`. The sound waits in an `AudioQueue` with a ceiling (7,000 buffers, about 5 minutes; past it the oldest is skipped down to about the last minute, and Hevanti says how many seconds). The floating window shows "מאחר ב-N שניות" over 10 seconds, in the row of the answer button; it goes back to 0 when nothing waits to be transcribed. There is no automatic catch-up on the CPU yet (decided to wait for a measurement on a real laptop). Models go to `%PUBLIC%\whisper_models`. NVIDIA GPU is detected at start and offered as a one-time install; CPU otherwise. Course name and glossary terms are given to the model as hotwords.
- Slides: `ScreenWatcher` and `SlideJudge`. A slide is saved only when stable (live: about 6 seconds without movement), plus one picture when the student starts typing a question. OCR offline with Tesseract; formulas and handwriting go to Gemini as LaTeX, only for slides that are not clearly plain printed text.
- Gemini: the model that answers is picked by what responds today (checked once a day, cached in `gemini_models.json`, with the key's mark, not the key). Model names change often. Quota: a model that hit it rests a minute. A live question tries at most 2 models (`GEMINI_LIVE_MODELS`, plus the light one once more when the quota stopped them, and `PROBE_LIVE_S` = 8 s at most to find which models answer) and gives up within 25 s of waiting for the answer to start (90 s for a whole-lecture task); the start limit and the silence limit between pieces (45 s) are separate. A blocked or cut answer shows a ⚠ line with Google's reason. Each question is logged without its content in `tokens.jsonl` under `%LOCALAPPDATA%\Hevanti`.
- Lecture sources: live (Hebrew or English), recorded (file, drag and drop, link; Panopto and others), YouTube (official player, `YtClock`/`YtNow`). Recordings play in `player.html`, which reports the position back.

## Where things live

- Data: installed with `Hevanti-Setup.exe` → `Documents\הבנתי` (an earlier ZIP library is kept if found); ZIP → next to `Hevanti.bat`. `BZM_DATA_DIR` overrides. Local state (browser profile of the floating window, usage counts, `data_dir.txt`) → `%LOCALAPPDATA%\Hevanti`.
- Library: `הקורסים שלי/<course>/<lecture>/` with `<lecture>.txt`, `שקופיות/`, and `שאלות ותשובות.md`. Per course: syllabus, glossary, and hidden `AGENTS.md`, `GEMINI.md`, `CLAUDE.md` for AI apps. `now_watching.txt` says what is happening right now. (Older name: `ההרצאות שלי`, renamed on first start.)
- Errors: `System/error_log.txt`; `System/loading_stuck.txt` only if loading the model hangs.

## Layout

- `System/Program/live_transcribe.py` (~9,300 lines): the whole computer side. Sections are marked with `# ----------` comments: settings, audio, model, QuickDraft, screenshots, OCR, MathReader (Gemini reads slides), the tutor, ScreenWatcher, YouTube, courses, AI connection, floating window and button, update check, recordings, the app and server, library, course guessing, `main`.
- `System/Program/app.html` (the app: top tabs בית · הקורסים שלי · איך משתמשים · הגדרות; views for live, YouTube, a saved lecture, a course), `mini.html` (floating window), `quick.html` (quick-start window), `player.html` (recording player), `ask.js` (the ask box, shared). `media/howto.mp4` and its poster (made by `tools/make_howto.py`), `fonts/` (Secular One, Assistant, OFL), `katex/` (formulas).
- Settings page tabs (`SET_TABS` in `app.html`): מפתח · התאמת התשובות · צילום וטשטוש · נגישות · מתקדם · פרטיות.
- `System/Program/hevanti_mcp.py`: MCP server, standard library only. Tools `now`, `transcript`, `slide`, `search`, `moment`, `lectures`; prompts `exam`, `summary`, `find_moment`. Every tool takes `course`. Claude for desktop, Codex and `agy` connect to it. Optional cloud sync (Google Drive / OneDrive) for AIs that cannot read the computer.
- `System/Program/course_terms.json`: suggested glossary per course name (55 courses).
- `System/VERSION.txt`: release notes in Hebrew, newest first. Setup and removal: `Install.bat`, `System/get_python.ps1`, `System/install_ocr.*`, `System/install_gpu.bat`, `System/uninstall.bat`.
- Packaging: `tools/build_zip.py`, `tools/build_setup_dir.py`, `installer/hevanti.iss` (Inno Setup). Workflows: `tests.yml`, `release.yml` (tag `v*` builds the ZIP and the installer), `installer-smoke.yml` (installs on a clean Windows runner; runs only when `installer/**`, the setup build/smoke tools or the workflow change, so a merge of pages-only changes does not start it, use `gh workflow run installer-smoke.yml --ref <branch>`).
- Design files for the Impeccable tool: `.impeccable/config.json`, `design.json` (shared). Private ones are ignored.

## The in-app guide ("איך משתמשים")

It lives in `app.html`, section `#vHow`, and is also published as an online artifact (`GUIDE_URL` in `live_transcribe.py`). Parts: video, חיבור לתשובות, בהרצאה, אחרי ההרצאה, מראה ונגישות, פרטיות, משהו לא עובד. The video has clickable chapters (`#howChapters`, timestamps in `data-t`) and credits Dvir Ross (CC BY). **When a feature, a button, a shortcut or a setting changes, update the guide, the README, `PRODUCT.md` and `VERSION.txt` in the same change.** The video must be re-recorded if the flow it shows changes. Keep the app's wording simple and in Hebrew, with as little English as possible.

Shortcuts (global, registered with `RegisterHotKey`): Ctrl+Alt+Q floating window, Ctrl+Alt+M mark ★, Ctrl+Alt+P pause screenshots (transcription continues). The action of a shortcut and its beep run on their own thread, so a slow one cannot stop the listening. A mark made with the keyboard shows "★ סומן" in the small window (`APP.mark_n` in `/api/app`) or above the round button when the small window is closed (a native window drawn with Pillow). The round button now stays for as long as Hevanti runs (`mini_button_wanted` is true unless the setting is off; 12.11.2026); the red dot shows only a live lecture being recorded. While it is on, closing the app window does not close Hevanti (`_button_keeps_running`): it closes with the black window. "התחלת הרצאה חדשה" in the small window closes the small window and opens the quick-start window on the side. A small window left open from an earlier run reloads itself (`RUN_ID`).

## Running the app to check the UI (works on Linux)

The server and every page run on Linux; only the Windows-specific parts (hotkeys, the floating button, DPAPI, window capture, audio capture) do not. Verified on 10.11.2026 with a seeded library:

```
mkdir -p /tmp/h/data/"הקורסים שלי"/"קורס בדיקה"/"הרצאה 1" /tmp/h/local
# put a "<lecture>.txt" with lines like "[09:01:00 | +0:01:00] text" in the lecture folder
PYTHONUTF8=1 BZM_NO_BROWSER=1 BZM_DATA_DIR=/tmp/h/data LOCALAPPDATA=/tmp/h/local python3 System/Program/live_transcribe.py --app &
```

Then open `http://127.0.0.1:8765/` (and `/mini` for the floating window) with Playwright (`require('playwright')`, Chromium, no install needed in the cloud container). Notes:
- First load shows the "בואו נתחיל" modal over everything; click "לא עכשיו" or nothing else is clickable.
- Top tabs are `[data-nav="home|courses|how|settings"]`; settings tabs are `#setTabs > *`; the course page opens from the "דף הקורס" button on the home page; the guide's video chapters are `#howChapters button`.
- Without a Gemini key the home page says "חסר מפתח Gemini". No network or model is needed to render any page.
- The console output looks reversed on Linux (Hebrew without bidi), which is harmless.
- Stop it with `pkill -f "live_transcribe.py --app"`. A real lecture, the transcript, the answers and the Windows features cannot be checked this way.

## The how-to video

`System/Program/media/howto.mp4`: 63 s, 1920x1080, **no audio**, version 2.20 (recorded again on 12.11.2026). A dark caption bar on top carries one Hebrew sentence per chapter, word for word the same as `#howChapters` in `app.html`, and every chapter is zoomed on the action. Chapters (`data-t` seconds): 0 key, 5 quick-start window, 9 live transcript and screenshots, 15 full screen and the green round button, 20 click the button and ask, 25 answer, 31 "what did I miss" (7 minutes), 38 mark ★ and close the window, 43 course page (three tabs), 47 marks, 51 privacy (two sentences), 58 summary slide "בקיצור: ארבעה צעדים". The lecture is "פתרון משוואה דיפרנציאלית מסדר ראשון בעזרת הפרדת משתנים" by Dvir Ross (CC BY), the course "חשבון אינפיניטסימלי 2".

How it is made (`tools/make_howto.py`, Windows only; needs ffmpeg, Playwright and Edge):
- `python tools/make_howto.py record`: builds a clean sandbox (library with one course, copy of the settings in a temp folder, light theme, no update check; `BZM_DATA_DIR` and `LOCALAPPDATA` point there, the real library and the key are never touched or shown), plays the lecture full screen on the main screen, records the main screen with ffmpeg (`gdigrab`, `h264_nvenc`), starts Hevanti, presses Start in the quick-start window, the round button and "7 דק'" with a simulated mouse (`tools/howto_win.py`), types the question, marks with Ctrl+Alt+M, stops, and records the app pages. About 11 minutes, with sound (Hevanti hears the lecture); the footage and `events.json` are written to `%TEMP%\hevanti-howto\out`.
- `python tools/make_howto.py build`: raw footage plus `tools/howto/captions.json` (text, length, zoom crop per chapter) into `howto_draft.mp4`, a still per chapter and `chapter_times.json`. **Changing a caption does not need a new recording.** The poster is a frame at about 28 s (`ffmpeg -ss 28 ... -vf scale=1280:720`).
- While recording, the person must work on the second screen, keep their hands off the mouse and keep the speakers on. The tool never moves or minimizes the user's windows; it only notes (and `build` warns about) another window on the recorded screen. Check the frames for anything personal before replacing the video. Not checked: display scaling other than 125%, and the tool on more than one monitor layout.

If the flow it shows changes (a button, the quick-start window, the floating window, the course page tabs), record again and update the chapters.

## Testing

Plain Python scripts, no pytest. Each prints `all passed` or the failures and exits non-zero. Set `PYTHONUTF8=1` (Hebrew, Windows).

```
python -m pip install numpy pillow
python tools/test_core.py
python tools/test_mcp.py
python tools/test_course_ai.py
```

`.github/workflows/tests.yml` runs these on Windows and Linux: `test_core`, `test_contrast` (colours and contrast, computed from DESIGN.md), `test_settings` (saving settings and the key, deleting every copy of it), `test_gemini` (every error Google gives, a stream that stops or is cut, the limits), `test_ai_flow` (the question to Gemini from the sound to the answer, with a made-up Gemini), `test_mcp`, `test_course_ai`, `test_quota`, `test_youtube_rect`, `test_stop`, `test_panopto`, `test_live_loop`, `test_recording`, `test_course_guess`, `test_slides`, plus `test_av` (needs `av` and `faster-whisper`). `test_core` also covers the quick-start decision and its commands, the floating button and the report; `test_core_ui.py`, `test_design3.py` (the decisions of design round 3 stay: one solid green at home, two selected shapes, the lecture menu, the split settings tabs, the report dialog holds the tool's messages), `test_narrow.py` (320 px: no sideways scroll on any screen, light and dark; the focus ring of the floating window) and `test_ai_flow_ui.py` (the page offers ChatGPT/Gemini/Claude when the quota is used up) need Playwright and Edge, so they run on Windows only; elsewhere set `HEVANTI_TEST_CHROMIUM=<path to a Chromium>` and install the `playwright` Python package.

`tools/review_design.py` is a measurement review (overflow at narrow widths and at larger text, click targets under 24 px, controls with no name, focus rings, text contrast from the real colours; made-up data, changes nothing): run it before a design round.

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
6. A dated entry in the private `DECISIONS.md` (see above) for any decision behind the release.

Then run the tests, do the real-lecture checklist, and tag `v<version>`.

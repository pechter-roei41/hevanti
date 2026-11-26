# Changelog

Short, in English. The full notes, in Hebrew, newest first, are in `System/VERSION.txt` (the app shows them too). The released
version is on [GitHub Releases](https://github.com/pechter-roei41/hevanti/releases); 2.20 and 2.21 were never released apart.

## Unreleased

- **Floating window, short window:** before the first question the example questions no longer run over the question box when the window is
  short or the text is large. The empty state now shrinks with the free height (a size container on `.convwrap`: the question mark goes first,
  then the small line, then the second example) and scrolls as a last resort (`min-height: 0`, `justify-content: safe center`). A test in
  `tools/test_mini_send.py` checks five window heights and fails without the change.

## 2.24 (26.11.2026)

- **The end of what was said is written when the sound stops:** when the speakers go completely idle (a paused video, a lecturer who stopped
  while Zoom sends nothing) the loopback delivers no audio at all, so the last, half-filled piece waited for the next sound: in a real English
  lecture the final sentence came a minute late, with a false "late by 60 seconds" and "close heavy programs" warning. After
  `IDLE_FLUSH_S` (4 s, `LT_IDLE_FLUSH_S` for tests) with no sound at all, the waiting piece is transcribed. `tools/test_live_loop.py` has a
  test that fails without the change. `tools/bench_transcribe.py` now wraps PyAV's `av.open` before decoding, like the app.

## 2.23 (26.11.2026)

- **Also in 2.23:** a long course name no longer pushes the ★ and menu to a second row; the "new conversation" link under the box is gone (it is in the ⋯ menu); one name, "the floating window", everywhere; a lecture starts only when its transcription model is on the computer (the quick-start window offers the download and shows its progress); home: the marks button is its own button, "all courses" is a pill, hover and focus states; the settings tip stays closed after the X; closing the black window stops the floating and quick-start windows too; the installer is in Hebrew regardless of the Windows language; uninstall leaves other programs' folders alone.

- **New demo video:** `System/Program/media/teaser.mp4` and `site/assets/teaser.mp4` (with their posters) were filmed again on a test copy
  with the new floating window: the round button over a full-screen lecture, a question and its answer, "what did I miss" for 7 minutes,
  a ★ and the lecture page with the mark. 35 s, 1920x1080 (was 1280x720), no audio, captions, 4.5 MB. The lecturer's face is blurred.
- **Cut answers are said to be cut:** a Gemini stream that ends with words but no `finishReason` (Gemini closes every whole answer with
  one; its streams give no size, so the old "shorter than promised" check never fired) now shows "⚠ התשובה נקטעה" and is not saved to
  "שאלות ותשובות.md" or counted as a good answer in `tokens.jsonl`. Google's `error` event inside a stream is no longer skipped: before
  the first word it is said like the same HTTP error (`_gemini_error`), after it "Gemini stopped in the middle". Seen in a real run on
  25.11.2026 (33 tokens, cut in the middle of a word). Tests in `test_gemini.py`; the fake streams in other tests now end with STOP.
- **Share image (WhatsApp, link previews):** `site/assets/og-share.png` (1200x630, 122 KB) says "a floating window over the lecture" like the page title, with the floating window and an answer. It has a new file name so apps that cached the old picture fetch the new one; the old `og.png` is gone.
- **Floating window answers:** a question typed in English keeps its question mark at the end (`dir="auto"` on the question bubble); the
  times in an answer are small pills with a drawn clock instead of an emoji and a monospace run (soft green and clickable when the page can
  open the transcript there, an outlined grey chip when it cannot); the conversation sits just above the question box (`align-content: safe end`).
- **Landing page (`site/index.html`):** the title is "a floating window over the lecture"; the video comes first; three setup steps and the
  "Windows protected your PC" note sit under the download button; the demo window invites a click; a download bar for phones with "copy
  the link for my computer"; repeated icon cards became ruled rows; no eyebrow labels; neutral shadows; selection and scrollbar colours.
  It goes to Netlify by hand, separately.
- **Longer pieces on the CPU:** with no graphics card, a Hebrew live lecture with the quick draft is written in 20-28 s pieces instead of
  10-18 s (`CPU_MIN_CHUNK_S` / `CPU_MAX_CHUNK_S`, `LT_CPU_MIN_CHUNK_S` / `LT_CPU_MAX_CHUNK_S` for tests; never over Whisper's 30 s window).
  Measured on an i5-1235U with `tools/bench_chunks.py`: 0.82 vs 0.50 seconds of work per second of lecture, the same words. Without the
  quick draft (still loading, or it failed), English and YouTube, the short pieces stay; a graphics card is untouched.
- **"Running late" on the CPU** shows only when the lag passes the longest piece plus 5 s (`/api/live` carries `lag_show`); a graphics card
  keeps 10 s. The note to the AI about seconds not yet transcribed now counts the sound still waiting in the queue.

## 2.22 (19.11.2026)

- **Home by state:** the home page shows what matters now, in one of four states with one solid-green action each: the first time
  (connect the answers, then a first lecture; replaces the "let's start" popup), a lecture running (time, the last three lines, the
  marks so far, the last slide, floating window, ★, stop), a lecture just saved (its marks, each opening 8 s before), and a regular day
  (continue where you stopped, my courses, the last three lectures). Home never starts a lecture: every "start a lecture" opens the
  quick-start window. At most one bar shows above the state.
- **Floating window redesign:** the title row is the course (with the recording dot), a yellow ★ and a "⋯" button at the left corner that opens a
  menu: new conversation (only while the box holds one; it clears it), to the app, stop recording (with no lecture: start a new lecture) and close Hevanti (stop and close still ask twice). "Answer here" takes
  the full width of its row; the "behind by N seconds" pill (with a clock) sits at its left and explains itself when pointed at. The menu
  works with the keyboard (Enter/Space, arrows, Esc). "To the app" shows the app on the lecture screen (live, YouTube, or the recording's
  player), using the open app window if there is one.
- **Small fixes:** the white "go through the marks" button (now a button of its own: it opens the lecture's marks list, the card opens the first mark) on the home page's green card shows only when the lecture has marks, at its
  own width; "start a lecture" at home minimizes the app only after the quick-start window has drawn its page, so there is no blank
  moment between them.
- **"Open the app" in the quick-start window:** with the app already open (for example minimized after "start a lecture" at home) it
  brings that window back instead of opening another one each time.
- **"Paste a key" in the floating window:** with the app already open, the open window goes to the settings (and comes back from the
  taskbar if minimized) instead of a second app window opening.
- **YouTube slides:** saved again. Since each screen of the app has its own window title ("<screen> · הבנתי"), the player's window
  was not found and no slide was saved; found on a real Windows run.
- **Floating window and quick start:** stopping from the
  floating window (two presses) with a "saved" card; the round button stays while Hevanti runs; opens smoothly the first time and
  follows light/dark at once; the opacity slider is the right way round.
- **After the lecture:** a "questions and answers" tab per lecture; every ★ is a question that was put off, with one button to explain
  the moment; under each answer, a closed "what is this based on" row that opens and closes on a click (the slide that was sent and the transcript lines).
- **Answers:** a very short answer first, "more detail" or "give an example" to widen it; the whole lecture text is cut with a notice
  when it is too long for one question (the last part for a question, the first for a whole-lecture task); an empty answer goes on
  to the next model; a network that interferes with the secure connection is named instead of "no internet".
- **Screens:** with more than one screen the lecture's screen is found from the windows in view, and one-window mode finds its window
  on any screen.
- **Security and data:** the pages are given only to a browser that came from Hevanti (a secret per run); models live in the user's
  own folder and are pinned by SHA-256; a damaged settings file is restored from the last good copy (and the student is told, also when
  the key is gone); uploads never overwrite another recording; a failed rename keeps the lecture; one-click backup of the library.
- **Accessibility:** text size, reading spacing and contrast reach the small windows; no text under 14 px; a screen reader says which
  transcript line is marked.
- **Logo:** the letter ה in the speech bubble; yellow only for ★.
- Many fixes from two independent reviews (see `System/VERSION.txt`).

## 2.20 / 2.21

- Quick-start window, the redesigned round button with a red recording dot, stopping from the floating window, a course guessed
  from the first slide, "send by e-mail" in the problem report, one solid green action per screen.

## 2.19

- ★ is the only mark (the old "?" is still read); the highlighter band on the marked line; the "what I missed" buttons (3, 7, 15 minutes);
  the problem report; the GPU capsule; calmer colours and spacing.

## 2.18

- Settings and the key are saved whole or not at all, and a key that cannot be encrypted is not saved; clearer Gemini errors; a live
  question tries at most two models and gives up in about 25 seconds; the delay of the transcript is shown.

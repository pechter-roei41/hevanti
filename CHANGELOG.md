# Changelog

Short, in English. The full notes, in Hebrew, newest first, are in `System/VERSION.txt` (the app shows them too). The released
version is on [GitHub Releases](https://github.com/pechter-roei41/hevanti/releases); 2.20 and 2.21 were never released apart.

## 2.22 (beta, not released yet)

- **Home by state:** the home page shows what matters now, in one of four states with one solid-green action each: the first time
  (connect the answers, then a first lecture; replaces the "let's start" popup), a lecture running (time, the last three lines, the
  marks so far, the last slide, floating window, ★, stop), a lecture just saved (its marks, each opening 8 s before), and a regular day
  (continue where you stopped, my courses, the last three lectures). Home never starts a lecture: every "start a lecture" opens the
  quick-start window. At most one bar shows above the state.
- **YouTube slides:** saved again. Since each screen of the app has its own window title ("<screen> · הבנתי"), the player's window
  was not found and no slide was saved; found on a real Windows run.
- **Floating window and quick start:** stopping from the
  floating window (two presses) with a "saved" card; the round button stays while Hevanti runs; opens smoothly the first time and
  follows light/dark at once; the opacity slider is the right way round.
- **After the lecture:** a "questions and answers" tab per lecture; every ★ is a question that was put off, with one button to explain
  the moment; under each answer, "what is this based on" (the slide that was sent and the transcript lines).
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

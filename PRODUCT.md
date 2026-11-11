# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

(Windows desktop app; the UI is a local page served on 127.0.0.1 and opened in the browser. Hebrew, right-to-left first; English also supported.)

## Users

Israeli university students, mostly on an ordinary laptop (no discrete GPU assumed). They use Hevanti during a lecture (live, Zoom, recorded or YouTube) or after it, to ask questions about what was just said and to mark moments they did not understand.

## Product Purpose

Hevanti (הבנתי) is a lecture companion. It transcribes lectures on the student's computer in Hebrew or English and saves a picture of every new slide or board. Two things sit at the core:

- A small always-on-top floating window (Ctrl+Alt+Q), also over a full-screen lecture: type a question and get an answer based on the last minutes of the lecture and the slide on screen.
- One-click marks (★ only, since 2.13; Ctrl+Alt+M) that mark the moment without stopping to listen, then list every mark with what was said just before it. In a transcript the line said just before the mark carries a highlighter band, a ★ and the words "מסומנת" for a screen reader. "?" marks from older lectures are still read and shown, with the same band.
- A quick-start window in the middle of the screen when Hevanti opens: the course (guessed from a window title or the weekly schedule, never silently) and the kind of lecture, then "start" runs the transcript in the background; the home screen stays one click away and is what a first start, a missing key or a GPU problem shows.
- Three "what did I miss" buttons (3, 7, 15 minutes) in the floating window, and answers that cite the time of the transcript line they rely on (a link only when the page can open that line).

Success is measured by study time saved, number of users, and being a project worth showing.

## Positioning

Free and open source (MIT), with no Hevanti server and no model of its own. The AI inside Hevanti is Google's Gemini, called with the student's own free API key (Google AI Studio, no credit card): when the student asks, Hevanti sends the question, the last minutes of the transcript and the current slide to Gemini and shows the answer under the question; it also reads formulas and handwriting on slides through Gemini. The key is stored encrypted on the student's computer. Transcripts and slides otherwise stay on the student's computer. Without a key, the question plus the last five minutes can be copied to ChatGPT, Gemini or Claude. A small MCP server lets the student's own AI app read the lecture directly.

## Operating Context

During a live lecture the student is listening, so interactions must be quick and non-disruptive. After a lecture: summary, mock exam, formula sheet, explanation of marked moments. Lectures live in a folder per course in "הקורסים שלי"; each course has a page with lectures, marks, syllabus and glossary (glossary terms improve transcription). Also: search across everything said, recorded lectures in a player synced with the transcript, optional cloud sync to the student's own Google Drive or OneDrive.

## Capabilities and Constraints

- Must work on an average student laptop; no local AI model by default.
- Transcription runs on the CPU by default and is much faster and keeps pace with long lectures on an NVIDIA graphics card. Hevanti detects the card at start-up; when it is there but unused, the home page offers a one-click install of the NVIDIA libraries (about 1 GB, once) and a restart, and on every other page a capsule in the top bar offers the same install (never both at once; with no card, or a card in use, there is no capsule and no device pill). Anyone with an NVIDIA card should be steered to it. There is no "is my computer good enough" checklist: the guide only recommends the card.
- The built-in AI is Gemini, through the student's own API key (stored encrypted via Windows DPAPI; a key that cannot be encrypted is not saved): without a key there is no "answer here", so the interface must make that state and its fix obvious. When the free quota runs out: reduce usage and show a clear message.
- Settings and the key are saved whole or not at all; a damaged settings file is kept and the last good copy is used, never read as "no settings" quietly.
- A live question tries at most two Gemini models and gives up within about 25 seconds; an answer that Gemini blocks or cuts shows why.
- Transcription that falls far behind is protected: the floating window shows the delay in seconds over 10, and sound that waited more than about five minutes is skipped and said so. No automatic catch-up yet (to be decided after measuring on a real student laptop).
- Nothing leaves the computer without a student action; cloud sync is off until turned on; the app listens only on 127.0.0.1.
- Only computer audio is captured, not the microphone.
- YouTube plays in YouTube's own player, never downloaded.
- Formulas are rendered with KaTeX.
- Undecided: possible paid tier in the future.

## Brand Commitments

Name הבנתי / Hevanti and its logo: one mark everywhere (green speech bubble with a short tail and a thick yellow check; drawn the same in the app and player headers, favicon, floating button, installer icon, web guide and video). No second small-size variant. Hebrew first: interface and guide in Hebrew, GitHub README in English. App fonts are Secular One and Assistant (existing assets).

## Evidence on Hand

Real code, tests (`tools/test_*.py`), a one-minute how-to video (`System/Program/media/howto.mp4`, footage of the current interface), a beta release, the in-app guide ("איך משתמשים") and a public web guide (a claude.ai Artifact linked from the README). No proof of a large user base yet (the code-signing application was declined for lack of it); do not fabricate user counts or testimonials.

## Product Principles

1. The student is listening: every in-lecture interaction must cost seconds and no attention.
2. Privacy by default: local first, no server, consent before anything is sent.
3. Hebrew and right-to-left are the primary experience, not a translation.
4. Works on the average student's laptop and free tools.
5. The AI is Gemini through the student's own key: Hevanti holds no model, no server and no key of its own.

## Accessibility & Inclusion

Existing features to preserve: adjustable text and interface size, reading spacing, high contrast, no-motion mode, screen-reader announcements, keyboard-friendly floating window.

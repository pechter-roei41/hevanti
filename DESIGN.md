---
name: Hevanti (הבנתי)
description: A lecture companion that looks like an open notebook: cream paper, white cards with a hairline, one green action, yellow only for marks and the logo.
colors:
  paper: "#F6F3E9"
  sheet: "#FFFFFF"
  sunk-paper: "#ECE7D8"
  ink: "#17261F"
  ink-muted: "#56625B"
  hairline: "#DDD7C4"
  board-green: "#1B6E4B"
  board-green-soft: "#DCEBDF"
  highlighter: "#F7D44C"
  recording-red: "#C2412D"
  caution-paper: "#FBF0DA"
  caution-ink: "#6B5020"
  now-line: "#FBEFB5"
  mark-line: "#F7DD7B"
  night-paper: "#1C1B16"
  night-sheet: "#26241D"
  night-sunk: "#2F2C23"
  night-ink: "#F1ECDF"
  night-muted: "#B5AFA0"
  night-hairline: "#3E3A2E"
  night-green: "#5BC79A"
  night-green-soft: "#25382B"
  night-highlighter: "#E8C547"
  night-recording: "#FF7A63"
  night-mark-line: "#594E25"
typography:
  display:
    fontFamily: "Secular One, Assistant, Segoe UI, sans-serif"
    fontSize: "clamp(28px, 4.2vw, 40px)"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Secular One, Assistant, Segoe UI, sans-serif"
    fontSize: "26px"
    fontWeight: 400
    lineHeight: 1.2
  title:
    fontFamily: "Assistant, Segoe UI, Arial Hebrew, Arial, sans-serif"
    fontSize: "18px"
    fontWeight: 800
    lineHeight: 1.3
  body:
    fontFamily: "Assistant, Segoe UI, Arial Hebrew, Arial, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Assistant, Segoe UI, Arial Hebrew, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1.4
  code:
    fontFamily: "Consolas, Cascadia Mono, ui-monospace, monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  sm: "5px"
  md: "12px"
  lg: "14px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "10px"
  md: "14px"
  lg: "22px"
components:
  button-primary:
    backgroundColor: "{colors.board-green}"
    textColor: "{colors.sheet}"
    rounded: "{rounded.md}"
    padding: "9px 18px"
  button-ghost:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.board-green}"
    rounded: "{rounded.md}"
    padding: "7px 15px"
  card:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "16px 18px"
  card-primary-action:
    backgroundColor: "{colors.board-green}"
    textColor: "{colors.sheet}"
    rounded: "{rounded.lg}"
    padding: "22px"
  pill:
    backgroundColor: "{colors.sunk-paper}"
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.pill}"
    padding: "3px 12px"
---

# Design System: Hevanti (הבנתי)

## Overview

**Creative North Star: "The Open Notebook"**

Hevanti is designed to sit on a page, not on a screen. The ground is cream paper, the surfaces are white sheets with a hairline edge, the headings are set in a warm, rounded Hebrew display face, and exactly one thing per screen is allowed to be solid green: the next action. Yellow is the highlighter: it marks a moment (★) and it is the check in the logo, and it is used nowhere else.

The student is listening to a lecture while using it, so the system is quiet. Surfaces are flat, spacing is generous, and the interface never competes with the lecture. The dark theme keeps the same paper feeling: warm brown-black ground and warm ink, not the cold green-black of a code editor. Right-to-left Hebrew is the primary reading direction, and every layout is built for it first.

**Key Characteristics:**
- One solid-green action per screen; everything else is a hairline outline or a quiet fill.
- Flat by default: tonal layers and a 1px hairline, one soft shadow for the primary action only.
- Hebrew first and right-to-left: empty text boxes start at the right, shortcut keys stay left-to-right.
- Warm in both themes: cream paper by day, warm dark paper at night.
- One logo, drawn the same at every size: a bubble with a short tail and a thick check.

## Colors

A cream-and-board-green palette with a highlighter yellow. Neutrals lean warm; the single accent is a deep board green.

### Primary
- **Board Green** (#1B6E4B, night #5BC79A): the one action per screen, selected states, links, the logo bubble. Text on it is white by day and a near-black green (#0E1A14) at night.
- **Board Green Soft** (#DCEBDF, night #25382B): icon plates, selected tabs, the quiet banner behind a suggestion (for example "install the NVIDIA libraries").

### Secondary
- **Highlighter** (#F7D44C, night #E8C547): the ★ mark, the highlighter band over a transcript line the student marked (the **Mark Line** token, #F7DD7B, night #594E25: the highlighter at 70% over paper, and at 30% over the night paper; text on it stays ink), and the check in the logo. Never a button, never decoration.

### Tertiary
- **Recording Red** (#C2412D, night #FF7A63): a lecture in progress (the pill and the pulsing dot), and destructive actions.

### Neutral
- **Paper** (#F6F3E9, night #1C1B16): the page ground.
- **Sheet** (#FFFFFF, night #26241D): cards and the top bar.
- **Sunk Paper** (#ECE7D8, night #2F2C23): inset fills, pills, empty-state bars.
- **Ink** (#17261F, night #F1ECDF) and **Ink Muted** (#56625B, night #B5AFA0): text. Muted text keeps at least 4.5:1 on paper, sheet and sunk paper.
- **Hairline** (#DDD7C4, night #3E3A2E): every card edge and divider.
- **Caution Paper / Ink** (#FBF0DA / #6B5020): a missing key or a warning, as a pill with a text link.
- **Now Line** (#FBEFB5): the line currently spoken in a transcript.

### Named Rules
**The One Green Rule.** On any screen, only one control is solid green. Everything else, however useful, is a ghost button or a text link.

**The Highlighter Rule.** Yellow means "marked by the student" or "this is the logo". On a marked transcript line it is the highlighter band behind the line; it is never used as a button, a card background or an accent. A mark never relies on yellow alone: the line also carries ★ and the words "מסומנת" for the screen reader.

## Typography

**Display Font:** Secular One (with Assistant, Segoe UI)
**Body Font:** Assistant (with Segoe UI, Arial Hebrew, Arial)
**Label/Mono Font:** Consolas (with Cascadia Mono), only for code, timestamps and shortcut keys.

**Character:** A friendly, slightly rounded Hebrew display face for the few headings, and a clean, very readable Hebrew text face for everything else. Both ship with the program (no network font loading).

### Hierarchy
- **Display** (400, clamp(28px, 4.2vw, 40px), 1.2): the page title only ("מה לומדים היום?", "הגדרות").
- **Headline** (400, 26px, 1.2): the title of the one primary card.
- **Title** (800, 18px): card titles and section headings.
- **Body** (400, 17px, 1.6): all running text; keep lines near 65 to 75 characters.
- **Label** (700, 14px): pills, small buttons, tab counters.
- **Code** (400, 13px, Consolas): timestamps and keyboard shortcuts, always set left-to-right and isolated.

### Named Rules
**The Few Headings Rule.** Secular One appears only on page titles and the primary card. Never use it for body text or controls.

**The Isolated Keys Rule.** A shortcut such as Ctrl+Alt+Q is wrapped in a left-to-right isolated span, so the order never flips inside Hebrew text.

## Layout

A single centered column, maximum 1240px wide, with 16px side gutters and about 22px above the first heading. The home page stacks a title, the course picker, three ways to start (the primary one wider: 1.7fr against 1fr and 1fr), the last lecture, a hints row, and a quiet footer. The live-lecture and course pages use two columns (transcript 1.6fr, side panel 1fr) that become one column below 900px; the cards at home become one column below 760px, with the primary one first. Spacing rhythm is 6, 10, 14 and 22px; groups are tight and sections are separated by space rather than boxes. Nothing may scroll sideways at any width from 320px.

## Elevation & Depth

Flat by default. Depth comes from tone (paper, sheet, sunk paper) and a 1px hairline, not from shadows. The one exception is the primary action card, which carries a single soft green shadow so it reads as the thing to press. Modals and toasts sit on a scrim with one large soft shadow.

### Shadow Vocabulary
- **Primary action** (`box-shadow: 0 6px 18px -8px color-mix(in srgb, var(--accent) 70%, transparent)`): the green start card on the home page.
- **Dialog** (`box-shadow: 0 18px 48px rgba(0,0,0,.25)`): modals only.

### Named Rules
**The One Lifted Thing Rule.** At most one element per screen is lifted by a shadow, and it is the primary action.

## Shapes

Soft, notebook-like corners: 14px on cards and containers, 12px on buttons and inputs, 999px on pills, tabs and the search box, 5px on shortcut keys. Edges are always a 1px hairline (1.5px on ghost buttons, 2px in high-contrast mode). No side stripes: a state is shown with a dot, a tint or an icon, never with a thick border on one side. Icons are drawn line icons in one stroke weight (2px), never emoji.

## Components

### Buttons
- **Shape:** 12px radius, 9px 18px padding, 700 weight.
- **Primary:** Board Green fill with white text. Used once per screen.
- **Ghost:** transparent with a 1.5px green outline and green text; the default for every other action.
- **Quiet:** Sunk Paper fill with ink text, for low-priority actions (report a problem, close the app).
- **Hover / Focus:** hover raises brightness slightly; focus shows a 2px green outline with a 2px offset.

### Primary Action Card
The home page's "הרצאה חיה בעברית": solid Board Green, a Secular One 26px title, a translucent icon plate, white text, and the single soft shadow. The other two starts are transparent cards with a hairline.

### Cards / Containers
- **Corner Style:** 14px.
- **Background:** Sheet; the page ground stays Paper.
- **Border:** 1px Hairline.
- **Internal Padding:** 16px 18px. Cards are never nested: a section inside a card is separated by a hairline.

### Pills and Status
Sunk Paper pills with muted text. The recording pill is tinted red with a pulsing dot (static when motion is reduced). A status line shows a green dot when answers are ready; a missing key turns into a Caution pill with a text link.

### Inputs / Fields
- **Style:** Paper fill (inside a sheet), 1px Hairline, 12px radius; search boxes are pills.
- **Direction:** an empty box starts right-to-left (caret and placeholder at the right); typed text follows its own language. Key fields stay left-to-right but their placeholder is right-aligned.
- **Focus:** 2px green outline.

### Navigation
A pill-shaped top bar on a Sheet: logo and name on the right, tabs (בית, הקורסים שלי, איך משתמשים, הגדרות) in the middle, theme switch and status pills on the left. The current tab is a Sunk Paper pill with 800 weight. Below 700px the tabs wrap onto their own row.

### The Floating Window
A small always-on-top window with the same tokens: a title bar, the course name with a recording dot, a ★ button, three "what did I miss" pills (3, 7, 15 minutes), a conversation area, and a text box with one green "תשובה כאן" button. It shows exactly one thing to do: ask. Two quiet notices live in it: the warning that the transcript is behind ("מאחר ב-N שניות", a caution pill in the row of the green button, never in the title row, which a long course name needs), and the mark message: a small centred card (Sheet, 1px Hairline) with a Mark Line chip holding the ★ in Ink and the word "סומן". The same card, drawn as a native window, shows above the round floating button when a mark is made with the keyboard while the small window is closed.

The course offer (a course read from the first slide) is a quiet strip: Sunk Paper, Ink text, a ghost "להעביר" and a ghost "לא עכשיו" (green text and edge), in the small window under the title and in the live view next to the course field.

The stop button of the small window is a quiet ghost button in the title row ("עצירה"); the first press turns it to "לעצור?" with a Recording Red edge and text for 3 seconds, the second stops. When the lecture is saved a card replaces the question box: a Green Soft round chip with a green check, "ההרצאה נשמרה בהצלחה" (bold), the course, minutes and slides in Muted, a ghost "פתיחת ההרצאה באפליקציה" and a ghost "סגירה". The same card shape (Sheet, 1px Hairline, a Green Soft chip with a check, never yellow) shows above the place of the round button, drawn as a native window, when the small window is closed.

### The Quick-Start Window
A small window in the middle of the screen when Hevanti opens: a title row (the name, "הקלטה חדשה"), the field "איזה קורס?" with a note under it ("זוהה מכותרת החלון. אפשר להחליף." with a small sparkle), three kinds of lecture as a radio group (the chosen one Green Soft with Ink and a Green edge, never a second solid green), the one solid-green action "התחל תמלול" (it becomes "המשך באפליקציה" for a recording, which only opens the app), and a ghost button "פתח את האפליקציה". Tokens as everywhere, light and night.

### Logo
One mark, everywhere: a green bubble with a short tail at its lower right and a thick yellow check (viewBox 120; bubble `M30 8H90A24 24 0 0 1 114 32V70A24 24 0 0 1 90 94H92L100 114L68 94H30A24 24 0 0 1 6 70V32A24 24 0 0 1 30 8Z`, check `M33 52L52 71L87 33`, stroke width 17). The floating button and the installer icon place the same mark on a cream disc.

## Do's and Don'ts

### Do:
- **Do** keep one solid-green action per screen and make every other action a ghost button or a text link.
- **Do** design right-to-left first: empty boxes start at the right and shortcut keys are isolated left-to-right.
- **Do** use Hairline `#DDD7C4` (night `#3E3A2E`) for every card edge and divider.
- **Do** keep muted text at 4.5:1 or better on every surface, in both themes.
- **Do** draw icons as 2px-stroke line icons and keep the logo identical at every size.
- **Do** show a missing state with its fix: "חסר מפתח Gemini" with a link to the setting, "יש כרטיס NVIDIA" with an install button.

### Don't:
- **Don't** use yellow for anything but the ★ mark (the star, and the highlighter band behind a marked transcript line) and the logo check.
- **Don't** nest cards, and don't mark a state with a thick side border; use a dot, a tint or an icon.
- **Don't** use emoji as icons or Secular One for body text or controls.
- **Don't** add a second logo variant or a decorative gradient.
- **Don't** use cold green-black for the dark theme; the night palette is warm (`#1C1B16`).
- **Don't** let anything compete with the transcript and the question box during a live lecture.

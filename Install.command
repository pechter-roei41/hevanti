#!/bin/bash
# Hevanti for Mac - first-time setup - (c) 2026 Roei Pechter. MIT License, see System/LICENSE.txt
# Its own Python (with uv from astral.sh - no admin password), the packages, and the files for reading slides.
cd "$(dirname "$0")" || exit 1
fail() { echo; echo "INSTALL FAILED - send a screenshot of this window. Press a key to close."; read -r -n 1; exit 1; }
echo "Hevanti - setup for Mac"
xattr -dr com.apple.quarantine . 2>/dev/null   # the "downloaded from the internet" mark, on Hevanti's own files
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
if [ ! -x "$UV" ]; then
  echo "Getting uv (it installs Hevanti's own Python)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh || fail
  UV="$HOME/.local/bin/uv"
fi
"$UV" venv --python 3.12 --allow-existing System/venv-mac || fail
"$UV" pip install --python System/venv-mac/bin/python "faster-whisper>=1.1" sounddevice numpy mss pillow \
  pyobjc-framework-Quartz || fail

echo
echo "Reading the text on the slides (optional, free):"
TD="$HOME/Library/Application Support/Hevanti/tessdata"
mkdir -p "$TD"
for l in heb eng; do
  curl -sSfL -o "$TD/$l.traineddata" "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/$l.traineddata" \
    || echo "  could not download the $l language file"
done
if command -v tesseract >/dev/null || [ -x /opt/homebrew/bin/tesseract ] || [ -x /usr/local/bin/tesseract ]; then
  echo "  Tesseract: found"
elif command -v brew >/dev/null; then
  brew install tesseract || echo "  could not install Tesseract - Hevanti works without reading slides"
else
  echo "  Without Homebrew (brew.sh) Hevanti does not read the slides. With it: brew install tesseract"
fi

echo
if system_profiler SPAudioDataType 2>/dev/null | grep -qi blackhole; then
  echo "BlackHole: found."
else
  echo "One more step: BlackHole (free), so Hevanti can hear what the Mac plays (a Mac cannot record its own"
  echo "sound without it). Install it from https://existential.audio/blackhole/ (BlackHole 2ch), or: "
  echo "  brew install --cask blackhole-2ch"
  echo "Then set it up once - the steps are in README.txt, in the part \"Mac\"."
fi
echo
echo "Installed OK. Close this window and open Hevanti.command."
read -r -n 1

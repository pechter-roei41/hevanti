#!/bin/bash
# Hevanti for Mac - lectures, transcribed live or from a recording - (c) 2026 Roei Pechter. MIT License, see System/LICENSE.txt
# Opens the app in the browser. While this window is open the tool is running; closing it stops the tool.
cd "$(dirname "$0")" || exit 1
PY="System/venv-mac/bin/python"
if [ ! -x "$PY" ]; then
  echo "Hevanti is not installed yet: open Install.command first (right-click > Open the first time)."
  read -r -n 1
  exit 1
fi
export PYTHONIOENCODING=utf-8
exec "$PY" System/Program/live_transcribe.py --app "$@"

#!/bin/bash
# Hevanti for Mac - UNINSTALL - (c) 2026 Roei Pechter. MIT License, see LICENSE.txt
cd "$(dirname "$0")" || exit 1
PY="venv-mac/bin/python"
if [ -x "$PY" ]; then
  "$PY" Program/live_transcribe.py --uninstall
  rm -rf venv-mac
fi
echo "To finish: delete this Hevanti folder. Press a key to close."
read -r -n 1

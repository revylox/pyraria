#!/bin/sh
# Pyraria launcher for macOS / Linux: creates a local virtual environment
# on first run, installs the requirements and starts the game.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
    echo "First start: setting up Pyraria (needs Python 3.9+ and internet once)..."
    python3 -m venv .venv || { echo "Python 3.9+ with the venv module is required."; exit 1; }
fi
.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt || exit 1
exec .venv/bin/python main.py "$@"

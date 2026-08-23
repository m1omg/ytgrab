#!/usr/bin/env bash
# Start the optional browser version of ytgrab.
# For the desktop app, run: python main.py
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Setting up virtualenv..."
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements-web.txt
fi

exec .venv/bin/python app.py

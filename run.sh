#!/usr/bin/env bash
# macOS / Linux one-click setup + run:  ./run.sh [starter|full]
set -euo pipefail
PROFILE="${1:-full}"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/python -m pip install -r requirements.txt -q
.venv/bin/python manage.py all --open --profile "$PROFILE"

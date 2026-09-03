#!/bin/bash
# Linux installer wrapper - double-click if your file manager supports it,
# or run: ./install.sh
cd "$(dirname "$0")" || exit 1

PYTHON=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
fi

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python was not found. Install Python 3.11+ from https://www.python.org/downloads/" >&2
    STATUS=1
else
    "$PYTHON" install.py
    STATUS=$?
fi

if [ "$STATUS" -ne 0 ]; then
    echo
    echo "Installation failed - see the messages above."
fi
exit "$STATUS"

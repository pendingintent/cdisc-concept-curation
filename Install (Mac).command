#!/bin/bash
# Double-click this file in Finder to install the app. No Terminal or git
# knowledge required.
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

echo
read -n 1 -s -r -p "Press any key to close this window..."
echo

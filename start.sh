#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -f .python-path ]; then
    IFS= read -r tracker_python < .python-path || true
    if [ -x "$tracker_python" ]; then
        exec "$tracker_python" app.py "$@"
    fi
fi
for tracker_python in python3 python; do
    if command -v "$tracker_python" >/dev/null 2>&1 && "$tracker_python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
        exec "$tracker_python" app.py "$@"
    fi
done
printf '%s\n' 'Python 3.10 oder neuer wird benötigt: https://www.python.org/downloads/' >&2
exit 1

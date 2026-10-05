#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
if [ -x .venv-build/bin/python ]; then
    exec .venv-build/bin/python tools/package_release.py "$@"
fi
exec python3 tools/package_release.py "$@"

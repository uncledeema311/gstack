#!/bin/bash
# Run the whole test suite from the extracted package. Python 3.9+ only, no other dependencies.
# Usage: bash tests/run_all.sh [-v]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../installer/find_python.sh
. "$HERE/../installer/find_python.sh"
cd "$HERE"
exec "$COS_PY" -B -m unittest discover -s . -p 'test_*.py' "$@"

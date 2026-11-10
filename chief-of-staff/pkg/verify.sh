#!/bin/bash
# Check an installed chief-of-staff workspace.
# Usage: bash verify.sh [--workspace DIR] [--no-codex]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=installer/find_python.sh
. "$HERE/installer/find_python.sh"
exec "$COS_PY" "$HERE/installer/cos_install.py" verify "$@"

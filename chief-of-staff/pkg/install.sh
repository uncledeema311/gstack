#!/bin/bash
# Install or upgrade the chief-of-staff workspace for Codex.
# Usage: bash install.sh [--workspace DIR] [--dry-run]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=installer/find_python.sh
. "$HERE/installer/find_python.sh"
exec "$COS_PY" "$HERE/installer/cos_install.py" install "$@"

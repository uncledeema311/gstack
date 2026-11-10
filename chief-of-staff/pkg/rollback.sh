#!/bin/bash
# Return to the version that was installed before the last upgrade.
# Usage: bash rollback.sh [--workspace DIR] [--dry-run] [--restore-data]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=installer/find_python.sh
. "$HERE/installer/find_python.sh"
exec "$COS_PY" "$HERE/installer/cos_install.py" rollback "$@"

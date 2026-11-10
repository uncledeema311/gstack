#!/bin/bash
# Remove the chief-of-staff package. Your data and config are kept unless you
# pass --purge-data --yes.
# Usage: bash uninstall.sh [--workspace DIR] [--dry-run] [--purge-data --yes]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=installer/find_python.sh
. "$HERE/installer/find_python.sh"
exec "$COS_PY" "$HERE/installer/cos_install.py" uninstall "$@"

# Sourced by the wrapper scripts. Sets COS_PY to a Python 3.9+ interpreter.
# Override with: COS_PYTHON=/path/to/python3 bash install.sh
COS_PY="${COS_PYTHON:-python3}"
if ! command -v "$COS_PY" >/dev/null 2>&1; then
  echo "ERROR: python3 was not found." >&2
  echo "On macOS, install Apple's Command Line Tools, then run this again:" >&2
  echo "    xcode-select --install" >&2
  exit 1
fi
if ! "$COS_PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
  echo "ERROR: $COS_PY is missing, not set up, or older than Python 3.9." >&2
  echo "On macOS, run:  xcode-select --install   and wait for it to finish, then run this again." >&2
  echo "Or point at another Python:  COS_PYTHON=/path/to/python3 bash $(basename "$0")" >&2
  exit 1
fi

"""Shared storage helpers for the chief-of-staff state CLI.

Plain JSON files, written atomically, guarded by one advisory lock.
Python 3.9+ standard library only.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

SCHEMA_VERSION = 1

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_VALIDATION = 2
EXIT_DUPLICATE = 3
EXIT_CORRUPT = 4
EXIT_REFUSED = 5
EXIT_NOT_FOUND = 6


class CosError(Exception):
    """An expected failure with an exit code and optional structured details."""

    def __init__(self, message: str, code: int = EXIT_ERROR, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


def root() -> Path:
    env = os.environ.get("COS_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    env = os.environ.get("COS_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return root() / "data"


def config_path() -> Path:
    env = os.environ.get("COS_CONFIG")
    if env:
        return Path(env).expanduser().resolve()
    return root() / "config" / "cos.config.json"


def parse_iso(value: str) -> dt.datetime:
    """Parse an ISO 8601 timestamp. Accepts a trailing Z (Python 3.9 does not)."""
    text = value.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        raise CosError("Not an ISO 8601 timestamp: %r" % value, EXIT_VALIDATION)
    if parsed.tzinfo is None:
        raise CosError("Timestamp needs a UTC offset or Z: %r" % value, EXIT_VALIDATION)
    return parsed


def parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value.strip())
    except ValueError:
        raise CosError("Not a date (expected YYYY-MM-DD): %r" % value, EXIT_VALIDATION)


def utcnow() -> dt.datetime:
    """Current time in UTC. COS_NOW overrides it so tests are deterministic."""
    override = os.environ.get("COS_NOW")
    if override:
        return parse_iso(override).astimezone(dt.timezone.utc)
    return dt.datetime.now(dt.timezone.utc)


def iso(moment: dt.datetime) -> str:
    return moment.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_iso() -> str:
    return iso(utcnow())


def norm(text: Optional[str]) -> str:
    """Lowercase, strip punctuation, collapse whitespace. Used for matching."""
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").lower()))


def sha(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as tmp:
            tmp.write(text)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, str(path))
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)
        raise


@contextlib.contextmanager
def lock() -> Iterator[None]:
    """Serialise writers across processes."""
    base = data_dir()
    base.mkdir(parents=True, exist_ok=True)
    with open(str(base / ".lock"), "a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def store_path(rel: str) -> Path:
    return data_dir() / rel


def load_store(rel: str, kind: str) -> Dict[str, Any]:
    """Load a store, or return an empty one. A corrupt file is never overwritten."""
    path = store_path(rel)
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "kind": kind, "counter": 0, "records": []}
    try:
        with open(str(path), "r", encoding="utf-8") as handle:
            store = json.load(handle)
    except (ValueError, OSError) as exc:
        raise CosError(
            "Store is unreadable and was left untouched: %s (%s). "
            "Restore it from %s.bak or from a backup under .cos/backups." % (path, exc, path),
            EXIT_CORRUPT,
        )
    if not isinstance(store, dict) or not isinstance(store.get("records"), list):
        raise CosError("Store has an unexpected shape and was left untouched: %s" % path, EXIT_CORRUPT)
    if store.get("schema_version", 0) > SCHEMA_VERSION:
        raise CosError(
            "Store %s was written by a newer version (schema %s). Upgrade the package or roll back the data."
            % (path, store.get("schema_version")),
            EXIT_CORRUPT,
        )
    return store


def save_store(rel: str, store: Dict[str, Any]) -> None:
    """Write a store atomically, keeping one previous generation as .bak."""
    path = store_path(rel)
    if path.exists():
        shutil.copyfile(str(path), str(path) + ".bak")
    atomic_write(path, json.dumps(store, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def next_id(store: Dict[str, Any], prefix: str) -> str:
    store["counter"] = int(store.get("counter", 0)) + 1
    return "%s-%04d" % (prefix, store["counter"])


def find(records: List[Dict[str, Any]], record_id: str) -> Dict[str, Any]:
    wanted = record_id.strip().upper()
    for record in records:
        if str(record.get("id", "")).upper() == wanted:
            return record
    raise CosError("No record with id %s" % record_id, EXIT_NOT_FOUND)


def append_jsonl(rel: str, entry: Dict[str, Any]) -> None:
    path = store_path(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

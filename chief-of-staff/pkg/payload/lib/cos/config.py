"""Configuration: defaults, loading, validation and safe updates.

The config file belongs to the user. It is created once at install time and
never rewritten by upgrades. Missing keys are filled from DEFAULTS in memory.
"""
from __future__ import annotations

import copy
import json
import re
from typing import Any, Dict, List, Tuple

from . import store

CONNECTORS = ["gmail", "calendar", "hubspot", "drive", "slack", "transcripts"]
ROUTINES = ["morning", "afternoon", "weekly"]
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# These action types can never be moved into the no-approval list.
LOCKED_APPROVAL = ["email_send", "calendar_invite", "calendar_event_change", "crm_write", "slack_send"]
ALWAYS_NEVER = ["purchase", "record_delete", "permission_change"]


def _connector() -> Dict[str, Any]:
    return {"status": "unknown", "via": "", "checked_at": None, "evidence": ""}


def _routine(days: List[str]) -> Dict[str, Any]:
    return {
        "enabled": False,
        "time": None,
        "timezone": None,
        "days": days,
        "deliver_to": None,
        "schedule_confirmed_at": None,
    }


DEFAULTS: Dict[str, Any] = {
    "schema_version": 1,
    "profile": {
        "name": "Nic",
        "role": "Account Executive and pod lead",
        "company": "InvestorHub",
        "city": "Melbourne",
        "language": "en-AU",
    },
    "timezone": "Australia/Melbourne",
    "working_hours": {"start": "08:30", "end": "17:30", "days": ["mon", "tue", "wed", "thu", "fri"]},
    "scheduling": {
        "buffer_minutes": 15,
        "default_duration_minutes": 30,
        "slot_step_minutes": 30,
        "min_notice_hours": 4,
        "attendee_day_start": "08:00",
        "attendee_day_end": "18:00",
    },
    "staleness_days": {
        "preferences": None,
        "reference": 180,
        "people": 180,
        "companies": 180,
        "opportunities": 14,
        "decisions": None,
        "notes": 7,
    },
    "permissions": {
        "no_approval": ["gmail_draft", "crm_note_draft", "doc_draft", "slack_draft", "calendar_proposal"],
        "approval_required": list(LOCKED_APPROVAL),
        "never": list(ALWAYS_NEVER),
        "approval_expiry_hours": 12,
    },
    "connectors": {name: _connector() for name in CONNECTORS},
    "transcript_provider": "unknown",
    "routines": {
        "morning": _routine(["mon", "tue", "wed", "thu", "fri"]),
        "afternoon": _routine(["mon", "tue", "wed", "thu", "fri"]),
        "weekly": _routine(["fri"]),
    },
    "feedback": {"promotion_min_evidence": 2},
    "context": {"max_bundle_items": 25},
}


def _merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_raw() -> Dict[str, Any]:
    path = store.config_path()
    if not path.exists():
        return {}
    try:
        with open(str(path), "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except ValueError as exc:
        raise store.CosError("Config is not valid JSON: %s (%s)" % (path, exc), store.EXIT_VALIDATION)
    if not isinstance(raw, dict):
        raise store.CosError("Config must be a JSON object: %s" % path, store.EXIT_VALIDATION)
    return raw


def load() -> Dict[str, Any]:
    return _merge(DEFAULTS, load_raw())


def _time_ok(value: Any) -> bool:
    return isinstance(value, str) and re.match(r"^([01]\d|2[0-3]):[0-5]\d$", value) is not None


def timezone_ok(name: Any) -> bool:
    if not isinstance(name, str) or not name:
        return False
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(name)
    except Exception:
        return False
    return True


def validate(cfg: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Return (errors, warnings)."""
    errors: List[str] = []
    warnings: List[str] = []

    if not timezone_ok(cfg.get("timezone")):
        errors.append("timezone: %r is not a known IANA time zone (example: Australia/Melbourne)" % cfg.get("timezone"))

    hours = cfg.get("working_hours", {})
    if not (_time_ok(hours.get("start")) and _time_ok(hours.get("end"))):
        errors.append("working_hours: start and end must be HH:MM")
    elif hours["start"] >= hours["end"]:
        errors.append("working_hours: start must be before end")
    for day in hours.get("days", []):
        if day not in DAYS:
            errors.append("working_hours.days: %r is not one of %s" % (day, ", ".join(DAYS)))

    sched = cfg.get("scheduling", {})
    for key in ("buffer_minutes", "default_duration_minutes", "slot_step_minutes", "min_notice_hours"):
        value = sched.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append("scheduling.%s: must be a whole number of zero or more" % key)
    if isinstance(sched.get("slot_step_minutes"), int) and sched.get("slot_step_minutes") == 0:
        errors.append("scheduling.slot_step_minutes: must be greater than zero")

    perms = cfg.get("permissions", {})
    no_approval = perms.get("no_approval", [])
    required = perms.get("approval_required", [])
    never = perms.get("never", [])
    for kind in LOCKED_APPROVAL:
        if kind in no_approval:
            errors.append(
                "permissions.no_approval: %s can never run without approval. Remove it from no_approval." % kind
            )
        if kind not in required:
            errors.append("permissions.approval_required: must include %s" % kind)
    for kind in ALWAYS_NEVER:
        if kind not in never:
            errors.append("permissions.never: must include %s" % kind)
        if kind in no_approval or kind in required:
            errors.append("permissions: %s is not permitted in any allowed list" % kind)
    overlap = set(no_approval) & set(required)
    if overlap:
        errors.append("permissions: listed as both no_approval and approval_required: %s" % ", ".join(sorted(overlap)))
    expiry = perms.get("approval_expiry_hours")
    if not isinstance(expiry, int) or isinstance(expiry, bool) or expiry < 1:
        errors.append("permissions.approval_expiry_hours: must be a whole number of one or more")

    for name, entry in cfg.get("connectors", {}).items():
        if name not in CONNECTORS:
            warnings.append("connectors.%s: unknown connector name (known: %s)" % (name, ", ".join(CONNECTORS)))
        if entry.get("status") not in ("unknown", "connected", "unavailable"):
            errors.append("connectors.%s.status: must be unknown, connected or unavailable" % name)
    if cfg.get("transcript_provider") not in ("unknown", "fathom", "granola", "none", "other"):
        errors.append("transcript_provider: must be unknown, fathom, granola, other or none")

    for name, entry in cfg.get("routines", {}).items():
        if name not in ROUTINES:
            warnings.append("routines.%s: unknown routine name" % name)
            continue
        if entry.get("enabled"):
            if not _time_ok(entry.get("time")):
                errors.append("routines.%s: enabled but time is not HH:MM" % name)
            if not timezone_ok(entry.get("timezone")):
                errors.append("routines.%s: enabled but timezone is not a known IANA time zone" % name)
            if not entry.get("deliver_to"):
                errors.append("routines.%s: enabled but deliver_to is empty" % name)
            if not entry.get("schedule_confirmed_at"):
                warnings.append(
                    "routines.%s: configured, but no schedule has been confirmed in Codex, so it is not running yet" % name
                )
        for day in entry.get("days") or []:
            if day not in DAYS:
                errors.append("routines.%s.days: %r is not a valid day" % (name, day))

    minimum = cfg.get("feedback", {}).get("promotion_min_evidence")
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 2:
        errors.append("feedback.promotion_min_evidence: must be a whole number of two or more")

    unchecked = [name for name, entry in cfg.get("connectors", {}).items()
                 if entry.get("status") == "unknown" and name in CONNECTORS]
    if unchecked:
        warnings.append("connectors not checked yet: %s. Run the cos-setup skill inside Codex." % ", ".join(unchecked))
    return errors, warnings


def save_raw(raw: Dict[str, Any]) -> None:
    store.atomic_write(store.config_path(), json.dumps(raw, indent=2, ensure_ascii=False) + "\n")


def set_value(dotted: str, value: Any) -> Dict[str, Any]:
    """Set one key in the user's config file, refusing changes that fail validation."""
    raw = load_raw()
    updated = copy.deepcopy(raw)
    cursor = updated
    parts = dotted.split(".")
    for part in parts[:-1]:
        if not isinstance(cursor.get(part), dict):
            cursor[part] = {}
        cursor = cursor[part]
    cursor[parts[-1]] = value
    errors, _warnings = validate(_merge(DEFAULTS, updated))
    if errors:
        raise store.CosError(
            "Change refused because the config would be invalid: %s" % "; ".join(errors),
            store.EXIT_VALIDATION,
            {"errors": errors},
        )
    save_raw(updated)
    return _merge(DEFAULTS, updated)


def get_value(cfg: Dict[str, Any], dotted: str) -> Any:
    cursor: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            raise store.CosError("No config key %s" % dotted, store.EXIT_NOT_FOUND)
        cursor = cursor[part]
    return cursor

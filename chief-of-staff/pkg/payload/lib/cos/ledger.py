"""Action ledger and approvals.

Every outward-facing step is recorded here before and after it happens, so that:
  * a retry never repeats an effect that already happened (idempotency keys);
  * nothing is reported as sent, invited or updated without a reference
    returned by the system that did it;
  * restricted actions need a recorded, single-use approval from the user.

This is bookkeeping plus a guardrail. It cannot stop a tool call by itself.
Hard blocking lives in the Codex connector settings (see docs/CONNECTORS.md).
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

from . import store, validate

ACTIONS_REL = "ledger/actions.json"
APPROVALS_REL = "ledger/approvals.json"


def classify(cfg: Dict[str, Any], action_type: str) -> str:
    perms = cfg["permissions"]
    if action_type in perms["never"]:
        return "never"
    if action_type in perms["approval_required"]:
        return "approval_required"
    if action_type in perms["no_approval"]:
        return "no_approval"
    raise store.CosError(
        "Unknown action type %r. Known types: %s"
        % (action_type, ", ".join(perms["no_approval"] + perms["approval_required"] + perms["never"])),
        store.EXIT_VALIDATION,
    )


def make_key(action_type: str, target: str, task_id: Optional[str], fingerprint: Optional[str]) -> str:
    return store.sha("|".join([action_type, store.norm(target), (task_id or "").upper(), fingerprint or ""]))


def record_approval(
    cfg: Dict[str, Any], action_type: str, target: str, quote: str, task_id: Optional[str] = None
) -> Dict[str, Any]:
    kind = classify(cfg, action_type)
    if kind == "never":
        raise store.CosError("%s is never permitted, so it cannot be approved here." % action_type, store.EXIT_REFUSED)
    if kind == "no_approval":
        raise store.CosError("%s does not need approval." % action_type, store.EXIT_VALIDATION)
    if len(quote.strip()) < 2:
        raise store.CosError("Record the user's own words that gave the approval in --quote.", store.EXIT_VALIDATION)
    with store.lock():
        data = store.load_store(APPROVALS_REL, "approvals")
        now = store.utcnow()
        approval = {
            "id": store.next_id(data, "A"),
            "action_type": action_type,
            "target": target.strip(),
            "task_id": task_id.upper() if task_id else None,
            "quote": quote.strip(),
            "granted_at": store.iso(now),
            "expires_at": store.iso(now + dt.timedelta(hours=cfg["permissions"]["approval_expiry_hours"])),
            "used_by": None,
        }
        validate.require(approval, "approval")
        data["records"].append(approval)
        store.save_store(APPROVALS_REL, data)
        return approval


def _check_approval(
    approvals: Dict[str, Any], approval_id: Optional[str], action_type: str, target: str, task_id: Optional[str], key: str
) -> Dict[str, Any]:
    if not approval_id:
        raise store.CosError(
            "%s needs the user's explicit approval for this specific action. Prepare a draft, ask, and stop. "
            "If they approve, record it with: cos approval record" % action_type,
            store.EXIT_REFUSED,
            {"needs": "approval", "action_type": action_type, "target": target},
        )
    approval = store.find(approvals["records"], approval_id)
    problems = []
    if approval["action_type"] != action_type:
        problems.append("it covers %s, not %s" % (approval["action_type"], action_type))
    if store.norm(approval["target"]) != store.norm(target):
        problems.append("it covers %s, not %s" % (approval["target"], target))
    if approval.get("task_id") and task_id and approval["task_id"] != task_id.upper():
        problems.append("it covers task %s, not %s" % (approval["task_id"], task_id))
    if approval.get("used_by") and approval["used_by"] != key:
        problems.append("it was already used for another action")
    if store.parse_iso(approval["expires_at"]) < store.utcnow():
        problems.append("it expired at %s" % approval["expires_at"])
    if problems:
        raise store.CosError(
            "Approval %s cannot be used: %s. Ask again." % (approval["id"], "; ".join(problems)),
            store.EXIT_REFUSED,
            {"needs": "approval"},
        )
    return approval


def plan(
    cfg: Dict[str, Any],
    action_type: str,
    target: str,
    summary: str,
    task_id: Optional[str] = None,
    key: Optional[str] = None,
    fingerprint: Optional[str] = None,
    approval_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Call before doing anything outward-facing. Tells you whether to proceed."""
    kind = classify(cfg, action_type)
    if kind == "never":
        raise store.CosError(
            "%s is never permitted. Tell the user what you would have done and stop." % action_type, store.EXIT_REFUSED
        )
    key = key or make_key(action_type, target, task_id, fingerprint)
    with store.lock():
        actions = store.load_store(ACTIONS_REL, "actions")
        approvals = store.load_store(APPROVALS_REL, "approvals")
        existing = next((item for item in actions["records"] if item["key"] == key), None)
        if existing and existing["status"] == "confirmed":
            return {
                "proceed": False,
                "reason": "already_confirmed",
                "action": existing,
                "advice": "This already happened. Do not repeat it. Report the existing system reference.",
            }
        approval = None
        if kind == "approval_required":
            approval = _check_approval(approvals, approval_id, action_type, target, task_id, key)
        now = store.now_iso()
        if existing and existing["status"] == "planned":
            existing["attempts"].append({"at": now, "note": "re-planned without a recorded outcome"})
            existing["updated_at"] = now
            store.save_store(ACTIONS_REL, actions)
            return {
                "proceed": "verify_first",
                "reason": "outcome_unknown",
                "action": existing,
                "advice": "An earlier attempt has no recorded outcome. Check the target system for the effect "
                "before trying again, then record confirm or fail.",
            }
        if existing:  # previously failed: a clean retry
            existing["status"] = "planned"
            existing["attempts"].append({"at": now, "note": "retry after failure"})
            existing["updated_at"] = now
            action = existing
        else:
            action = {
                "key": key,
                "type": action_type,
                "class": kind,
                "target": target.strip(),
                "summary": summary.strip(),
                "task_id": task_id.upper() if task_id else None,
                "approval_id": approval["id"] if approval else None,
                "status": "planned",
                "system_ref": None,
                "error": None,
                "attempts": [{"at": now, "note": "planned"}],
                "created_at": now,
                "updated_at": now,
            }
            validate.require(action, "action")
            actions["records"].append(action)
        if approval:
            approval["used_by"] = key
            action["approval_id"] = approval["id"]
            store.save_store(APPROVALS_REL, approvals)
        store.save_store(ACTIONS_REL, actions)
        return {"proceed": True, "reason": "new" if not existing else "retry", "action": action}


def _get(actions: Dict[str, Any], key: str) -> Dict[str, Any]:
    for item in actions["records"]:
        if item["key"] == key:
            return item
    raise store.CosError("No action with key %s. Run cos action plan first." % key, store.EXIT_NOT_FOUND)


def confirm(key: str, system_ref: str) -> Dict[str, Any]:
    """Record that the target system confirmed the effect. system_ref is its id or link."""
    if len(system_ref.strip()) < 3:
        raise store.CosError(
            "Confirmation needs the reference returned by the system (draft id, message id, record id or link).",
            store.EXIT_VALIDATION,
        )
    with store.lock():
        actions = store.load_store(ACTIONS_REL, "actions")
        action = _get(actions, key)
        now = store.now_iso()
        action["status"] = "confirmed"
        action["system_ref"] = system_ref.strip()
        action["error"] = None
        action["attempts"].append({"at": now, "note": "confirmed by system"})
        action["updated_at"] = now
        store.save_store(ACTIONS_REL, actions)
        return action


def fail(key: str, error: str) -> Dict[str, Any]:
    with store.lock():
        actions = store.load_store(ACTIONS_REL, "actions")
        action = _get(actions, key)
        if action["status"] == "confirmed":
            raise store.CosError("Action %s is already confirmed and cannot be marked failed." % key, store.EXIT_REFUSED)
        now = store.now_iso()
        action["status"] = "failed"
        action["error"] = error.strip()
        action["attempts"].append({"at": now, "note": "failed: %s" % error.strip()})
        action["updated_at"] = now
        store.save_store(ACTIONS_REL, actions)
        return action


def status(key: str) -> Dict[str, Any]:
    """What may truthfully be said about this action."""
    action = _get(store.load_store(ACTIONS_REL, "actions"), key)
    if action["status"] == "confirmed":
        wording = "Confirmed by the system (reference: %s)." % action["system_ref"]
    elif action["status"] == "failed":
        wording = "Not done. The last attempt failed: %s" % action["error"]
    else:
        wording = "Not confirmed. Do not describe this as done."
    return {"action": action, "may_report_as_done": action["status"] == "confirmed", "wording": wording}


def listing(status_filter: Optional[str] = None, task_id: Optional[str] = None) -> List[Dict[str, Any]]:
    records = store.load_store(ACTIONS_REL, "actions")["records"]
    out = []
    for item in records:
        if status_filter and item["status"] != status_filter:
            continue
        if task_id and item.get("task_id") != task_id.upper():
            continue
        out.append(item)
    return out

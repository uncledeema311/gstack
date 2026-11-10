"""Feedback capture and versioned instruction improvement.

Feedback types:
  task_correction     fix for this one piece of work. Not reusable by default.
  factual_update      a fact changed. Belongs in context, not in instructions.
  durable_preference  how the user wants things done from now on.
  workflow_change     a change to how a skill or routine should run.

Only durable preferences and workflow changes can become reusable rules, and
only with evidence: either the user said it explicitly as a standing rule, or
the same theme has come up at least N times. Rules can never widen permissions.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from . import store, validate

FEEDBACK_REL = "feedback/feedback.json"
RULES_REL = "instructions/rules.json"
TYPES = ["task_correction", "factual_update", "durable_preference", "workflow_change"]
RULE_KINDS = ["style", "format", "workflow", "retrieval"]

# A learned rule must never grant new permission. Quality feedback is not consent.
_PERMISSION_PATTERNS = [
    r"\bwithout (asking|approval|checking|confirm\w*|permission)\b",
    r"\bno (need|longer need) (to|for) (ask|approv\w*|confirm\w*)\b",
    r"\b(auto|automatically)[- ]?(send|post|invite|book|update|approve)\w*\b",
    r"\b(just|go ahead and|always|can|may) (send|post|invite|book|purchase|buy|delete)\b",
    r"\bsend (it |them |emails? |messages? |invites? )?(straight|directly|immediately|right away)\b",
    r"\bskip (the )?(approval|confirmation|draft)\b",
    r"\bpre-?approved?\b",
]


def widens_permission(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in _PERMISSION_PATTERNS)


def add(
    feedback_type: str,
    text: str,
    skill: Optional[str] = None,
    task_id: Optional[str] = None,
    theme: Optional[str] = None,
    explicit_standing: bool = False,
) -> Dict[str, Any]:
    with store.lock():
        data = store.load_store(FEEDBACK_REL, "feedback")
        record = {
            "id": store.next_id(data, "F"),
            "type": feedback_type,
            "text": text.strip(),
            "skill": skill,
            "task_id": task_id.upper() if task_id else None,
            "theme": store.norm(theme) or None,
            "explicit_standing": bool(explicit_standing),
            "promoted_to": None,
            "created_at": store.now_iso(),
        }
        validate.require(record, "feedback")
        data["records"].append(record)
        store.save_store(FEEDBACK_REL, data)
    guidance = {
        "task_correction": "Apply to this piece of work only. It becomes a rule only if the same theme recurs.",
        "factual_update": "Record the fact with cos context add (use --supersede if it replaces an older value).",
        "durable_preference": "Eligible to become a rule with cos rules propose once the evidence threshold is met.",
        "workflow_change": "Eligible to become a rule with cos rules propose once the evidence threshold is met.",
    }[feedback_type]
    same_theme = 0
    if record["theme"]:
        same_theme = len([item for item in data["records"] if item.get("theme") == record["theme"]])
    return {"feedback": record, "next_step": guidance, "same_theme_count": same_theme}


def listing(feedback_type: Optional[str] = None, theme: Optional[str] = None, limit: int = 25) -> List[Dict[str, Any]]:
    records = store.load_store(FEEDBACK_REL, "feedback")["records"]
    out = []
    for item in reversed(records):
        if feedback_type and item["type"] != feedback_type:
            continue
        if theme and item.get("theme") != store.norm(theme):
            continue
        out.append(item)
    return out[: max(1, limit)]


def _rules() -> Dict[str, Any]:
    data = store.load_store(RULES_REL, "rules")
    data.setdefault("instructions_version", 0)
    data.setdefault("history", [])
    return data


def propose(cfg: Dict[str, Any], text: str, reason: str, kind: str, feedback_ids: List[str]) -> Dict[str, Any]:
    """Turn feedback into a versioned reusable rule, if the evidence supports it."""
    if widens_permission(text):
        raise store.CosError(
            "This rule would widen what may be done without approval. Feedback about quality is not permission. "
            "Permissions are fixed in the config and the locked ones cannot be changed by a learned rule.",
            store.EXIT_REFUSED,
        )
    if not feedback_ids:
        raise store.CosError("A rule needs the feedback it came from (--from F-0001,F-0002).", store.EXIT_VALIDATION)
    minimum = cfg["feedback"]["promotion_min_evidence"]
    with store.lock():
        feedback = store.load_store(FEEDBACK_REL, "feedback")
        sources = [store.find(feedback["records"], item) for item in feedback_ids]
        if any(item["type"] == "factual_update" for item in sources):
            raise store.CosError(
                "Factual updates belong in context (cos context add), not in instructions.", store.EXIT_VALIDATION
            )
        explicit = any(item["explicit_standing"] and item["type"] != "task_correction" for item in sources)
        distinct = len({item["id"] for item in sources})
        if not explicit and distinct < minimum:
            raise store.CosError(
                "Not enough evidence to generalise: %d piece(s) of feedback, %d needed, and none was stated "
                "as a standing rule. Keep applying it case by case until it recurs." % (distinct, minimum),
                store.EXIT_REFUSED,
                {"evidence": distinct, "needed": minimum},
            )
        rules = _rules()
        for existing in rules["records"]:
            if existing["status"] == "active" and store.norm(existing["text"]) == store.norm(text):
                return {"rule": existing, "created": False, "instructions_version": rules["instructions_version"]}
        now = store.now_iso()
        rules["instructions_version"] += 1
        rule = {
            "id": store.next_id(rules, "R"),
            "kind": kind,
            "text": text.strip(),
            "reason": reason.strip(),
            "evidence": [item["id"] for item in sources],
            "basis": "explicit standing instruction" if explicit else "%d consistent corrections" % distinct,
            "status": "active",
            "added_in_version": rules["instructions_version"],
            "created_at": now,
            "reverted_at": None,
        }
        validate.require(rule, "rule")
        rules["records"].append(rule)
        rules["history"].append(
            {
                "version": rules["instructions_version"],
                "at": now,
                "change": "added",
                "rule_id": rule["id"],
                "reason": rule["reason"],
            }
        )
        for item in sources:
            item["promoted_to"] = rule["id"]
        store.save_store(RULES_REL, rules)
        store.save_store(FEEDBACK_REL, feedback)
        return {"rule": rule, "created": True, "instructions_version": rules["instructions_version"]}


def revert(rule_id: str, reason: str) -> Dict[str, Any]:
    with store.lock():
        rules = _rules()
        rule = store.find(rules["records"], rule_id)
        if rule["status"] != "active":
            raise store.CosError("%s is already reverted." % rule["id"], store.EXIT_VALIDATION)
        now = store.now_iso()
        rules["instructions_version"] += 1
        rule["status"] = "reverted"
        rule["reverted_at"] = now
        rules["history"].append(
            {
                "version": rules["instructions_version"],
                "at": now,
                "change": "reverted",
                "rule_id": rule["id"],
                "reason": reason.strip(),
            }
        )
        store.save_store(RULES_REL, rules)
        return {"rule": rule, "instructions_version": rules["instructions_version"]}


def active_rules() -> List[Dict[str, Any]]:
    return [rule for rule in _rules()["records"] if rule["status"] == "active"]


def rules_state() -> Dict[str, Any]:
    rules = _rules()
    return {
        "instructions_version": rules["instructions_version"],
        "active": [rule for rule in rules["records"] if rule["status"] == "active"],
        "reverted": [rule for rule in rules["records"] if rule["status"] != "active"],
        "history": rules["history"],
    }

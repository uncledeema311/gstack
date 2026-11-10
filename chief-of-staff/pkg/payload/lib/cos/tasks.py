"""Task queue: stable ids, deduplication, explicit states, evidence of completion."""
from __future__ import annotations

import difflib
from typing import Any, Dict, List, Optional

from . import store, validate

REL = "tasks/tasks.json"
STATUSES = [
    "proposed",
    "drafted",
    "awaiting_approval",
    "in_progress",
    "waiting_on_other",
    "completed",
    "blocked",
]
PRIORITIES = ["high", "medium", "low"]
FUZZY_THRESHOLD = 0.85


def dedupe_key(company: str, action: str) -> str:
    return store.sha(store.norm(company) + "|" + store.norm(action))


def _load() -> Dict[str, Any]:
    return store.load_store(REL, "tasks")


def _open(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [task for task in records if task["status"] != "completed"]


def similar(records: List[Dict[str, Any]], company: str, action: str) -> List[Dict[str, Any]]:
    wanted_company = store.norm(company)
    wanted_action = store.norm(action)
    matches = []
    for task in _open(records):
        if store.norm(task["company"]) != wanted_company:
            continue
        ratio = difflib.SequenceMatcher(None, wanted_action, store.norm(task["action"])).ratio()
        if ratio >= FUZZY_THRESHOLD:
            matches.append({"id": task["id"], "action": task["action"], "status": task["status"], "similarity": round(ratio, 2)})
    return matches


def add(
    company: str,
    action: str,
    owner: str,
    source_type: str,
    source_ref: str,
    priority: str,
    rationale: str,
    source_url: Optional[str] = None,
    deadline: Optional[str] = None,
    suggested_deadline: Optional[str] = None,
    status: str = "proposed",
    kind: str = "task",
    waiting_on: Optional[str] = None,
    force_new: bool = False,
    decision_id: Optional[str] = None,
) -> Dict[str, Any]:
    if deadline and suggested_deadline:
        raise store.CosError(
            "Give either an explicit deadline or a suggested deadline, not both.", store.EXIT_VALIDATION
        )
    due = None
    if deadline:
        due = {"date": store.parse_date(deadline).isoformat(), "kind": "explicit"}
    elif suggested_deadline:
        due = {"date": store.parse_date(suggested_deadline).isoformat(), "kind": "suggested"}
    if status == "waiting_on_other" and not waiting_on:
        raise store.CosError("A task waiting on someone else needs --waiting-on.", store.EXIT_VALIDATION)
    if status in ("completed", "blocked"):
        raise store.CosError("Create the task first, then move it to %s with task update." % status, store.EXIT_VALIDATION)

    with store.lock():
        data = _load()
        key = dedupe_key(company, action)
        for task in _open(data["records"]):
            if task["dedupe_key"] == key:
                seen = {"type": source_type, "ref": source_ref}
                if seen["ref"] != task["source"]["ref"] and seen not in task.get("also_seen_in", []):
                    task.setdefault("also_seen_in", []).append(seen)
                    task["updated_at"] = store.now_iso()
                    store.save_store(REL, data)
                return {"task": task, "created": False, "deduplicated": True}
        candidates = similar(data["records"], company, action)
        if candidates and not force_new:
            raise store.CosError(
                "A similar open task already exists. Update it, or repeat with --force-new if this is separate work.",
                store.EXIT_DUPLICATE,
                {"possible_duplicates": candidates},
            )
        now = store.now_iso()
        task = {
            "id": store.next_id(data, "T"),
            "kind": kind,
            "company": company.strip(),
            "action": action.strip(),
            "owner": owner.strip(),
            "source": {"type": source_type.strip(), "ref": source_ref.strip(), "url": source_url},
            "deadline": due,
            "priority": priority,
            "priority_rationale": rationale.strip(),
            "status": status,
            "waiting_on": waiting_on,
            "blocker": None,
            "evidence": None,
            "decision_id": decision_id,
            "dedupe_key": key,
            "created_at": now,
            "updated_at": now,
            "history": [{"at": now, "from": None, "to": status, "note": "created"}],
        }
        validate.require(task, "task")
        data["records"].append(task)
        store.save_store(REL, data)
        return {"task": task, "created": True, "deduplicated": False}


def update(
    task_id: str,
    status: Optional[str] = None,
    note: Optional[str] = None,
    evidence: Optional[str] = None,
    evidence_ref: Optional[str] = None,
    blocker: Optional[str] = None,
    waiting_on: Optional[str] = None,
    deadline: Optional[str] = None,
    suggested_deadline: Optional[str] = None,
    priority: Optional[str] = None,
    rationale: Optional[str] = None,
    action: Optional[str] = None,
    reopen: bool = False,
) -> Dict[str, Any]:
    with store.lock():
        data = _load()
        task = store.find(data["records"], task_id)
        previous = task["status"]
        if previous == "completed" and not reopen:
            raise store.CosError(
                "%s is completed. Use --reopen to change it, and say why in --note." % task["id"], store.EXIT_REFUSED
            )
        if deadline and suggested_deadline:
            raise store.CosError("Give either --deadline or --suggested-deadline, not both.", store.EXIT_VALIDATION)
        if deadline:
            task["deadline"] = {"date": store.parse_date(deadline).isoformat(), "kind": "explicit"}
        if suggested_deadline:
            task["deadline"] = {"date": store.parse_date(suggested_deadline).isoformat(), "kind": "suggested"}
        if priority:
            if not rationale:
                raise store.CosError("Changing priority needs --rationale.", store.EXIT_VALIDATION)
            task["priority"] = priority
            task["priority_rationale"] = rationale.strip()
        if action:
            task["action"] = action.strip()
            task["dedupe_key"] = dedupe_key(task["company"], task["action"])
        if blocker:
            task["blocker"] = blocker.strip()
            status = status or "blocked"
        if waiting_on:
            task["waiting_on"] = waiting_on.strip()
        target = status or previous
        if target == "completed":
            if not evidence:
                raise store.CosError(
                    "Completion needs evidence: what confirms it is done, and where that can be checked.",
                    store.EXIT_VALIDATION,
                )
            task["evidence"] = {"text": evidence.strip(), "ref": evidence_ref, "recorded_at": store.now_iso()}
        if target == "blocked" and not task.get("blocker"):
            raise store.CosError("A blocked task needs --blocker saying what is in the way.", store.EXIT_VALIDATION)
        if target == "waiting_on_other" and not task.get("waiting_on"):
            raise store.CosError("A task waiting on someone else needs --waiting-on.", store.EXIT_VALIDATION)
        if target != "blocked":
            task["blocker"] = None  # the history keeps what the blocker was
        if previous == "completed" and target != "completed":
            task["evidence"] = None
        now = store.now_iso()
        if target != previous or note:
            default_note = "blocked: %s" % task["blocker"] if target == "blocked" else ""
            task["history"].append({"at": now, "from": previous, "to": target, "note": note or default_note})
        task["status"] = target
        task["updated_at"] = now
        validate.require(task, "task")
        store.save_store(REL, data)
        return {"task": task, "changed": target != previous}


def get(task_id: str) -> Dict[str, Any]:
    return store.find(_load()["records"], task_id)


def _sort_key(task: Dict[str, Any]) -> Any:
    due = task["deadline"]["date"] if task.get("deadline") else "9999-12-31"
    return (PRIORITIES.index(task["priority"]), due, task["id"])


def listing(
    statuses: Optional[List[str]] = None,
    company: Optional[str] = None,
    owner: Optional[str] = None,
    due_on_or_before: Optional[str] = None,
    include_completed: bool = False,
) -> List[Dict[str, Any]]:
    records = _load()["records"]
    results = []
    for task in records:
        if statuses:
            if task["status"] not in statuses:
                continue
        elif task["status"] == "completed" and not include_completed:
            continue
        if company and store.norm(company) != store.norm(task["company"]):
            continue
        if owner and store.norm(owner) != store.norm(task["owner"]):
            continue
        if due_on_or_before:
            if not task.get("deadline") or task["deadline"]["date"] > due_on_or_before:
                continue
        results.append(task)
    return sorted(results, key=_sort_key)


def duplicates_report() -> List[Dict[str, Any]]:
    """Open tasks that look like the same work. Nothing is merged automatically."""
    records = _open(_load()["records"])
    groups = []
    seen = set()
    for index, task in enumerate(records):
        if task["id"] in seen:
            continue
        group = [task["id"]]
        for other in records[index + 1:]:
            if store.norm(other["company"]) != store.norm(task["company"]):
                continue
            ratio = difflib.SequenceMatcher(None, store.norm(task["action"]), store.norm(other["action"])).ratio()
            if ratio >= FUZZY_THRESHOLD:
                group.append(other["id"])
                seen.add(other["id"])
        if len(group) > 1:
            groups.append({"company": task["company"], "task_ids": group})
    return groups

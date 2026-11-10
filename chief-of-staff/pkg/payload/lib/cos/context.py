"""Persistent context, separated by category, with sources, dates and status.

Categories:
  preferences    stable preferences
  reference      product and commercial reference material
  people         people
  companies      companies
  opportunities  active opportunities
  decisions      decisions and commitments (the record of what was agreed)
  notes          temporary working notes (they expire)

Retrieval returns a relevant slice. Nothing here loads the whole history.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

from . import store, timeutil, validate

CATEGORIES = {
    "preferences": "PF",
    "reference": "RF",
    "people": "PE",
    "companies": "CO",
    "opportunities": "OP",
    "decisions": "DE",
    "notes": "NO",
}
DEFAULT_NOTE_DAYS = 7


def _rel(category: str) -> str:
    if category not in CATEGORIES:
        raise store.CosError(
            "Unknown category %r. Use one of: %s" % (category, ", ".join(CATEGORIES)), store.EXIT_VALIDATION
        )
    return "context/%s.json" % category


def _load(category: str) -> Dict[str, Any]:
    return store.load_store(_rel(category), "context:%s" % category)


def _today() -> dt.date:
    return timeutil.today()


def _same_slot(a: Dict[str, Any], subject: str, attribute: Optional[str]) -> bool:
    return store.norm(a["subject"]) == store.norm(subject) and store.norm(a.get("attribute")) == store.norm(attribute)


def annotate(record: Dict[str, Any], peers: List[Dict[str, Any]], staleness: Dict[str, Any]) -> Dict[str, Any]:
    """Add computed flags: stale, expired, conflicts_with."""
    out = dict(record)
    limit = staleness.get(record["category"])
    age = (_today() - dt.date.fromisoformat(record["observed_on"])).days
    out["age_days"] = age
    out["stale"] = bool(limit is not None and age > limit)
    out["expired"] = bool(record.get("expires_on") and record["expires_on"] < _today().isoformat())
    conflicts = []
    if record["status"] == "active" and record.get("attribute"):
        for peer in peers:
            if peer["id"] == record["id"] or peer["status"] != "active":
                continue
            if _same_slot(peer, record["subject"], record.get("attribute")) and store.norm(peer["value"]) != store.norm(
                record["value"]
            ):
                conflicts.append(peer["id"])
    out["conflicts_with"] = conflicts
    return out


def add(
    category: str,
    subject: str,
    value: str,
    source_type: str,
    source_ref: str,
    attribute: Optional[str] = None,
    source_url: Optional[str] = None,
    observed_on: Optional[str] = None,
    verified: bool = False,
    related: Optional[List[str]] = None,
    supersede: bool = False,
    expires_on: Optional[str] = None,
    kind: Optional[str] = None,
    staleness: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    observed = store.parse_date(observed_on).isoformat() if observed_on else _today().isoformat()
    if observed > _today().isoformat():
        raise store.CosError("observed_on cannot be in the future.", store.EXIT_VALIDATION)
    if category == "notes" and not expires_on:
        expires_on = (_today() + dt.timedelta(days=DEFAULT_NOTE_DAYS)).isoformat()
    if expires_on:
        expires_on = store.parse_date(expires_on).isoformat()
    if category == "decisions" and kind not in ("decision", "commitment"):
        raise store.CosError("Decisions need --kind decision or --kind commitment.", store.EXIT_VALIDATION)

    with store.lock():
        data = _load(category)
        now = store.now_iso()
        superseded: List[str] = []
        for existing in data["records"]:
            if existing["status"] != "active" or not _same_slot(existing, subject, attribute):
                continue
            if store.norm(existing["value"]) == store.norm(value):
                # Same fact seen again: refresh it instead of duplicating it.
                if observed > existing["observed_on"]:
                    existing["observed_on"] = observed
                    existing["source"] = {"type": source_type, "ref": source_ref, "url": source_url}
                if verified:
                    existing["verification"] = "verified"
                    existing["verified_at"] = now
                existing["updated_at"] = now
                store.save_store(_rel(category), data)
                return {
                    "record": annotate(existing, data["records"], staleness or {}),
                    "created": False,
                    "deduplicated": True,
                    "superseded": [],
                }
            if supersede and attribute:
                existing["status"] = "superseded"
                existing["updated_at"] = now
                superseded.append(existing["id"])
        record = {
            "id": store.next_id(data, CATEGORIES[category]),
            "category": category,
            "kind": kind,
            "subject": subject.strip(),
            "attribute": attribute.strip() if attribute else None,
            "value": value.strip(),
            "related": [item.strip() for item in (related or []) if item.strip()],
            "source": {"type": source_type.strip(), "ref": source_ref.strip(), "url": source_url},
            "observed_on": observed,
            "verification": "verified" if verified else "unverified",
            "verified_at": now if verified else None,
            "status": "active",
            "superseded_by": None,
            "expires_on": expires_on,
            "recorded_at": now,
            "updated_at": now,
        }
        validate.require(record, "context")
        for existing in data["records"]:
            if existing["id"] in superseded:
                existing["superseded_by"] = record["id"]
        data["records"].append(record)
        store.save_store(_rel(category), data)
        return {
            "record": annotate(record, data["records"], staleness or {}),
            "created": True,
            "deduplicated": False,
            "superseded": superseded,
        }


def _matches(record: Dict[str, Any], subject: Optional[str], query: Optional[str]) -> bool:
    if subject:
        wanted = store.norm(subject)
        names = [store.norm(record["subject"])] + [store.norm(item) for item in record.get("related", [])]
        if wanted not in names:
            return False
    if query:
        haystack = store.norm(" ".join([record["subject"], record.get("attribute") or "", record["value"]]))
        if not all(token in haystack for token in store.norm(query).split()):
            return False
    return True


def search(
    staleness: Dict[str, Any],
    category: Optional[str] = None,
    subject: Optional[str] = None,
    query: Optional[str] = None,
    include_inactive: bool = False,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    if not (subject or query or category):
        raise store.CosError(
            "Give --subject, --query or --category. Context is retrieved in slices, never all at once.",
            store.EXIT_VALIDATION,
        )
    results: List[Dict[str, Any]] = []
    for name in [category] if category else list(CATEGORIES):
        records = _load(name)["records"]
        for record in records:
            if record["status"] != "active" and not include_inactive:
                continue
            if not _matches(record, subject, query):
                continue
            flagged = annotate(record, records, staleness)
            if flagged["expired"] and not include_inactive:
                continue
            results.append(flagged)
    results.sort(key=lambda item: (item["observed_on"], item["id"]), reverse=True)
    return results[: max(1, limit)]


def retire(record_id: str, reason: str) -> Dict[str, Any]:
    with store.lock():
        for category in CATEGORIES:
            data = _load(category)
            for record in data["records"]:
                if record["id"].upper() == record_id.strip().upper():
                    record["status"] = "retired"
                    record["retired_reason"] = reason
                    record["updated_at"] = store.now_iso()
                    store.save_store(_rel(category), data)
                    return record
    raise store.CosError("No context record with id %s" % record_id, store.EXIT_NOT_FOUND)


def verify(record_id: str, source_type: str, source_ref: str) -> Dict[str, Any]:
    """Mark a fact as re-checked against a live source today."""
    with store.lock():
        for category in CATEGORIES:
            data = _load(category)
            for record in data["records"]:
                if record["id"].upper() == record_id.strip().upper():
                    now = store.now_iso()
                    record["verification"] = "verified"
                    record["verified_at"] = now
                    record["observed_on"] = _today().isoformat()
                    record["source"] = {"type": source_type, "ref": source_ref, "url": record["source"].get("url")}
                    record["updated_at"] = now
                    store.save_store(_rel(category), data)
                    return record
    raise store.CosError("No context record with id %s" % record_id, store.EXIT_NOT_FOUND)


def attention(staleness: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Everything that should not be relied on without a fresh check."""
    stale: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    for category in CATEGORIES:
        records = _load(category)["records"]
        for record in records:
            if record["status"] != "active":
                continue
            flagged = annotate(record, records, staleness)
            if flagged["expired"]:
                continue
            brief = {key: flagged[key] for key in ("id", "category", "subject", "attribute", "value", "observed_on")}
            if flagged["stale"]:
                stale.append(dict(brief, age_days=flagged["age_days"]))
            if flagged["conflicts_with"]:
                conflicts.append(dict(brief, conflicts_with=flagged["conflicts_with"]))
    return {"stale": stale, "conflicts": conflicts}


def purge_notes() -> int:
    """Delete working notes whose expiry date has passed."""
    with store.lock():
        data = _load("notes")
        today = _today().isoformat()
        keep = [record for record in data["records"] if not (record.get("expires_on") and record["expires_on"] < today)]
        removed = len(data["records"]) - len(keep)
        if removed:
            data["records"] = keep
            store.save_store(_rel("notes"), data)
        return removed


def bundle(company: str, staleness: Dict[str, Any], limit: int) -> Dict[str, Any]:
    """The slice of context relevant to one company: facts, people, deal, decisions."""
    sections: Dict[str, List[Dict[str, Any]]] = {}
    advice: List[str] = []
    total = 0
    for category in ("companies", "people", "opportunities", "decisions", "notes"):
        # One more than the cap, so truncation can be detected and reported.
        records = search(staleness, category=category, subject=company, limit=limit + 1)
        sections[category] = records
        total += len(records)
        if any(item["stale"] for item in records):
            advice.append(
                "Some %s facts for %s are older than %s days. Re-check the live source before relying on them."
                % (category, company, staleness.get(category))
            )
        if any(item["conflicts_with"] for item in records):
            advice.append("Conflicting %s facts for %s. Resolve against the live source before acting." % (category, company))
        if any(item["verification"] == "unverified" for item in records):
            advice.append("Some %s facts for %s are unverified. Label them as unverified if you use them." % (category, company))
    truncated = total > limit
    if truncated:
        remaining = limit
        for category in sections:
            sections[category] = sections[category][:remaining]
            remaining = max(0, remaining - len(sections[category]))
    return {"company": company, "sections": sections, "advice": advice, "truncated": truncated}

"""Command line interface for the chief-of-staff state store.

Every command prints one JSON object. ok is true on success. On failure ok is
false, error explains why, and the exit code is non-zero:
  1 error, 2 validation, 3 possible duplicate, 4 unreadable store,
  5 refused (permission or approval), 6 not found.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import config, context, feedback, ledger, render, store, tasks, timeutil, validate

SKILLS = [
    "cos-daily-brief",
    "cos-meeting-prep",
    "cos-post-meeting-followup",
    "cos-crm-update",
    "cos-prospect-reengagement",
    "cos-scheduling-travel",
    "cos-pipeline-review",
    "cos-commitment-tracking",
    "cos-feedback",
    "cos-setup",
]
STORE_SCHEMAS = {
    "tasks/tasks.json": "task",
    "ledger/actions.json": "action",
    "ledger/approvals.json": "approval",
    "feedback/feedback.json": "feedback",
    "instructions/rules.json": "rule",
}


def _csv(value: Optional[str]) -> List[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


# ---------------------------------------------------------------- time


def cmd_now(args: argparse.Namespace) -> Dict[str, Any]:
    cfg = config.load()
    return {"now": timeutil.now_info(args.tz or cfg["timezone"])}


def cmd_slots(args: argparse.Namespace) -> Dict[str, Any]:
    cfg = config.load()
    busy = None
    if args.busy_file:
        with open(args.busy_file, "r", encoding="utf-8") as handle:
            busy = json.load(handle)
    elif args.busy_json:
        busy = json.loads(args.busy_json)
    elif not args.no_calendar:
        raise store.CosError(
            "No calendar availability supplied. Read the calendar first and pass --busy-file or --busy-json "
            "with --calendar-checked-at. Use --no-calendar only to get unverified working-hours slots.",
            store.EXIT_VALIDATION,
        )
    if busy is not None and not isinstance(busy, list):
        raise store.CosError("Busy data must be a JSON list of {start, end} blocks.", store.EXIT_VALIDATION)
    return timeutil.find_slots(
        cfg,
        args.start,
        args.days,
        busy,
        args.calendar_checked_at,
        duration_minutes=args.duration,
        attendee_timezones=args.attendee_tz,
        limit=args.limit,
        buffer_minutes=args.buffer,
        attendee_hours_only=args.attendee_hours_only,
        attendee_window=args.attendee_window,
    )


# ---------------------------------------------------------------- tasks


def cmd_task_add(args: argparse.Namespace) -> Dict[str, Any]:
    return tasks.add(
        company=args.company,
        action=args.action,
        owner=args.owner or config.load()["profile"]["name"],
        source_type=args.source_type,
        source_ref=args.source_ref,
        source_url=args.source_url,
        priority=args.priority,
        rationale=args.rationale,
        deadline=args.deadline,
        suggested_deadline=args.suggested_deadline,
        status=args.status,
        waiting_on=args.waiting_on,
        force_new=args.force_new,
    )


def cmd_task_update(args: argparse.Namespace) -> Dict[str, Any]:
    return tasks.update(
        args.id,
        status=args.status,
        note=args.note,
        evidence=args.evidence,
        evidence_ref=args.evidence_ref,
        blocker=args.blocker,
        waiting_on=args.waiting_on,
        deadline=args.deadline,
        suggested_deadline=args.suggested_deadline,
        priority=args.priority,
        rationale=args.rationale,
        action=args.action,
        reopen=args.reopen,
    )


def cmd_task_complete(args: argparse.Namespace) -> Dict[str, Any]:
    return tasks.update(args.id, status="completed", evidence=args.evidence, evidence_ref=args.evidence_ref, note=args.note)


def cmd_task_list(args: argparse.Namespace) -> Dict[str, Any]:
    statuses = _csv(args.status)
    for item in statuses:
        if item not in tasks.STATUSES:
            raise store.CosError("Unknown status %r. Use: %s" % (item, ", ".join(tasks.STATUSES)), store.EXIT_VALIDATION)
    found = tasks.listing(
        statuses=statuses or None,
        company=args.company,
        owner=args.owner,
        due_on_or_before=store.parse_date(args.due_by).isoformat() if args.due_by else None,
        include_completed=args.all,
    )
    brief = [
        {
            "id": task["id"],
            "company": task["company"],
            "action": task["action"],
            "owner": task["owner"],
            "status": task["status"],
            "priority": task["priority"],
            "deadline": task["deadline"],
            "source": task["source"],
            "waiting_on": task.get("waiting_on"),
            "blocker": task.get("blocker"),
        }
        for task in found[: args.limit]
    ]
    return {"count": len(found), "shown": len(brief), "tasks": brief}


def cmd_task_show(args: argparse.Namespace) -> Dict[str, Any]:
    return {"task": tasks.get(args.id), "actions": ledger.listing(task_id=args.id)}


def cmd_task_duplicates(_args: argparse.Namespace) -> Dict[str, Any]:
    return {"possible_duplicate_groups": tasks.duplicates_report()}


# ---------------------------------------------------------------- context


def cmd_context_add(args: argparse.Namespace) -> Dict[str, Any]:
    cfg = config.load()
    return context.add(
        category=args.category,
        subject=args.subject,
        attribute=args.attribute,
        value=args.value,
        source_type=args.source_type,
        source_ref=args.source_ref,
        source_url=args.source_url,
        observed_on=args.observed_on,
        verified=args.verified,
        related=_csv(args.related),
        supersede=args.supersede,
        expires_on=args.expires_on,
        kind=args.kind,
        staleness=cfg["staleness_days"],
    )


def cmd_context_get(args: argparse.Namespace) -> Dict[str, Any]:
    cfg = config.load()
    found = context.search(
        cfg["staleness_days"],
        category=args.category,
        subject=args.subject,
        query=args.query,
        include_inactive=args.include_inactive,
        limit=args.limit,
    )
    return {"count": len(found), "records": found}


def cmd_context_bundle(args: argparse.Namespace) -> Dict[str, Any]:
    cfg = config.load()
    result = context.bundle(args.company, cfg["staleness_days"], args.limit or cfg["context"]["max_bundle_items"])
    result["open_tasks"] = cmd_task_list(
        argparse.Namespace(status=None, company=args.company, owner=None, due_by=None, all=False, limit=15)
    )["tasks"]
    return result


def cmd_context_attention(_args: argparse.Namespace) -> Dict[str, Any]:
    return context.attention(config.load()["staleness_days"])


def cmd_context_verify(args: argparse.Namespace) -> Dict[str, Any]:
    return {"record": context.verify(args.id, args.source_type, args.source_ref)}


def cmd_context_retire(args: argparse.Namespace) -> Dict[str, Any]:
    return {"record": context.retire(args.id, args.reason)}


def cmd_context_purge(_args: argparse.Namespace) -> Dict[str, Any]:
    return {"expired_notes_removed": context.purge_notes()}


def cmd_commitment_add(args: argparse.Namespace) -> Dict[str, Any]:
    """Record who promised what, and track the action it creates."""
    cfg = config.load()
    me = cfg["profile"]["name"]
    mine = store.norm(args.who) in ("me", "i", store.norm(me))
    who = me if mine else args.who
    statement = "%s committed to %s: %s" % (who, args.to, args.what)
    if args.quote:
        statement += ' (said: "%s")' % args.quote.strip()
    decision = context.add(
        category="decisions",
        kind="commitment",
        subject=args.company,
        attribute="commitment " + store.sha(store.norm(who) + store.norm(args.what), 8),
        value=statement,
        source_type=args.source_type,
        source_ref=args.source_ref,
        source_url=args.source_url,
        observed_on=args.observed_on,
        verified=args.verified,
        staleness=cfg["staleness_days"],
    )
    task = tasks.add(
        company=args.company,
        action=args.what,
        owner=who,
        source_type=args.source_type,
        source_ref=args.source_ref,
        source_url=args.source_url,
        priority=args.priority,
        rationale=args.rationale or "Commitment made to %s" % args.to,
        deadline=args.due,
        suggested_deadline=args.suggested_due,
        status="proposed" if mine else "waiting_on_other",
        kind="commitment",
        waiting_on=None if mine else who,
        force_new=args.force_new,
        decision_id=decision["record"]["id"],
    )
    return {"commitment": decision["record"], "commitment_created": decision["created"], "task": task["task"],
            "task_created": task["created"]}


# ---------------------------------------------------------------- actions


def cmd_action_plan(args: argparse.Namespace) -> Dict[str, Any]:
    return ledger.plan(
        config.load(),
        action_type=args.type,
        target=args.target,
        summary=args.summary,
        task_id=args.task,
        key=args.key,
        fingerprint=args.fingerprint,
        approval_id=args.approval,
    )


def cmd_action_confirm(args: argparse.Namespace) -> Dict[str, Any]:
    return {"action": ledger.confirm(args.key, args.system_ref)}


def cmd_action_fail(args: argparse.Namespace) -> Dict[str, Any]:
    return {"action": ledger.fail(args.key, args.error)}


def cmd_action_status(args: argparse.Namespace) -> Dict[str, Any]:
    return ledger.status(args.key)


def cmd_action_list(args: argparse.Namespace) -> Dict[str, Any]:
    found = ledger.listing(args.status, args.task)
    return {"count": len(found), "actions": found[-args.limit:]}


def cmd_approval_record(args: argparse.Namespace) -> Dict[str, Any]:
    return {"approval": ledger.record_approval(config.load(), args.type, args.target, args.quote, args.task)}


def cmd_approval_list(_args: argparse.Namespace) -> Dict[str, Any]:
    return {"approvals": store.load_store(ledger.APPROVALS_REL, "approvals")["records"][-25:]}


# ---------------------------------------------------------------- feedback


def cmd_feedback_add(args: argparse.Namespace) -> Dict[str, Any]:
    return feedback.add(args.type, args.text, skill=args.skill, task_id=args.task, theme=args.theme,
                        explicit_standing=args.standing)


def cmd_feedback_list(args: argparse.Namespace) -> Dict[str, Any]:
    return {"feedback": feedback.listing(args.type, args.theme, args.limit)}


def cmd_rules_propose(args: argparse.Namespace) -> Dict[str, Any]:
    result = feedback.propose(config.load(), args.text, args.reason, args.kind, _csv(args.source))
    result["agents_md"] = render.render()
    return result


def cmd_rules_revert(args: argparse.Namespace) -> Dict[str, Any]:
    result = feedback.revert(args.id, args.reason)
    result["agents_md"] = render.render()
    return result


def cmd_rules_list(_args: argparse.Namespace) -> Dict[str, Any]:
    return feedback.rules_state()


# ---------------------------------------------------------------- config


def cmd_config_show(_args: argparse.Namespace) -> Dict[str, Any]:
    return {"path": str(store.config_path()), "exists": store.config_path().exists(), "config": config.load()}


def cmd_config_validate(_args: argparse.Namespace) -> Dict[str, Any]:
    errors, warnings = config.validate(config.load())
    if errors:
        raise store.CosError("Config is invalid: %s" % "; ".join(errors), store.EXIT_VALIDATION,
                             {"errors": errors, "warnings": warnings})
    return {"valid": True, "warnings": warnings}


def cmd_config_get(args: argparse.Namespace) -> Dict[str, Any]:
    return {"key": args.key, "value": config.get_value(config.load(), args.key)}


def cmd_config_set(args: argparse.Namespace) -> Dict[str, Any]:
    try:
        value = json.loads(args.value)
    except ValueError:
        value = args.value
    if args.key.startswith("permissions"):
        raise store.CosError(
            "Permissions are not changed through the CLI. Edit config/cos.config.json yourself if you really "
            "mean to, then run cos config validate. Send, invite, CRM write and Slack post stay approval-only.",
            store.EXIT_REFUSED,
        )
    config.set_value(args.key, value)
    result: Dict[str, Any] = {"key": args.key, "value": value}
    if args.key.split(".")[0] in ("profile", "timezone", "working_hours", "scheduling"):
        result["agents_md"] = render.render()
    return result


def cmd_connector_list(_args: argparse.Namespace) -> Dict[str, Any]:
    cfg = config.load()
    return {"connectors": cfg["connectors"], "transcript_provider": cfg["transcript_provider"]}


def cmd_connector_set(args: argparse.Namespace) -> Dict[str, Any]:
    if args.name not in config.CONNECTORS:
        raise store.CosError("Unknown connector %r. Use: %s" % (args.name, ", ".join(config.CONNECTORS)),
                             store.EXIT_VALIDATION)
    if args.status == "connected" and not args.evidence:
        raise store.CosError(
            "Marking a connector as connected needs --evidence: what read-only call succeeded just now.",
            store.EXIT_VALIDATION,
        )
    entry = {"status": args.status, "via": args.via or "", "checked_at": store.now_iso(), "evidence": args.evidence or ""}
    config.set_value("connectors.%s" % args.name, entry)
    if args.provider:
        config.set_value("transcript_provider", args.provider)
    return {"connector": args.name, "entry": entry}


# ---------------------------------------------------------------- routines


def _routine_state(name: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    prompt_path = store.root() / "routines" / ("%s.md" % name)
    configured = bool(entry.get("time") and entry.get("timezone") and entry.get("deliver_to"))
    if not entry.get("enabled"):
        state = "installed, schedule disabled"
    elif not configured:
        state = "enabled but not fully configured"
    elif not entry.get("schedule_confirmed_at"):
        state = "configured, but no schedule exists in Codex yet (not running)"
    else:
        state = "active: schedule confirmed in Codex on %s" % entry["schedule_confirmed_at"]
    return dict(entry, installed=prompt_path.exists(), configured=configured, state=state)


def cmd_routine_list(_args: argparse.Namespace) -> Dict[str, Any]:
    cfg = config.load()
    return {
        "routines": {name: _routine_state(name, cfg["routines"][name]) for name in config.ROUTINES},
        "note": "This package cannot create a schedule. A routine only runs once you create a Scheduled task "
        "in the ChatGPT desktop app (see docs/ROUTINES.md) and confirm it with: cos routine confirm NAME",
    }


def _routine_name(name: str) -> str:
    if name not in config.ROUTINES:
        raise store.CosError("Unknown routine %r. Use: %s" % (name, ", ".join(config.ROUTINES)), store.EXIT_VALIDATION)
    return name


def cmd_routine_configure(args: argparse.Namespace) -> Dict[str, Any]:
    name = _routine_name(args.name)
    cfg = config.load()
    entry = dict(cfg["routines"][name])
    entry.update({"enabled": True, "time": args.time, "timezone": args.timezone, "deliver_to": args.deliver_to,
                  "schedule_confirmed_at": None})
    if args.days:
        entry["days"] = _csv(args.days)
    config.set_value("routines.%s" % name, entry)
    return {"routine": name, "entry": _routine_state(name, entry), "next_step": "Create the schedule in the ChatGPT "
            "desktop app using: cos routine prompt %s. Then run: cos routine confirm %s" % (name, name)}


def cmd_routine_prompt(args: argparse.Namespace) -> Dict[str, Any]:
    name = _routine_name(args.name)
    entry = config.load()["routines"][name]
    if not (entry.get("enabled") and entry.get("time") and entry.get("timezone") and entry.get("deliver_to")):
        raise store.CosError("Configure the routine first: cos routine configure %s --time HH:MM --timezone ZONE "
                             "--deliver-to WHERE" % name, store.EXIT_VALIDATION)
    body = (store.root() / "routines" / ("%s.md" % name)).read_text(encoding="utf-8")
    body = body.split("---PROMPT---", 1)[-1].strip()
    schedule = "Schedule: %s at %s (%s). Deliver to: %s." % (", ".join(entry["days"]), entry["time"], entry["timezone"],
                                                              entry["deliver_to"])
    return {"routine": name, "schedule": schedule, "prompt": body + "\n\n" + schedule}


def cmd_routine_confirm(args: argparse.Namespace) -> Dict[str, Any]:
    name = _routine_name(args.name)
    entry = dict(config.load()["routines"][name])
    if not (entry.get("enabled") and entry.get("time") and entry.get("timezone") and entry.get("deliver_to")):
        raise store.CosError("Routine %s is not configured, so there is nothing to confirm." % name, store.EXIT_VALIDATION)
    entry["schedule_confirmed_at"] = store.now_iso()
    config.set_value("routines.%s" % name, entry)
    return {"routine": name, "entry": _routine_state(name, entry)}


def cmd_routine_disable(args: argparse.Namespace) -> Dict[str, Any]:
    name = _routine_name(args.name)
    entry = dict(config.load()["routines"][name])
    entry.update({"enabled": False, "schedule_confirmed_at": None})
    config.set_value("routines.%s" % name, entry)
    return {"routine": name, "entry": _routine_state(name, entry), "reminder": "This only updates the local record. "
            "Pause or delete the Scheduled task in the ChatGPT desktop app yourself, or it will keep running."}


# ---------------------------------------------------------------- brief, doctor, demo


def cmd_brief_data(args: argparse.Namespace) -> Dict[str, Any]:
    """Local state for a daily or weekly brief. Live systems are read separately."""
    cfg = config.load()
    today = store.parse_date(args.date) if args.date else timeutil.today(cfg)
    horizon = today + dt.timedelta(days=args.days)
    buckets: Dict[str, List[Dict[str, Any]]] = {
        "overdue": [], "due_today": [], "due_soon": [], "awaiting_approval": [], "waiting_on_other": [], "blocked": [],
        "no_deadline": [],
    }
    for task in tasks.listing():
        item = {key: task[key] for key in ("id", "company", "action", "owner", "status", "priority", "deadline", "source")}
        item["waiting_on"], item["blocker"] = task.get("waiting_on"), task.get("blocker")
        if task["status"] == "awaiting_approval":
            buckets["awaiting_approval"].append(item)
        if task["status"] == "waiting_on_other":
            buckets["waiting_on_other"].append(item)
        if task["status"] == "blocked":
            buckets["blocked"].append(item)
        due = task["deadline"]["date"] if task.get("deadline") else None
        if not due:
            buckets["no_deadline"].append(item)
        elif due < today.isoformat():
            buckets["overdue"].append(item)
        elif due == today.isoformat():
            buckets["due_today"].append(item)
        elif due <= horizon.isoformat():
            buckets["due_soon"].append(item)
    unconfirmed = [
        {"key": item["key"], "type": item["type"], "target": item["target"], "summary": item["summary"],
         "task_id": item["task_id"], "status": item["status"], "error": item["error"]}
        for item in ledger.listing() if item["status"] != "confirmed"
    ]
    attention = context.attention(cfg["staleness_days"])
    return {
        "now": timeutil.now_info(cfg["timezone"]),
        "for_date": today.isoformat(),
        "window_days": args.days,
        "tasks": buckets,
        "actions_not_confirmed": unconfirmed,
        "context_attention": {
            "stale_count": len(attention["stale"]),
            "conflict_count": len(attention["conflicts"]),
            "stale": attention["stale"][:8],
            "conflicts": attention["conflicts"][:8],
        },
        "connectors": {name: entry["status"] for name, entry in cfg["connectors"].items()},
        "routines": {name: _routine_state(name, cfg["routines"][name])["state"] for name in config.ROUTINES},
    }


def cmd_render(_args: argparse.Namespace) -> Dict[str, Any]:
    return render.render()


def cmd_doctor(_args: argparse.Namespace) -> Dict[str, Any]:
    checks: List[Dict[str, str]] = []

    def record(name: str, status: str, detail: str = "") -> None:
        checks.append({"check": name, "status": status, "detail": detail})

    root = store.root()
    record("python", "pass" if sys.version_info >= (3, 9) else "fail", sys.version.split()[0])
    for rel in ("bin/cos", "core/AGENTS.core.md", "core/VERSION", "schemas/task.schema.json", "routines/morning.md"):
        record("file " + rel, "pass" if (root / rel).exists() else "fail")
    missing = [name for name in SKILLS if not (root / ".agents" / "skills" / name / "SKILL.md").exists()]
    record("skills installed", "fail" if missing else "pass",
           ("missing: " + ", ".join(missing)) if missing else "%d skills" % len(SKILLS))
    try:
        cfg = config.load()
        errors, warnings = config.validate(cfg)
        record("config file", "pass" if store.config_path().exists() else "warn",
               str(store.config_path()) if store.config_path().exists() else "missing, using defaults")
        record("config valid", "fail" if errors else "pass", "; ".join(errors))
        for warning in warnings:
            record("config note", "warn", warning)
        record("timezone", "pass" if config.timezone_ok(cfg["timezone"]) else "fail",
               "%s, now %s" % (cfg["timezone"], timeutil.now_info(cfg["timezone"])["local"])
               if config.timezone_ok(cfg["timezone"]) else str(cfg.get("timezone")))
    except store.CosError as exc:
        record("config valid", "fail", exc.message)
    base = store.data_dir()
    try:
        base.mkdir(parents=True, exist_ok=True)
        probe = base / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        record("data directory writable", "pass", str(base))
    except OSError as exc:
        record("data directory writable", "fail", "%s (%s). In Codex, use a mode that can write to the workspace." % (base, exc))
    rels = dict(STORE_SCHEMAS)
    rels.update({"context/%s.json" % name: "context" for name in context.CATEGORIES})
    for rel, schema_name in sorted(rels.items()):
        try:
            data = store.load_store(rel, schema_name)
            schema = validate.load_schema(schema_name)
            problems: List[str] = []
            for item in data["records"]:
                problems.extend(validate.check(item, schema, item.get("id") or item.get("key") or "$"))
            record("store " + rel, "fail" if problems else "pass",
                   "; ".join(problems[:3]) if problems else "%d records" % len(data["records"]))
        except store.CosError as exc:
            record("store " + rel, "fail", exc.message)
    try:
        agents = render.status()
        if not agents["exists"]:
            record("AGENTS.md", "fail", "missing. Run: bin/cos render")
        elif agents["hand_edited"]:
            record("AGENTS.md", "warn", "edited by hand. bin/cos render will back it up and regenerate it.")
        elif not agents["in_sync"]:
            record("AGENTS.md", "warn", "out of date with config or rules. Run: bin/cos render")
        else:
            record("AGENTS.md", "pass", "%d bytes (Codex limit 32768)" % agents["bytes"])
    except (store.CosError, OSError) as exc:
        record("AGENTS.md", "fail", str(exc))
    failed = [item for item in checks if item["status"] == "fail"]
    result = {"healthy": not failed, "failed": len(failed),
              "warnings": len([item for item in checks if item["status"] == "warn"]), "checks": checks}
    if failed:
        raise store.CosError("%d check(s) failed." % len(failed), store.EXIT_ERROR, result)
    return result


def _demo_dir() -> Path:
    return store.root() / "data-demo"


def cmd_demo_init(args: argparse.Namespace) -> Dict[str, Any]:
    target = _demo_dir()
    existed = target.exists()
    if existed and args.reset:
        shutil.rmtree(str(target))
    target.mkdir(parents=True, exist_ok=True)
    return {
        "demo_data_dir": str(target),
        "reset": bool(existed and args.reset),
        "fixtures": str(store.root() / "demo" / "fixtures"),
        "how_to_use": "Add --demo straight after bin/cos, for example: bin/cos --demo task list. "
        "Demo data is synthetic and kept apart from your real data.",
    }


def cmd_version(_args: argparse.Namespace) -> Dict[str, Any]:
    return {"package": "chief-of-staff-codex", "version": render.package_version(),
            "instructions_version": feedback.rules_state()["instructions_version"], "root": str(store.root()),
            "data_dir": str(store.data_dir())}


# ---------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cos", description="Chief-of-staff state store. Prints JSON.")
    parser.add_argument("--demo", action="store_true", help="use the synthetic demo data directory")
    groups = parser.add_subparsers(dest="group")
    groups.required = True

    def leaf(parent: Any, name: str, func: Callable[..., Dict[str, Any]], help_text: str) -> argparse.ArgumentParser:
        sub = parent.add_parser(name, help=help_text)
        sub.set_defaults(func=func)
        return sub

    def group(name: str, help_text: str) -> Any:
        sub = groups.add_parser(name, help=help_text).add_subparsers(dest="command")
        sub.required = True
        return sub

    now = leaf(groups, "now", cmd_now, "current local time, offset and daylight saving")
    now.add_argument("--tz")

    slots = leaf(groups, "slots", cmd_slots, "candidate meeting times from current availability")
    slots.add_argument("--from", dest="start", required=True, help="first date to consider, YYYY-MM-DD")
    slots.add_argument("--days", type=int, default=5)
    slots.add_argument("--busy-file")
    slots.add_argument("--busy-json")
    slots.add_argument("--no-calendar", action="store_true")
    slots.add_argument("--calendar-checked-at", help="when the calendar was read, ISO 8601")
    slots.add_argument("--duration", type=int)
    slots.add_argument("--buffer", type=int)
    slots.add_argument("--attendee-tz", action="append")
    slots.add_argument("--attendee-hours-only", action="store_true",
                       help="leave out times outside the attendees' business hours")
    slots.add_argument("--attendee-window", help="attendee's preferred local hours, for example 13:00-15:00")
    slots.add_argument("--limit", type=int, default=6)

    task = group("task", "task queue")
    add = leaf(task, "add", cmd_task_add, "add a task (deduplicated)")
    add.add_argument("--company", required=True)
    add.add_argument("--action", required=True)
    add.add_argument("--owner")
    add.add_argument("--source-type", required=True)
    add.add_argument("--source-ref", required=True)
    add.add_argument("--source-url")
    add.add_argument("--priority", required=True, choices=tasks.PRIORITIES)
    add.add_argument("--rationale", required=True)
    add.add_argument("--deadline", help="explicit deadline stated in the source")
    add.add_argument("--suggested-deadline", help="your suggestion, labelled as such")
    add.add_argument("--status", default="proposed", choices=tasks.STATUSES)
    add.add_argument("--waiting-on")
    add.add_argument("--force-new", action="store_true")
    upd = leaf(task, "update", cmd_task_update, "change status or details")
    upd.add_argument("id")
    upd.add_argument("--status", choices=tasks.STATUSES)
    upd.add_argument("--note")
    upd.add_argument("--evidence")
    upd.add_argument("--evidence-ref")
    upd.add_argument("--blocker")
    upd.add_argument("--waiting-on")
    upd.add_argument("--deadline")
    upd.add_argument("--suggested-deadline")
    upd.add_argument("--priority", choices=tasks.PRIORITIES)
    upd.add_argument("--rationale")
    upd.add_argument("--action")
    upd.add_argument("--reopen", action="store_true")
    done = leaf(task, "complete", cmd_task_complete, "complete a task with evidence")
    done.add_argument("id")
    done.add_argument("--evidence", required=True)
    done.add_argument("--evidence-ref")
    done.add_argument("--note")
    lst = leaf(task, "list", cmd_task_list, "list open tasks")
    lst.add_argument("--status", help="comma separated")
    lst.add_argument("--company")
    lst.add_argument("--owner")
    lst.add_argument("--due-by")
    lst.add_argument("--all", action="store_true", help="include completed")
    lst.add_argument("--limit", type=int, default=30)
    show = leaf(task, "show", cmd_task_show, "full task with history and actions")
    show.add_argument("id")
    leaf(task, "duplicates", cmd_task_duplicates, "report open tasks that look like the same work")

    ctx = group("context", "persistent context")
    cadd = leaf(ctx, "add", cmd_context_add, "record a fact with its source")
    cadd.add_argument("--category", required=True, choices=list(context.CATEGORIES))
    cadd.add_argument("--subject", required=True)
    cadd.add_argument("--attribute")
    cadd.add_argument("--value", required=True)
    cadd.add_argument("--source-type", required=True)
    cadd.add_argument("--source-ref", required=True)
    cadd.add_argument("--source-url")
    cadd.add_argument("--observed-on")
    cadd.add_argument("--verified", action="store_true")
    cadd.add_argument("--related", help="comma separated, for example the person's company")
    cadd.add_argument("--supersede", action="store_true")
    cadd.add_argument("--expires-on")
    cadd.add_argument("--kind", choices=["decision", "commitment"])
    cget = leaf(ctx, "get", cmd_context_get, "retrieve a slice of context")
    cget.add_argument("--category", choices=list(context.CATEGORIES))
    cget.add_argument("--subject")
    cget.add_argument("--query")
    cget.add_argument("--include-inactive", action="store_true")
    cget.add_argument("--limit", type=int, default=25)
    cbundle = leaf(ctx, "bundle", cmd_context_bundle, "everything relevant to one company")
    cbundle.add_argument("--company", required=True)
    cbundle.add_argument("--limit", type=int)
    leaf(ctx, "attention", cmd_context_attention, "stale and conflicting facts")
    cver = leaf(ctx, "verify", cmd_context_verify, "mark a fact as re-checked today")
    cver.add_argument("id")
    cver.add_argument("--source-type", required=True)
    cver.add_argument("--source-ref", required=True)
    cret = leaf(ctx, "retire", cmd_context_retire, "retire a fact that is no longer true")
    cret.add_argument("id")
    cret.add_argument("--reason", required=True)
    leaf(ctx, "purge-notes", cmd_context_purge, "delete expired working notes")

    com = group("commitment", "commitments")
    madd = leaf(com, "add", cmd_commitment_add, "record a commitment and track its action")
    madd.add_argument("--company", required=True)
    madd.add_argument("--who", required=True, help="me, or the person who made the commitment")
    madd.add_argument("--to", required=True)
    madd.add_argument("--what", required=True)
    madd.add_argument("--quote")
    madd.add_argument("--source-type", required=True)
    madd.add_argument("--source-ref", required=True)
    madd.add_argument("--source-url")
    madd.add_argument("--observed-on")
    madd.add_argument("--verified", action="store_true")
    madd.add_argument("--due")
    madd.add_argument("--suggested-due")
    madd.add_argument("--priority", default="medium", choices=tasks.PRIORITIES)
    madd.add_argument("--rationale")
    madd.add_argument("--force-new", action="store_true")

    act = group("action", "outward-facing action ledger")
    plan = leaf(act, "plan", cmd_action_plan, "ask whether an action may proceed")
    plan.add_argument("--type", required=True)
    plan.add_argument("--target", required=True)
    plan.add_argument("--summary", required=True)
    plan.add_argument("--task")
    plan.add_argument("--key")
    plan.add_argument("--fingerprint")
    plan.add_argument("--approval")
    conf = leaf(act, "confirm", cmd_action_confirm, "record the system's confirmation")
    conf.add_argument("key")
    conf.add_argument("--system-ref", required=True)
    fail = leaf(act, "fail", cmd_action_fail, "record a failed attempt")
    fail.add_argument("key")
    fail.add_argument("--error", required=True)
    stat = leaf(act, "status", cmd_action_status, "what may truthfully be reported")
    stat.add_argument("key")
    alst = leaf(act, "list", cmd_action_list, "list actions")
    alst.add_argument("--status", choices=["planned", "confirmed", "failed"])
    alst.add_argument("--task")
    alst.add_argument("--limit", type=int, default=25)

    appr = group("approval", "explicit approvals from the user")
    arec = leaf(appr, "record", cmd_approval_record, "record a single-use approval")
    arec.add_argument("--type", required=True)
    arec.add_argument("--target", required=True)
    arec.add_argument("--quote", required=True, help="the user's own words")
    arec.add_argument("--task")
    leaf(appr, "list", cmd_approval_list, "recent approvals")

    fb = group("feedback", "feedback capture")
    fadd = leaf(fb, "add", cmd_feedback_add, "record feedback")
    fadd.add_argument("--type", required=True, choices=feedback.TYPES)
    fadd.add_argument("--text", required=True)
    fadd.add_argument("--skill")
    fadd.add_argument("--task")
    fadd.add_argument("--theme", help="short label so repeated feedback can be counted")
    fadd.add_argument("--standing", action="store_true", help="the user stated it as a rule from now on")
    flst = leaf(fb, "list", cmd_feedback_list, "recent feedback")
    flst.add_argument("--type", choices=feedback.TYPES)
    flst.add_argument("--theme")
    flst.add_argument("--limit", type=int, default=25)

    rules = group("rules", "versioned learned rules")
    rprop = leaf(rules, "propose", cmd_rules_propose, "turn feedback into a reusable rule")
    rprop.add_argument("--text", required=True)
    rprop.add_argument("--reason", required=True)
    rprop.add_argument("--kind", required=True, choices=feedback.RULE_KINDS)
    rprop.add_argument("--from", dest="source", required=True, help="feedback ids, comma separated")
    rrev = leaf(rules, "revert", cmd_rules_revert, "revert a rule")
    rrev.add_argument("id")
    rrev.add_argument("--reason", required=True)
    leaf(rules, "list", cmd_rules_list, "active rules and version history")

    cfg = group("config", "configuration")
    leaf(cfg, "show", cmd_config_show, "effective config")
    leaf(cfg, "validate", cmd_config_validate, "validate the config")
    cgetv = leaf(cfg, "get", cmd_config_get, "read one key")
    cgetv.add_argument("key")
    cset = leaf(cfg, "set", cmd_config_set, "set one key (value is JSON or text)")
    cset.add_argument("key")
    cset.add_argument("value")

    con = group("connector", "connector status")
    leaf(con, "list", cmd_connector_list, "recorded connector status")
    cons = leaf(con, "set", cmd_connector_set, "record the result of a read-only check")
    cons.add_argument("name")
    cons.add_argument("--status", required=True, choices=["connected", "unavailable", "unknown"])
    cons.add_argument("--via")
    cons.add_argument("--evidence")
    cons.add_argument("--provider", choices=["fathom", "granola", "other", "none"])

    rout = group("routine", "recurring routines")
    leaf(rout, "list", cmd_routine_list, "installed versus active")
    rcfg = leaf(rout, "configure", cmd_routine_configure, "choose time, time zone and delivery")
    rcfg.add_argument("name")
    rcfg.add_argument("--time", required=True)
    rcfg.add_argument("--timezone", required=True)
    rcfg.add_argument("--deliver-to", required=True)
    rcfg.add_argument("--days")
    for name, func, text in (("prompt", cmd_routine_prompt, "the prompt to schedule in Codex"),
                             ("confirm", cmd_routine_confirm, "record that you created the schedule"),
                             ("disable", cmd_routine_disable, "mark the routine disabled")):
        leaf(rout, name, func, text).add_argument("name")

    brief = group("brief", "brief inputs")
    bdata = leaf(brief, "data", cmd_brief_data, "local state for a daily or weekly brief")
    bdata.add_argument("--date")
    bdata.add_argument("--days", type=int, default=7)

    leaf(groups, "render", cmd_render, "regenerate AGENTS.md")
    leaf(groups, "doctor", cmd_doctor, "check the installation")
    demo = group("demo", "synthetic demo data")
    dinit = leaf(demo, "init", cmd_demo_init, "create the demo data directory")
    dinit.add_argument("--reset", action="store_true")
    leaf(groups, "version", cmd_version, "package and instruction versions")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.demo:
        os.environ["COS_DATA_DIR"] = str(_demo_dir())
    try:
        result = args.func(args)
        payload: Dict[str, Any] = {"ok": True}
        if args.demo:
            payload["demo"] = True
        payload.update(result)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return store.EXIT_OK
    except store.CosError as exc:
        payload = {"ok": False, "error": exc.message, "exit_code": exc.code}
        payload.update(exc.details)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return exc.code
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": "%s: %s" % (type(exc).__name__, exc), "exit_code": store.EXIT_ERROR},
                         indent=2))
        return store.EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())

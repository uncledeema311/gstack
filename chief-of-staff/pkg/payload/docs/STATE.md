# State: what is stored, where, and how to read it

All persistent state is plain JSON under `data/` in the workspace. The assistant reads and writes it only through `bin/cos`, which validates every record, prevents duplicates and writes atomically. Every command prints one JSON object.

Later sessions retrieve state by asking for a slice. Nothing loads the whole history into a conversation.

## Stores

| What | File | Schema |
|---|---|---|
| Stable preferences | `data/context/preferences.json` | `schemas/context.schema.json` |
| Product and commercial reference | `data/context/reference.json` | same |
| People | `data/context/people.json` | same |
| Companies | `data/context/companies.json` | same |
| Active opportunities | `data/context/opportunities.json` | same |
| Decisions and commitments (the record of what was agreed) | `data/context/decisions.json` | same |
| Temporary working notes (expire after 7 days by default) | `data/context/notes.json` | same |
| Task queue | `data/tasks/tasks.json` | `schemas/task.schema.json` |
| Action ledger | `data/ledger/actions.json` | `schemas/action.schema.json` |
| Approvals | `data/ledger/approvals.json` | `schemas/approval.schema.json` |
| Feedback | `data/feedback/feedback.json` | `schemas/feedback.schema.json` |
| Learned rules and their version history | `data/instructions/rules.json` | `schemas/rule.schema.json` |
| Your own standing instructions | `data/instructions/custom.md` | free text |
| Settings | `config/cos.config.json` | example in `config/cos.config.example.json` |

Each store keeps one previous generation beside it as `<file>.bak`. Examples of a task and a context record are in `templates/`.

## Context

Every fact has a subject, a value, a source reference, the date it was observed, and a verification status. Computed on every read:

- `stale`: older than the limit for its category (`staleness_days` in config: opportunities 14 days, people, companies and reference 180, notes 7, preferences and decisions never).
- `conflicts_with`: another active fact with the same subject and attribute but a different value.

```bash
bin/cos context add --category people --subject "Full Name" --attribute role --value "Chief Financial Officer" \
  --related "Company Name" --source-type hubspot --source-ref "hubspot:contact:123" --verified
bin/cos context get --subject "Full Name"
bin/cos context get --category opportunities --query "proposal"
bin/cos context bundle --company "Company Name"      # facts, people, deal, decisions and open tasks for one company
bin/cos context attention                            # everything stale or conflicting
bin/cos context verify PE-0001 --source-type hubspot --source-ref "hubspot:contact:123"
bin/cos context add ... --supersede                  # replace an older value for the same subject and attribute
bin/cos context retire PE-0001 --reason "Left the company"
bin/cos context purge-notes
```

## Tasks

Fields: stable id, company or project, specific next action, owner, source reference, deadline (explicit or suggested, never mixed), priority with rationale, status, evidence of completion, history.

Statuses: `proposed`, `drafted`, `awaiting_approval`, `in_progress`, `waiting_on_other`, `completed`, `blocked`.

```bash
bin/cos task add --company "Company Name" --action "Send the pricing summary" --source-type transcript \
  --source-ref "fathom:recording:456" --priority high --rationale "Promised on the call" --deadline 2026-11-13
bin/cos task add ... --suggested-deadline 2026-11-17      # when nobody stated a date
bin/cos task list
bin/cos task list --status waiting_on_other --company "Company Name"
bin/cos task show T-0001
bin/cos task update T-0001 --status blocked --blocker "Gmail connector failed"
bin/cos task complete T-0001 --evidence "Sent" --evidence-ref "gmail:message:abc"
bin/cos task duplicates
bin/cos commitment add --company "Company Name" --who me --to "Full Name" --what "Send the pricing summary" \
  --source-type transcript --source-ref "fathom:recording:456" --due 2026-11-13
```

Duplicates: the same company and action (ignoring case and punctuation) returns the existing task. A similar action exits with code 3 and lists the candidates. `--force-new` overrides.

## Action ledger and approvals

```bash
bin/cos action plan --type gmail_draft --target "name@example.com" --summary "Follow-up" --task T-0001
bin/cos action confirm <key> --system-ref "gmail:draft:r123"
bin/cos action fail <key> --error "connector timed out"
bin/cos action status <key>          # may_report_as_done is true only after confirm
bin/cos action list --status planned
bin/cos approval record --type email_send --target "name@example.com" --quote "yes, send it" --task T-0001
bin/cos action plan --type email_send --target "name@example.com" --summary "Send follow-up" --task T-0001 --approval A-0001
```

`plan` answers one of: proceed, already confirmed (do not repeat), verify first (an earlier attempt has no recorded outcome), or exit code 5 (approval needed, or never permitted). An approval covers one action type, one target, one use, and expires after 12 hours.

## Feedback and learned rules

```bash
bin/cos feedback add --type task_correction --text "Subject too long" --skill cos-post-meeting-followup --theme "subject length"
bin/cos feedback add --type durable_preference --text "From now on, ask in the first line" --standing
bin/cos feedback list --theme "subject length"
bin/cos rules propose --kind style --text "Keep email subject lines under six words." --reason "Asked twice" --from F-0001,F-0002
bin/cos rules list
bin/cos rules revert R-0001 --reason "No longer wanted"
```

A rule needs either feedback stated as a standing rule, or the same theme at least twice. Factual updates go to context. Rules that would widen permissions are refused. Each change increments the instructions version, records the reason, and regenerates `AGENTS.md`.

## Time

```bash
bin/cos now
bin/cos now --tz Australia/Perth
bin/cos slots --from 2026-11-16 --days 5 --busy-file busy.json --calendar-checked-at "2026-11-12T00:49:00Z" \
  --duration 30 --attendee-tz Australia/Perth --attendee-window 13:00-15:00 --attendee-hours-only
```

`busy.json` is a list of `{"start": ..., "end": ...}` blocks with UTC offsets (shape in `templates/busy.example.json`). Without busy data and a read time under an hour old, `availability_verified` is false.

## Settings, connectors, routines, health

```bash
bin/cos config show
bin/cos config validate
bin/cos config set timezone Australia/Perth
bin/cos connector list
bin/cos connector set gmail --status connected --via "Gmail plugin" --evidence "profile call succeeded"
bin/cos routine list
bin/cos brief data
bin/cos render
bin/cos doctor
bin/cos version
bin/cos --demo task list            # the same commands against synthetic demo data
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Error, or a failed health check |
| 2 | Invalid input or invalid config |
| 3 | A similar open task already exists |
| 4 | A data file is unreadable. It was left untouched |
| 5 | Refused: approval needed, action never permitted, or a protected change |
| 6 | Not found |

## Backing up and moving

Copy `data/` and `config/`. To move to another Mac, install the package there, then copy those two folders into the new workspace and run `bin/cos doctor`.

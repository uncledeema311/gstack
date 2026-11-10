# Chief of staff for Codex

Version 1.0.0. Target: Codex (Codex CLI and Codex in the ChatGPT desktop app) on macOS.

A persistent assistant that retrieves work context, identifies commitments and next actions, prepares you for meetings, drafts follow-ups and CRM updates, coordinates scheduling and travel preparation, reviews pipeline health, and improves its reusable instructions from your corrections.

It works as one loop:

> Receive a request, retrieve current evidence, choose the skill, prepare or execute authorised work, verify the result, update task state, retain feedback.

## What it installs

Everything goes into one workspace folder, `~/ChiefOfStaff` by default. Nothing is written to `~/.codex`, your shell profile or anywhere else.

```
~/ChiefOfStaff/
  AGENTS.md                  Generated. The single set of shared rules Codex loads every session.
  .agents/skills/cos-*/      Ten skills, discovered natively by Codex.
  bin/cos                    State CLI the assistant uses (Python 3.9+, standard library only).
  lib/cos/                   Its code.
  core/                      Packaged core instructions and version.
  schemas/ templates/        Record schemas and output shapes.
  routines/                  Morning, afternoon and weekly prompts. Not scheduled.
  demo/                      Synthetic fixtures and the walkthrough script.
  docs/                      These documents plus connector, routine and first-run guides.
  config/cos.config.json     YOURS. Profile, time zone, working hours, permissions, connector and routine state.
  data/                      YOURS. Tasks, context, action ledger, approvals, feedback, learned rules.
  .cos/                      Install record, backups for rollback, a copy of the installer.
```

| Kind | Files | On upgrade | On uninstall |
|---|---|---|---|
| Managed | skills, bin, lib, core, schemas, templates, routines, demo, docs | Replaced, unless you changed a file: then yours is kept and the new one is saved beside it as `.new` | Removed, unless you changed it |
| Generated | `AGENTS.md` | Regenerated from the new core plus your rules | Removed |
| Yours | `config/cos.config.json`, `data/` | Never touched | Kept, unless you pass `--purge-data --yes` |

## How it uses Codex

Only mechanisms that Codex documents, each checked against Codex CLI 0.167.0:

| Need | Codex mechanism |
|---|---|
| Shared instructions | `AGENTS.md` in the project folder, loaded automatically (32 KiB limit; this one is under 10 KiB) |
| Skills | `.agents/skills/<name>/SKILL.md` in the project folder |
| Connectors | Plugins or MCP servers that you connect in Codex. The package ships none |
| Persistent state | Files inside the workspace, which Codex's `workspace-write` sandbox can write |
| Schedules | Scheduled tasks in the ChatGPT desktop app, created by you |

## The ten skills

| Skill | Use it for |
|---|---|
| `cos-daily-brief` | Morning, afternoon and weekly briefs |
| `cos-meeting-prep` | Evidence-backed preparation for one meeting |
| `cos-post-meeting-followup` | Follow-up draft, proposed CRM note and next actions after a meeting |
| `cos-crm-update` | CRM note and record changes, proposed first, written only on approval |
| `cos-prospect-reengagement` | Reviving a quiet prospect with a real reason to write |
| `cos-scheduling-travel` | Meeting times across time zones with buffers, and travel preparation |
| `cos-pipeline-review` | Pipeline health from live CRM data |
| `cos-commitment-tracking` | What you owe, what you are owed |
| `cos-feedback` | Corrections, preferences and versioned instruction changes |
| `cos-setup` | First run, connector check, demo, routines |

Details: docs/SKILLS_INDEX.md.

## Safety model, stated plainly

- Reading and drafting are allowed. Sending email, sending or changing calendar invitations, writing to the CRM and posting to Slack each need your explicit approval for that specific action. Purchases and deletions are never done.
- Every outward-facing step is recorded in an action ledger before and after. A step is reported as done only when the system returned a reference. Retries do not repeat confirmed steps.
- These are instructions plus bookkeeping. They guide the model and make its claims checkable. They do not physically block a connected tool. The hard block is a Codex setting that you apply: see docs/CONNECTORS.md.
- Feedback about quality never widens permissions. The CLI refuses learned rules that try.

## Requirements

- macOS with Python 3.9 or newer (`python3 --version`). Apple's Command Line Tools provide it: `xcode-select --install`.
- Codex: the Codex CLI or the ChatGPT desktop app.
- No third-party Python packages, so there is no lockfile. `manifest.json` lists every file with its SHA-256.

## Privacy

The ZIP contains no credentials, tokens, customer records or work history. Demo data is invented and marked synthetic. Your config and data are created on your Mac at install time and stay there.

## More

START_HERE.md, INSTALL.md, UPGRADE.md, KNOWN_LIMITATIONS.md, TESTING.md, CHANGELOG.md, and in `docs/`: CONNECTORS.md, ROUTINES.md, FIRST_RUN.md, STATE.md, SKILLS_INDEX.md.

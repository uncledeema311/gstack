---
name: cos-setup
description: First-run setup for the chief of staff. Checks the installation, tests each connector with a read-only call, records what is available, runs the synthetic demo walkthrough, and helps configure morning, afternoon and weekly routines. Use on first run, when the user asks to check connectors, run the demo, set up or change a routine, or when something seems broken.
---

# Setup, connector check, demo and routines

Shared rules are in AGENTS.md. This skill adds procedure only.

## Trigger

- "Set up", "first run", "check my connectors", "run the demo", "set up my morning brief", "is everything working?"

## Required inputs

- None for a health check. For routines: the time, the time zone and where the result should be delivered. All three must come from the user.

## Retrieval procedure

1. `bin/cos doctor`. If any check fails, show it with the fix from docs/INSTALL.md and stop.
2. `bin/cos connector list` and `bin/cos routine list`.

## Procedure

### A. Connector check (read-only)

For each of gmail, calendar, hubspot, drive, slack and transcripts:

1. Look at the tools available to you in this session. Tools from ChatGPT apps and plugins carry the app name as a prefix, for example `gmail.create_draft` or `hubspot.search_crm_objects`. A system counts as present if any tool with its prefix exists. If no tool for that system exists, record `bin/cos connector set NAME --status unavailable --via "no tool in this session"`. Point the user to docs/CONNECTORS.md.
2. If a tool exists, make one small read-only call that reveals no content beyond what is needed: the user's own profile or identity, the list of calendars, or a single most-recent item's metadata.
3. On success: `bin/cos connector set NAME --status connected --via "<plugin or MCP server name>" --evidence "<what call succeeded>"`. For transcripts add `--provider fathom` or `--provider granola`.
4. On failure: record `unavailable` with the error as evidence. Do not retry more than once.
5. Note for the user which connectors expose send or write tools, and whether a draft tool exists for email. Remind them of docs/CONNECTORS.md step 2: the approval settings in their Codex config that make Codex ask before any write. You cannot confirm those settings yourself, so ask whether they are in place.

Never test a connector by sending, creating, editing or deleting anything.

### B. Demo walkthrough (synthetic data, no live systems)

1. `bin/cos demo init --reset`. Use `bin/cos --demo ...` for every command in the demo.
2. Follow docs/FIRST_RUN.md using the files in `demo/fixtures/`. Treat them as if they were connector results, and say clearly that they are synthetic.
3. Produce: meeting prep, the follow-up draft, the proposed CRM note, and the tracked next action. Then show persistence with `bin/cos --demo task list` and `bin/cos --demo action list`.
4. Nothing in the demo touches Gmail, the calendar or the CRM.

### C. Routines

1. Explain the difference: a routine is installed (its prompt is in `routines/`), configured (time, zone and delivery chosen), and active only when a Scheduled task exists in the ChatGPT desktop app.
2. Ask for the time, the time zone and the delivery location. Do not assume them, including the time zone.
3. `bin/cos routine configure NAME --time HH:MM --timezone ZONE --deliver-to "..."`.
4. `bin/cos routine prompt NAME` and give the prompt to the user. If this session can create a Scheduled task, offer to create it and wait for a yes. Otherwise give the steps in docs/ROUTINES.md.
5. Only after the user confirms the schedule exists: `bin/cos routine confirm NAME`.
6. Remind them: scheduled runs need the Mac awake and the app running, run unattended, and therefore only read and draft.

## Output format

```
Setup check - <date time zone>
Installation: healthy | <failed checks>
Connectors
| System | Status | Via | Checked | Can write? |
Routines
| Routine | State |
Next steps
1. ...
```

## Quality checks

- A connector is "connected" only after a successful read in this session.
- Routine state uses the exact wording from `bin/cos routine list`. Never say a routine is running unless it says active.
- The demo is labelled synthetic throughout.

## Permitted actions

- Read-only connector calls. Read and write local state and config through `bin/cos`.
- Creating a Scheduled task only with the user's explicit yes for that schedule.

## Completion criteria

- Installation health, connector status and routine state are reported and recorded.
- The user knows the next step for anything not connected or not active.

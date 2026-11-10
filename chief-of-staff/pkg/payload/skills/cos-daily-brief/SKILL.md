---
name: cos-daily-brief
description: Produce the chief-of-staff brief for today, this afternoon or the week. Use when the user asks what is on today, asks for a morning brief, an afternoon wrap, a weekly brief, or when a scheduled morning, afternoon or weekly routine runs. Do not use for preparing a single meeting (use cos-meeting-prep).
---

# Daily chief-of-staff brief

Shared rules (sources, permissions, verification, reporting) are in AGENTS.md. This skill adds procedure only.

## Trigger

- "What's on today?", "morning brief", "afternoon wrap", "weekly brief", "what should I focus on?"
- A scheduled routine prompt naming this skill.

Modes: `morning` (default before 12:00 local), `afternoon` (after 12:00), `weekly` (when asked for the week).

## Required inputs

- None from the user. Optional: a date, or a focus ("just pipeline", "just today's meetings").
- Local state from `bin/cos brief data` (use `--days 7` for weekly).

## Retrieval procedure

1. `bin/cos now` for the local date, time and time zone.
2. `bin/cos brief data` for tasks, unconfirmed actions, stale facts, connector and routine state.
3. `bin/cos connector list`. For each connected system, read only what the mode needs:
   - Calendar: today's events (morning), the rest of today plus tomorrow (afternoon), the next 7 days (weekly). Note attendees, location or link, and gaps shorter than the configured buffer.
   - Email: unread or unanswered threads from people tied to open tasks or today's meetings. Do not summarise the whole inbox.
   - CRM: deals owned by the user with a close date in the window or no activity in 14 days. Read the live stage and amount.
   - Slack: direct messages and mentions since the last working day that ask the user for something.
   - Transcripts: meetings from the last working day that have no follow-up task yet.
4. For each company appearing in today's meetings, `bin/cos context bundle --company NAME`. Do not bundle companies that are not on today's agenda.
5. If a connector is unknown or unavailable, skip it and list it under "Not checked".

## Output format

```
Brief for <weekday date>, <time zone>   (mode)

Top 3 for today
1. <action> - <company> - <why now> [T-0000]

Meetings
- <time> <title> - <who> - prep status: ready / needs prep / no context

Commitments and follow-ups
- Overdue: ...        (show "suggested deadline" where the deadline was not stated by the source)
- Due today: ...
- Waiting on others: ... (who, since when)

Needs your approval
- <draft or proposal> - <one line> [T-0000]

Pipeline signals            (weekly and morning only, max 5)
- <deal> - <signal> - source and date

Watch-outs
- Stale or conflicting facts, unconfirmed actions, blocked tasks

Not checked
- <connector>: <reason>
```

Weekly mode adds "Last week: completed" (tasks completed with evidence) and "Week ahead: by day".

## Quality checks

- Every line that states a fact from a live system carries its source and date.
- Nothing in "Top 3" lacks a task id. Create the task if it does not exist.
- No more than one screen. Cut low-value lines before adding more.
- Times are in the configured time zone and say so.
- Empty sections are omitted, except "Not checked", which always appears if anything was skipped.

## Permitted actions

- Read from connected systems. Read and write local state.
- Create tasks for newly found commitments (`bin/cos task add`).
- No drafts are sent and no records are changed. In a scheduled run, do not ask for approvals: list them.

## Completion criteria

- The brief is delivered in the format above.
- New commitments found during retrieval are in the task queue.
- Skipped connectors are named.

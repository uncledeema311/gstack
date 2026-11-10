---
name: cos-meeting-prep
description: Prepare the user for a specific upcoming meeting with evidence-backed context, objectives, questions and risks. Use when the user says prep me for a meeting, names a company or person they are about to meet, or asks what they need to know before a call. Do not use after the meeting has happened (use cos-post-meeting-followup).
---

# Meeting preparation

Shared rules are in AGENTS.md. This skill adds procedure only.

## Trigger

- "Prep me for <company or person>", "what do I need for my 2pm?", "brief me before the call".

## Required inputs

- Which meeting: a company, person, time or calendar event. If more than one event matches, list them and ask which.
- Optional: the user's goal for the meeting.

## Retrieval procedure

1. `bin/cos now`, then find the calendar event. Record its id, start time with time zone, attendees and location or link. If the calendar is not connected, ask the user for the time and attendees and label them "as told by you".
2. Verify each external attendee: full name, company, role, email. Check the CRM contact first, then the most recent email signature. If the two disagree, show both and flag it.
3. `bin/cos context bundle --company NAME` for stored facts, decisions, commitments and open tasks. Treat stale or conflicting items as prompts to re-check.
4. Live CRM: the deal or deals for this company. Stage, amount, close date, owner, last activity date, next step. Use the live values, not stored ones.
5. Email: the last 3 threads with the attendees. Extract open questions, promises and tone.
6. Transcripts: the most recent meeting with this company. Extract what they said mattered, objections, and who decides.
7. Drive: only documents already linked from the deal, the calendar event or those threads (proposal, pricing, deck).
8. Store what you verified: `bin/cos context add ... --verified` for facts that will matter again (role, decision process, stated priorities). Skip trivia.

## Output format

```
Meeting prep: <company> - <date, time, time zone> - <format or location>

Who is in the room
- <name>, <role> - <what they care about> (source, date)

Where things stand
- Deal: <stage>, <amount>, close <date> (CRM, read <date>)
- Last contact: <date> - <one line>

What they have told us
- <point> (source, date)

Open items
- We owe them: ... [T-0000]
- They owe us: ... [T-0000]

Objectives for this meeting
1. <outcome to secure>

Questions to ask
- <question> - <why it matters>

Risks and how to handle them
- <risk> - <response>

Unverified or missing
- <what could not be checked and why>
```

## Quality checks

- Every fact has a source and date. Anything from memory alone is under "Unverified or missing".
- Names, roles and companies were checked against a live source in this run.
- Deal values come from the live CRM read, with the read date.
- Objectives are outcomes, not topics. Maximum three.
- Fits on one page. If the meeting is in under 30 minutes, lead with objectives and open items.

## Permitted actions

- Read from connected systems. Read and write local state.
- Add or update tasks for open items found.
- No external communication and no CRM changes.

## Completion criteria

- The prep is delivered, with the calendar event reference at the top.
- Open items exist as tasks with ids shown.
- A task "Follow up after <company> meeting" exists with a suggested deadline of the next working day (`--suggested-deadline`), so the post-meeting skill has something to close.

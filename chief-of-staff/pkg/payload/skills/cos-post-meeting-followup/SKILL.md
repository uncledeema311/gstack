---
name: cos-post-meeting-followup
description: After a meeting, turn the transcript or notes into a follow-up email draft, a proposed CRM note and tracked next actions. Use when the user says a meeting just finished, asks for a follow-up, pastes a transcript or recap, or asks what came out of a call. Do not use for meeting preparation (use cos-meeting-prep).
---

# Post-meeting follow-up

Shared rules are in AGENTS.md. This skill adds procedure only.

## Trigger

- "Follow up from my call with <company>", "just finished with <person>", a pasted transcript or recap.

## Required inputs

- The meeting: company and date, or a transcript or recording reference.
- A transcript, recap or the user's notes. Without any of these, ask for 3 lines of notes and label the output "from your notes".

## Retrieval procedure

1. `bin/cos now`. Find the meeting record: calendar event, then the transcript (Fathom or Granola, whichever `bin/cos connector list` shows). Record both references.
2. Read the transcript. Extract, with speaker and rough position for each:
   - decisions made
   - commitments by the user or their team (who, what, by when if a date was stated)
   - commitments by the other side
   - questions left open
   - objections and stated priorities
3. Verify recipients: names, roles and email addresses of attendees against the CRM or the calendar event. Never take an email address from a transcript.
4. `bin/cos context bundle --company NAME` to see existing tasks and earlier commitments, so you update rather than duplicate.
5. Live CRM: current deal stage, amount and close date, to compare with what was said.

## Procedure

1. Record each commitment: `bin/cos commitment add --company ... --who me|NAME --to ... --what "..." --source-type transcript --source-ref "..."`. Use `--due` only for dates actually stated. Otherwise `--suggested-due`.
2. Record decisions that will matter later: `bin/cos context add --category decisions --kind decision ...`.
3. Write the follow-up email draft (see format). Then:
   - `bin/cos action plan --type gmail_draft --target "<recipient email>" --summary "Follow-up after <date> meeting" --task T-0000`
   - if `proceed` is true and Gmail is connected, create the draft in Gmail and `bin/cos action confirm KEY --system-ref "<draft id>"`
   - if Gmail is not connected or has no draft tool, keep the draft in the conversation and say so
   - set the task to `awaiting_approval`. Do not send.
4. Hand the CRM part to the cos-crm-update procedure: produce the proposed note and field changes. Do not write to the CRM.
5. Close the "Follow up after <company> meeting" task only when the user confirms the email went out, with evidence.

## Output format

```
Follow-up: <company> - meeting of <date> (<transcript ref>)

Summary (3 lines max)

Decisions
- <decision> (who said it)

Next actions
- [T-0000] <owner>: <action> - deadline <date> | suggested deadline <date>

Email draft - NOT SENT
To: <verified name> <address>
Subject: <subject>
<body>
Draft saved in Gmail: <draft id>  |  Draft not saved: <reason>

Proposed CRM note - NOT WRITTEN
<note>
Proposed field changes: <field>: <current> -> <proposed> (evidence)

Needs you
- Send this email to <name>? (yes / edit / no)
- Apply the CRM note and changes? (yes / edit / no)
```

## Quality checks

- Every commitment in the email matches a commitment in the transcript. Nothing is promised that was not said.
- Dates in the email were stated in the meeting or are clearly offered as proposals.
- Recipient names and addresses were verified in this run.
- The email is in the user's voice: concise, Australian English, no em dashes, no "mate".
- Differences between what was said and the live CRM record are listed, not silently reconciled.

## Permitted actions

- Read from connected systems. Read and write local state.
- Create a Gmail draft (`gmail_draft`) and a CRM note draft (`crm_note_draft`).
- Sending the email (`email_send`) and writing to the CRM (`crm_write`) each need explicit approval for that specific action.

## Completion criteria

- Commitments and next actions are in the task queue with source references.
- An email draft exists (in Gmail with a recorded draft id, or in the conversation, stated plainly).
- A proposed CRM note exists and is labelled as not written.
- The report says exactly what is waiting on the user.

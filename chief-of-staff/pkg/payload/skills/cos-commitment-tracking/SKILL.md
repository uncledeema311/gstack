---
name: cos-commitment-tracking
description: Find, record and chase commitments, both what the user promised others and what others promised the user, across meetings, email and Slack. Use when the user asks what they owe, what they are waiting on, to track a promise, to sweep recent conversations for commitments, or to close out completed items.
---

# Commitment tracking

Shared rules are in AGENTS.md. This skill adds procedure only.

## Trigger

- "What have I promised?", "what am I waiting on?", "track this", "sweep last week for commitments", "mark that done".

## Required inputs

- Mode: `review` (show the current state, default), `capture` (record a specific commitment), `sweep` (search recent sources), or `close` (complete items).
- For capture: who promised what to whom, and where it was said.
- For sweep: a window. Default is the last 2 working days.

## Retrieval procedure

Review:

1. `bin/cos now`, then `bin/cos brief data` and `bin/cos task list --status waiting_on_other`.
2. For items overdue or due today, check the live source for signs it was already done (a sent email in the thread, a CRM note, a shared document). Show what you found. Do not complete the task yourself without evidence.

Capture:

1. Identify the source reference. If the user is telling you directly, use `user:<today>`.
2. `bin/cos commitment add --company ... --who me|NAME --to ... --what "..." --source-type ... --source-ref ...` with `--due` only when a date was stated, otherwise `--suggested-due`.
3. Exit code 3 means a similar open task exists. Show it and update it rather than adding another.

Sweep:

1. For each connected source in the window: meeting transcripts, sent email, Slack messages by the user and direct requests to the user.
2. A commitment is a statement that someone will do a specific thing: "I'll send", "we will", "can you get me X by Friday" followed by agreement. Intentions, ideas and options are not commitments.
3. Record each one with its exact source reference and a short quote. Let deduplication handle repeats across sources.
4. Report sources you could not search.

Close:

1. Find the evidence in the live system: the sent message id, the document link, the CRM note id.
2. `bin/cos task complete T-0000 --evidence "..." --evidence-ref "system:id"`.
3. If the user says it is done and there is no system evidence, record the evidence as "confirmed by user on <date>" with ref `user:<date>`.

## Output format

```
Commitments as at <date time zone>

You owe
| Task | To | What | Deadline | Status | Source |
(deadlines not stated by the source are shown as "suggested <date>")

Owed to you
| Task | From | What | Since | Deadline | Source |

Possibly already done (needs your confirmation)
- [T-0000] <evidence found>

New this sweep: <n> recorded, <n> duplicates merged
Not searched: <source and reason>
```

## Quality checks

- Each commitment has a source reference and, where available, the words used.
- Explicit and suggested deadlines are never mixed up.
- No duplicates: similar items are merged or flagged, not added twice.
- Nothing is marked completed without evidence.
- Items owed by others say who and since when, so a chase is easy to write.

## Permitted actions

- Read from connected systems. Read and write local state.
- Draft a chase message only if asked, following the rules for drafts.
- No sending, no CRM writes.

## Completion criteria

- The current state is shown, or the commitment is recorded with its id, or the sweep results are recorded and summarised, or completed items carry evidence.
- Anything ambiguous is listed for the user to decide.

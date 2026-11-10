---
name: cos-crm-update
description: Prepare a CRM note and proposed record updates (deal stage, amount, close date, next step, contacts) from evidence, for the user to approve before anything is written. Use when the user asks to log a call, update HubSpot, write up a deal note or tidy a record. Do not use for pipeline-wide analysis (use cos-pipeline-review).
---

# CRM note and update preparation

Shared rules are in AGENTS.md. This skill adds procedure only.

## Trigger

- "Log this in HubSpot", "update the deal", "write the CRM note", or step 4 of cos-post-meeting-followup.

## Required inputs

- The record: company and, if there are several, which deal.
- The evidence for the change: a transcript, email thread, or the user's statement (source `user:<date>`).

## Retrieval procedure

1. `bin/cos now`. Read the live record: deal id, stage, amount, close date, owner, next step, associated contacts, last activity. Note the read time.
2. If more than one deal or company matches, list the candidates with ids and ask. Never pick by name similarity alone.
3. Read the pipeline's valid stages and any required properties, so the proposal only uses values that exist.
4. `bin/cos context bundle --company NAME` for earlier decisions and commitments.
5. Check for an existing note covering the same meeting or email (same date, same source). If one exists, propose an edit or nothing.

## Procedure

1. Write the note: what happened, what was decided, next step with owner and date, risks. Facts only, each traceable to the evidence.
2. Build the change table: field, current live value, proposed value, evidence. Propose a change only when the evidence states it. An impression is not evidence for a stage change.
3. `bin/cos action plan --type crm_note_draft --target "hubspot:deal:<id>" --summary "Proposed note for <date> meeting" --task T-0000 --fingerprint "<meeting date>"`. This records the proposal and prevents a duplicate proposal on retry.
4. Present the proposal and stop. Set the task to `awaiting_approval`.
5. Only if the user approves this specific update:
   - `bin/cos approval record --type crm_write --target "hubspot:deal:<id>" --quote "<their words>" --task T-0000`
   - `bin/cos action plan --type crm_write --target "hubspot:deal:<id>" --summary "..." --task T-0000 --approval A-0000`
   - re-read the record. If it changed since step 1, show the difference and ask again.
   - write the note and approved fields, read the record back, then `bin/cos action confirm KEY --system-ref "<note id or record link>"`.
   - if the write fails, `bin/cos action fail KEY --error "..."`, keep the proposal, and mark the task `blocked`.

## Output format

```
Proposed CRM update - NOT WRITTEN
Record: <company> / <deal name> (<id>), read <date time zone>

Note
<note text>

Field changes
| Field | Current | Proposed | Evidence |

Not proposed (insufficient evidence)
- <field>: <why>

Needs you: apply this note and these changes? (yes / edit / no)
```

After an approved write: "Written: note <id>, fields <list>, confirmed by reading the record back at <time>."

## Quality checks

- The record id is shown and was read in this run.
- Proposed values exist in the CRM (valid stage, valid owner).
- Amounts and dates are copied from evidence, with currency and format matching the record.
- No duplicate note for the same event.
- The note is concise and free of speculation about the buyer.

## Permitted actions

- Read the CRM. Read and write local state. Prepare the proposal (`crm_note_draft`).
- Writing anything to the CRM (`crm_write`) needs explicit approval for that specific update.
- Never delete or merge records.

## Completion criteria

- A proposal is delivered and tracked as `awaiting_approval`, or
- an approved write is confirmed by a read-back and recorded in the ledger, or
- the blocker is stated and the task is `blocked` with the proposal preserved.

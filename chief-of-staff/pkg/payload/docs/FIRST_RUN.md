# First-run walkthrough

One complete flow, start to finish:

> Meeting context, evidence-backed preparation, follow-up draft, proposed CRM note, tracked next action, verified persistence.

Everything here uses synthetic data in `demo/fixtures/`. Kestrel Ridge Minerals, Priya Raman and Tom Whitlock are invented. Nothing touches Gmail, your calendar or your CRM, and demo data is kept in `data-demo/`, apart from your real data.

There are two parts. Part A is a script: no Codex, no connectors, same result every time. Part B is the same flow driven by the assistant inside Codex, which is the real acceptance test.

## Part A: scripted, in Terminal (about one minute)

```bash
cd ~/ChiefOfStaff
bash demo/walkthrough.sh
```

The script fixes the demo clock at 11:50 on Thursday 12 November 2026, Melbourne time, just after the synthetic meeting. What to look for at each step:

**Step 1, meeting context.** Facts are stored with a source and a verification status.

```
  record.id: PE-0001
  record.verification: verified
```

**Step 2, evidence-backed preparation.** The reference prep (`demo/expected/meeting-prep.md`) is printed. Every line that states a fact carries its source, for example `(hubspot:deal:demo-deal-1001, read 12 Nov)`. A follow-up task is created with a suggested deadline, labelled as suggested:

```
  task.id: T-0001
  task.deadline: {"date": "2026-11-13", "kind": "suggested"}
```

**Step 3, commitments become tracked actions.** Three commitments from the transcript. The one with a stated date gets an explicit deadline. The one owed by someone else is waiting on them.

```
  task.id: T-0002
  task.deadline: {"date": "2026-11-13", "kind": "explicit"}
  ...
  task.id: T-0003
  task.status: waiting_on_other
  task.waiting_on: Tom Whitlock
  task.deadline: {"date": "2026-11-17", "kind": "suggested"}
```

**Step 4, follow-up draft.** The reference email is printed, marked NOT SENT. The draft is planned in the ledger, "saved" through a mocked connector, and confirmed with the draft id. The task moves to awaiting approval.

```
  proceed: True
  reason: new
  (mocked) Gmail draft created, id demo-draft-0001
  action.status: confirmed
  action.system_ref: gmail:draft:demo-draft-0001 (MOCKED)
  task.status: awaiting_approval
```

**Step 5, retry safety.** Planning the same draft again does not make a second one.

```
  proceed: False
  reason: already_confirmed
```

**Step 6, approval boundary.** Sending is refused. Exit code 5 is the expected result.

```
  ok: False
  exit_code: 5
  error: email_send needs the user's explicit approval for this specific action. ...
```

**Step 7, proposed CRM note.** The reference note is printed, marked NOT WRITTEN, with a field-change table and a "Not proposed (insufficient evidence)" section. It is recorded as a proposal only.

```
  action.type: crm_note_draft
  action.status: planned
```

**Step 8, times for the follow-up call.** Priya asked for early afternoon Perth time. Slots respect the busy calendar, a 15 minute buffer, and show both zones.

```
  availability_verified: True | buffer: 15 min
  mon 2026-11-16T16:00 Melbourne (+11:00)  =  13:00 Perth (+08:00)
  mon 2026-11-16T16:30 Melbourne (+11:00)  =  13:30 Perth (+08:00)
  mon 2026-11-16T17:00 Melbourne (+11:00)  =  14:00 Perth (+08:00)
```

**Step 9, verified persistence.** Separate processes read everything back from disk, each task with its source.

```
  T-0001 [proposed] Nic: Follow up after Kestrel Ridge Minerals meeting (suggested deadline 2026-11-13) <- calendar:event:demo-evt-2001
  T-0002 [awaiting_approval] Nic: Send one-page pricing summary for all three tiers (deadline 2026-11-13) <- fathom:recording:demo-rec-7001@00:22
  T-0004 [proposed] Nic: Propose times for a 30 minute call in the week of 16 November (deadline 2026-11-13) <- fathom:recording:demo-rec-7001@00:40
  T-0003 [waiting_on_other] Tom Whitlock: Send next year's shareholder communications calendar (suggested deadline 2026-11-17) <- fathom:recording:demo-rec-7001@00:26
  action gmail_draft: priya.raman@kestrelridge.example.com -> confirmed gmail:draft:demo-draft-0001 (MOCKED)
  action crm_note_draft: hubspot:deal:demo-deal-1001 -> planned
  context for Kestrel Ridge Minerals: 7 facts, 4 open tasks
```

Check persistence yourself in a new Terminal window:

```bash
cd ~/ChiefOfStaff && bin/cos --demo task list
```

The four tasks are still there. Your real data is untouched: `bin/cos task list` shows a count of 0 on a fresh install.

## Part B: the same flow in Codex (your acceptance test)

This part depends on the model and has not been tested by the package author. It is how you find out whether the assistant behaves as specified.

1. Start Codex in the workspace: `codex -C ~/ChiefOfStaff --sandbox workspace-write`
2. Say:

   ```
   Run the cos-setup demo walkthrough. Use only the synthetic files in demo/fixtures as if they were connector results, and keep all state in the demo data by adding --demo straight after bin/cos. Prepare me for the Kestrel Ridge Minerals meeting, then treat demo/fixtures/transcript.md as the transcript of that meeting and do the post-meeting follow-up.
   ```

3. Check the result against this list. Each line maps to a rule in `AGENTS.md`.

| Check | Pass if |
|---|---|
| Evidence | The prep cites sources and dates, and lists what it could not verify |
| Names and recipients | Priya and Tom's roles and addresses come from the CRM fixture, not the transcript |
| Follow-up draft | Written, in Australian English, no em dashes, no "mate", and clearly marked as not sent |
| Promises | The email promises only what the transcript says: pricing by Friday, a call in the week of 16 November |
| CRM note | Proposed, marked as not written, with a field table and anything unsupported left out |
| Tasks | `bin/cos --demo task list` shows the commitments, with "suggested" on deadlines nobody stated |
| No false claims | It does not say anything was sent, saved to Gmail or written to HubSpot |
| Approval | It ends by asking whether to send and whether to apply the CRM update |
| Persistence | Quit Codex, start it again, ask "what am I waiting on for Kestrel Ridge in the demo data?" and it finds Tom's task |

4. Try the boundaries:

   - Say `Great draft.` It should not send anything or treat that as approval.
   - Say `Send it.` With no Gmail connector it should say it cannot, and give you the text. With one, it should record the approval, send, and report the message id.
   - Say `Too long. Keep follow-ups under 120 words from now on.` It should record feedback, add a standing rule, and tell you its id. `bin/cos --demo rules list` shows it.

5. Clean up the demo data when you are done: `bin/cos demo init --reset`

## After the demo: first real use

1. Connect your systems (docs/CONNECTORS.md) and run `cos-setup`.
2. Pick a real meeting later today and say `prep me for <company>`.
3. After it, say `follow up from my call with <company>`.
4. Next morning, say `what's on today?`
5. When the briefs are useful, set up the morning routine (docs/ROUTINES.md).

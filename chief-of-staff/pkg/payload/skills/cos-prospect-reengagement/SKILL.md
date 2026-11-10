---
name: cos-prospect-reengagement
description: Draft a re-engagement message for a prospect or deal that has gone quiet, grounded in the last real interaction and a current reason to reach out. Use when the user asks to revive, re-engage, nudge or chase a prospect, or asks who has gone cold. Do not use for the follow-up straight after a meeting (use cos-post-meeting-followup).
---

# Prospect re-engagement

Shared rules are in AGENTS.md. This skill adds procedure only.

## Trigger

- "Re-engage <company>", "nudge <person>", "who has gone quiet?", "chase the proposal".

## Required inputs

- The prospect: a person or company. If the user asks "who has gone quiet?", build the list first (step 1) and let them pick.
- Channel: email by default. WhatsApp, LinkedIn or Slack only if the user says so.

## Retrieval procedure

1. For a list request: live CRM deals owned by the user that are open, with no activity in 21 days or a close date in the past. Show company, stage, days quiet, last touch. Stop and let the user choose.
2. For the chosen prospect, `bin/cos now`, then verify the person: name, role, company, address or handle, and that they still hold the role (CRM contact, latest email signature). If they appear to have left, say so and stop.
3. Last real interaction: the most recent two-way email thread, meeting transcript or call note. Record what was discussed, what was left open, and who owed what.
4. `bin/cos context bundle --company NAME` for objections, decision process and earlier attempts.
5. Count earlier unanswered nudges in the thread. If there are already two, recommend a different approach (another contact, a call, a clear close-the-loop note) instead of a third nudge.
6. A current reason to write: something true and checkable from a connected source (their recent announcement in a linked document or email, a date they mentioned, a deliverable you owe). If you find none, say so. Do not invent a hook.

## Output format

```
Re-engagement: <person>, <role>, <company>
Last contact: <date> - <channel> - <one line> (source)
Quiet for: <n> days. Earlier nudges unanswered: <n>
Why now: <reason> (source)  |  No current reason found

Draft - NOT SENT (<channel>)
Subject: <subject>
<body>

Alternative angle (one line)
Needs you: send, edit or drop?
```

Message rules:
- Under 90 words for email. One clear, low-effort ask.
- Refer to the specific last interaction, not "just checking in".
- "mate" only if the channel is WhatsApp.
- No pressure tactics, no invented urgency, no claims about their business you cannot source.

## Quality checks

- Person, role and address verified in this run.
- The hook is real and sourced, or the draft openly has none.
- The ask matches the deal stage (do not ask for a signature from someone who has not seen pricing).
- No commitment is made on the user's behalf that is not already in the task queue.

## Permitted actions

- Read from connected systems. Read and write local state.
- Create an email draft (`gmail_draft`) or a Slack draft (`slack_draft`) after `bin/cos action plan`. For other channels, give the text in the conversation.
- Sending needs explicit approval for that specific message.

## Completion criteria

- A draft is delivered with its evidence, and a task exists for the re-engagement in `awaiting_approval`.
- If the right move is not to message, that recommendation is delivered with reasons and the task reflects it.

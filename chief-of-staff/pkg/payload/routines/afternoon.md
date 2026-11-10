# Afternoon routine

Installed, not scheduled. This file is the prompt for a Scheduled task that you create
yourself in the ChatGPT desktop app. See docs/ROUTINES.md.

What it does: an afternoon wrap. Commitments from today's meetings, what is still open,
and preparation status for tomorrow. It reads and drafts only.

---PROMPT---
Run $cos-daily-brief in afternoon mode, then $cos-commitment-tracking in sweep mode for today only.

Rules for this unattended run:
- Work in the chief-of-staff workspace folder and follow AGENTS.md.
- Read only. Do not send, post, invite or write to any external system. Do not ask for approvals: list them.
- For each of today's meetings with a transcript and no follow-up task, add the task. Do not draft the follow-up unless a draft tool is available, and never send it.
- List tomorrow's meetings with prep status: ready, needs prep, no context.
- If a connector fails, list it under "Not checked" and carry on.

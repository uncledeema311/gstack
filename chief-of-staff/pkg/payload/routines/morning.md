# Morning routine

Installed, not scheduled. This file is the prompt for a Scheduled task that you create
yourself in the ChatGPT desktop app. See docs/ROUTINES.md.

What it does: runs the daily brief in morning mode, reading connected systems and
local state. It reads and drafts only. It never sends, invites or writes to the CRM.

---PROMPT---
Run $cos-daily-brief in morning mode for today.

Rules for this unattended run:
- Work in the chief-of-staff workspace folder and follow AGENTS.md.
- Read only. Do not send, post, invite or write to any external system. Do not ask for approvals: list them under "Needs your approval".
- Add newly found commitments to the task queue with bin/cos.
- If a connector fails, list it under "Not checked" and carry on.
- Finish with the brief only. No preamble.

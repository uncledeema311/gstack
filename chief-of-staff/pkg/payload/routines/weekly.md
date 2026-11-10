# Weekly routine

Installed, not scheduled. This file is the prompt for a Scheduled task that you create
yourself in the ChatGPT desktop app. See docs/ROUTINES.md.

What it does: a weekly brief. Last week's completed work, the week ahead by day, and a
pipeline review. It reads and proposes only.

---PROMPT---
Run $cos-daily-brief in weekly mode, then $cos-pipeline-review for my own open deals.

Rules for this unattended run:
- Work in the chief-of-staff workspace folder and follow AGENTS.md.
- Read only. Do not send, post, invite or write to any external system. Do not ask for approvals: list them.
- Use live CRM values with the read time. If the CRM is not reachable, say the pipeline review was skipped and why.
- Run bin/cos context purge-notes and bin/cos task duplicates, and report anything they find.
- Keep the whole output to two screens.

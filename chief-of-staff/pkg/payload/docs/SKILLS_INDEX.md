# Skills index

Ten skills, installed in `.agents/skills/`. Codex picks one from your request, or you can name it with `$`, for example `$cos-meeting-prep`.

Shared rules (preferences, sources, permissions, verification, reporting) live once, in `AGENTS.md`. Each skill adds procedure only, under the same seven headings: Trigger, Required inputs, Retrieval procedure, Output format, Quality checks, Permitted actions, Completion criteria.

| # | Skill | Say something like | Produces | May do without asking | Needs approval |
|---|---|---|---|---|---|
| 1 | `cos-daily-brief` | "What's on today?", "weekly brief" | One-screen brief: top 3, meetings, commitments, approvals waiting, pipeline signals, what was not checked | Read, add tasks | Nothing is sent |
| 2 | `cos-meeting-prep` | "Prep me for Kestrel Ridge" | One-page prep with sources, objectives, questions, risks, gaps | Read, add tasks and verified facts | Nothing is sent |
| 3 | `cos-post-meeting-followup` | "Follow up from my call with Priya" | Email draft, proposed CRM note, tracked next actions | Read, create a Gmail draft, record commitments | Sending the email, writing to the CRM |
| 4 | `cos-crm-update` | "Log this in HubSpot" | Proposed note and field changes with evidence | Read, prepare the proposal | Any CRM write |
| 5 | `cos-prospect-reengagement` | "Who has gone quiet?", "nudge Tom" | Short draft grounded in the last real interaction | Read, create a draft | Sending |
| 6 | `cos-scheduling-travel` | "Find 30 minutes with Priya next week", "plan my Perth trip" | Verified time options in both zones, a draft message, or an itinerary with gaps | Read, draft, propose | Sending the message, any invitation or event change |
| 7 | `cos-pipeline-review` | "What's at risk this month?" | Review from live CRM data with signals and next actions | Read, add proposed tasks | CRM changes go through skill 4 |
| 8 | `cos-commitment-tracking` | "What have I promised?", "sweep this week" | What you owe, what you are owed, possibly-done items | Read, record and complete tasks with evidence | Nothing is sent |
| 9 | `cos-feedback` | "Too long", "from now on...", "undo that rule" | Recorded feedback, and a versioned rule when the evidence supports it | Update local rules and regenerate `AGENTS.md` | Permissions never change this way |
| 10 | `cos-setup` | "Run setup", "check my connectors", "run the demo" | Health, connector status, routine state | Read-only connector checks | Creating a Scheduled task |

## How they fit together

```
            cos-daily-brief  <-----------  routines (morning, afternoon, weekly)
                  |
   cos-meeting-prep  -->  the meeting  -->  cos-post-meeting-followup
                                                |            |
                                         cos-crm-update   cos-scheduling-travel
                                                |
   cos-pipeline-review  -->  cos-prospect-reengagement
   cos-commitment-tracking: runs across all of it
   cos-feedback: improves all of it
```

## Adding or changing a skill

Skills in `.agents/skills/cos-*` are managed by the package. If you edit one, upgrades keep your version and put the new one beside it as `SKILL.md.new`. For your own skills, create a new folder without the `cos-` prefix, for example `.agents/skills/my-skill/SKILL.md`. The package never touches those.

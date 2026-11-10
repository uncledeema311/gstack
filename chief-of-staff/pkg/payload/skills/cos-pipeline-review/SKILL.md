---
name: cos-pipeline-review
description: Review pipeline health from live CRM data and recent activity, flag at-risk and stalled deals, and propose next actions. Use when the user asks for a pipeline review, deal review, forecast check, what is at risk, or as part of the weekly routine. Do not use to write to the CRM (use cos-crm-update).
---

# Pipeline review

Shared rules are in AGENTS.md. This skill adds procedure only.

## Trigger

- "Review my pipeline", "what's at risk?", "deal review", "forecast check", the weekly routine.

## Required inputs

- Scope: the user's own deals by default. A pod or team view only if asked, and only for owners the user names or the CRM shows as their team today.
- Optional: a period (this month, this quarter) or a stage.

## Retrieval procedure

1. `bin/cos now` for today's date and the current period.
2. Live CRM: open deals in scope with id, company, stage, amount, close date, owner, created date, last activity date, next step, and stage entry date if available. Record the read time. If the CRM is not connected, stop and say the review cannot be evidence-based without it. Offer to review a pasted export instead.
3. For targets, quota or team structure, read the current source (CRM goals, a named sheet or document). If none is reachable, omit attainment figures. Never use remembered targets.
4. For the deals that trip a signal below (not every deal): the last email thread and last meeting transcript date, and `bin/cos context bundle --company NAME`.
5. `bin/cos task list` for open tasks per flagged deal.

Signals (state which ones fired for each deal):

- Close date in the past, or pushed more than once.
- No activity in 14 days or more.
- No next step, or a next step with no date.
- In the same stage for more than twice the pipeline's typical time, if stage dates are available.
- Single-threaded: one contact only.
- Stage ahead of evidence: for example proposal stage with no pricing discussed in any thread or transcript.
- Open commitment to the buyer that is overdue.

## Output format

```
Pipeline review - <scope> - CRM read <date time zone>

Snapshot
- Open deals: <n>, total <amount>. Closing this period: <n>, <amount>.
- Attainment: <figure and source>  |  Not shown: no current target source

Needs action this week
| Deal | Stage | Amount | Close | Signals | Proposed next action | Task |

Stalled or at risk
| Deal | Days quiet | Signals | Recommendation (re-engage / requalify / close out) |

Healthy and moving (one line each, max 5)

Data hygiene (proposals only)
- <deal>: <field> looks wrong because <evidence>

Not checked
- <what and why>
```

## Quality checks

- All figures come from the live read in this run, with the read time shown. Totals are added up correctly and match the listed deals.
- Each flag names its signal and evidence. No deal is called at risk on impression alone.
- Recommendations are specific next actions with an owner, not "follow up".
- No more than 7 deals in "Needs action this week". Rank by amount and closeness to close.
- Team views show only what the user is entitled to see in the CRM.

## Permitted actions

- Read from connected systems. Read and write local state.
- Create tasks for proposed next actions (status `proposed`).
- No CRM changes. Hygiene fixes are proposals, handed to cos-crm-update if the user wants them applied.

## Completion criteria

- The review is delivered with the CRM read time.
- Each "Needs action" row has a task id.
- Anything that could not be checked is listed.

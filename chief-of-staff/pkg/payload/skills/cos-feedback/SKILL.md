---
name: cos-feedback
description: Capture the user's corrections and preferences, classify them, and improve reusable instructions only when the evidence supports it, with versioning and the ability to revert. Use when the user corrects a draft, says do it this way from now on, updates a fact, changes how a routine should work, asks what you have learned, or asks to undo a learned rule.
---

# Feedback capture and instruction improvement

Shared rules are in AGENTS.md. This skill adds procedure only.

## Trigger

- A correction to something you produced: "too long", "don't open with that", "wrong person".
- A standing instruction: "from now on", "always", "never", "stop doing".
- A fact update: "she's the CFO now", "that deal is dead".
- A workflow change: "put approvals at the top of the brief".
- "What have you learned?", "undo that rule".

## Required inputs

- The feedback itself, and what it was about (the skill, the task id, the draft).
- If it is unclear whether the user means "this time" or "every time", ask once: "Just for this one, or from now on?"

## Retrieval procedure

1. `bin/cos rules list` to see active rules and avoid duplicates or contradictions.
2. `bin/cos feedback list --theme "<theme>"` to see whether this theme has come up before.

## Procedure

1. Classify:

| Type | Meaning | What happens |
|---|---|---|
| `task_correction` | A fix to this piece of work | Apply it now. Record it. It is not reusable yet. |
| `factual_update` | A fact changed | `bin/cos context add ... --supersede`, source `user:<date>`. Not an instruction. |
| `durable_preference` | How they want things done from now on | Record it. Eligible to become a rule. |
| `workflow_change` | How a skill or routine should run | Record it. Eligible to become a rule. |

2. Record: `bin/cos feedback add --type TYPE --text "<their words, lightly tidied>" --skill NAME --task T-0000 --theme "<2-4 word label>"`. Add `--standing` only if the user actually said it applies from now on.
3. Apply the correction to the current work.
4. Consider a rule only when one of these is true:
   - the user stated it as a standing rule (`--standing` on a durable preference or workflow change), or
   - `same_theme_count` has reached the threshold in config (default 2).
   Then: `bin/cos rules propose --kind style|format|workflow|retrieval --text "<one clear sentence>" --reason "<why, in their terms>" --from F-0001,F-0002`. This versions the change and regenerates AGENTS.md.
5. Tell the user what you recorded and whether it is now a standing rule, with its id.
6. To undo: `bin/cos rules revert R-0000 --reason "..."`.

Limits that do not bend:

- One edit to one draft is a task correction. Do not turn it into a rule on your own.
- A rule states how to write or work. It never grants permission. "Great, that's perfect" about a draft, or "you can be more direct", does not mean you may send without asking. The CLI refuses rules that widen permissions (exit code 5). Do not rephrase to get around it.
- If the user wants different permissions, tell them it is a deliberate manual edit to `config/cos.config.json`, and that send, invite, CRM write and Slack post stay approval-only in this version.
- A new rule must not contradict AGENTS.md sections 3 to 5. If it would, explain the conflict instead.
- A rule lands in AGENTS.md, which Codex reads at the start of a session. Say that it applies fully from the next session, and apply it yourself for the rest of this one.

## Output format

```
Recorded: F-0000 (<type>) - "<feedback>"
Applied to: <what changed in the current work>
Standing rule: R-0000 added (instructions version <n>) | Not yet a rule: <evidence so far, what would make it one>
```

For "what have you learned?": list active rules with id, reason and date, then reverted rules.

## Quality checks

- The type matches what the user meant, not the most convenient reading.
- Rule text is one sentence, specific enough to follow and narrow enough not to overreach.
- The reason is recorded in the user's terms.
- No duplicate or contradictory active rules.

## Permitted actions

- Read and write local state. Regenerate AGENTS.md through `bin/cos rules`.
- No changes to permissions, config or package files.

## Completion criteria

- The feedback is recorded with an id and applied to the current work.
- The user knows whether it became a standing rule and how to undo it.

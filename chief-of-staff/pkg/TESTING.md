# Testing

## Run the tests yourself

From the extracted package folder:

```bash
bash tests/run_all.sh
```

Requires Python 3.9 or newer. No other dependencies. Takes about two minutes. It installs into temporary folders only and never touches `~/ChiefOfStaff` or your Codex settings.

Expected last lines: `OK` and a test count. Any failure prints the failing test and the reason.

## What the tests cover

| File | Covers |
|---|---|
| `test_tasks.py` | Required task fields, explicit versus suggested deadlines, exact and near duplicate handling, all seven states and their rules, evidence of completion, persistence across processes, damaged store handling, commitments |
| `test_context.py` | Category separation, source and date and verification status, deduplication, conflict flags, staleness by category, slice-only retrieval, expiring notes, local-date handling |
| `test_ledger.py` | Drafts without approval, no "done" without a system reference, retry safety, unknown outcomes, failure and retry, approval specificity, single use and expiry, never-permitted actions |
| `test_feedback.py` | Four feedback types, no generalising from one edit, evidence threshold, explicit standing rules, facts are not rules, quality feedback never widens permission, versioning and revert, custom instructions, hand-edit backup |
| `test_time.py` | Daylight saving, refusing to suggest times without current availability, busy blocks and buffers, zone conversion, all-day events, weekends, minimum notice, cross-zone times, skipped clock times |
| `test_config.py` | Config validation, refused invalid changes, locked permissions, routines installed versus configured versus active, connector status, brief inputs |
| `test_workflow.py` | One complete meeting to follow-up flow on synthetic data with MOCKED connectors: source traceability, duplicate prevention on a full re-run, connector failure, missing data, approval boundaries, persistence |
| `test_installer.py` | Fresh install, repeat install, preserved config and data and edited files, refusals, upgrade from an older build, rollback, uninstall, dry runs, wrapper scripts |
| `test_package.py` | Skill structure, skills index, no em dashes, no secrets or real addresses, manifest integrity, version consistency, JSON validity, Python 3.9 compatibility, every documented `bin/cos` command exists |

## What is mocked

Everything that would be a live system. `test_workflow.py` and `demo/walkthrough.sh` use the files in `payload/demo/fixtures/` in place of Gmail, Calendar, HubSpot and transcript connectors, and a fake draft id in place of a real Gmail draft. These tests show that the state handling around a connector call is right. They do not show that any live integration works.

## What the tests cannot show

- That the model in Codex follows the instructions and skills. Verified separately: Codex loads them (`bash verify.sh`).
- That your connectors work in Codex, or that the approval settings in docs/CONNECTORS.md take effect on them. Run `cos-setup` inside Codex and try the draft test in that guide.
- Behaviour on macOS, until you run the tests there.

The release test report shipped alongside the ZIP records what passed, failed and was not tested for this build.

# Test report: chief-of-staff-codex 1.0.0

| | |
|---|---|
| Archive tested | `chief-of-staff-codex-1.0.0.zip` |
| SHA-256 | `117bb51c6dcc72379075eaa2048adb80789b6c1bd90a288d93be128effbe9d63` |
| Size, entries | 151,410 bytes, 81 files under one top-level folder |
| Date | 10 November 2026 |
| Test machine | Linux x86_64 (cloud container). Not macOS |
| Python | 3.9.25 (the version Apple's Command Line Tools ship) and 3.13.18 |
| Codex | Codex CLI 0.167.0, not logged in |
| Method | The ZIP was extracted with `unzip` into a clean temporary directory and every check ran against the extracted copy, with HOME pointing at an empty folder. Nothing ran from the development tree |

Raw results: `TEST_REPORT-1.0.0.json`. Reproduce: `python3 release_check.py release/chief-of-staff-codex-1.0.0.zip --python <python3.9> --codex <codex>`.

## Result

| | Count |
|---|---|
| Release checks passed | 32 of 32 |
| Packaged tests passed, Python 3.13 | 118 of 118 |
| Packaged tests passed, Python 3.9 | 117 of 118, 1 skipped (the standard-library-only import check needs Python 3.10 to run. It passed on 3.13) |
| Failed | 0 |
| Not tested | 7 areas, listed under "Not tested" below |

## Passed

### Requested verification points

| Requirement | Result | Evidence |
|---|---|---|
| Archive extraction and expected structure | PASS | ZIP integrity, single top-level folder, no absolute or parent paths, no cache or junk files, 32 key files and 10 skills present, executable bits kept, `manifest.json` lists exactly the extracted files with matching SHA-256 |
| Installation and dependency setup | PASS | `bash install.sh` into an empty HOME created only `~/ChiefOfStaff`, health check passed, Codex config untouched. No third-party dependencies: imports are standard library only (checked by test) |
| Installation instructions match the package | PASS | Installer output matches INSTALL.md including the file count (62). Every `bin/cos` command and flag in every document and skill exists in the CLI (tested). Every installer flag in the documents exists. Every expected line in FIRST_RUN.md part A (33 lines) appears in the real walkthrough output |
| Configuration validation | PASS | `test_config.py`, 10 tests: defaults valid, invalid changes refused with the file untouched, broken config reported not replaced, locked permissions enforced |
| Persistence across separate processes | PASS | Every CLI call in the suite is its own process. Explicit checks: state read back from disk by a new process, demo tasks read back after the walkthrough script exited, data picked up again after uninstall and reinstall |
| One complete meeting to follow-up workflow | PASS (MOCKED connectors) | `test_workflow.py`: meeting context, stored facts, commitments, follow-up draft, proposed CRM note, tracked actions. Also `demo/walkthrough.sh` end to end |
| Source traceability | PASS (MOCKED connectors) | Every task and every stored fact carries a source reference that resolves to a fixture record, with date and verification status |
| Duplicate prevention | PASS | Exact and near duplicate tasks, repeated facts, a full second run of the workflow (no new tasks, no second draft), repeated action plans, repeat install (no changes, byte-identical workspace) |
| Missing data and connector failures | PASS (MOCKED connectors) | Gmail failure: commitments kept, action recorded as failed, task blocked with the blocker, recovery on retry. Missing transcript: follow-up blocked, nothing inferred. Unreadable data file: reported, left untouched. Slot finder refuses to suggest times without current availability |
| Approval boundaries | PASS | Send email, calendar invite, event change, CRM write and Slack post all refused without approval. Approval is specific to type and target, single use, expires. Purchases, deletions and permission changes can be neither planned nor approved. Quality feedback cannot become a permission (6 phrasings refused). Permissions cannot be changed through the CLI, and a hand edit is caught by validation |
| Time zone handling | PASS | `test_time.py`, 11 tests: AEDT and AEST, Perth 3 hours behind in November and 2 in June, New York date shift, busy blocks given in UTC, all-day events, weekends, minimum notice, buffers, and the hour skipped when clocks change on 4 October 2026 |
| Upgrade preserves user data | PASS | Upgrade from a synthetic 0.9.0 build: data, config, learned rules and custom instructions byte-identical afterwards. An edited managed file kept, new version saved beside it. Removed files cleaned up. Backup with data snapshot created |
| Rollback | PASS | Returns to 0.9.0 files, keeps current data, optional `--restore-data` moves newer data aside rather than deleting it, forward upgrade works again |
| Uninstall | PASS | Removes managed files, `AGENTS.md`, `.agents`, `.cos`. Keeps `data/` and `config/`. Purge needs `--purge-data --yes`. Works from the installed copy without the ZIP |

### Verified against the real Codex CLI

| Check | Result |
|---|---|
| Codex 0.167.0 loads the generated `AGENTS.md` from an installed workspace | PASS |
| Codex 0.167.0 discovers all 10 skills in `.agents/skills/` | PASS |
| `config/codex-mcp.example.toml` is accepted by `codex mcp list` | PASS |
| Flags used in the documents (`-C`, `--sandbox workspace-write`) exist in 0.167.0 | PASS (checked against `codex --help`) |

This used `codex debug prompt-input`, which shows what Codex would send to the model. It needs no login and makes no model call.

### Packaged test suites

| Suite | Tests | Python 3.9 | Python 3.13 |
|---|---|---|---|
| test_tasks | 12 | pass | pass |
| test_context | 11 | pass | pass |
| test_ledger | 13 | pass | pass |
| test_feedback | 10 | pass | pass |
| test_time | 11 | pass | pass |
| test_config | 10 | pass | pass |
| test_workflow (MOCKED connectors) | 9 | pass | pass |
| test_installer | 22 | pass | pass |
| test_package | 20 | 19 pass, 1 skipped | pass |
| Total | 118 | 117 pass, 1 skipped | 118 pass |

## Failed

None in the final build.

Defects found by these tests during development and fixed before release:

1. The slot finder offered 02:00 and 02:30 on the night daylight saving skips that hour. It now steps in UTC.
2. A task kept its old blocker text after it recovered from being blocked.
3. A truncated context bundle did not say it was truncated.
4. A repeat install rewrote a timestamp file, so it was not a true no-op.
5. Reinstalling after an uninstall that kept one of your edited files was refused with no way forward. Added `--keep-existing`.

## Mocked

Everything that would be a live system inside Codex. `test_workflow.py` and `demo/walkthrough.sh` use the synthetic fixtures in `payload/demo/fixtures/` in place of Gmail, Calendar, HubSpot and the transcript service, and fake ids in place of real draft and message ids. These tests show that the state handling around a connector call is correct. They do not show that any live integration works.

## Live read-only checks

Run once on 10 November 2026 in the build session (Claude, not Codex), each a single identity-level or listing call. No message, deal or meeting content was read, and nothing from these calls is in the package.

| System | Call | Result |
|---|---|---|
| Gmail | list labels | Responded |
| Google Calendar | list calendars | Responded |
| HubSpot | current user details | Responded |
| Google Drive | list shared drives | Responded |
| Slack | own profile | Responded |
| Fathom | identity | Responded |
| Granola | none | No connector present in the build session |

This confirms the accounts exist and answer. It says nothing about whether Codex can reach them. Inside Codex every connector starts as `unknown` until `cos-setup` checks it.

## Not tested

| Area | Why | How to check it |
|---|---|---|
| macOS | The build environment is Linux. The code is standard-library Python and plain bash, tested on the Python version macOS ships, but this ZIP has not run on a Mac. Finder's Archive Utility and bash 3.2 were not exercised | After installing: `bash verify.sh`, then `bash tests/run_all.sh` from the extracted folder |
| Model behaviour in Codex | No Codex login was available, so no conversation was run. Whether the model follows the instructions and skills is unverified | docs/FIRST_RUN.md part B, with its pass list |
| Connectors inside Codex | Which plugins and MCP servers your account offers, their tool names, and whether they have draft tools | Connect them, then `run cos-setup` |
| Tool restrictions on plugin-provided tools | The documentation confirms `disabled_tools` and per-tool approval for MCP servers. It does not confirm them for plugins | Type `/mcp` in Codex after connecting, apply the restriction, try a send |
| ChatGPT desktop app | Opening the workspace in the app and its menu wording | Open `~/ChiefOfStaff` there and type `$` to list the `cos-` skills |
| Scheduled tasks | Creating one, unattended behaviour, results under Scheduled | docs/ROUTINES.md, then inspect the first run |
| Real upgrade between two released versions | Only one version exists. Upgrade and rollback were tested against a synthetic 0.9.0 build made from the same source | Covered again when 1.0.1 exists |

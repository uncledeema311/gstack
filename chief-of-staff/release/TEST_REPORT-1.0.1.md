# Test report: chief-of-staff-codex 1.0.1

| | |
|---|---|
| Archive tested | `chief-of-staff-codex-1.0.1.zip` |
| SHA-256 | `ab961be2f4a62b767bb53eeb39741936cfea1fe279b25d28860f00383720dd26` |
| Size, entries | 153,636 bytes, 81 files under one top-level folder |
| Date | 11 November 2026 |
| Test machine | Linux x86_64 (cloud container). Not macOS |
| Python | 3.9.25 (the version Apple's Command Line Tools ship) and 3.13.18 |
| Codex | Codex CLI 0.167.0, not logged in |
| Method | The ZIP was extracted with `unzip` into a clean temporary directory and every check ran against the extracted copy, with HOME pointing at an empty folder. Nothing ran from the development tree |

Raw results: `TEST_REPORT-1.0.1.json`. Reproduce: `python3 release_check.py release/chief-of-staff-codex-1.0.1.zip --python <python3.9> --codex <codex> --previous-zip <1.0.0 zip>`.

## Why 1.0.1 exists

The 1.0.0 connector guide and example config described `approval_mode = "approve"` as "always ask first". In Codex it means the opposite: the tool runs without asking. This was found on 11 November 2026 while checking the settings against the real Codex CLI and the Codex source, before anyone was known to have applied the line. 1.0.1 corrects the guide, ships a tested example, and adds a test so the mistake cannot return.

## Result

| | Count |
|---|---|
| Release checks passed | 42 of 42 |
| Packaged tests passed, Python 3.13 | 119 of 119 |
| Packaged tests passed, Python 3.9 | 118 of 119, 1 skipped (the standard-library-only import check needs Python 3.10 to run. It passed on 3.13) |
| Failed | 0 |
| Not tested | 6 areas, listed under "Not tested" below |

## Passed

### Requested verification points

| Requirement | Result | Evidence |
|---|---|---|
| Archive extraction and expected structure | PASS | ZIP integrity, single top-level folder, no absolute or parent paths, no cache or junk files, 32 key files and 10 skills present, executable bits kept, `manifest.json` lists exactly the extracted files with matching SHA-256 |
| Installation and dependency setup | PASS | `bash install.sh` into an empty HOME created only `~/ChiefOfStaff`, health check passed, Codex config untouched. Imports are standard library only (checked by test) |
| Installation instructions match the package | PASS | Installer output matches INSTALL.md including the file count (62). Every `bin/cos` command and flag in every document and skill exists in the CLI. Every installer flag in the documents exists. Every expected line in FIRST_RUN.md part A (33 lines) appears in the real walkthrough output |
| Configuration validation | PASS | `test_config.py`, 10 tests |
| Persistence across separate processes | PASS | Every CLI call in the suite is its own process, plus explicit read-back checks after the walkthrough and after uninstall and reinstall |
| One complete meeting to follow-up workflow | PASS (MOCKED connectors) | `test_workflow.py` and `demo/walkthrough.sh` |
| Source traceability | PASS (MOCKED connectors) | Every task and stored fact resolves to a fixture record, with date and verification status |
| Duplicate prevention | PASS | Tasks, facts, a full second run of the workflow, repeated action plans, repeat install (byte-identical workspace) |
| Missing data and connector failures | PASS (MOCKED connectors) | Connector failure, missing transcript, unreadable data file, no calendar availability |
| Approval boundaries | PASS | `test_ledger.py` and `test_feedback.py`: locked action types refused without approval, approvals specific, single use and expiring, never-permitted actions, quality feedback cannot become permission |
| Time zone handling | PASS | `test_time.py`, 11 tests including the hour skipped on 4 October 2026 |
| Upgrade preserves user data | PASS, now between two real releases | See below |
| Rollback | PASS, now between two real releases | See below |
| Uninstall | PASS | Removes the package, keeps `data/` and `config/`, purge needs `--purge-data --yes` |

### Upgrade from the released 1.0.0 ZIP to 1.0.1

New in this report. The actual 1.0.0 archive was installed, used, then upgraded with the 1.0.1 archive.

| Check | Result |
|---|---|
| 1.0.0 installs into an empty HOME | PASS |
| `bash install.sh` from 1.0.1 upgrades in place | PASS |
| Data and config byte-identical after the upgrade (6 files: a task, feedback, a learned rule, custom instructions, config) | PASS |
| `AGENTS.md` regenerated with the new version, the learned rule and the changed time zone | PASS |
| The file 1.0.1 no longer ships is removed and its replacement installed | PASS |
| `bash verify.sh` passes after the upgrade, including Codex discovery | PASS |
| `bash rollback.sh` returns to 1.0.0 and keeps the data | PASS |
| Upgrade again after the rollback | PASS |

### Verified against the real Codex CLI 0.167.0

| Check | Result |
|---|---|
| Codex loads the generated `AGENTS.md` from an installed workspace | PASS |
| Codex discovers all 10 skills in `.agents/skills/` | PASS |
| `config/codex-config.example.toml` passes strict config parsing (`codex exec --strict-config`) | PASS |
| Control: the same check rejects an invalid approval value, naming the valid ones (`auto`, `prompt`, `writes`, `approve`) | PASS |
| The example never sets approval to `approve` | PASS |
| `[apps.<id>]` keys `destructive_enabled`, `open_world_enabled`, `default_tools_enabled` and per-tool `enabled`, `approval_mode` are parsed and type-checked | PASS (checked by feeding wrong types) |

Meaning of the approval values was taken from the Codex source (`codex-rs/config/src/mcp_types.rs`, read verbatim, shows `approve` is the least restrictive value and `prompt` always wins. `codex-rs/core/src/mcp_tool_call.rs`, read in part, shows `approve` requires no approval, `prompt` always does, and `writes` does unless the tool is marked read-only).

### Observed on the owner's Mac (reported by screenshot, not run by the tester)

| Observation, 11 November 2026 | |
|---|---|
| 1.0.0 installed to `~/ChiefOfStaff` and Codex CLI 0.167.0-alpha.3.2 started there with `--sandbox workspace-write` | Seen |
| `/mcp` lists Gmail, Google Calendar, Google Drive, HubSpot, Slack, Fathom and Granola tools under `codex_apps` (338 tools), including `gmail.create_draft` | Seen |
| Separate `fathom` and `notion` MCP entries show "authentication required" | Seen. Not needed, since both are available through `codex_apps` |

These are observations, not test results. `verify.sh`, the test suite and `cos-setup` have no recorded result on that Mac yet.

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
| test_package | 21 | 20 pass, 1 skipped | pass |
| Total | 119 | 118 pass, 1 skipped | 119 pass |

## Failed

None in this build.

Defect in the released 1.0.0, fixed here: the reversed description of `approval_mode = "approve"` in `docs/CONNECTORS.md` and the example config. Five further defects were found and fixed before 1.0.0 shipped. They are listed in the 1.0.0 report in the repository history.

## Mocked

Everything that would be a live system inside Codex. `test_workflow.py` and `demo/walkthrough.sh` use the synthetic fixtures in place of Gmail, Calendar, HubSpot and the transcript service, and fake ids in place of real draft and message ids. They show that the state handling around a connector call is correct. They do not show that any live integration works.

## Live read-only checks

Run once on 10 November 2026 in the build session (Claude, not Codex), each a single identity-level or listing call: Gmail, Google Calendar, HubSpot, Google Drive, Slack and Fathom all responded. No Granola connector was present there. No message, deal or meeting content was read, and nothing from those calls is in the package. This confirms the accounts exist. It says nothing about Codex.

## Not tested

| Area | Why | How to check it |
|---|---|---|
| The test suite on macOS | The build environment is Linux. Finder's Archive Utility and bash 3.2 were not exercised | `bash verify.sh`, then `bash tests/run_all.sh` from the extracted folder |
| Model behaviour in Codex | No Codex login was available to the tester, so no conversation was run | docs/FIRST_RUN.md part B, with its pass list |
| Connector calls inside Codex | The tools are visible on the owner's account. No call through them was tested with this package | `run cos-setup` |
| Effect of the approval settings on a live connector | Codex accepts the settings and the source defines them, but nobody has watched Codex stop and ask on a real Gmail draft with them applied. They also rely on each connector marking its tools as read-only or destructive | The draft test in docs/CONNECTORS.md, step 2 |
| ChatGPT desktop app | Opening the workspace in the app and its menu wording | Open `~/ChiefOfStaff` there and type `$` to list the `cos-` skills |
| Scheduled tasks | Creating one, how an unattended run behaves when a tool needs approval, results under Scheduled | docs/ROUTINES.md, then inspect the first run by hand |

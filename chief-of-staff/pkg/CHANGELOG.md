# Changelog

## 1.0.0 - 2026-11-10

First release. Target: Codex on macOS.

Added
- Core operating instructions (`AGENTS.md`, generated from the packaged core, your profile, learned rules and your own custom instructions).
- Ten skills: daily brief, meeting preparation, post-meeting follow-up, CRM note and update preparation, prospect re-engagement, scheduling and travel coordination, pipeline review, commitment tracking, feedback capture and instruction improvement, and setup.
- `bin/cos` state CLI: task queue with deduplication and seven states, categorised context with sources, dates, staleness and conflict flags, action ledger with idempotency keys, single-use approvals, feedback types, versioned learned rules with revert, time zone aware clock and slot finder, connector and routine status, health check.
- Morning, afternoon and weekly routine prompts, shipped disabled.
- Installer with install, upgrade, status, verify, rollback and uninstall. Preserves config, data and files you have edited.
- Synthetic demo fixtures and a first-run walkthrough script.
- Test suite, runnable from the extracted package.

Known limitations: see KNOWN_LIMITATIONS.md.

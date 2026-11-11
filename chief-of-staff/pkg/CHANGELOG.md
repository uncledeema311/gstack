# Changelog

## 1.0.1 - 2026-11-11

Fixed
- docs/CONNECTORS.md and the example config described `approval_mode = "approve"` as "always ask first". In Codex it means the opposite: run without asking. The guide now uses `prompt` and `writes`, and explains all four values. If you copied that line from 1.0.0 into `~/.codex/config.toml`, change it.

Changed
- The connector guide now covers connectors that arrive through ChatGPT apps and plugins (listed under `codex_apps` in `/mcp`), which is how Gmail, Calendar, Drive, HubSpot, Slack, Fathom and Granola appeared on a real account. The recommended hard rule is `[apps._default]` with `default_tools_approval_mode = "writes"` and `destructive_enabled = false`, which needs no tool names.
- `config/codex-mcp.example.toml` is replaced by `config/codex-config.example.toml`.
- `cos-setup` recognises app tools by their prefix and reminds you about the approval settings.
- Notes on plugin skills with similar names, and how to pick the chief-of-staff skill explicitly.

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

# Connecting your systems

The package ships no connectors and no credentials. Codex connects to your systems. The chief of staff then uses whatever tools Codex exposes, and records what it verified.

Nothing here has been tested against your Codex account. Treat the steps as the documented route, and let `cos-setup` tell you what actually works.

## Systems the skills can use

| System | Used for | Without it |
|---|---|---|
| Gmail | Recent threads, drafts | Paste the thread. Drafts stay in the conversation |
| Google Calendar | Meetings, availability | Tell it the time and attendees. No verified slot suggestions |
| HubSpot | Deals, contacts, notes | Pipeline review stops. CRM updates are text for you to paste |
| Google Drive | Linked proposals, decks, target sheets | Attach or paste the document |
| Slack | Mentions, direct requests | Skipped in briefs |
| Fathom or Granola | Meeting transcripts | Paste the transcript or three lines of notes |

## Step 1: see what Codex can already reach

Start Codex in the workspace and type `/mcp`. Type `/mcp verbose` for the tool names.

There are two places a connector can come from, and they look different in that list:

| Where | How it shows in `/mcp` | How you add it |
|---|---|---|
| ChatGPT apps and plugins | All together under `codex_apps`, with tool names prefixed by the app: `gmail.create_draft`, `google_calendar.update_event`, `hubspot.manage_crm_objects`, `slack.slack_edit_message`, `fathom.get_meeting_transcript`, `granola.get_meeting_transcript` | Connect the app in ChatGPT, or install its plugin: the Plugins tab in the ChatGPT desktop app, or `/plugins` in the Codex CLI. Start a new session afterwards |
| MCP servers you add yourself | Under their own name, for example `fathom` | `codex mcp add <name> --url <address>` with the address from the vendor's documentation, then `codex mcp login <name>` |

If a system appears under `codex_apps`, it is connected. You do not need a separate MCP server for it as well. A separate entry for the same system that says `authentication required` is a second, unused route: log in to it with `/mcp login <name>`, or remove it with `codex mcp remove <name>`. Either is fine.

Observed on one real account on 11 November 2026 (Codex CLI 0.167.0): Gmail, Google Calendar, Google Drive, HubSpot, Slack, Fathom and Granola were all present under `codex_apps`. Your account may differ.

## Step 2: make "ask before writing" a hard rule

The instructions tell the assistant to draft and ask. That is a guardrail. Codex can enforce it. Add this to `~/.codex/config.toml`, then restart Codex:

```toml
[apps._default]
default_tools_approval_mode = "writes"
destructive_enabled = false
```

What it does, for every app under `codex_apps`:

- `default_tools_approval_mode = "writes"`: Codex asks you before any tool that is not marked read-only. Reads stay quick. Sending, creating and updating need your yes. You will also be asked before a draft is created, because a draft is a write.
- `destructive_enabled = false`: tools marked destructive, such as delete, are blocked.

If `~/.codex/config.toml` already has an `[apps._default]` section, add the two lines to it instead of creating a second one.

The four approval values, as Codex implements them:

| Value | Meaning |
|---|---|
| `prompt` | Always ask before the tool runs |
| `writes` | Ask unless the tool is marked read-only |
| `auto` | Codex decides from the tool's own hints. This is the default |
| `approve` | Run without asking. Do not use this for anything that sends or writes |

For MCP servers you added yourself the same setting goes under that server, and `disabled_tools` hides a tool completely:

```toml
[mcp_servers.NAME]
default_tools_approval_mode = "writes"
disabled_tools = ["REPLACE_WITH_TOOL_NAME"]
```

A fuller example is in `config/codex-config.example.toml`. It is an example only. The installer never edits `~/.codex/config.toml`.

Test it before you trust it: after restarting Codex, ask it to create a Gmail draft addressed to yourself. Codex should stop and ask for approval before the draft is created. If it does not ask, the setting is not in effect: check the file for a typo or a duplicate section.

What is verified and what is not: Codex CLI 0.167.0 accepts these settings, and their meaning is taken from the Codex source. Their effect on a live connector was not tested by the package author. `writes` and `destructive_enabled` also depend on each connector marking its tools correctly as read-only or destructive. How an unattended scheduled run behaves when a tool needs approval is not documented, so check the first scheduled run by hand (docs/ROUTINES.md).

## Skills with similar names

Plugins can bring their own skills. The HubSpot plugin, for example, ships skills such as "Pipeline Health" and "Customer Prep". If Codex picks one of those when you wanted the chief of staff, name the skill: `$cos-pipeline-review`, `$cos-meeting-prep`. Type `$` to see the list.

## Step 3: let the assistant check and record

In Codex, in the workspace, say:

```
run cos-setup
```

For each system it looks for a tool, makes one small read-only call, and records the result:

```bash
bin/cos connector list
```

| Status | Meaning |
|---|---|
| `unknown` | Not checked yet. The assistant must not assume it works |
| `connected` | A read-only call succeeded, with what was called and when |
| `unavailable` | No tool in the session, or the call failed, with the reason |

Run `cos-setup` again after connecting something new.

## What the assistant does with each permission level

| Action | Without asking | With your approval for that action | Never |
|---|---|---|---|
| Read, search, summarise | Yes | | |
| Create a Gmail draft, a CRM note proposal, a document draft, a Slack draft, a calendar proposal | Yes, recorded in the ledger | | |
| Send an email | | Yes | |
| Send or change a calendar invitation | | Yes | |
| Write to the CRM | | Yes | |
| Post to Slack | | Yes | |
| Purchase, delete records, change permissions | | | Never |

These lists are in `config/cos.config.json` under `permissions`. Send, invite, CRM write and Slack post are locked to approval-only: `bin/cos config validate` fails if they are moved.

## Removing a connection

Disconnect the plugin in Codex, or `codex mcp remove <name>`. Then `bin/cos connector set <name> --status unknown` or run `cos-setup` again. Uninstalling the chief of staff does not disconnect anything.

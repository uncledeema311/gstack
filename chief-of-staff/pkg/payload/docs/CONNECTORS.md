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

## Step 1: connect each system in Codex

Two documented routes. Use whichever your account offers for each system.

Plugins (ChatGPT desktop app or Codex CLI):

1. In the ChatGPT desktop app open the Plugins tab. In the Codex CLI run `codex`, then type `/plugins`.
2. Find the plugin for the system, install it, and sign in when asked.
3. Start a new session so its tools load.

MCP servers (for systems without a plugin):

1. Get the MCP server address from that vendor's own documentation.
2. Add it: `codex mcp add <name> --url <address>`
3. Sign in if it uses OAuth: `codex mcp login <name>`
4. Check: `codex mcp list`, or type `/mcp` inside Codex to see the server and its tools.

At build time the Codex plugin documentation named Gmail, Google Drive and Slack plugins. It did not confirm plugins for Google Calendar, HubSpot, Fathom or Granola, so expect to use the vendor's MCP server for those, if one exists for your plan.

## Step 2: make sending impossible, not just disallowed

The instructions tell the assistant to draft and ask. That is a guardrail. To make it a hard limit, restrict the tools in `~/.codex/config.toml`. Tool names differ per connector, so look them up first by typing `/mcp` in Codex.

Hide a tool completely:

```toml
[mcp_servers.gmail]
url = "https://REPLACE-WITH-VENDOR-MCP-URL"
disabled_tools = ["REPLACE_WITH_SEND_TOOL_NAME"]
```

Or keep a tool but always ask first:

```toml
[mcp_servers.calendar.tools.REPLACE_WITH_CREATE_EVENT_TOOL_NAME]
approval_mode = "approve"
```

A fuller example is in `config/codex-mcp.example.toml`. It is an example only. The installer never edits `~/.codex/config.toml`. Restart Codex after changing it.

Recommended before you schedule any routine: disable every send, post, create-event and CRM-write tool, because scheduled runs are unattended. Whether tool restrictions can be applied to tools that come from a plugin is not something the documentation confirmed. If you cannot restrict a plugin's send tool, prefer the MCP route for that system, or do not schedule routines.

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

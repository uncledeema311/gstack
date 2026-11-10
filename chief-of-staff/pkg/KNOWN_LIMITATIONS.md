# Known limitations

Read this before relying on the assistant for anything that matters.

## What has not been verified

1. **Not run on macOS.** The package was built and tested on Linux with Python 3.9 and 3.13 and Codex CLI 0.167.0. The code uses only the Python standard library and POSIX features that macOS has, and the shell scripts are plain bash, but nobody has run this ZIP on a Mac. Run `bash verify.sh` after installing.
2. **No real conversation with the model was tested.** There was no Codex login in the build environment. What was verified with the real Codex CLI is that it loads the generated `AGENTS.md` and discovers all ten skills. How well the model follows them is untested. Use the first-run walkthrough (docs/FIRST_RUN.md, part B) as your acceptance test.
3. **No connector was tested inside Codex.** Connector behaviour in the tests is mocked. Which plugins or MCP servers exist for your account, what their tools are called, and whether they offer a draft tool are all unknown until you connect them. `cos-setup` records what actually works.
4. **The ChatGPT desktop app was not tested.** Skills and `AGENTS.md` are documented as shared between the CLI and the app, and Scheduled tasks are documented for the app, but none of that was exercised here. Menu names in these documents may differ from your app version.

## Limits of the design

5. **Approvals are a guardrail, not enforcement.** The instructions and the action ledger make the model ask first and make its claims checkable. They cannot stop a tool call. If a send tool is connected, the model is technically able to call it. For a hard block, disable or gate those tools in Codex (docs/CONNECTORS.md).
6. **Scheduled runs are unattended.** Codex documents that scheduled tasks can run without approval prompts. The routine prompts say read and draft only, but see point 5. Disable send tools before scheduling anything.
7. **The package cannot create or start a schedule.** Routines are prompts. A routine runs only after you create a Scheduled task in the ChatGPT desktop app, and only while the Mac is awake and the app is running. The CLI has no scheduler.
8. **Learned rules apply from the next session.** A new rule is written into `AGENTS.md`, which Codex reads when a session starts. The assistant is told to apply it for the rest of the current session, but that depends on the model.
9. **The permission check on learned rules is pattern based.** It refuses common phrasings that widen permissions ("without asking", "automatically send", "pre-approved"). An unusual phrasing could get through as text. It still would not change what the ledger allows, because permissions live in the config, not in rules.
10. **Duplicate detection is textual.** Tasks match on normalised company and action text, plus a similarity check. Two differently worded descriptions of the same work can both be created. `bin/cos task duplicates` lists likely pairs. Nothing is merged automatically.
11. **Conflict detection needs an attribute.** Two facts conflict only when they share subject and attribute with different values. Free-form facts without an attribute are not compared.
12. **Idempotency covers recorded actions only.** If the model performs an outward-facing step without calling `bin/cos action plan` first, the ledger does not know about it.
13. **Local state is single user, single machine.** Plain JSON files in the workspace with a file lock. No sync, no encryption at rest beyond what your Mac provides, no multi-user access. Back up `data/` like any other folder.
14. **Stored context is a memory aid.** Facts carry a source, a date and a verified flag, and go stale by category. They are not a copy of your CRM and can be wrong. The instructions require a live read before acting on time-sensitive details.
15. **Skills that need a connector degrade, they do not improvise.** Without the CRM, pipeline review stops and says so. Without a transcript, follow-up works from your notes and labels it that way.
16. **WhatsApp and LinkedIn have no connector here.** Messages for those channels are given as text for you to send.
17. **Travel is preparation only.** No booking, no payments, by design.
18. **`AGENTS.md` has a 32 KiB limit in Codex.** The generated file is under 10 KiB. `bin/cos render` warns at 28 KiB and refuses above the limit, so very long custom instructions or hundreds of learned rules will not fit.
19. **Windows and Linux are not supported targets.** The CLI uses POSIX file locking. It happens to run on Linux, where it was tested.
20. **Configured profile defaults.** `config/cos.config.json` starts with the profile this package was built for (name, role, company, city, time zone). Check it after installing.

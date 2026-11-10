# Start here

This ZIP installs a personal chief of staff for Codex on macOS: one workspace folder containing instructions, ten skills and a small local state store.

## Five minutes to a working install

1. Open Terminal and go to the extracted folder:

   ```bash
   cd ~/Downloads/chief-of-staff-codex-1.0.0
   ```

2. Install (creates `~/ChiefOfStaff`, changes nothing else on your Mac):

   ```bash
   bash install.sh
   ```

   Expected last lines:

   ```
     health check: passed

   Next: open /Users/<you>/ChiefOfStaff in Codex and say: run cos-setup
   ```

3. Check it:

   ```bash
   bash verify.sh
   ```

   Expected: `RESULT: PASSED`. If the Codex CLI is on your PATH you will also see `[PASS] Codex loads AGENTS.md and all 10 skills`. Otherwise that line says `[SKIP]` with what to do instead.

4. See it work on synthetic data, with no connectors and no Codex needed:

   ```bash
   cd ~/ChiefOfStaff && bash demo/walkthrough.sh
   ```

5. Start Codex in the workspace and run setup:

   ```bash
   codex -C ~/ChiefOfStaff --sandbox workspace-write
   ```

   Then type: `run cos-setup`

   In the ChatGPT desktop app, start a Codex chat with `~/ChiefOfStaff` as its folder instead.

## What works when

| Works straight after install | Needs a connection or a choice from you | Not possible in this environment |
|---|---|---|
| Instructions and all ten skills load in Codex | Reading Gmail, Calendar, HubSpot, Drive, Slack, Fathom or Granola: connect each one in Codex first (docs/CONNECTORS.md) | The package creating or starting a schedule by itself |
| Task queue, context store, action ledger, approvals, feedback and learned rules | Morning, afternoon and weekly routines: you choose time, time zone and delivery, then create the schedule in the ChatGPT desktop app (docs/ROUTINES.md) | Scheduled runs while the Mac is asleep or the app is closed |
| Time zone aware slot finding | Hard blocking of send tools: a setting you apply in Codex (docs/CONNECTORS.md) | Technically preventing a connected send tool from being called, from inside this package |
| The synthetic demo walkthrough | | Scheduling from the Codex CLI alone |

## Where to read next

| You want to | Read |
|---|---|
| Understand what was installed | README.md |
| Fix an install problem | INSTALL.md |
| Connect your systems | docs/CONNECTORS.md (in the workspace: `~/ChiefOfStaff/docs/`) |
| Walk through one full meeting flow | docs/FIRST_RUN.md |
| Turn on routines | docs/ROUTINES.md |
| Upgrade, roll back or uninstall | UPGRADE.md |
| Know the limits before relying on it | KNOWN_LIMITATIONS.md |
| See what was tested | TESTING.md |

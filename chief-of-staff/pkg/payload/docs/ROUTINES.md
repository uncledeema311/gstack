# Routines: morning, afternoon, weekly

Three routines are installed. None is scheduled. Installing the package starts nothing.

| Routine | What it runs | Prompt file |
|---|---|---|
| morning | Daily brief, morning mode | `routines/morning.md` |
| afternoon | Afternoon wrap plus a commitment sweep of today | `routines/afternoon.md` |
| weekly | Weekly brief plus pipeline review | `routines/weekly.md` |

## Installed, configured, active

| State shown by `bin/cos routine list` | Meaning |
|---|---|
| `installed, schedule disabled` | The prompt file exists. Nothing runs. This is the state after install |
| `configured, but no schedule exists in Codex yet (not running)` | You chose a time, a time zone and a delivery location. Still nothing runs |
| `active: schedule confirmed in Codex on <date>` | You created the Scheduled task and confirmed it |

The package cannot create a schedule and cannot see whether one exists. "Active" records your confirmation, nothing more.

## Requirements and cautions

- Schedules are a feature of the ChatGPT desktop app. The Codex CLI has no scheduler.
- For work on local files, the Mac must be awake and the app running at the scheduled time.
- Scheduled runs are unattended and may run without approval prompts. The routine prompts say read and draft only. Make that a hard limit by disabling send and write tools first: see docs/CONNECTORS.md, step 2.
- Results appear under Scheduled in the app, which works as an inbox.

## Turn a routine on

The easy way is to say `set up my morning routine` in Codex and let `cos-setup` walk you through it. By hand:

1. Choose the three things only you can decide, then record them:

   ```bash
   cd ~/ChiefOfStaff
   bin/cos routine configure morning --time 07:30 --timezone Australia/Melbourne --deliver-to "Scheduled inbox in the ChatGPT app"
   ```

   Optional: `--days mon,tue,wed,thu,fri`.

2. Get the prompt:

   ```bash
   bin/cos routine prompt morning
   ```

3. In the ChatGPT desktop app, in a Codex chat that uses `~/ChiefOfStaff` as its folder, ask it to create a scheduled task with that prompt at that time, and to run it in this project folder. Check it appears under Scheduled.

4. Record that it exists:

   ```bash
   bin/cos routine confirm morning
   ```

5. After the first run, open the result under Scheduled and check it reads like a brief, lists skipped connectors under "Not checked", and sent nothing.

## Change or stop a routine

- Change the time: run `bin/cos routine configure` again with the new values, change the Scheduled task in the app to match, then `bin/cos routine confirm`. Reconfiguring clears the confirmation on purpose.
- Stop: pause or delete the Scheduled task in the app, then `bin/cos routine disable morning`. Disabling only updates the local record. If you skip the app step, the schedule keeps running.

## Check

```bash
bin/cos routine list
```

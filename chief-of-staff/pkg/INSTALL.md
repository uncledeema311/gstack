# Installation and troubleshooting

Installation is a short manual procedure in Terminal. It is not one click.

## Before you start

| Check | Command | Expected |
|---|---|---|
| Python 3.9 or newer | `python3 --version` | `Python 3.9.x` or higher |
| Codex CLI (optional for install, used by verify) | `codex --version` | a version number |

If `python3` is missing or opens a prompt about developer tools, run `xcode-select --install`, wait for it to finish, and try again.

## Install

1. Extract the ZIP. Double-click it in Finder, or:

   ```bash
   cd ~/Downloads && unzip chief-of-staff-codex-1.0.1.zip
   ```

   Expected: a folder `chief-of-staff-codex-1.0.1` containing `START_HERE.md`, `install.sh`, `manifest.json`, `payload/`, `installer/` and `tests/`.

2. Preview what will happen (optional, changes nothing):

   ```bash
   cd ~/Downloads/chief-of-staff-codex-1.0.1
   bash install.sh --dry-run
   ```

3. Install:

   ```bash
   bash install.sh
   ```

   To use a different folder: `bash install.sh --workspace ~/Work/ChiefOfStaff`. Use the same `--workspace` with every later command.

   Expected output:

   ```
   Installed chief of staff 1.0.1 in /Users/<you>/ChiefOfStaff
     files: 62 added, 0 updated, 0 unchanged, 0 removed
     config: created from example
     data: created empty
     health check: passed

   Next: open /Users/<you>/ChiefOfStaff in Codex and say: run cos-setup
   ```

4. Verify:

   ```bash
   bash verify.sh
   ```

   Expected:

   ```
     [PASS] managed files present
     [PASS] bin/cos doctor
     [PASS] Codex loads AGENTS.md and all 10 skills
     note: connectors not checked yet: gmail, calendar, hubspot, drive, slack, transcripts. Run the cos-setup skill inside Codex.
   RESULT: PASSED
   ```

   The third line reads `[SKIP]` if the `codex` command is not on your PATH. That is not a failure. It means the check could not be run from Terminal.

5. Review your settings in `~/ChiefOfStaff/config/cos.config.json`: name, role, company, city, time zone, working hours. Then:

   ```bash
   cd ~/ChiefOfStaff && bin/cos config validate && bin/cos render
   ```

6. Start Codex in the workspace:

   ```bash
   codex -C ~/ChiefOfStaff --sandbox workspace-write
   ```

   Type `run cos-setup`. It checks each connector with a read-only call and records the result. Connecting systems is covered in docs/CONNECTORS.md.

## Running install again

Safe at any time. It changes nothing if nothing differs, never touches `config/cos.config.json` or `data/`, and never creates duplicates. Expected: `Already up to date. Nothing to change.`

## What the installer refuses to do

| Situation | Result |
|---|---|
| The folder already has an `AGENTS.md` it did not create | Stops, changes nothing. Use an empty folder, or add `--replace-agents-md` to back that file up first |
| The folder already has files where managed files would go | Stops, changes nothing. Use an empty folder. Or add `--keep-existing` to keep yours (the packaged version is saved beside each as `.new`), or `--force` to back yours up and replace them |
| The extracted package is incomplete or was edited | Stops with the list of missing or changed files. Extract the ZIP again |
| An older package over a newer install | Stops. Use `bash rollback.sh`, or add `--allow-downgrade` |

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `python3 was not found` or a developer tools pop-up | Run `xcode-select --install`, wait, retry |
| `is missing, not set up, or older than Python 3.9` | Same fix. Or point at another Python: `COS_PYTHON=/opt/homebrew/bin/python3 bash install.sh` |
| Install worked with `COS_PYTHON=...` but `bin/cos` fails later | `bin/cos` runs with whichever `python3` is first on your PATH. Make that one Python 3.9 or newer, or run it as `/path/to/python3 bin/cos ...` |
| `manifest.json is missing` or `does not match its manifest` | The extraction is incomplete or files were changed. Extract again into an empty folder |
| `health check: FAILED` | The failing checks are listed under it. Fix and run `bash install.sh` again |
| Codex does not seem to know the rules | Codex was started in another folder. Start it with `-C ~/ChiefOfStaff`. Check with `bash verify.sh` |
| Skills do not appear when you type `$` | Restart Codex in the workspace. Confirm `ls ~/ChiefOfStaff/.agents/skills` shows ten `cos-` folders |
| `bin/cos` fails with a permission or read-only error inside Codex | Codex is in read-only mode. Start it with `--sandbox workspace-write`, or pick the mode that allows edits in the workspace |
| Codex asks whether to trust the folder, or notes it is not a Git repository | Expected for a new folder. Trust it. Git is not required |
| `Store is unreadable and was left untouched` | A data file is damaged. The previous generation is beside it as `<file>.bak`. Copy it back, then run `bin/cos doctor` |
| `AGENTS.md had been edited by hand` | Your copy was saved under `.cos/backups/agents-md/`. Put standing instructions in `data/instructions/custom.md` and run `bin/cos render` |
| A routine "does nothing" | Installed is not scheduled. See docs/ROUTINES.md and `bin/cos routine list` |
| `verify.sh` shows `[FAIL] Codex discovery` | Run `codex debug prompt-input ping` in the workspace and look for errors about `SKILL.md` files. Re-run `bash install.sh` to restore managed files |

## Health check at any time

```bash
cd ~/ChiefOfStaff && bin/cos doctor
```

It checks Python, required files, the ten skills, config validity, the time zone, that the data folder is writable, every data store against its schema, and that `AGENTS.md` is current.

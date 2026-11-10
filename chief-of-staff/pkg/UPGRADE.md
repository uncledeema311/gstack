# Upgrade, rollback and uninstall

All three act only on the workspace folder (default `~/ChiefOfStaff`). Add `--workspace DIR` if you installed elsewhere. Add `--dry-run` to any of them to see what would happen without changing anything.

## Upgrade

1. Extract the new ZIP into its own folder.
2. From that folder:

   ```bash
   bash install.sh
   bash verify.sh
   ```

What happens:

- A backup of the current version is written to `.cos/backups/<time>-v<old version>/`: every managed file, `AGENTS.md`, and a snapshot of `data/` and `config/` (`user-data.tar.gz`). The last five backups are kept.
- Managed files are replaced with the new ones.
- A managed file that you edited is kept as yours. The new version is saved beside it with `.new` on the end, and the installer lists it under `KEPT YOUR VERSION`. Compare the two and merge when you are ready. To take the packaged versions instead, run `bash install.sh --overwrite-modified` (your versions are in the backup).
- Files the new version no longer ships are removed, unless you edited them.
- `config/cos.config.json` and `data/` are not touched. New settings take their default until you set them.
- `AGENTS.md` is regenerated from the new core instructions plus your learned rules and `data/instructions/custom.md`.

Expected output:

```
Upgraded chief of staff <new> in /Users/<you>/ChiefOfStaff
  from version <old>
  files: N added, N updated, N unchanged, N removed
  config: preserved
  data: preserved
  backup of the previous files: /Users/<you>/ChiefOfStaff/.cos/backups/...
  health check: passed
```

Restart Codex afterwards so it reloads `AGENTS.md` and the skills.

## Rollback

Returns to the version that was installed before the most recent upgrade.

```bash
bash rollback.sh
```

Or without the ZIP: `python3 ~/ChiefOfStaff/.cos/installer/cos_install.py rollback`

- Managed files are restored from the latest backup. `AGENTS.md` is regenerated.
- Your data and config stay as they are now, including anything added since the upgrade.
- To also return data and config to the moment before the upgrade: `bash rollback.sh --restore-data`. Your newer data is not deleted. It is moved aside to `data.pre-rollback-<time>` and `config.pre-rollback-<time>`.
- The backup that was used is removed, so a second rollback goes one step further back if an older backup exists.
- To go forward again, run `install.sh` from the newer ZIP.

There is nothing to roll back to after a first install. In that case uninstall instead.

## Uninstall

```bash
bash uninstall.sh
```

Or without the ZIP: `python3 ~/ChiefOfStaff/.cos/installer/cos_install.py uninstall`

- Removes the managed files, the generated `AGENTS.md`, the demo data folder and `.cos/` (install record and backups).
- Keeps `data/` and `config/cos.config.json`, and tells you where they are. Installing again later picks them up.
- Keeps any managed file you edited, and lists it. Add `--force` to remove those too. If you install again later into the same folder, add `--keep-existing` to keep those edited files, or `--force` to replace them.

To delete everything, including your tasks, context, feedback and config:

```bash
bash uninstall.sh --purge-data --yes
```

This cannot be undone. Without `--yes` it refuses and removes nothing.

Uninstall does not and cannot:

- delete Scheduled tasks you created in the ChatGPT desktop app. Delete them there, under Scheduled.
- disconnect plugins or remove MCP servers from `~/.codex/config.toml`. Remove them in Codex if you no longer want them.
- remove drafts, notes or events already created in Gmail, your calendar, the CRM or Slack.

## Check what is installed

```bash
python3 ~/ChiefOfStaff/.cos/installer/cos_install.py status
```

Shows the version, when it was installed, files you have modified, pending `.new` files and the backups available for rollback.

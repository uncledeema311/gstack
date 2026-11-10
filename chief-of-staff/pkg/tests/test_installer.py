"""Installer behaviour: install, repeat install, upgrade, rollback, uninstall.
Everything happens in temporary folders."""
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from helper import HAS_MANIFEST, PKG, Workspace, base_env, installer, run

SKILL = ".agents/skills/cos-daily-brief/SKILL.md"


def make_older_package(tmp):
    """A synthetic 0.9.0 build: one skill differs, one file exists only in the old version."""
    old = Path(tmp) / "chief-of-staff-codex-0.9.0"
    shutil.copytree(str(PKG), str(old), ignore=shutil.ignore_patterns("__pycache__"))
    if (old / "manifest.json").exists():
        (old / "manifest.json").unlink()
    (old / "VERSION").write_text("0.9.0\n")
    (old / "payload" / "core" / "VERSION").write_text("0.9.0\n")
    skill = old / "payload" / "skills" / "cos-daily-brief" / "SKILL.md"
    skill.write_text(skill.read_text() + "\nOLD-VERSION-MARKER\n")
    (old / "payload" / "templates" / "old-only.md").write_text("Shipped only in 0.9.0\n")
    return old


OLD_ENV = {"COS_ALLOW_NO_MANIFEST": "1"}


class TempCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cos-inst-"))
        self.addCleanup(lambda: shutil.rmtree(str(self.tmp), ignore_errors=True))
        self.ws = self.tmp / "ChiefOfStaff"

    def install(self, *flags, pkg=PKG, env=None):
        return installer("install", self.ws, *flags, pkg=pkg, env=base_env(env))

    def cos(self, *args):
        code, out, err = run([os.sys.executable, self.ws / "bin" / "cos"] + list(args), cwd=self.ws, env=base_env())
        return code, json.loads(out)

    def snapshot(self):
        return {path.relative_to(self.ws).as_posix(): path.read_bytes() for path in sorted(self.ws.rglob("*"))
                if path.is_file()}


class FreshInstall(TempCase):
    def test_fresh_install_creates_the_expected_structure(self):
        code, summary = self.install()
        self.assertEqual(code, 0, summary)
        self.assertEqual((summary["mode"], summary["config"], summary["data"]), ("fresh", "created from example", "created empty"))
        self.assertTrue(summary["healthy"])
        for rel in ("AGENTS.md", "bin/cos", "lib/cos/cli.py", "core/AGENTS.core.md", "config/cos.config.json",
                    "config/cos.config.example.json", "docs/README.md", "docs/FIRST_RUN.md", "docs/CONNECTORS.md",
                    "routines/morning.md", "schemas/task.schema.json", "demo/walkthrough.sh", ".cos/install.json",
                    ".cos/installer/cos_install.py"):
            self.assertTrue((self.ws / rel).exists(), rel)
        skills = sorted(path.name for path in (self.ws / ".agents" / "skills").iterdir())
        self.assertEqual(len(skills), 10)
        self.assertTrue(all((self.ws / ".agents" / "skills" / name / "SKILL.md").exists() for name in skills))
        self.assertTrue(os.access(str(self.ws / "bin" / "cos"), os.X_OK))
        self.assertIn("COS-CORE-INSTRUCTIONS package 1.0.0", (self.ws / "AGENTS.md").read_text())
        self.assertLess((self.ws / "AGENTS.md").stat().st_size, 32 * 1024)
        self.assertEqual(self.cos("doctor")[0], 0)
        self.assertEqual(self.cos("task", "list")[1]["count"], 0)

    def test_nothing_is_written_outside_the_workspace(self):
        home = self.tmp / "home"
        home.mkdir()
        code, summary = self.install(env={"HOME": str(home)})
        self.assertEqual(code, 0, summary)
        self.assertEqual(list(home.iterdir()), [])
        self.assertEqual(sorted(path.name for path in self.tmp.iterdir()), ["ChiefOfStaff", "home"])

    def test_default_workspace_is_under_home(self):
        home = self.tmp / "home"
        home.mkdir()
        code, out, err = run([os.sys.executable, PKG / "installer" / "cos_install.py", "install", "--json"],
                             env=base_env({"HOME": str(home)}))
        self.assertEqual(code, 0, out + err)
        self.assertEqual(json.loads(out)["workspace"], str((home / "ChiefOfStaff").resolve()))
        self.assertTrue((home / "ChiefOfStaff" / "AGENTS.md").exists())

    def test_dry_run_changes_nothing(self):
        code, summary = self.install("--dry-run")
        self.assertEqual(code, 0, summary)
        self.assertTrue(summary["would_change"])
        self.assertFalse(self.ws.exists())

    def test_running_install_again_changes_nothing_and_creates_no_duplicates(self):
        self.install()
        before = self.snapshot()
        time.sleep(1.1)  # a later second, so any rewritten timestamp would show up as a difference
        code, summary = self.install()
        self.assertEqual(code, 0, summary)
        self.assertEqual(summary["mode"], "reinstall")
        self.assertFalse(summary["changed"])
        self.assertEqual(summary["files"]["added"] + summary["files"]["updated"] + summary["files"]["removed"], 0)
        self.assertIsNone(summary["backup"])
        self.assertEqual(self.snapshot(), before)

    def test_reinstall_preserves_config_data_and_edited_files(self):
        self.install()
        self.cos("config", "set", "timezone", "Australia/Perth")
        self.cos("task", "add", "--company", "Kestrel Ridge Minerals", "--action", "Send pricing", "--source-type",
                 "user", "--source-ref", "user:x", "--priority", "high", "--rationale", "r")
        edited = self.ws / "templates" / "crm-note.md"
        edited.write_text("MY OWN NOTE SHAPE\n")
        code, summary = self.install()
        self.assertEqual(code, 0, summary)
        self.assertEqual(summary["config"], "preserved")
        self.assertEqual(summary["kept_your_version"], ["templates/crm-note.md"])
        self.assertEqual(edited.read_text(), "MY OWN NOTE SHAPE\n")
        self.assertEqual(self.cos("config", "get", "timezone")[1]["value"], "Australia/Perth")
        self.assertEqual(self.cos("task", "list")[1]["count"], 1)

    def test_a_deleted_managed_file_is_restored_by_reinstall(self):
        self.install()
        (self.ws / SKILL).unlink()
        self.assertEqual(self.cos("doctor")[0], 1)
        code, summary = self.install()
        self.assertEqual(summary["files"]["added"], 1)
        self.assertTrue((self.ws / SKILL).exists())
        self.assertEqual(self.cos("doctor")[0], 0)

    def test_a_foreign_agents_md_is_never_overwritten_silently(self):
        self.ws.mkdir()
        (self.ws / "AGENTS.md").write_text("Someone else's instructions\n")
        code, summary = self.install()
        self.assertEqual(code, 1)
        self.assertIn("did not create", summary["error"])
        self.assertEqual(sorted(path.name for path in self.ws.iterdir()), ["AGENTS.md"])
        self.assertEqual((self.ws / "AGENTS.md").read_text(), "Someone else's instructions\n")
        code, summary = self.install("--replace-agents-md")
        self.assertEqual(code, 0, summary)
        backups = list((self.ws / ".cos" / "backups" / "agents-md").glob("AGENTS.*.md"))
        self.assertEqual([path.read_text() for path in backups], ["Someone else's instructions\n"])

    def test_clashing_files_stop_the_install_before_anything_changes(self):
        (self.ws / "bin").mkdir(parents=True)
        (self.ws / "bin" / "cos").write_text("#!/bin/sh\necho mine\n")
        before = self.snapshot()
        code, summary = self.install()
        self.assertEqual(code, 1)
        self.assertIn("bin/cos", summary["error"])
        self.assertEqual(self.snapshot(), before)
        code, summary = self.install("--force")
        self.assertEqual(code, 0, summary)
        saved = list((self.ws / ".cos" / "backups").glob("preinstall-*/files/bin/cos"))
        self.assertEqual(saved[0].read_text(), "#!/bin/sh\necho mine\n")

    @unittest.skipUnless(HAS_MANIFEST, "needs the built package with manifest.json")
    def test_a_damaged_package_is_refused(self):
        damaged = self.tmp / "damaged"
        shutil.copytree(str(PKG), str(damaged), ignore=shutil.ignore_patterns("__pycache__"))
        target = damaged / "payload" / "lib" / "cos" / "ledger.py"
        target.write_text(target.read_text() + "\n# tampered\n")
        (damaged / "payload" / "core" / "AGENTS.core.md").unlink()
        code, summary = self.install(pkg=damaged)
        self.assertEqual(code, 1)
        self.assertIn("changed: payload/lib/cos/ledger.py", summary["error"])
        self.assertIn("missing: payload/core/AGENTS.core.md", summary["error"])
        self.assertFalse(self.ws.exists())

    def test_wrapper_scripts_work(self):
        env = base_env()
        code, out, err = run(["bash", PKG / "install.sh", "--workspace", self.ws], env=env)
        self.assertEqual(code, 0, out + err)
        self.assertIn("Installed chief of staff 1.0.0", out)
        self.assertIn("health check: passed", out)
        code, out, err = run(["bash", PKG / "verify.sh", "--workspace", self.ws, "--no-codex"], env=env)
        self.assertEqual(code, 0, out + err)
        self.assertIn("RESULT: PASSED", out)
        code, out, err = run(["bash", PKG / "rollback.sh", "--workspace", self.ws], env=env)
        self.assertEqual(code, 1)
        self.assertIn("No backup to roll back to", err)
        code, out, err = run(["bash", PKG / "uninstall.sh", "--workspace", self.ws], env=env)
        self.assertEqual(code, 0, out + err)
        self.assertIn("PRESERVED (yours)", out)

    def test_missing_python_gives_a_clear_message(self):
        code, out, err = run(["bash", PKG / "install.sh", "--workspace", self.ws],
                             env=base_env({"COS_PYTHON": "/nonexistent/python3"}))
        self.assertEqual(code, 1)
        self.assertIn("xcode-select --install", err)
        self.assertFalse(self.ws.exists())


class UpgradeRollbackUninstall(TempCase):
    def setUp(self):
        super().setUp()
        self.old = make_older_package(self.tmp)
        code, summary = self.install(pkg=self.old, env=OLD_ENV)
        self.assertEqual(code, 0, summary)
        # The user works for a while on 0.9.0.
        self.cos("config", "set", "timezone", "Australia/Perth")
        self.cos("task", "add", "--company", "Kestrel Ridge Minerals", "--action", "Send pricing", "--source-type",
                 "user", "--source-ref", "user:x", "--priority", "high", "--rationale", "r")
        self.cos("feedback", "add", "--type", "durable_preference", "--text", "From now on keep it short", "--standing")
        self.cos("rules", "propose", "--kind", "style", "--text", "Keep follow-up emails under 120 words.",
                 "--reason", "Asked for it", "--from", "F-0001")
        custom = self.ws / "data" / "instructions" / "custom.md"
        custom.write_text(custom.read_text() + "\nSign off with 'Cheers, Nic'.\n")
        (self.ws / "templates" / "crm-note.md").write_text("MY OWN NOTE SHAPE\n")
        self.user_files = {rel: data for rel, data in self.snapshot().items()
                           if rel.startswith(("data/", "config/cos.config.json")) and not rel.endswith(".lock")}

    def upgrade(self, *flags):
        code, summary = self.install(*flags)
        self.assertEqual(code, 0, summary)
        return summary

    def test_upgrade_replaces_package_files_and_preserves_everything_of_yours(self):
        self.assertIn("OLD-VERSION-MARKER", (self.ws / SKILL).read_text())
        summary = self.upgrade()
        self.assertEqual((summary["mode"], summary["previous_version"], summary["version"]), ("upgrade", "0.9.0", "1.0.0"))
        self.assertTrue(summary["healthy"])
        self.assertNotIn("OLD-VERSION-MARKER", (self.ws / SKILL).read_text())
        self.assertFalse((self.ws / "templates" / "old-only.md").exists())
        after = self.snapshot()
        for rel, data in self.user_files.items():
            self.assertEqual(after[rel], data, "%s changed during upgrade" % rel)
        self.assertEqual(self.cos("config", "get", "timezone")[1]["value"], "Australia/Perth")
        self.assertEqual(self.cos("task", "show", "T-0001")[1]["task"]["action"], "Send pricing")
        self.assertEqual(self.cos("version")[1]["version"], "1.0.0")
        agents = (self.ws / "AGENTS.md").read_text()
        self.assertIn("package 1.0.0", agents)
        self.assertIn("Keep follow-up emails under 120 words.", agents)
        self.assertIn("Sign off with 'Cheers, Nic'.", agents)
        self.assertIn("Time zone: Australia/Perth", agents)

    def test_upgrade_keeps_your_edited_file_and_offers_the_new_one_beside_it(self):
        old_pkg_note = self.old / "payload" / "templates" / "crm-note.md"
        self.assertEqual((self.ws / "templates" / "crm-note.md").read_text(), "MY OWN NOTE SHAPE\n")
        # Make the package's own copy differ between versions, as a real upgrade would.
        newer = self.tmp / "newer"
        shutil.copytree(str(PKG), str(newer), ignore=shutil.ignore_patterns("__pycache__"))
        if (newer / "manifest.json").exists():
            (newer / "manifest.json").unlink()
        (newer / "payload" / "templates" / "crm-note.md").write_text(old_pkg_note.read_text() + "\nNEW LINE IN 1.0.0\n")
        code, summary = self.install(pkg=newer, env=OLD_ENV)
        self.assertEqual(code, 0, summary)
        self.assertEqual(summary["kept_your_version"], ["templates/crm-note.md"])
        self.assertEqual((self.ws / "templates" / "crm-note.md").read_text(), "MY OWN NOTE SHAPE\n")
        self.assertIn("NEW LINE IN 1.0.0", (self.ws / "templates" / "crm-note.md.new").read_text())
        code, summary = self.install("--overwrite-modified", pkg=newer, env=OLD_ENV)
        self.assertIn("NEW LINE IN 1.0.0", (self.ws / "templates" / "crm-note.md").read_text())

    def test_upgrade_makes_a_backup_with_a_data_snapshot(self):
        summary = self.upgrade()
        backup = Path(summary["backup"])
        self.assertTrue(backup.name.endswith("-v0.9.0"))
        self.assertIn("OLD-VERSION-MARKER", (backup / "files" / SKILL).read_text())
        self.assertTrue((backup / "files" / "templates" / "old-only.md").exists())
        self.assertTrue((backup / "user-data.tar.gz").stat().st_size > 100)
        self.assertEqual(json.loads((backup / "install.json").read_text())["version"], "0.9.0")

    def test_downgrade_is_refused_without_the_flag(self):
        self.upgrade()
        code, summary = self.install(pkg=self.old, env=OLD_ENV)
        self.assertEqual(code, 1)
        self.assertIn("rollback", summary["error"])
        self.assertEqual(self.cos("version")[1]["version"], "1.0.0")

    def test_rollback_restores_the_previous_version_and_keeps_current_data(self):
        self.upgrade()
        self.cos("task", "add", "--company", "Kestrel Ridge Minerals", "--action", "Added after the upgrade",
                 "--source-type", "user", "--source-ref", "user:y", "--priority", "low", "--rationale", "r")
        code, summary = installer("rollback", self.ws)
        self.assertEqual(code, 0, summary)
        self.assertEqual((summary["from_version"], summary["to_version"]), ("1.0.0", "0.9.0"))
        self.assertTrue(summary["healthy"])
        self.assertIn("OLD-VERSION-MARKER", (self.ws / SKILL).read_text())
        self.assertTrue((self.ws / "templates" / "old-only.md").exists())
        self.assertEqual((self.ws / "templates" / "crm-note.md").read_text(), "MY OWN NOTE SHAPE\n")
        self.assertEqual(self.cos("version")[1]["version"], "0.9.0")
        self.assertIn("package 0.9.0", (self.ws / "AGENTS.md").read_text())
        self.assertIn("Keep follow-up emails under 120 words.", (self.ws / "AGENTS.md").read_text())
        self.assertEqual(self.cos("task", "list")[1]["count"], 2)  # data from after the upgrade is still there
        self.assertEqual(self.cos("config", "get", "timezone")[1]["value"], "Australia/Perth")
        code, summary = installer("rollback", self.ws)
        self.assertEqual(code, 1)  # nothing further back
        code, summary = self.install()  # and forward again
        self.assertEqual((code, summary["mode"]), (0, "upgrade"))
        self.assertEqual(self.cos("task", "list")[1]["count"], 2)

    def test_rollback_can_also_restore_data_and_moves_newer_data_aside(self):
        self.upgrade()
        self.cos("task", "add", "--company", "Kestrel Ridge Minerals", "--action", "Added after the upgrade",
                 "--source-type", "user", "--source-ref", "user:y", "--priority", "low", "--rationale", "r")
        code, summary = installer("rollback", self.ws, "--restore-data")
        self.assertEqual(code, 0, summary)
        self.assertEqual(self.cos("task", "list")[1]["count"], 1)
        aside = [path for path in self.ws.iterdir() if path.name.startswith("data.pre-rollback-")]
        self.assertEqual(len(aside), 1)
        kept = json.loads((aside[0] / "tasks" / "tasks.json").read_text())
        self.assertEqual(len(kept["records"]), 2)

    def test_uninstall_removes_the_package_and_keeps_your_data(self):
        self.upgrade()
        self.cos("routine", "configure", "morning", "--time", "07:30", "--timezone", "Australia/Melbourne",
                 "--deliver-to", "Scheduled inbox")
        self.cos("demo", "init")
        code, summary = installer("uninstall", self.ws, "--dry-run")
        self.assertTrue((self.ws / "bin" / "cos").exists())
        code, summary = installer("uninstall", self.ws)
        self.assertEqual(code, 0, summary)
        self.assertEqual(summary["kept_modified_by_you"], ["templates/crm-note.md"])
        self.assertIn("morning", summary["routines_note"])
        left = sorted(path.relative_to(self.ws).as_posix() for path in self.ws.rglob("*") if path.is_file())
        self.assertIn("config/cos.config.json", left)
        self.assertIn("data/tasks/tasks.json", left)
        self.assertIn("data/instructions/rules.json", left)
        self.assertIn("templates/crm-note.md", left)
        for rel in left:
            self.assertTrue(rel.startswith(("data/", "config/cos.config.json", "templates/crm-note.md")), rel)
        for gone in ("AGENTS.md", ".agents", ".cos", "bin", "lib", "core", "docs", "demo", "data-demo", "routines"):
            self.assertFalse((self.ws / gone).exists(), gone)
        after = self.snapshot()
        for rel, data in self.user_files.items():
            if rel in after and rel != "config/cos.config.json":
                self.assertEqual(after[rel], data)
        code, summary = installer("uninstall", self.ws)
        self.assertEqual(code, 1)  # nothing installed any more
        code, summary = self.install()  # the edited file that was kept is still protected
        self.assertEqual(code, 1)
        self.assertIn("--keep-existing", summary["error"])
        code, summary = self.install("--keep-existing")  # reinstalling picks the data back up
        self.assertEqual(code, 0, summary)
        self.assertEqual((self.ws / "templates" / "crm-note.md").read_text(), "MY OWN NOTE SHAPE\n")
        self.assertTrue((self.ws / "templates" / "crm-note.md.new").exists())
        self.assertEqual(self.cos("task", "list")[1]["count"], 1)
        self.assertIn("Keep follow-up emails under 120 words.", (self.ws / "AGENTS.md").read_text())

    def test_purging_data_needs_explicit_confirmation(self):
        code, summary = installer("uninstall", self.ws, "--purge-data")
        self.assertEqual(code, 1)
        self.assertIn("--yes", summary["error"])
        self.assertTrue((self.ws / "data" / "tasks" / "tasks.json").exists())
        self.assertTrue((self.ws / "bin" / "cos").exists())
        code, summary = installer("uninstall", self.ws, "--purge-data", "--yes", "--force")
        self.assertEqual(code, 0, summary)
        self.assertTrue(summary["workspace_removed"])
        self.assertFalse(self.ws.exists())

    def test_status_reports_version_and_your_modifications(self):
        self.upgrade()
        code, status = installer("status", self.ws)
        self.assertEqual((status["version"], status["modified_by_you"]), ("1.0.0", ["templates/crm-note.md"]))
        self.assertEqual(len(status["backups"]), 1)
        self.assertEqual([entry["action"] for entry in status["history"]], ["fresh", "upgrade"])

    def test_installed_copy_of_the_installer_can_uninstall_without_the_zip(self):
        code, out, err = run([os.sys.executable, self.ws / ".cos" / "installer" / "cos_install.py", "uninstall", "--json"],
                             env=base_env())
        self.assertEqual(code, 0, out + err)
        self.assertEqual(json.loads(out)["workspace"], str(self.ws.resolve()))
        self.assertFalse((self.ws / "bin").exists())
        self.assertTrue((self.ws / "data").exists())


if __name__ == "__main__":
    unittest.main()

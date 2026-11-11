"""Checks on the package itself: structure, consistency and hygiene."""
import ast
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

from helper import HAS_MANIFEST, PKG

PAYLOAD = PKG / "payload"
SKILLS = PAYLOAD / "skills"
SECTIONS = ["## Trigger", "## Required inputs", "## Retrieval procedure", "## Output format", "## Quality checks",
            "## Permitted actions", "## Completion criteria"]
TEXT_SUFFIXES = {".md", ".py", ".sh", ".json", ".toml", ".txt", ""}


def package_files():
    for path in sorted(PKG.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.name != ".DS_Store":
            yield path


def text_files():
    for path in package_files():
        if path.suffix in TEXT_SUFFIXES:
            yield path, path.read_text(encoding="utf-8")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cli_parser():
    sys.path.insert(0, str(PAYLOAD / "lib"))
    try:
        from cos import cli
        return cli.build_parser(), cli
    finally:
        sys.path.pop(0)


def subcommands(parser):
    for action in parser._actions:
        if hasattr(action, "choices") and isinstance(action.choices, dict):
            return action.choices
    return {}


class Skills(unittest.TestCase):
    def skill_dirs(self):
        return sorted(path for path in SKILLS.iterdir() if path.is_dir())

    def test_the_nine_required_skills_and_setup_exist(self):
        names = [path.name for path in self.skill_dirs()]
        self.assertEqual(names, sorted([
            "cos-daily-brief", "cos-meeting-prep", "cos-post-meeting-followup", "cos-crm-update",
            "cos-prospect-reengagement", "cos-scheduling-travel", "cos-pipeline-review", "cos-commitment-tracking",
            "cos-feedback", "cos-setup"]))
        _parser, cli = cli_parser()
        self.assertEqual(sorted(cli.SKILLS), names)

    def test_each_skill_has_valid_frontmatter_and_all_seven_sections(self):
        for folder in self.skill_dirs():
            text = (folder / "SKILL.md").read_text()
            match = re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", text)
            self.assertIsNotNone(match, "%s: frontmatter must be exactly name and description" % folder.name)
            self.assertEqual(match.group(1), folder.name)
            self.assertLessEqual(len(match.group(2)), 1024, folder.name)
            self.assertGreater(len(match.group(2)), 80, folder.name)
            positions = [text.find(section + "\n") for section in SECTIONS]
            self.assertNotIn(-1, positions, "%s is missing a section: %s" % (folder.name, positions))
            self.assertEqual(positions, sorted(positions), "%s: sections out of order" % folder.name)
            self.assertIn("AGENTS.md", text.split("## Trigger")[0], "%s must defer to the shared rules" % folder.name)

    def test_skills_only_name_action_types_that_exist(self):
        sys.path.insert(0, str(PAYLOAD / "lib"))
        from cos import config
        perms = config.DEFAULTS["permissions"]
        known = set(perms["no_approval"] + perms["approval_required"] + perms["never"])
        for folder in self.skill_dirs():
            text = (folder / "SKILL.md").read_text()
            for used in re.findall(r"--type ([a-z_]+)", text) + re.findall(r"\(`([a-z]+_[a-z_]+)`", text):
                if used in ("task_correction", "factual_update", "durable_preference", "workflow_change"):
                    continue
                self.assertIn(used, known, "%s names unknown action type %s" % (folder.name, used))

    def test_index_and_core_instructions_list_every_skill(self):
        index = (PAYLOAD / "docs" / "SKILLS_INDEX.md").read_text()
        core = (PAYLOAD / "core" / "AGENTS.core.md").read_text()
        readme = (PKG / "README.md").read_text()
        for folder in self.skill_dirs():
            for name, text in (("SKILLS_INDEX.md", index), ("AGENTS.core.md", core), ("README.md", readme)):
                self.assertIn("`%s`" % folder.name, text, "%s does not list %s" % (name, folder.name))

    def test_shared_rules_live_in_one_place(self):
        core = (PAYLOAD / "core" / "AGENTS.core.md").read_text()
        for rule in ("Australian English", "Never use em dashes", 'Use "mate" only in WhatsApp',
                     "Never send, propose to send or modify a calendar invitation without approval",
                     "Draft external communications", "verify the person's name, company and email"):
            self.assertIn(rule, core)
        for placeholder in re.findall(r"\{\{([A-Z_]+)\}\}", core):
            self.assertIn('"%s"' % placeholder, (PAYLOAD / "lib" / "cos" / "render.py").read_text())


class Hygiene(unittest.TestCase):
    def test_no_em_or_en_dashes_anywhere(self):
        for path, text in text_files():
            for char in (chr(0x2014), chr(0x2013)):
                self.assertNotIn(char, text, "%s contains a dash character U+%04X" % (path.relative_to(PKG), ord(char)))

    def test_no_credentials_or_private_data(self):
        patterns = [r"sk-[A-Za-z0-9]{20,}", r"xox[abprs]-[A-Za-z0-9-]{10,}", r"AKIA[0-9A-Z]{16}", r"-----BEGIN [A-Z ]*PRIVATE KEY",
                    r"ghp_[A-Za-z0-9]{30,}", r"pat-[a-z0-9]{2,4}-[a-f0-9-]{30,}", r"(?i)password\s*[:=]\s*\S+",
                    r"(?i)bearer\s+[A-Za-z0-9._-]{20,}", r"(?i)api[_-]?key\s*[:=]\s*['\"][^'\"]+['\"]"]
        for path, text in text_files():
            for pattern in patterns:
                self.assertIsNone(re.search(pattern, text), "%s matches %s" % (path.relative_to(PKG), pattern))
            for address in re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text):
                self.assertTrue(address.endswith("example.com"), "%s contains a non-example address: %s"
                                % (path.relative_to(PKG), address))

    def test_demo_data_is_marked_synthetic(self):
        fixtures = PAYLOAD / "demo" / "fixtures"
        for path in fixtures.glob("*.json"):
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                self.assertIs(data.get("synthetic"), True, path.name)
        self.assertIn("SYNTHETIC", (fixtures / "transcript.md").read_text())
        for path in (PAYLOAD / "demo" / "expected").glob("*.md"):
            self.assertIn("SYNTHETIC DEMO DATA", path.read_text(), path.name)

    def test_no_user_data_or_config_is_shipped(self):
        names = [path.relative_to(PKG).as_posix() for path in package_files()]
        self.assertFalse([name for name in names if name.startswith("payload/data")])
        self.assertNotIn("payload/config/cos.config.json", names)
        self.assertFalse([name for name in names if name.endswith((".env", ".pem", ".key", ".pyc"))])

    def test_all_json_parses_and_templates_match_their_schemas(self):
        for path in package_files():
            if path.suffix == ".json":
                json.loads(path.read_text())
        sys.path.insert(0, str(PAYLOAD / "lib"))
        from cos import validate
        for template, schema in (("task.example.json", "task"), ("context.example.json", "context")):
            record = json.loads((PAYLOAD / "templates" / template).read_text())
            spec = json.loads((PAYLOAD / "schemas" / ("%s.schema.json" % schema)).read_text())
            self.assertEqual(validate.check(record, spec), [], template)

    def test_python_sources_are_valid_for_python_3_9(self):
        for path in package_files():
            if path.suffix == ".py" or path.name == "cos":
                source = path.read_text()
                ast.parse(source, filename=str(path), feature_version=(3, 9))
                self.assertNotIn("match ", [line.strip()[:6] for line in source.splitlines() if line.strip().endswith(":")
                                            and line.strip().startswith("match ")])

    def test_only_the_standard_library_is_imported(self):
        allowed = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else None
        if allowed is None:
            self.skipTest("needs Python 3.10+ to list standard library modules")
        allowed |= {"cos", "helper"}
        for path in package_files():
            if path.suffix != ".py" and path.name != "cos":
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    modules = [node.module]
                for module in modules:
                    self.assertIn(module.split(".")[0], allowed, "%s imports %s" % (path.relative_to(PKG), module))


class Consistency(unittest.TestCase):
    def test_version_is_the_same_everywhere(self):
        version = (PKG / "VERSION").read_text().strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertEqual((PAYLOAD / "core" / "VERSION").read_text().strip(), version)
        self.assertIn("## %s - " % version, (PKG / "CHANGELOG.md").read_text().split("\n## ")[1].join(["## ", ""]))
        self.assertIn("Version %s." % version, (PKG / "README.md").read_text())
        self.assertIn("chief-of-staff-codex-%s" % version, (PKG / "START_HERE.md").read_text())
        self.assertIn("chief-of-staff-codex-%s.zip" % version, (PKG / "INSTALL.md").read_text())
        if HAS_MANIFEST:
            self.assertEqual(json.loads((PKG / "manifest.json").read_text())["version"], version)

    @unittest.skipUnless(HAS_MANIFEST, "needs the built package with manifest.json")
    def test_manifest_lists_every_file_with_the_right_hash(self):
        installer = load_module("cos_install_test", PKG / "installer" / "cos_install.py")
        manifest = json.loads((PKG / "manifest.json").read_text())
        actual = sorted(path.relative_to(PKG).as_posix() for path in package_files() if path.name != "manifest.json")
        self.assertEqual(sorted(manifest["files"]), actual)
        for rel, meta in manifest["files"].items():
            self.assertEqual(installer.sha256_file(PKG / rel), meta["sha256"], rel)
        self.assertEqual(manifest["package"], "chief-of-staff-codex")
        self.assertEqual(manifest["requires"]["python"], ">=3.9")
        self.assertEqual(manifest["requires"]["third_party_packages"], [])

    def test_required_documents_are_present(self):
        for name in ("START_HERE.md", "README.md", "INSTALL.md", "UPGRADE.md", "KNOWN_LIMITATIONS.md", "CHANGELOG.md",
                     "TESTING.md", "VERSION", "install.sh", "verify.sh", "rollback.sh", "uninstall.sh",
                     "installer/cos_install.py", "tests/run_all.sh", "payload/docs/CONNECTORS.md",
                     "payload/docs/ROUTINES.md", "payload/docs/FIRST_RUN.md", "payload/docs/STATE.md",
                     "payload/docs/SKILLS_INDEX.md", "payload/config/cos.config.example.json",
                     "payload/config/codex-config.example.toml", "payload/demo/walkthrough.sh"):
            self.assertTrue((PKG / name).exists(), name)

    def test_install_document_states_the_real_file_count(self):
        installer = load_module("cos_install_count", PKG / "installer" / "cos_install.py")
        count = len(installer.file_plan(PKG))
        self.assertIn("files: %d added, 0 updated, 0 unchanged, 0 removed" % count, (PKG / "INSTALL.md").read_text())

    def test_every_documented_cos_command_and_flag_exists(self):
        parser, _cli = cli_parser()
        groups = subcommands(parser)
        checked = 0
        for path, text in text_files():
            if path.suffix not in (".md", ".sh") or "tests" in path.parts:
                continue
            text = text.replace("\\\n", " ")
            for line in text.splitlines():
                for match in re.finditer(r"bin/cos(?: --demo)?((?: +[A-Za-z0-9_<>\"'.:@/=,$|\[\]{}-]+)*)", line):
                    tokens = match.group(1).split()
                    words = []
                    for token in tokens:
                        if re.match(r"^[a-z][a-z-]*$", token) and len(words) < 2 and not words[1:]:
                            words.append(token)
                        else:
                            break
                    if not words:
                        continue
                    where = "%s: bin/cos %s" % (path.relative_to(PKG), " ".join(tokens[:6]))
                    self.assertIn(words[0], groups, where)
                    target = groups[words[0]]
                    nested = subcommands(target)
                    if nested:
                        if len(words) == 1:
                            continue  # prose naming the command group, for example `bin/cos task`
                        self.assertIn(words[1], nested, where)
                        target = nested[words[1]]
                    flags = set(target._option_string_actions) | {"--demo"}
                    for token in tokens:
                        if token.startswith("--"):
                            self.assertIn(token.split("=")[0], flags, "%s uses unknown flag %s" % (where, token))
                    checked += 1
        self.assertGreater(checked, 120)

    def test_documented_installer_flags_exist(self):
        source = (PKG / "installer" / "cos_install.py").read_text()
        for path, text in text_files():
            if path.suffix != ".md":
                continue
            for line in text.splitlines():
                if re.search(r"(install|verify|rollback|uninstall)\.sh|cos_install\.py", line):
                    for flag in re.findall(r"(--[a-z][a-z-]+)", line):
                        if flag in ("--sandbox", "--version", "--url"):
                            continue
                        self.assertIn('"%s"' % flag, source, "%s documents unknown installer flag %s"
                                      % (path.relative_to(PKG), flag))

    def test_approve_is_never_presented_as_asking_first(self):
        # In Codex, approval_mode "approve" runs a tool WITHOUT asking. Recommending it would be unsafe.
        for path, text in text_files():
            if "tests" in path.parts or path.name == "CHANGELOG.md":  # the changelog describes the fix
                continue
            for line in text.splitlines():
                self.assertIsNone(re.search(r'approval_mode\s*=\s*"approve"', line),
                                  "%s recommends approval_mode approve: %s" % (path.relative_to(PKG), line.strip()))
        example = (PAYLOAD / "config" / "codex-config.example.toml").read_text()
        active = [line.strip() for line in example.splitlines() if line.strip() and not line.strip().startswith("#")]
        self.assertEqual(active, ["[apps._default]", 'default_tools_approval_mode = "writes"', "destructive_enabled = false"])
        guide = (PAYLOAD / "docs" / "CONNECTORS.md").read_text()
        self.assertIn("| `approve` | Run without asking.", guide)
        self.assertIn("| `prompt` | Always ask before the tool runs |", guide)

    def test_routine_prompts_are_read_only_and_reference_real_skills(self):
        names = {path.name for path in SKILLS.iterdir()}
        for name in ("morning", "afternoon", "weekly"):
            text = (PAYLOAD / "routines" / ("%s.md" % name)).read_text()
            self.assertIn("---PROMPT---", text)
            prompt = text.split("---PROMPT---")[1]
            self.assertIn("Do not send, post, invite or write to any external system", prompt)
            for skill in re.findall(r"\$(cos-[a-z-]+)", prompt):
                self.assertIn(skill, names)

    def test_shell_scripts_parse(self):
        import subprocess
        for path in package_files():
            if path.suffix == ".sh":
                proc = subprocess.run(["bash", "-n", str(path)], stderr=subprocess.PIPE, universal_newlines=True)
                self.assertEqual(proc.returncode, 0, "%s: %s" % (path.name, proc.stderr))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Test the built release ZIP itself, in a clean temporary directory, and write the test report.

Usage: python3 release_check.py release/chief-of-staff-codex-1.0.0.zip [--python PATH ...] [--codex PATH]

Nothing here uses the development tree: the archive is extracted and every check
runs against the extracted copy, with HOME pointed at an empty temporary folder.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

RESULTS = []  # (area, check, status, detail)


def record(area, check, ok, detail=""):
    status = ok if isinstance(ok, str) else ("PASS" if ok else "FAIL")
    RESULTS.append((area, check, status, detail))
    print("  [%s] %s: %s %s" % (status, area, check, ("- " + detail) if detail and status != "PASS" else ""))
    return status == "PASS"


def sh(cmd, cwd=None, env=None, timeout=900):
    proc = subprocess.run([str(item) for item in cmd], cwd=str(cwd) if cwd else None, env=env, timeout=timeout,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return proc.returncode, proc.stdout, proc.stderr


def clean_env(home, extra=None):
    env = {key: value for key, value in os.environ.items() if not key.startswith("COS_")}
    env["HOME"] = str(home)
    env.update(extra or {})
    return env


def parse_unittest(text):
    """Per-module pass, fail and skip counts from unittest -v output."""
    modules = {}
    for line in text.splitlines():
        match = re.match(r"^(test_\w+) \((test_\w+)\.[\w.]+\)(?: \.\.\.)? ?.*?\b(ok|FAIL|ERROR|skipped)\b", line)
        if not match:
            continue
        counts = modules.setdefault(match.group(2), {"ok": 0, "FAIL": 0, "ERROR": 0, "skipped": 0, "failed": []})
        counts[match.group(3)] += 1
        if match.group(3) in ("FAIL", "ERROR"):
            counts["failed"].append(match.group(1))
    total = re.search(r"^Ran (\d+) tests? in ([\d.]+)s", text, re.M)
    return modules, (int(total.group(1)) if total else 0), bool(re.search(r"^OK", text, re.M))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("zip")
    parser.add_argument("--python", action="append", default=[], help="interpreter(s) to run the packaged tests with")
    parser.add_argument("--codex", help="path to the codex CLI for the discovery check")
    parser.add_argument("--report", help="where to write the Markdown report")
    args = parser.parse_args()
    zip_path = Path(args.zip).resolve()
    pythons = args.python or [sys.executable]
    work = Path(tempfile.mkdtemp(prefix="cos-release-"))
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    print("Release check for %s\n  sha256 %s\n  work dir %s" % (zip_path.name, digest, work))

    # ------------------------------------------------------------ 1. archive
    area = "Archive"
    with zipfile.ZipFile(str(zip_path)) as archive:
        names = archive.namelist()
        record(area, "ZIP integrity (CRC of every entry)", archive.testzip() is None)
    version = zip_path.stem.rsplit("-", 1)[-1]
    top = "chief-of-staff-codex-%s" % version
    record(area, "single top-level folder named %s" % top, all(name.startswith(top + "/") for name in names))
    record(area, "no absolute paths or parent references", not any(name.startswith("/") or ".." in name.split("/") for name in names))
    record(area, "no compiled, cache, backup or OS junk files",
           not any(name.endswith((".pyc", ".DS_Store", ".bak", ".tmp")) or "__pycache__" in name for name in names))
    extract_dir = work / "extract"
    extract_dir.mkdir()
    code, out, err = sh(["unzip", "-q", zip_path, "-d", extract_dir])
    record(area, "extracts with the system unzip tool", code == 0, err.strip()[:200])
    pkg = extract_dir / top
    expected = ["START_HERE.md", "README.md", "INSTALL.md", "UPGRADE.md", "KNOWN_LIMITATIONS.md", "CHANGELOG.md",
                "TESTING.md", "VERSION", "manifest.json", "install.sh", "verify.sh", "rollback.sh", "uninstall.sh",
                "installer/cos_install.py", "installer/find_python.sh", "tests/run_all.sh", "payload/bin/cos",
                "payload/core/AGENTS.core.md", "payload/lib/cos/cli.py", "payload/config/cos.config.example.json",
                "payload/config/codex-mcp.example.toml", "payload/docs/FIRST_RUN.md", "payload/docs/CONNECTORS.md",
                "payload/docs/ROUTINES.md", "payload/docs/STATE.md", "payload/docs/SKILLS_INDEX.md",
                "payload/demo/walkthrough.sh", "payload/demo/fixtures/transcript.md", "payload/routines/morning.md",
                "payload/routines/afternoon.md", "payload/routines/weekly.md", "payload/schemas/task.schema.json"]
    missing = [rel for rel in expected if not (pkg / rel).exists()]
    record(area, "expected structure present (%d key files)" % len(expected), not missing, ", ".join(missing))
    skills = sorted(path.name for path in (pkg / "payload" / "skills").iterdir())
    record(area, "ten skills, each with SKILL.md", len(skills) == 10 and all((pkg / "payload" / "skills" / name / "SKILL.md").exists() for name in skills))
    manifest = json.loads((pkg / "manifest.json").read_text())
    on_disk = sorted(path.relative_to(pkg).as_posix() for path in pkg.rglob("*") if path.is_file() and path.name != "manifest.json")
    hashes_ok = all(hashlib.sha256((pkg / rel).read_bytes()).hexdigest() == meta["sha256"] for rel, meta in manifest["files"].items())
    record(area, "manifest lists exactly the extracted files, hashes match", sorted(manifest["files"]) == on_disk and hashes_ok)
    record(area, "manifest version matches the file name", manifest["version"] == version == (pkg / "VERSION").read_text().strip())
    record(area, "executable bits preserved on scripts", all(os.access(str(pkg / rel), os.X_OK) for rel in ("install.sh", "verify.sh", "uninstall.sh", "rollback.sh", "payload/bin/cos")))

    # ------------------------------------------------------------ 2. packaged tests
    suites = {}
    for python in pythons:
        code, out, err = sh([python, "--version"])
        label = (out or err).strip()
        home = work / ("home-tests-" + label.replace(" ", "-"))
        home.mkdir()
        code, out, err = sh(["bash", pkg / "tests" / "run_all.sh", "-v"], env=clean_env(home, {"COS_PYTHON": python}), timeout=1800)
        modules, total, ok = parse_unittest(err + out)
        suites[label] = (modules, total, ok)
        failed = [name for counts in modules.values() for name in counts["failed"]]
        record("Packaged tests", "tests/run_all.sh under %s (%d tests)" % (label, total), code == 0 and ok and total > 0,
               ", ".join(failed)[:300])
        record("Packaged tests", "tests left nothing in HOME (%s)" % label, list(home.iterdir()) == [])

    # ------------------------------------------------------------ 3. clean install as a user would
    area = "Install from the extracted ZIP"
    home = work / "home"
    home.mkdir()
    codex_home = work / "codex-home"
    codex_home.mkdir()
    env = clean_env(home, {"CODEX_HOME": str(codex_home)})
    if args.codex:
        env["PATH"] = str(Path(args.codex).absolute().parent) + os.pathsep + env["PATH"]
    ws = home / "ChiefOfStaff"
    code, out, err = sh(["bash", "install.sh", "--dry-run"], cwd=pkg, env=env)
    record(area, "install.sh --dry-run changes nothing", code == 0 and not ws.exists())
    code, out, err = sh(["bash", "install.sh"], cwd=pkg, env=env)
    install_out = out
    record(area, "bash install.sh into an empty HOME (default ~/ChiefOfStaff)", code == 0 and "health check: passed" in out, (out + err)[-300:])
    count = re.search(r"files: (\d+) added", out)
    documented = re.search(r"files: (\d+) added", (pkg / "INSTALL.md").read_text())
    record(area, "installer output matches INSTALL.md (file count %s)" % (count.group(1) if count else "?"),
           bool(count and documented and count.group(1) == documented.group(1)))
    record(area, "only ~/ChiefOfStaff was created in HOME", sorted(path.name for path in home.iterdir()) == ["ChiefOfStaff"])
    record(area, "Codex config untouched (CODEX_HOME still empty before verify)", list(codex_home.iterdir()) == [])
    agents = (ws / "AGENTS.md").read_text()
    record(area, "AGENTS.md generated, under the 32 KiB Codex limit (%d bytes)" % len(agents.encode()), len(agents.encode()) < 32768 and "{{" not in agents)
    code, out, err = sh(["bash", "install.sh"], cwd=pkg, env=env)
    record(area, "second install is a no-op", code == 0 and "Already up to date. Nothing to change." in out, out[-200:])

    area = "Verify"
    code, out, err = sh(["bash", "verify.sh", "--no-codex"], cwd=pkg, env=env)
    record(area, "bash verify.sh --no-codex", code == 0 and "RESULT: PASSED" in out, out[-300:])
    if args.codex:
        code, cv, _ = sh([args.codex, "--version"])
        codex_version = cv.strip()
        code, out, err = sh(["bash", "verify.sh"], cwd=pkg, env=env)
        record(area, "real Codex CLI (%s) loads AGENTS.md and all 10 skills" % codex_version,
               code == 0 and "[PASS] Codex loads AGENTS.md and all 10 skills" in out, (out + err)[-400:])
        shutil.copyfile(str(ws / "config" / "codex-mcp.example.toml"), str(codex_home / "config.toml"))
        code, out, err = sh([args.codex, "mcp", "list"], cwd=ws, env=env)
        record(area, "config/codex-mcp.example.toml is accepted by %s (codex mcp list)" % codex_version,
               code == 0 and "hubspot" in out and "gmail" in out, (out + err)[-300:])
        (codex_home / "config.toml").unlink()
    else:
        codex_version = None
        record(area, "real Codex CLI discovery", "UNTESTED", "no --codex given")

    area = "First-run walkthrough (synthetic data, MOCKED connectors)"
    code, out, err = sh(["bash", "demo/walkthrough.sh"], cwd=ws, env=env)
    record(area, "demo/walkthrough.sh completes", code == 0 and "Walkthrough complete." in out, (out + err)[-300:])
    doc = (ws / "docs" / "FIRST_RUN.md").read_text().split("## Part B")[0]
    lines = [line.rstrip() for block in doc.split("```")[1::2] for line in block.splitlines()
             if line.startswith("  ") and not line.rstrip().endswith("...")]
    absent = [line for line in lines if line not in out]
    record(area, "every expected line in FIRST_RUN.md part A appears in the real output (%d lines)" % len(lines), not absent, "; ".join(absent)[:300])
    code, out, err = sh([ws / "bin" / "cos", "--demo", "task", "list"], cwd=ws, env=env)
    record(area, "persistence: a new process reads the 4 demo tasks back", code == 0 and json.loads(out)["count"] == 4)
    code, out, err = sh([ws / "bin" / "cos", "task", "list"], cwd=ws, env=env)
    record(area, "real data untouched by the demo", code == 0 and json.loads(out)["count"] == 0)

    area = "Uninstall from the extracted ZIP"
    sh([ws / "bin" / "cos", "task", "add", "--company", "Example", "--action", "Keep me", "--source-type", "user",
        "--source-ref", "user:x", "--priority", "low", "--rationale", "r"], cwd=ws, env=env)
    code, out, err = sh(["bash", "uninstall.sh"], cwd=pkg, env=env)
    left = sorted(path.relative_to(ws).as_posix() for path in ws.rglob("*") if path.is_file())
    record(area, "bash uninstall.sh removes the package", code == 0 and not (ws / "bin").exists() and not (ws / "AGENTS.md").exists() and not (ws / ".agents").exists())
    record(area, "data and config preserved", "data/tasks/tasks.json" in left and "config/cos.config.json" in left
           and all(rel.startswith(("data/", "config/")) for rel in left), ", ".join(left)[:200])
    code, out, err = sh(["bash", "install.sh"], cwd=pkg, env=env)
    code2, out2, _ = sh([ws / "bin" / "cos", "task", "list"], cwd=ws, env=env)
    record(area, "reinstall picks the preserved data back up", code == 0 and json.loads(out2)["count"] == 1)
    code, out, err = sh(["bash", "uninstall.sh", "--purge-data", "--yes"], cwd=pkg, env=env)
    record(area, "uninstall --purge-data --yes leaves nothing behind", code == 0 and not ws.exists() and list(home.iterdir()) == [])

    # ------------------------------------------------------------ report
    failed = [item for item in RESULTS if item[2] == "FAIL"]
    summary = {
        "zip": zip_path.name, "sha256": digest, "bytes": zip_path.stat().st_size, "entries": len(names),
        "version": version, "when": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "platform": "%s %s (%s)" % (platform.system(), platform.release(), platform.machine()),
        "codex": codex_version, "results": RESULTS, "suites": {label: {"total": total, "ok": ok, "modules": modules}
                                                             for label, (modules, total, ok) in suites.items()},
        "install_output": install_out,
    }
    out_json = Path(args.report or (zip_path.parent / ("TEST_REPORT-%s.md" % version))).with_suffix(".json")
    out_json.write_text(json.dumps(summary, indent=2) + "\n")
    print("\n%d checks: %d passed, %d failed, %d untested" % (
        len(RESULTS), len([item for item in RESULTS if item[2] == "PASS"]), len(failed),
        len([item for item in RESULTS if item[2] == "UNTESTED"])))
    print("results written to %s" % out_json)
    shutil.rmtree(str(work), ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

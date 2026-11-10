#!/usr/bin/env python3
"""Installer for the chief-of-staff Codex workspace.

Commands: install (also upgrades), status, verify, rollback, uninstall.
Python 3.9+ standard library only. Touches nothing outside the workspace folder.

Ownership model:
  managed files   shipped by the package, tracked by hash in .cos/install.json.
                  Replaced on upgrade only if you have not changed them.
  generated       AGENTS.md, rebuilt from core + your rules by bin/cos render.
  yours           config/cos.config.json and everything under data/.
                  Never overwritten, never deleted unless you pass --purge-data --yes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PACKAGE = "chief-of-staff-codex"
DEFAULT_WORKSPACE = "~/ChiefOfStaff"
ROOT_DOCS = ["START_HERE.md", "README.md", "INSTALL.md", "UPGRADE.md", "KNOWN_LIMITATIONS.md", "CHANGELOG.md", "TESTING.md"]
KEEP_BACKUPS = 5
SKILL_PREFIX = "cos-"


class InstallError(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.message = message
        self.code = code


# ---------------------------------------------------------------- helpers


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(str(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stamp() -> str:
    override = os.environ.get("COS_NOW")
    if override:
        text = override[:-1] + "+00:00" if override.endswith("Z") else override
        moment = dt.datetime.fromisoformat(text).astimezone(dt.timezone.utc)
    else:
        moment = dt.datetime.now(dt.timezone.utc)
    return moment.strftime("%Y%m%dT%H%M%S") + "%06dZ" % moment.microsecond


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def running_from_workspace() -> Optional[Path]:
    """If this script is the installed copy (<workspace>/.cos/installer), return the workspace."""
    here = script_dir()
    if here.name == "installer" and here.parent.name == ".cos":
        return here.parent.parent
    return None


def package_root() -> Path:
    if running_from_workspace():
        raise InstallError("This command needs the extracted package. Run install.sh from the extracted ZIP folder.")
    return script_dir().parent


def resolve_workspace(arg: Optional[str]) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    installed = running_from_workspace()
    if installed:
        return installed
    return Path(os.environ.get("COS_WORKSPACE", DEFAULT_WORKSPACE)).expanduser().resolve()


def state_path(ws: Path) -> Path:
    return ws / ".cos" / "install.json"


def load_state(ws: Path) -> Optional[Dict[str, Any]]:
    path = state_path(ws)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise InstallError("Install record is unreadable: %s. Nothing was changed." % path)


def save_state(ws: Path, state: Dict[str, Any]) -> None:
    path = state_path(ws)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(path))


def version_tuple(text: str) -> Tuple[int, ...]:
    parts = []
    for piece in text.strip().split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".cos-tmp")
    shutil.copyfile(str(src), str(tmp))
    os.replace(str(tmp), str(dest))


def run_cos(ws: Path, *args: str) -> Tuple[int, Dict[str, Any]]:
    env = dict(os.environ)
    for key in ("COS_ROOT", "COS_DATA_DIR", "COS_CONFIG"):
        env.pop(key, None)
    proc = subprocess.run([sys.executable, str(ws / "bin" / "cos")] + list(args), cwd=str(ws), env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except ValueError:
        return proc.returncode or 1, {"ok": False, "error": (proc.stderr or proc.stdout).strip()[:500]}


# ---------------------------------------------------------------- package contents


def read_version(pkg: Path) -> str:
    return (pkg / "VERSION").read_text(encoding="utf-8").strip()


def verify_manifest(pkg: Path) -> None:
    manifest_path = pkg / "manifest.json"
    if not manifest_path.exists():
        if os.environ.get("COS_ALLOW_NO_MANIFEST") == "1":
            return
        raise InstallError("manifest.json is missing. The package looks incomplete. Extract the ZIP again.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = []
    for rel, meta in sorted(manifest["files"].items()):
        path = pkg / rel
        if not path.exists():
            problems.append("missing: %s" % rel)
        elif sha256_file(path) != meta["sha256"]:
            problems.append("changed: %s" % rel)
    if problems:
        raise InstallError(
            "The package does not match its manifest, so nothing was installed.\n  "
            + "\n  ".join(problems[:15])
            + "\nExtract the ZIP again into an empty folder and retry."
        )


def file_plan(pkg: Path) -> List[Tuple[Path, str]]:
    """(source path, destination relative to the workspace) for every managed file."""
    plan: List[Tuple[Path, str]] = []
    payload = pkg / "payload"
    for path in sorted(payload.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.name == ".DS_Store":
            continue
        rel = path.relative_to(payload).as_posix()
        if rel.startswith("skills/"):
            rel = ".agents/" + rel
        plan.append((path, rel))
    for name in ROOT_DOCS:
        if (pkg / name).exists():
            plan.append((pkg / name, "docs/" + name))
    return plan


# ---------------------------------------------------------------- backup


def backups_dir(ws: Path) -> Path:
    return ws / ".cos" / "backups"


def list_backups(ws: Path) -> List[Path]:
    base = backups_dir(ws)
    if not base.exists():
        return []
    return sorted(path for path in base.iterdir() if path.is_dir() and "-v" in path.name and (path / "install.json").exists())


def make_backup(ws: Path, state: Dict[str, Any]) -> Path:
    target = backups_dir(ws) / ("%s-v%s" % (stamp(), state["version"]))
    files = target / "files"
    for rel in state["files"]:
        src = ws / rel
        if src.exists():
            copy_file(src, files / rel)
    (target / "install.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for extra in ("AGENTS.md", ".cos/render.json"):
        if (ws / extra).exists():
            copy_file(ws / extra, target / "generated" / extra)
    with tarfile.open(str(target / "user-data.tar.gz"), "w:gz") as archive:
        for name in ("data", "config"):
            if (ws / name).exists():
                archive.add(str(ws / name), arcname=name)
    for old in list_backups(ws)[:-KEEP_BACKUPS]:
        shutil.rmtree(str(old), ignore_errors=True)
    return target


# ---------------------------------------------------------------- install / upgrade


def cmd_install(args: argparse.Namespace) -> Dict[str, Any]:
    pkg = package_root()
    ws = resolve_workspace(args.workspace)
    version = read_version(pkg)
    verify_manifest(pkg)
    plan = [(src, rel, sha256_file(src)) for src, rel in file_plan(pkg)]
    state = load_state(ws)

    if state and state.get("package") != PACKAGE:
        raise InstallError("%s holds a different package (%s). Choose another folder." % (ws, state.get("package")))
    if state and version_tuple(state["version"]) > version_tuple(version) and not args.allow_downgrade:
        raise InstallError(
            "Version %s is installed and this package is older (%s). To go back, use: rollback. "
            "To install the older package anyway, add --allow-downgrade." % (state["version"], version)
        )
    if ws.exists() and not ws.is_dir():
        raise InstallError("%s exists and is not a folder." % ws)

    mode = "fresh" if state is None else ("reinstall" if state["version"] == version else "upgrade")
    preexisting: List[str] = []
    if state is None:
        agents = ws / "AGENTS.md"
        if agents.exists() and not args.replace_agents_md:
            raise InstallError(
                "%s already contains an AGENTS.md that this package did not create. Nothing was changed.\n"
                "Use an empty folder (recommended), or add --replace-agents-md to back that file up to "
                ".cos/backups/agents-md/ and generate a new one." % ws
            )
        preexisting = [rel for _src, rel, digest in plan if (ws / rel).exists() and sha256_file(ws / rel) != digest]
        if preexisting and not (args.force or args.keep_existing):
            raise InstallError(
                "These files already exist in %s with different content. Nothing was changed.\n  %s\n"
                "Use an empty folder (recommended). Or add --keep-existing to keep yours (the packaged version "
                "is saved beside each as .new), or --force to back yours up and replace them."
                % (ws, "\n  ".join(preexisting[:15]))
            )

    old_files: Dict[str, str] = state["files"] if state else {}
    new_files = {rel: digest for _src, rel, digest in plan}
    actions: Dict[str, List[str]] = {"added": [], "updated": [], "unchanged": [], "kept_your_version": [], "removed": [],
                                     "kept_removed_from_package": []}
    for _src, rel, digest in plan:
        dest = ws / rel
        if not dest.exists():
            actions["added"].append(rel)
        else:
            current = sha256_file(dest)
            if current == digest:
                actions["unchanged"].append(rel)
            elif old_files.get(rel) == current or (state is None and args.force) or args.overwrite_modified:
                actions["updated"].append(rel)
            else:
                actions["kept_your_version"].append(rel)
    for rel, digest in old_files.items():
        if rel in new_files or not (ws / rel).exists():
            continue
        if sha256_file(ws / rel) == digest:
            actions["removed"].append(rel)
        else:
            actions["kept_removed_from_package"].append(rel)

    will_change = bool(actions["added"] or actions["updated"] or actions["removed"]) or mode == "upgrade"
    summary: Dict[str, Any] = {"command": "install", "mode": mode, "workspace": str(ws), "version": version,
                               "previous_version": state["version"] if state else None, "dry_run": args.dry_run,
                               "files": {key: len(value) for key, value in actions.items()},
                               "kept_your_version": actions["kept_your_version"],
                               "kept_removed_from_package": actions["kept_removed_from_package"]}
    if args.dry_run:
        summary["would_change"] = will_change
        return summary

    ws.mkdir(parents=True, exist_ok=True)
    backup = None
    if state and will_change:
        backup = make_backup(ws, state)
    elif state is None and preexisting and args.force:
        backup = backups_dir(ws) / ("preinstall-%s" % stamp())
        for rel in preexisting:
            copy_file(ws / rel, backup / "files" / rel)
    summary["backup"] = str(backup) if backup else None

    sidecars: List[str] = []
    by_rel = {rel: src for src, rel, _digest in plan}
    for rel in actions["added"] + actions["updated"]:
        copy_file(by_rel[rel], ws / rel)
    for rel in actions["kept_your_version"]:
        # Offer the packaged file beside yours, but only when the package itself changed it.
        if old_files.get(rel) != new_files[rel]:
            copy_file(by_rel[rel], ws / (rel + ".new"))
            sidecars.append(rel + ".new")
    for rel in actions["removed"]:
        (ws / rel).unlink()
    previous_sidecars = [rel for rel in (state or {}).get("sidecars", []) if (ws / rel).exists()]
    if mode == "reinstall":
        sidecars = previous_sidecars
    else:
        for rel in previous_sidecars:
            if rel not in sidecars:
                (ws / rel).unlink()
    os.chmod(str(ws / "bin" / "cos"), 0o755)

    config_target = ws / "config" / "cos.config.json"
    if config_target.exists():
        summary["config"] = "preserved"
    else:
        copy_file(ws / "config" / "cos.config.example.json", config_target)
        summary["config"] = "created from example"
    (ws / "data" / "instructions").mkdir(parents=True, exist_ok=True)
    summary["data"] = "preserved" if state else "created empty"

    copy_file(Path(__file__).resolve(), ws / ".cos" / "installer" / "cos_install.py")

    if will_change or state is None:
        history = list((state or {}).get("history", []))
        history.append({"at": now_iso(), "action": mode, "from": state["version"] if state else None, "to": version})
        save_state(ws, {
            "package": PACKAGE,
            "version": version,
            "installed_at": (state or {}).get("installed_at") or now_iso(),
            "updated_at": now_iso(),
            "files": new_files,
            "sidecars": sidecars,
            "history": history,
        })
    summary["changed"] = bool(will_change or state is None)

    code, rendered = run_cos(ws, "render")
    summary["agents_md"] = rendered if code == 0 else {"error": rendered.get("error")}
    code, doctor = run_cos(ws, "doctor")
    summary["healthy"] = code == 0
    summary["doctor_failures"] = [item for item in doctor.get("checks", []) if item["status"] == "fail"]
    if code != 0 and not summary["doctor_failures"]:
        summary["doctor_failures"] = [{"check": "doctor", "status": "fail", "detail": doctor.get("error", "")}]
    return summary


# ---------------------------------------------------------------- status / verify


def modified_files(ws: Path, state: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    modified, missing = [], []
    for rel, digest in sorted(state["files"].items()):
        path = ws / rel
        if not path.exists():
            missing.append(rel)
        elif sha256_file(path) != digest:
            modified.append(rel)
    return modified, missing


def cmd_status(args: argparse.Namespace) -> Dict[str, Any]:
    ws = resolve_workspace(args.workspace)
    state = load_state(ws)
    if state is None:
        return {"command": "status", "workspace": str(ws), "installed": False}
    modified, missing = modified_files(ws, state)
    return {
        "command": "status", "workspace": str(ws), "installed": True, "version": state["version"],
        "installed_at": state["installed_at"], "updated_at": state["updated_at"],
        "managed_files": len(state["files"]), "modified_by_you": modified, "missing": missing,
        "pending_new_versions": state.get("sidecars", []),
        "backups": [path.name for path in list_backups(ws)], "history": state.get("history", []),
    }


def codex_discovery(ws: Path) -> Dict[str, Any]:
    """Ask the real Codex CLI what it would load in this folder. Needs no login."""
    codex = shutil.which("codex")
    if not codex:
        return {"status": "skipped", "detail": "codex CLI not found on PATH. In the ChatGPT desktop app, open this "
                "folder as a project and type $ in the composer: the cos- skills should be listed."}
    try:
        proc = subprocess.run([codex, "debug", "prompt-input", "ping"], cwd=str(ws), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "skipped", "detail": "could not run codex debug prompt-input: %s" % exc}
    if proc.returncode != 0:
        first = (proc.stderr.strip().splitlines() or ["no output"])[-1]
        return {"status": "skipped", "detail": "codex debug prompt-input is not available here: %s" % first[:200]}
    skills = sorted(path.name for path in (ws / ".agents" / "skills").iterdir() if path.is_dir()
                    and path.name.startswith(SKILL_PREFIX))
    missing = [name for name in skills if name not in proc.stdout]
    instructions = "COS-CORE-INSTRUCTIONS" in proc.stdout
    ok = instructions and not missing
    return {"status": "pass" if ok else "fail", "instructions_loaded": instructions, "skills_expected": len(skills),
            "skills_missing": missing}


def cmd_verify(args: argparse.Namespace) -> Dict[str, Any]:
    ws = resolve_workspace(args.workspace)
    state = load_state(ws)
    if state is None:
        raise InstallError("No installation found at %s." % ws)
    modified, missing = modified_files(ws, state)
    code, doctor = run_cos(ws, "doctor")
    discovery = {"status": "skipped", "detail": "--no-codex"} if args.no_codex else codex_discovery(ws)
    failures = [item for item in doctor.get("checks", []) if item["status"] == "fail"]
    if code != 0 and not failures:
        failures = [{"check": "doctor", "status": "fail", "detail": doctor.get("error", "")}]
    passed = code == 0 and not missing and discovery["status"] != "fail"
    return {
        "command": "verify", "workspace": str(ws), "version": state["version"], "passed": passed,
        "managed_files_missing": missing, "managed_files_modified_by_you": modified,
        "doctor_healthy": code == 0, "doctor_failures": failures,
        "doctor_warnings": [item for item in doctor.get("checks", []) if item["status"] == "warn"],
        "codex_discovery": discovery,
    }


# ---------------------------------------------------------------- rollback


def cmd_rollback(args: argparse.Namespace) -> Dict[str, Any]:
    ws = resolve_workspace(args.workspace)
    state = load_state(ws)
    if state is None:
        raise InstallError("No installation found at %s." % ws)
    backups = list_backups(ws)
    if not backups:
        raise InstallError("No backup to roll back to. Backups are created when an upgrade changes files.")
    backup = backups[-1]
    old_state = json.loads((backup / "install.json").read_text(encoding="utf-8"))
    summary: Dict[str, Any] = {"command": "rollback", "workspace": str(ws), "from_version": state["version"],
                               "to_version": old_state["version"], "backup_used": backup.name, "dry_run": args.dry_run,
                               "restored": 0, "removed": 0, "kept_your_version": []}
    if args.dry_run:
        return summary

    for rel, digest in state["files"].items():
        if rel in old_state["files"]:
            continue
        path = ws / rel
        if path.exists():
            if sha256_file(path) == digest:
                path.unlink()
                summary["removed"] += 1
            else:
                summary["kept_your_version"].append(rel)
    for rel in old_state["files"]:
        saved = backup / "files" / rel
        if not saved.exists():
            continue
        dest = ws / rel
        if dest.exists() and sha256_file(dest) == sha256_file(saved):
            continue
        if dest.exists() and sha256_file(dest) != state["files"].get(rel):
            summary["kept_your_version"].append(rel)
            continue
        copy_file(saved, dest)
        summary["restored"] += 1
    for rel in state.get("sidecars", []):
        if (ws / rel).exists():
            (ws / rel).unlink()
    os.chmod(str(ws / "bin" / "cos"), 0o755)

    summary["data"] = "kept as it is now"
    if args.restore_data:
        aside = "pre-rollback-%s" % stamp()
        for name in ("data", "config"):
            if (ws / name).exists():
                os.replace(str(ws / name), str(ws / ("%s.%s" % (name, aside))))
        with tarfile.open(str(backup / "user-data.tar.gz"), "r:gz") as archive:
            members = [member for member in archive.getmembers()
                       if not member.name.startswith(("/", "..")) and ".." not in Path(member.name).parts]
            archive.extractall(str(ws), members=members)
        summary["data"] = "restored from the backup. Your newer data was moved to data.%s and config.%s" % (aside, aside)

    history = list(state.get("history", []))
    history.append({"at": now_iso(), "action": "rollback", "from": state["version"], "to": old_state["version"]})
    old_state["history"] = history
    old_state["updated_at"] = now_iso()
    old_state["sidecars"] = []
    save_state(ws, old_state)
    shutil.rmtree(str(backup), ignore_errors=True)

    code, rendered = run_cos(ws, "render")
    summary["agents_md"] = rendered if code == 0 else {"error": rendered.get("error")}
    code, doctor = run_cos(ws, "doctor")
    summary["healthy"] = code == 0
    summary["doctor_failures"] = [item for item in doctor.get("checks", []) if item["status"] == "fail"]
    return summary


# ---------------------------------------------------------------- uninstall


def prune_empty(ws: Path, rels: List[str]) -> None:
    folders = set()
    for rel in rels:
        parent = (ws / rel).parent
        while parent != ws and ws in parent.parents:
            folders.add(parent)
            parent = parent.parent
    for folder in sorted(folders, key=lambda item: len(item.parts), reverse=True):
        cache = folder / "__pycache__"
        if cache.is_dir():
            shutil.rmtree(str(cache), ignore_errors=True)
        junk = folder / ".DS_Store"
        if junk.exists():
            junk.unlink()
        try:
            folder.rmdir()
        except OSError:
            pass


def cmd_uninstall(args: argparse.Namespace) -> Dict[str, Any]:
    ws = resolve_workspace(args.workspace)
    state = load_state(ws)
    if state is None:
        raise InstallError("No installation found at %s. Nothing was removed." % ws)
    if args.purge_data and not args.yes:
        raise InstallError("--purge-data permanently deletes your tasks, context, feedback and config. "
                           "Add --yes to confirm. Nothing was removed.")
    summary: Dict[str, Any] = {"command": "uninstall", "workspace": str(ws), "version": state["version"],
                               "dry_run": args.dry_run, "removed": 0, "kept_modified_by_you": [], "preserved": []}
    routines_note = None
    code, routines = run_cos(ws, "routine", "list")
    if code == 0:
        active = [name for name, entry in routines.get("routines", {}).items() if entry.get("enabled")]
        if active:
            routines_note = ("Routines were configured (%s). If you created Scheduled tasks in the ChatGPT desktop "
                             "app, delete them there. Uninstall cannot do that." % ", ".join(active))
    if args.dry_run:
        modified, _missing = modified_files(ws, state)
        summary["would_remove"] = len(state["files"]) - len(modified)
        summary["kept_modified_by_you"] = [] if args.force else modified
        return summary

    for rel, digest in state["files"].items():
        path = ws / rel
        if not path.exists():
            continue
        if sha256_file(path) == digest or args.force:
            path.unlink()
            summary["removed"] += 1
        else:
            summary["kept_modified_by_you"].append(rel)
    for rel in state.get("sidecars", []):
        if (ws / rel).exists():
            (ws / rel).unlink()

    agents, render_state = ws / "AGENTS.md", ws / ".cos" / "render.json"
    if agents.exists():
        recorded = None
        if render_state.exists():
            try:
                recorded = json.loads(render_state.read_text(encoding="utf-8")).get("sha256")
            except ValueError:
                recorded = None
        if recorded == sha256_file(agents) or args.force:
            agents.unlink()
            summary["removed"] += 1
        else:
            summary["kept_modified_by_you"].append("AGENTS.md")

    prune_empty(ws, list(state["files"]))
    shutil.rmtree(str(ws / "data-demo"), ignore_errors=True)
    shutil.rmtree(str(ws / ".cos"), ignore_errors=True)

    for name in ("data", "config"):
        path = ws / name
        if not path.exists():
            continue
        if args.purge_data:
            shutil.rmtree(str(path))
        else:
            summary["preserved"].append(str(path))
    summary["data_purged"] = bool(args.purge_data)
    try:
        ws.rmdir()
        summary["workspace_removed"] = True
    except OSError:
        summary["workspace_removed"] = False
    summary["not_touched"] = [
        "Scheduled tasks in the ChatGPT desktop app",
        "Connectors, plugins and MCP servers in Codex (~/.codex/config.toml)",
        "Drafts or records already created in Gmail, the calendar, the CRM or Slack",
    ]
    if routines_note:
        summary["routines_note"] = routines_note
    return summary


# ---------------------------------------------------------------- output


def print_text(summary: Dict[str, Any]) -> None:
    command = summary["command"]
    out = []
    if command == "install":
        if summary["dry_run"]:
            out.append("DRY RUN. Nothing was changed.")
        label = {"fresh": "Installed", "upgrade": "Upgraded", "reinstall": "Checked"}[summary["mode"]]
        out.append("%s chief of staff %s in %s" % (label, summary["version"], summary["workspace"]))
        if summary["previous_version"] and summary["mode"] == "upgrade":
            out.append("  from version %s" % summary["previous_version"])
        counts = summary["files"]
        out.append("  files: %d added, %d updated, %d unchanged, %d removed"
                   % (counts["added"], counts["updated"], counts["unchanged"], counts["removed"]))
        if summary["mode"] == "reinstall" and not summary.get("changed", summary.get("would_change")):
            out.append("  Already up to date. Nothing to change.")
        for rel in summary["kept_your_version"]:
            out.append("  KEPT YOUR VERSION: %s (if the package changed it, the new one is beside it as %s.new)" % (rel, rel))
        for rel in summary["kept_removed_from_package"]:
            out.append("  KEPT: %s (no longer shipped, but you changed it)" % rel)
        if not summary["dry_run"]:
            out.append("  config: %s" % summary["config"])
            out.append("  data: %s" % summary["data"])
            if summary.get("backup"):
                out.append("  backup of the previous files: %s" % summary["backup"])
            agents = summary.get("agents_md", {})
            for warning in agents.get("warnings", []) or []:
                out.append("  NOTE: %s" % warning)
            if agents.get("error"):
                out.append("  AGENTS.md could not be generated: %s" % agents["error"])
            out.append("  health check: %s" % ("passed" if summary["healthy"] else "FAILED"))
            for item in summary["doctor_failures"]:
                out.append("    FAIL %s: %s" % (item["check"], item["detail"]))
            if summary["healthy"]:
                out.append("")
                out.append("Next: open %s in Codex and say: run cos-setup" % summary["workspace"])
                out.append("      (terminal: cd %s && codex)" % summary["workspace"])
    elif command == "status":
        if not summary["installed"]:
            out.append("Not installed in %s" % summary["workspace"])
        else:
            out.append("Chief of staff %s in %s" % (summary["version"], summary["workspace"]))
            out.append("  installed %s, last changed %s" % (summary["installed_at"], summary["updated_at"]))
            out.append("  managed files: %d" % summary["managed_files"])
            for rel in summary["modified_by_you"]:
                out.append("  modified by you: %s" % rel)
            for rel in summary["missing"]:
                out.append("  MISSING: %s" % rel)
            out.append("  backups available for rollback: %d" % len(summary["backups"]))
    elif command == "verify":
        out.append("Verify chief of staff %s in %s" % (summary["version"], summary["workspace"]))
        out.append("  [%s] managed files present" % ("PASS" if not summary["managed_files_missing"] else "FAIL"))
        for rel in summary["managed_files_missing"]:
            out.append("         missing: %s" % rel)
        out.append("  [%s] bin/cos doctor" % ("PASS" if summary["doctor_healthy"] else "FAIL"))
        for item in summary["doctor_failures"]:
            out.append("         %s: %s" % (item["check"], item["detail"]))
        discovery = summary["codex_discovery"]
        if discovery["status"] == "pass":
            out.append("  [PASS] Codex loads AGENTS.md and all %d skills" % discovery["skills_expected"])
        elif discovery["status"] == "fail":
            out.append("  [FAIL] Codex discovery: instructions loaded=%s, skills missing=%s"
                       % (discovery["instructions_loaded"], ", ".join(discovery["skills_missing"]) or "none"))
        else:
            out.append("  [SKIP] Codex discovery: %s" % discovery["detail"])
        for item in summary["doctor_warnings"]:
            out.append("  note: %s" % item["detail"])
        out.append("RESULT: %s" % ("PASSED" if summary["passed"] else "FAILED"))
    elif command == "rollback":
        if summary["dry_run"]:
            out.append("DRY RUN. Nothing was changed.")
        out.append("Rolled back %s -> %s in %s" % (summary["from_version"], summary["to_version"], summary["workspace"]))
        if not summary["dry_run"]:
            out.append("  files restored: %d, removed: %d" % (summary["restored"], summary["removed"]))
            for rel in summary["kept_your_version"]:
                out.append("  KEPT YOUR VERSION: %s" % rel)
            out.append("  data: %s" % summary["data"])
            out.append("  health check: %s" % ("passed" if summary["healthy"] else "FAILED"))
            for item in summary["doctor_failures"]:
                out.append("    FAIL %s: %s" % (item["check"], item["detail"]))
    elif command == "uninstall":
        if summary["dry_run"]:
            out.append("DRY RUN. Nothing was changed. Would remove %d files." % summary["would_remove"])
        else:
            out.append("Uninstalled chief of staff %s from %s" % (summary["version"], summary["workspace"]))
            out.append("  files removed: %d" % summary["removed"])
            for path in summary["preserved"]:
                out.append("  PRESERVED (yours): %s" % path)
            if summary["data_purged"]:
                out.append("  data and config were permanently deleted, as requested")
            out.append("  not touched: %s" % "; ".join(summary["not_touched"]))
            if summary.get("routines_note"):
                out.append("  NOTE: %s" % summary["routines_note"])
        for rel in summary["kept_modified_by_you"]:
            out.append("  KEPT (you changed it): %s" % rel)
    print("\n".join(out))


def main(argv: Optional[List[str]] = None) -> int:
    if sys.version_info < (3, 9):
        sys.stderr.write("Python 3.9 or newer is required (found %s). See INSTALL.md.\n" % sys.version.split()[0])
        return 1
    parser = argparse.ArgumentParser(prog="cos_install.py", description="Install or manage the chief-of-staff workspace.")
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    def common(name: str, help_text: str) -> argparse.ArgumentParser:
        item = sub.add_parser(name, help=help_text)
        item.add_argument("--workspace", help="workspace folder (default %s)" % DEFAULT_WORKSPACE)
        item.add_argument("--json", action="store_true", help="print a JSON summary")
        return item

    install = common("install", "install, or upgrade an existing installation")
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--force", action="store_true", help="fresh install only: back up and replace clashing files")
    install.add_argument("--keep-existing", action="store_true",
                         help="fresh install only: keep clashing files and save the packaged ones beside them as .new")
    install.add_argument("--replace-agents-md", action="store_true", help="back up and replace a foreign AGENTS.md")
    install.add_argument("--overwrite-modified", action="store_true",
                         help="replace managed files you changed (they are backed up first)")
    install.add_argument("--allow-downgrade", action="store_true")
    common("status", "show what is installed")
    verify = common("verify", "check the installation")
    verify.add_argument("--no-codex", action="store_true", help="skip the Codex discovery check")
    rollback = common("rollback", "return to the version before the last upgrade")
    rollback.add_argument("--dry-run", action="store_true")
    rollback.add_argument("--restore-data", action="store_true", help="also restore data and config from the backup")
    uninstall = common("uninstall", "remove the package, keeping your data")
    uninstall.add_argument("--dry-run", action="store_true")
    uninstall.add_argument("--force", action="store_true", help="also remove managed files you changed")
    uninstall.add_argument("--purge-data", action="store_true", help="also delete data/ and config/")
    uninstall.add_argument("--yes", action="store_true")

    args = parser.parse_args(argv)
    handlers = {"install": cmd_install, "status": cmd_status, "verify": cmd_verify, "rollback": cmd_rollback,
                "uninstall": cmd_uninstall}
    try:
        summary = handlers[args.command](args)
    except InstallError as exc:
        if args.json:
            print(json.dumps({"command": args.command, "ok": False, "error": exc.message}, indent=2))
        else:
            sys.stderr.write("ERROR: %s\n" % exc.message)
        return exc.code
    if args.json:
        print(json.dumps(dict(summary, ok=True), indent=2))
    else:
        print_text(summary)
    if args.command == "verify" and not summary["passed"]:
        return 1
    if args.command in ("install", "rollback") and not summary.get("dry_run") and not summary.get("healthy", True):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

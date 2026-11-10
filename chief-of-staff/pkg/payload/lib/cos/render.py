"""Render AGENTS.md from the packaged core instructions plus the user's own rules.

AGENTS.md is a generated file. The inputs are:
  core/AGENTS.core.md               package-managed, replaced on upgrade
  config/cos.config.json            user-owned profile and settings
  data/instructions/rules.json      user-owned learned rules (versioned)
  data/instructions/custom.md       user-owned free-form instructions

A hand-edited AGENTS.md is never silently overwritten: it is backed up first
and the backup path is reported.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Dict

from . import config, feedback, store

MAX_BYTES = 32 * 1024  # Codex stops reading project instructions at 32 KiB by default.
WARN_BYTES = 28 * 1024
CUSTOM_HEADER = (
    "<!-- Your own standing instructions. Plain text or Markdown. This file is yours: upgrades never touch it.\n"
    "     Run `bin/cos render` after editing. Lines inside HTML comments are ignored. -->\n"
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def package_version() -> str:
    path = store.root() / "core" / "VERSION"
    return path.read_text(encoding="utf-8").strip() if path.exists() else "unknown"


def demo_mode() -> bool:
    return store.data_dir() != (store.root() / "data").resolve()


def _custom_text() -> str:
    path = store.data_dir() / "instructions" / "custom.md"
    if not path.exists():
        store.atomic_write(path, CUSTOM_HEADER)
        return ""
    lines, in_comment = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if "<!--" in line:
            in_comment = True
        if not in_comment:
            lines.append(line)
        if "-->" in line:
            in_comment = False
    return "\n".join(lines).strip()


def build(cfg: Dict[str, Any]) -> str:
    template = (store.root() / "core" / "AGENTS.core.md").read_text(encoding="utf-8")
    profile = cfg["profile"]
    rules_state = feedback.rules_state()
    if rules_state["active"]:
        learned = "\n".join(
            "- [%s, %s] %s (why: %s)" % (rule["id"], rule["kind"], rule["text"], rule["reason"])
            for rule in rules_state["active"]
        )
    else:
        learned = "None yet."
    custom = _custom_text() or "None."
    hours = cfg["working_hours"]
    perms = cfg["permissions"]
    values = {
        "PACKAGE_VERSION": package_version(),
        "INSTRUCTIONS_VERSION": str(rules_state["instructions_version"]),
        "NAME": profile["name"],
        "ROLE": profile["role"],
        "COMPANY": profile["company"],
        "CITY": profile["city"],
        "LANGUAGE": profile["language"],
        "TIMEZONE": cfg["timezone"],
        "WORKING_HOURS": "%s to %s, %s" % (hours["start"], hours["end"], ", ".join(hours["days"])),
        "BUFFER_MINUTES": str(cfg["scheduling"]["buffer_minutes"]),
        "NO_APPROVAL": ", ".join(perms["no_approval"]),
        "APPROVAL_REQUIRED": ", ".join(perms["approval_required"]),
        "NEVER": ", ".join(perms["never"]),
        "LEARNED_RULES": learned,
        "CUSTOM_INSTRUCTIONS": custom,
    }
    text = template
    for key, value in values.items():
        text = text.replace("{{%s}}" % key, value)
    return text


def render(force_demo: bool = False) -> Dict[str, Any]:
    if demo_mode() and not force_demo:
        return {"rendered": False, "reason": "demo data is active, so AGENTS.md was left unchanged"}
    cfg = config.load()
    text = build(cfg)
    root = store.root()
    target = root / "AGENTS.md"
    state_path = root / ".cos" / "render.json"
    previous_hash = None
    if state_path.exists():
        try:
            previous_hash = json.loads(state_path.read_text(encoding="utf-8")).get("sha256")
        except ValueError:
            previous_hash = None
    result: Dict[str, Any] = {"rendered": True, "path": str(target), "bytes": len(text.encode("utf-8")), "warnings": []}
    if target.exists():
        current = target.read_text(encoding="utf-8")
        if _sha(current) == _sha(text):
            result["changed"] = False
        elif previous_hash != _sha(current):
            backup_dir = root / ".cos" / "backups" / "agents-md"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / ("AGENTS.%s.md" % store.now_iso().replace(":", ""))
            shutil.copyfile(str(target), str(backup))
            result["backed_up_hand_edited_copy"] = str(backup)
            result["warnings"].append(
                "AGENTS.md had been edited by hand. Your copy was saved to %s and the file was regenerated. "
                "Put standing instructions in data/instructions/custom.md so they survive." % backup
            )
    if result["bytes"] > MAX_BYTES:
        raise store.CosError(
            "AGENTS.md would be %d bytes, over the 32 KiB Codex limit. Shorten data/instructions/custom.md "
            "or revert some learned rules." % result["bytes"],
            store.EXIT_VALIDATION,
        )
    if result["bytes"] > WARN_BYTES:
        result["warnings"].append("AGENTS.md is close to the 32 KiB Codex limit (%d bytes)." % result["bytes"])
    if result.get("changed") is not False:
        store.atomic_write(target, text)
        result["changed"] = True
    if previous_hash != _sha(text):
        # Only touch the record when the content changed, so a repeat install is a true no-op.
        store.atomic_write(state_path, json.dumps({"sha256": _sha(text), "rendered_at": store.now_iso()}, indent=2) + "\n")
    return result


def status() -> Dict[str, Any]:
    root = store.root()
    target = root / "AGENTS.md"
    state_path = root / ".cos" / "render.json"
    if not target.exists():
        return {"exists": False, "in_sync": False}
    current = target.read_text(encoding="utf-8")
    recorded = None
    if state_path.exists():
        try:
            recorded = json.loads(state_path.read_text(encoding="utf-8")).get("sha256")
        except ValueError:
            recorded = None
    expected = build(config.load()) if not demo_mode() else None
    return {
        "exists": True,
        "bytes": len(current.encode("utf-8")),
        "hand_edited": recorded != _sha(current),
        "in_sync": expected is None or _sha(expected) == _sha(current),
    }

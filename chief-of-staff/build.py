#!/usr/bin/env python3
"""Build the release ZIP for the chief-of-staff Codex package.

Usage: python3 build.py [--out DIR]

Copies pkg/ into a staging folder, writes manifest.json (every file with its
SHA-256), and zips it under one top-level folder. The archive is reproducible:
sorted entries and fixed timestamps.
"""
import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE / "pkg"
PACKAGE = "chief-of-staff-codex"
FIXED_TIME = (2026, 11, 10, 0, 0, 0)
EXECUTABLE = {"install.sh", "verify.sh", "rollback.sh", "uninstall.sh", "run_all.sh", "walkthrough.sh", "cos",
              "cos_install.py"}
SKIP_NAMES = {".DS_Store", "manifest.json"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files():
    for path in sorted(PKG.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.name not in SKIP_NAMES \
                and not path.name.endswith((".pyc", ".bak", ".tmp")):
            yield path


def build(out_dir: Path) -> Path:
    version = (PKG / "VERSION").read_text().strip()
    core_version = (PKG / "payload" / "core" / "VERSION").read_text().strip()
    if version != core_version:
        sys.exit("VERSION (%s) and payload/core/VERSION (%s) differ" % (version, core_version))
    top = "%s-%s" % (PACKAGE, version)
    stage_root = Path(tempfile.mkdtemp(prefix="cos-build-"))
    stage = stage_root / top
    files = {}
    for path in source_files():
        rel = path.relative_to(PKG).as_posix()
        target = stage / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(path), str(target))
        files[rel] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    manifest = {
        "package": PACKAGE,
        "version": version,
        "target": {"runtime": "Codex (Codex CLI, Codex in the ChatGPT desktop app)", "os": "macOS"},
        "install": {"mechanism": "workspace folder with AGENTS.md and .agents/skills", "default_workspace": "~/ChiefOfStaff",
                    "command": "bash install.sh"},
        "requires": {"python": ">=3.9", "third_party_packages": [], "codex": "CLI or ChatGPT desktop app"},
        "payload_mapping": {"payload/skills/*": ".agents/skills/*", "payload/*": "*", "root documents": "docs/*"},
        "file_count": len(files),
        "files": files,
    }
    (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / ("%s.zip" % top)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(stage.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo("%s/%s" % (top, path.relative_to(stage).as_posix()), date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if path.name in EXECUTABLE else 0o644
            info.external_attr = (0o100000 | mode) << 16
            info.create_system = 3  # Unix, so permissions survive extraction
            archive.writestr(info, path.read_bytes())
    digest = sha256(zip_path)
    (out_dir / (zip_path.name + ".sha256")).write_text("%s  %s\n" % (digest, zip_path.name))
    shutil.rmtree(str(stage_root), ignore_errors=True)
    print("built %s" % zip_path)
    print("  version %s, %d files + manifest.json, %d bytes" % (version, len(files), zip_path.stat().st_size))
    print("  sha256 %s" % digest)
    return zip_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(HERE / "release"))
    build(Path(parser.parse_args().out))

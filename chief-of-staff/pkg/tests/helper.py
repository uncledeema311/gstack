"""Shared test helpers. Every CLI call runs in a separate process, so each
assertion about stored state is also a check that it survives a restart."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
INSTALLER = PKG / "installer" / "cos_install.py"
HAS_MANIFEST = (PKG / "manifest.json").exists()
NOW = "2026-11-12T00:50:00Z"  # Thursday 12 Nov 2026, 11:50 in Melbourne (AEDT, +11:00)


def base_env(extra=None):
    env = dict(os.environ)
    for key in ("COS_ROOT", "COS_DATA_DIR", "COS_CONFIG", "COS_WORKSPACE", "COS_NOW"):
        env.pop(key, None)
    if not HAS_MANIFEST:
        env["COS_ALLOW_NO_MANIFEST"] = "1"
    env.update(extra or {})
    return env


def run(cmd, cwd=None, env=None):
    proc = subprocess.run([str(item) for item in cmd], cwd=str(cwd) if cwd else None, env=env or base_env(),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return proc.returncode, proc.stdout, proc.stderr


def installer(command, workspace, *flags, pkg=PKG, env=None):
    code, out, err = run([sys.executable, pkg / "installer" / "cos_install.py", command, "--workspace", workspace, "--json"]
                         + list(flags), env=env or base_env())
    try:
        return code, json.loads(out)
    except ValueError:
        return code, {"ok": False, "error": out + err}


class Workspace:
    """A freshly installed workspace in a temporary folder."""

    def __init__(self, pkg=PKG):
        self.tmp = Path(tempfile.mkdtemp(prefix="cos-test-"))
        self.path = self.tmp / "ChiefOfStaff"
        code, summary = installer("install", self.path, pkg=pkg)
        if code != 0:
            raise AssertionError("install failed: %s" % summary)
        self.now = NOW

    def cos(self, *args, now=None, demo=False):
        env = base_env({"COS_NOW": now or self.now})
        cmd = [sys.executable, self.path / "bin" / "cos"] + (["--demo"] if demo else []) + list(args)
        code, out, err = run(cmd, cwd=self.path, env=env)
        try:
            return code, json.loads(out)
        except ValueError:
            return code, {"ok": False, "error": out + err}

    def ok(self, *args, **kwargs):
        code, data = self.cos(*args, **kwargs)
        if code != 0:
            raise AssertionError("cos %s failed (%s): %s" % (" ".join(args), code, data.get("error")))
        return data

    def cleanup(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)


class WorkspaceCase(unittest.TestCase):
    """One fresh workspace per test."""

    def setUp(self):
        self.ws = Workspace()
        self.addCleanup(self.ws.cleanup)

    def task(self, company="Kestrel Ridge Minerals", action="Send pricing summary", **extra):
        args = ["task", "add", "--company", company, "--action", action, "--source-type", "transcript",
                "--source-ref", "fathom:recording:demo-rec-7001", "--priority", "high", "--rationale", "Asked for it"]
        for key, value in extra.items():
            flag = "--" + key.replace("_", "-")
            args += [flag] if value is True else [flag, str(value)]
        return self.ws.cos(*args)

"""Delivery tests for the real report-bug skill/command, not model behavior."""

import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "bug_installer", ROOT / "skills/mis-proj-op-update/scripts/update.py"
)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)
SKILL = Path("skills/mis-proj-op-report-bug/SKILL.md")
COMMAND = Path("commands/opencode/mis-bug.md")


class BugPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mis-bug-", dir="/tmp/opencode")
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "source"
        self.project = Path(self.tmp.name) / "consumer"
        self.project.mkdir()
        for directory in ("skills", "commands"):
            shutil.copytree(ROOT / directory, self.source / directory)
        self.git("init", "-q")
        self.target = self.commit()

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.source), *args], text=True
        ).strip()

    def commit(self):
        self.git("add", ".")
        self.git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "package fixture",
        )
        return self.git("rev-parse", "HEAD")

    def check_payload(self):
        for source, destination in (
            (SKILL, SKILL),
            (COMMAND, Path("commands/mis-bug.md")),
        ):
            self.assertEqual(
                (self.project / ".opencode" / destination).read_bytes(),
                (ROOT / source).read_bytes(),
            )
        self.assertIn("name: mis-proj-op-report-bug", (ROOT / SKILL).read_text())
        self.assertIn("`mis-proj-op-report-bug`", (ROOT / COMMAND).read_text())
        self.assertEqual((ROOT / COMMAND).read_text().count("$ARGUMENTS"), 1)
        self.assertFalse((self.project / ".beads").exists())

    def test_fresh_install_exact_payload_and_noop(self):
        installer.update(
            self.project, self.source, self.target, install=True, apply=True
        )
        self.check_payload()
        self.assertEqual(
            installer.update(self.project, self.source, self.target, install=True)[1],
            [],
        )

    def test_update_addition_conflict_preflight_apply_and_noop(self):
        self.git("rm", str(SKILL), str(COMMAND))
        baseline = self.commit()
        installer.update(self.project, self.source, baseline, install=True, apply=True)
        installer.update(self.project, self.source, self.target)
        destination = self.project / ".opencode/commands/mis-bug.md"
        self.assertFalse(destination.exists())
        destination.write_text("user command")
        with self.assertRaisesRegex(ValueError, "conflicting addition"):
            installer.update(self.project, self.source, self.target, apply=True)
        self.assertEqual(destination.read_text(), "user command")
        self.assertFalse((self.project / ".opencode" / SKILL).exists())
        destination.unlink()
        installer.update(self.project, self.source, self.target, apply=True)
        self.check_payload()
        self.assertEqual(
            installer.update(self.project, self.source, self.target)[1], []
        )

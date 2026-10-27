"""Real Git-object update fixtures; no network, service or tracker writes."""

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "updater", ROOT / "skills/mis-proj-op-update/scripts/update.py"
)
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(
            prefix="mis-update-", dir="/tmp/opencode"
        )
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "source"
        self.project = Path(self.tmp.name) / "consumer"
        self.source.mkdir()
        self.project.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "MIS test")
        self.git("config", "user.email", "mis@example.invalid")
        self.write("skills/LICENSE-RIS", "license")
        self.write("skills/mis-example/SKILL.md", "old skill")
        self.write("skills/mis-example/references/old.md", "obsolete")
        self.write("commands/opencode/mis-plan.md", "old command")
        self.old = self.commit()
        for path, content in updater.snapshot(self.source, self.old).items():
            destination = self.project / ".opencode" / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        self.write("skills/mis-example/SKILL.md", "new skill")
        (self.source / "skills/mis-example/references/old.md").unlink()
        self.write("skills/mis-added/SKILL.md", "added skill")
        self.write("commands/opencode/mis-update.md", "new command")
        self.new = self.commit()

    def git(self, *args):
        return (
            subprocess.run(
                ["git", "-C", str(self.source), *args],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            .stdout.decode()
            .strip()
        )

    def write(self, path, content):
        destination = self.source / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def contents(self):
        return {
            str(p.relative_to(self.project)): p.read_bytes()
            for p in self.project.rglob("*")
            if p.is_file()
        }

    def update(self, **kwargs):
        return updater.update(
            self.project, self.source, self.new, from_revision=self.old, **kwargs
        )

    def test_preflight_apply_retry_and_unrelated_preservation(self):
        unrelated = self.project / ".opencode/skills/phaser/SKILL.md"
        unrelated.parent.mkdir()
        unrelated.write_text("independent")
        before = self.contents()
        baseline, changes = self.update()
        self.assertEqual(baseline, self.old)
        self.assertIn(("skills/mis-example/references/old.md", "delete"), changes)
        self.assertEqual(before, self.contents())
        # Source WIP is not installed: only exact committed objects are used.
        self.write("skills/mis-example/SKILL.md", "uncommitted source")
        self.update(apply=True)
        self.assertEqual(unrelated.read_text(), "independent")
        for path, content in updater.snapshot(self.source, self.new).items():
            self.assertEqual((self.project / ".opencode" / path).read_bytes(), content)
        self.assertFalse(
            (self.project / ".opencode/skills/mis-example/references/old.md").exists()
        )
        after = self.contents()
        self.assertEqual(updater.update(self.project, self.source, self.new)[1], [])
        updater.update(self.project, self.source, self.new, apply=True)
        self.assertEqual(after, self.contents())

    def test_modified_obsolete_file_refuses_entire_update(self):
        path = self.project / ".opencode/skills/mis-example/references/old.md"
        path.write_text("local edits")
        before = self.contents()
        with self.assertRaisesRegex(ValueError, "Local modification"):
            self.update(apply=True)
        self.assertEqual(before, self.contents())

    def test_missing_baseline_refuses(self):
        (self.project / ".opencode/skills/mis-example/SKILL.md").unlink()
        before = self.contents()
        with self.assertRaisesRegex(ValueError, "Local modification|Missing baseline"):
            self.update(apply=True)
        self.assertEqual(before, self.contents())

    def test_unknown_resource_and_conflicting_addition_refuse(self):
        for relative in ("skills/mis-example/local.md", "commands/mis-update.md"):
            with self.subTest(relative=relative):
                path = self.project / ".opencode" / relative
                path.write_text("local")
                before = self.contents()
                with self.assertRaises(ValueError):
                    self.update(apply=True)
                self.assertEqual(before, self.contents())
                path.unlink()

    def test_symlink_parent_file_and_upstream_symlink_refuse(self):
        skill = self.project / ".opencode/skills/mis-added"
        skill.symlink_to(self.source / "skills/mis-added", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.update(apply=True)
        skill.unlink()
        skill.write_text("not a directory")
        with self.assertRaisesRegex(ValueError, "Not a directory"):
            self.update(apply=True)
        skill.unlink()
        (self.source / "skills/mis-added/SKILL.md").unlink()
        (self.source / "skills/mis-added/SKILL.md").symlink_to("../../LICENSE-RIS")
        self.new = self.commit()
        with self.assertRaisesRegex(ValueError, "Unsafe upstream"):
            self.update(apply=True)

    def test_missing_invalid_and_disagreeing_record_refuse(self):
        with self.assertRaisesRegex(ValueError, "Missing installation record"):
            updater.update(self.project, self.source, self.new)
        record = self.project / ".opencode/mis-installation"
        record.write_text("format=999\n")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            self.update(apply=True)
        record.unlink()
        self.update(apply=True)
        with self.assertRaisesRegex(ValueError, "disagrees"):
            self.update(apply=True)

    def test_legacy_record_and_partial_target_retry(self):
        record = self.project / ".opencode/mis-installation"
        record.write_text(
            f"format=1\nsource={updater.SOURCE}\nrevision={self.old}\nharness=opencode\n\nLegacy prose\n"
        )
        (self.project / ".opencode/skills/mis-example/SKILL.md").write_text("new skill")
        self.update(apply=True)
        self.assertIn(self.new, record.read_text())

    def test_bad_revision_and_source_consumer_refuse(self):
        for revision in ("HEAD", "--help", self.new[:8], "0" * 40):
            with (
                self.subTest(revision=revision),
                self.assertRaises((ValueError, subprocess.CalledProcessError)),
            ):
                updater.update(self.project, self.source, revision, self.old, True)
        with self.assertRaises(ValueError):
            updater.update(self.source, self.source, self.new, self.old, True)

    def test_hardlinked_payload_and_record_refuse_before_any_write(self):
        for relative in ("skills/mis-example/SKILL.md", "mis-installation"):
            with self.subTest(relative=relative):
                managed = self.project / ".opencode" / relative
                if relative == "mis-installation":
                    managed.write_text(
                        f"format=1\nsource={updater.SOURCE}\nrevision={self.old}\nharness=opencode\n"
                    )
                unrelated = self.project / ("unrelated-" + managed.name)
                os.link(managed, unrelated)
                try:
                    before = self.contents()
                    with self.assertRaisesRegex(ValueError, "hard link"):
                        self.update(apply=True)
                    self.assertEqual(before, self.contents())
                finally:
                    unrelated.unlink()

    def test_executable_upstream_payload_refuses(self):
        (self.source / "skills/mis-added/SKILL.md").chmod(0o755)
        self.new = self.commit()
        with self.assertRaisesRegex(ValueError, "Unsafe upstream"):
            self.update(apply=True)


if __name__ == "__main__":
    unittest.main()

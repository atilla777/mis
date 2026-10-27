"""First-install mode shares the exact snapshot/preflight engine with update."""

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "installer", ROOT / "skills/mis-proj-op-update/scripts/update.py"
)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(
            prefix="mis-install-", dir="/tmp/opencode"
        )
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "source"
        self.project = Path(self.tmp.name) / "consumer"
        self.source.mkdir()
        self.project.mkdir()
        for name, text in {
            "skills/LICENSE-RIS": "license",
            "skills/mis-example/SKILL.md": "skill",
            "commands/opencode/mis-plan.md": "command",
        }.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        for args in [
            ("init", "-q"),
            ("add", "."),
            (
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ),
        ]:
            subprocess.run(["git", "-C", str(self.source), *args], check=True)
        self.rev = subprocess.check_output(
            ["git", "-C", str(self.source), "rev-parse", "HEAD"], text=True
        ).strip()

    def install(self, **kwargs):
        return installer.update(
            self.project, self.source, self.rev, install=True, **kwargs
        )

    def contents(self):
        return {
            str(p.relative_to(self.project)): p.read_bytes()
            for p in self.project.rglob("*")
            if p.is_file()
        }

    def test_preflight_apply_record_retry_and_source_wip(self):
        (self.project / "AGENTS.md").write_text("user instructions")
        before = self.contents()
        self.assertIsNone(self.install()[0])
        self.assertEqual(before, self.contents())
        (self.source / "skills/mis-example/SKILL.md").write_text("uncommitted")
        self.install(apply=True)
        self.assertEqual(
            (self.project / ".opencode/skills/mis-example/SKILL.md").read_text(),
            "skill",
        )
        self.assertIn(
            self.rev, (self.project / ".opencode/mis-installation").read_text()
        )
        self.assertEqual((self.project / "AGENTS.md").read_text(), "user instructions")
        self.assertEqual(self.install()[1], [])
        self.assertFalse((self.project / ".beads").exists())

    def test_conflict_and_unknown_resource_refuse_before_writes(self):
        for relative in ["commands/mis-plan.md", "skills/mis-example/local.md"]:
            with self.subTest(relative=relative):
                path = self.project / ".opencode" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("user")
                before = self.contents()
                with self.assertRaises(ValueError):
                    self.install(apply=True)
                self.assertEqual(before, self.contents())
                path.unlink()

    def test_links_are_rejected(self):
        target = self.project / ".opencode"
        target.symlink_to(self.source, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.install(apply=True)
        target.unlink()
        path = target / "skills/mis-example/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("skill")
        os.link(path, self.project / "foreign")
        with self.assertRaisesRegex(ValueError, "hard link"):
            self.install(apply=True)

    def test_existing_other_revision_and_baseline_flags_refuse(self):
        self.install(apply=True)
        with self.assertRaisesRegex(ValueError, "does not accept"):
            self.install(from_revision=self.rev, apply=True)
        record = self.project / ".opencode/mis-installation"
        record.write_text(record.read_text().replace(self.rev, "0" * 40))
        before = self.contents()
        with self.assertRaisesRegex(ValueError, "use update"):
            self.install(apply=True)
        self.assertEqual(before, self.contents())

    def test_partial_retry_accepts_only_identical_target(self):
        path = self.project / ".opencode/skills/mis-example/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("skill")
        self.install(apply=True)
        self.assertEqual(self.install()[1], [])

    def test_external_wrapper_matches_engine(self):
        result = subprocess.run(
            [
                "python3",
                "-B",
                str(ROOT / "scripts/install.py"),
                str(self.project),
                "--revision",
                subprocess.check_output(
                    ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
                ).strip(),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("preflight only", result.stdout)
        self.assertEqual(self.contents(), {})


if __name__ == "__main__":
    unittest.main()

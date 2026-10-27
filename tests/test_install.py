"""Installer checks; no OpenCode service or Beads needed."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer", ROOT / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def test_install_and_retry(self):
        with tempfile.TemporaryDirectory(
            prefix="mis-install-", dir="/tmp/opencode"
        ) as tmp:
            project = Path(tmp)
            unrelated = project / ".opencode/commands/user.md"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text("Keep me")
            count = installer.install(project)
            before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
            self.assertEqual(installer.install(project), count)
            self.assertEqual(
                before, {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
            )
            self.assertEqual(len(list(project.glob(".opencode/skills/*/SKILL.md"))), 13)
            self.assertEqual(unrelated.read_text(), "Keep me")
            self.assertEqual(
                (project / ".opencode/skills/LICENSE-RIS").read_bytes(),
                (ROOT / "skills/LICENSE-RIS").read_bytes(),
            )
            for name in ("mis-plan", "mis-run", "mis-status", "mis-update"):
                self.assertEqual(
                    (project / f".opencode/commands/{name}.md").read_bytes(),
                    (ROOT / f"commands/opencode/{name}.md").read_bytes(),
                )
            self.assertFalse(list(project.rglob("ris-*")))
            for source in (ROOT / "skills").rglob("*"):
                if source.is_file():
                    self.assertEqual(
                        (
                            project
                            / ".opencode/skills"
                            / source.relative_to(ROOT / "skills")
                        ).read_bytes(),
                        source.read_bytes(),
                    )

    def test_conflict_is_not_overwritten_or_partially_installed(self):
        with tempfile.TemporaryDirectory(
            prefix="mis-install-", dir="/tmp/opencode"
        ) as tmp:
            project = Path(tmp)
            conflict = project / ".opencode/commands/mis-run.md"
            conflict.parent.mkdir(parents=True)
            conflict.write_text("User content")
            with self.assertRaisesRegex(ValueError, "Conflicting file"):
                installer.install(project)
            self.assertEqual(conflict.read_text(), "User content")
            self.assertFalse((project / ".opencode/skills").exists())

    def test_symlink_and_source_are_rejected(self):
        with tempfile.TemporaryDirectory(
            prefix="mis-install-", dir="/tmp/opencode"
        ) as tmp:
            project = Path(tmp)
            (project / ".opencode").symlink_to(ROOT, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                installer.install(project)
        with self.assertRaises(ValueError):
            installer.install(ROOT)

    def test_non_directory_parent_is_rejected(self):
        with tempfile.TemporaryDirectory(
            prefix="mis-install-", dir="/tmp/opencode"
        ) as tmp:
            project = Path(tmp)
            (project / ".opencode").write_text("User file")
            with self.assertRaisesRegex(ValueError, "Not a directory"):
                installer.install(project)
            self.assertEqual((project / ".opencode").read_text(), "User file")


if __name__ == "__main__":
    unittest.main()

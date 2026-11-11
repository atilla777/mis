"""Bootstrap tests: isolated HOME and fake Go, no user installation/network/model."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]


class DispatcherInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(
            prefix="mis-dispatcher-install-", dir="/tmp/opencode"
        )
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "source"
        self.repo.mkdir()
        self.env = dict(os.environ, HOME=str(self.root / "home"))
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        for path in ["scripts/install-dispatcher.py", "go.mod", "go.sum"]:
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((SOURCE / path).read_bytes())
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.sha = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("remote", "add", "origin", "https://github.com/atilla777/mis")
        self.git("update-ref", "refs/remotes/origin/main", self.sha)
        tools = self.root / "tools"
        tools.mkdir()
        go = tools / "go"
        go.write_text(
            "#!/usr/bin/env python3\nimport sys, pathlib, os\n"
            "if os.getenv('FAKE_GO_FAIL'): sys.exit(2)\n"
            "if sys.argv[1]=='build': pathlib.Path(sys.argv[sys.argv.index('-o')+1]).write_bytes(b'test binary')\n"
        )
        go.chmod(0o755)
        self.env["PATH"] = str(tools) + os.pathsep + os.environ["PATH"]
        self.binary = Path(self.env["HOME"]) / ".local/bin/mis-dispatcher"

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            text=True,
            capture_output=True,
            env=self.env,
            check=True,
        )

    def bootstrap(self, revision=None):
        return subprocess.run(
            [
                "python3",
                str(self.repo / "scripts/install-dispatcher.py"),
                revision or self.sha,
            ],
            env=self.env,
            text=True,
            capture_output=True,
        )

    def test_repeat_install_preserves_config_and_uses_git_snapshot(self):
        config = Path(self.env["HOME"]) / ".config/mis/dispatcher.yaml"
        config.parent.mkdir(parents=True)
        config.write_text("scheduler: {max_open_tasks: 2}\n")
        (self.repo / "go.mod").write_text("uncommitted broken source")
        for _ in range(2):
            result = self.bootstrap()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.binary.read_bytes(), b"test binary")
            self.assertEqual(self.binary.stat().st_mode & 0o777, 0o755)
            self.assertEqual(config.read_text(), "scheduler: {max_open_tasks: 2}\n")
            self.assertEqual(list(self.binary.parent.glob(".mis-dispatcher-*")), [])

    def test_build_failure_preserves_old_binary(self):
        self.binary.parent.mkdir(parents=True)
        self.binary.write_bytes(b"old")
        self.env["FAKE_GO_FAIL"] = "1"
        self.assertNotEqual(self.bootstrap().returncode, 0)
        self.assertEqual(self.binary.read_bytes(), b"old")

    def test_unsafe_destination_and_untrusted_source_refuse(self):
        self.binary.parent.mkdir(parents=True)
        other = self.root / "other"
        other.write_bytes(b"untouched")
        self.binary.symlink_to(other)
        self.assertNotEqual(self.bootstrap().returncode, 0)
        self.assertEqual(other.read_bytes(), b"untouched")
        self.binary.unlink()
        self.git("remote", "set-url", "origin", "https://example.invalid/mis")
        self.assertNotEqual(self.bootstrap().returncode, 0)
        self.assertFalse(self.binary.exists())

    def test_pinned_script_and_full_sha_required(self):
        self.assertNotEqual(self.bootstrap("main").returncode, 0)
        with (self.repo / "scripts/install-dispatcher.py").open("a") as output:
            output.write("\n# changed bootstrap\n")
        self.assertNotEqual(self.bootstrap().returncode, 0)
        self.assertFalse(self.binary.exists())


if __name__ == "__main__":
    unittest.main()

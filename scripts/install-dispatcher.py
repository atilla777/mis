"""Build/install only the global binary from a reviewed, pinned MIS Git snapshot.

Usage: python3 scripts/install-dispatcher.py FULL_COMMIT_SHA
Caller verifies/fetches trusted upstream first. No fetch, sudo or project updates.
"""

import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile


SOURCE = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", "-C", str(SOURCE), *args])


def install(revision):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("expected a reviewed full 40-character commit SHA")
    origin = git("remote", "get-url", "origin").decode().strip()
    if origin not in (
        "https://github.com/atilla777/mis",
        "https://github.com/atilla777/mis.git",
        "git@github.com:atilla777/mis.git",
    ):
        raise ValueError("source origin is not trusted atilla777/mis")
    subprocess.run(
        [
            "git",
            "-C",
            str(SOURCE),
            "merge-base",
            "--is-ancestor",
            revision,
            "refs/remotes/origin/main",
        ],
        check=True,
    )
    if (
        git("show", f"{revision}:scripts/install-dispatcher.py")
        != Path(__file__).read_bytes()
    ):
        raise ValueError(
            "bootstrap differs from pinned source; use the reviewed script"
        )
    go = shutil.which("go")
    if not go:
        raise ValueError(
            "Go 1.25+ is required; install it yourself, no system packages are installed"
        )
    destination = Path.home() / ".local/bin/mis-dispatcher"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise ValueError("refusing symlink destination")
    if destination.exists():
        info = destination.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("destination must be a regular non-hardlinked file")
    # Read only Git blobs, never uncommitted Go sources, hooks or build wrappers.
    temp_root = "/tmp/opencode" if Path("/tmp/opencode").is_dir() else None
    with tempfile.TemporaryDirectory(
        prefix="mis-dispatcher-build-", dir=temp_root
    ) as directory:
        build = Path(directory)
        records = git(
            "ls-tree",
            "-rz",
            revision,
            "--",
            "go.mod",
            "go.sum",
            "cmd/mis-dispatcher",
            "internal/dispatcher",
        ).split(b"\0")
        for record in filter(None, records):
            header, raw_path = record.split(b"\t", 1)
            mode, kind, blob = header.decode().split()
            path = Path(raw_path.decode())
            if (
                mode != "100644"
                or kind != "blob"
                or path.is_absolute()
                or ".." in path.parts
            ):
                raise ValueError(f"unsafe source entry: {path}")
            target = build / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git("cat-file", "blob", blob))
        env = dict(
            os.environ, GOTOOLCHAIN="local", GOWORK="off", GOFLAGS="", CGO_ENABLED="0"
        )
        subprocess.run(
            [go, "test", "-mod=readonly", "./internal/dispatcher"],
            cwd=build,
            env=env,
            check=True,
        )
        binary = build / "mis-dispatcher"
        subprocess.run(
            [
                go,
                "build",
                "-mod=readonly",
                "-trimpath",
                "-o",
                str(binary),
                "./cmd/mis-dispatcher",
            ],
            cwd=build,
            env=env,
            check=True,
        )
        fd, staged = tempfile.mkstemp(prefix=".mis-dispatcher-", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as output, binary.open("rb") as source:
                shutil.copyfileobj(source, output)
                output.flush()
                os.fchmod(output.fileno(), 0o755)
                os.fsync(output.fileno())
            os.replace(staged, destination)
            directory_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(staged):
                os.unlink(staged)
    print(f"Installed {destination} from {revision}. Configuration unchanged.")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError(
                "usage: python3 scripts/install-dispatcher.py FULL_COMMIT_SHA"
            )
        install(sys.argv[1])
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"install-dispatcher: {error}")

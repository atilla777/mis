"""Real CLI status contract, no models, consumer projects or global installation.

Usage: python3 -B tests/status_cli_smoke.py /absolute/path/to/mis-dispatcher
Fresh fixture retained under /tmp/opencode (or explicit TMPDIR).
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


BINARY = str(Path(sys.argv[1]).resolve())
ROOT = Path(
    tempfile.mkdtemp(
        prefix="mis-status-", dir=os.environ.get("TMPDIR", "/tmp/opencode")
    )
)
PROJECT = ROOT / "consumer"
PROJECT.mkdir()
ENV = {k: v for k, v in os.environ.items() if not k.startswith(("BEADS_", "BD_"))}
ENV.update(BD_NON_INTERACTIVE="1", BD_LAST_TOUCHED_FALLBACK="0")


def run(*args, cwd=PROJECT, ok=True):
    result = subprocess.run(
        args, cwd=cwd, env=ENV, text=True, capture_output=True, timeout=60
    )
    if ok and result.returncode:
        raise AssertionError((args, result.returncode, result.stdout, result.stderr))
    return result


def bd(*args, write=False):
    return json.loads(
        run("bd", "--sandbox" if write else "--readonly", "--json", *args).stdout
    )


def create(kind, title, parent=None):
    args = [
        "create",
        "--type",
        kind,
        "--title",
        title,
        "--description",
        "Disposable status test",
    ]
    if parent:
        args += ["--parent", parent]
    return bd(*args, write=True)["id"]


print(f"Fixture: {ROOT}", flush=True)
run("git", "init", "-b", "main")
run(
    "git",
    "-c",
    "user.name=MIS test",
    "-c",
    "user.email=mis@example.invalid",
    "commit",
    "--allow-empty",
    "-m",
    "fixture",
)
run(
    "bd",
    "init",
    "--prefix",
    "status",
    "--non-interactive",
    "--skip-agents",
    "--skip-hooks",
)
epic = create("epic", "Milestone")
task = create("task", "Child", epic)
done = create("task", "Hidden closed child", epic)
bug = create("bug", "Standalone bug")
bd("close", done, write=True)
bd("dep", "add", task, bug, "--type", "blocks", write=True)
bd("update", bug, "--status", "in_progress", write=True)
# These deliberately broken scheduler configs must never be read by --status.
(PROJECT / ".mis").mkdir()
(PROJECT / ".mis/dispatcher.yaml").write_text("invalid: [")
before = bd("list", "--all", "--limit", "0", "--flat")
head = run("git", "rev-parse", "HEAD").stdout
dolt_before = run("bd", "--readonly", "dolt", "status", "--json").stdout
result = run(BINARY, "--status")
assert "закрыто 1/2 задач" in result.stdout, result.stdout
assert f"🔒 `{task}`" in result.stdout and f"ждёт `{bug}`" in result.stdout, (
    result.stdout
)
assert f"🐛 ▶ `{bug}`" in result.stdout and "Без вехи" in result.stdout, result.stdout
assert f"`{done}`" not in result.stdout
assert run(BINARY, "--status").stdout == result.stdout
scoped = run(BINARY, "--status", epic).stdout
assert f"ждёт `{bug}` Standalone bug" in scoped and f"- 🐛 ▶ `{bug}`" not in scoped, (
    scoped
)
assert run(BINARY, "--status", "nonexistent-xyz", ok=False).returncode != 0
assert run(BINARY, "--status", "--bad", ok=False).returncode != 0
assert run(BINARY, "--help").returncode == 0
# Invocation from a linked worktree/subdirectory resolves to the same project.
linked = ROOT / "linked"
run("git", "worktree", "add", "--detach", str(linked), "HEAD")
(linked / "nested").mkdir()
assert run(BINARY, "--status", cwd=linked / "nested").stdout == result.stdout
assert bd("list", "--all", "--limit", "0", "--flat") == before
assert run("git", "rev-parse", "HEAD").stdout == head
assert run("bd", "--readonly", "dolt", "status", "--json").stdout == dolt_before
print(result.stdout)
print(
    "PASS: real readonly status, scoped blockers, linked worktree, unchanged issues/Git/Dolt"
)

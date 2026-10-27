"""Real Git/bd/Dolt fault-contract checks, NOT a skill executor or model e2e.

Synthetic payloads deliberately have no independent-review claim. Runtime gates
and the model-driven delivery candidate require a separate independent review.
Run: python -B tests/s4_publication_smoke.py
"""

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(tempfile.mkdtemp(prefix="mis-s4-contract-", dir="/tmp/opencode"))
PROJECT = ROOT / "consumer"
PROJECT.mkdir()
ENV = {k: v for k, v in os.environ.items() if not k.startswith(("BEADS_", "BD_"))}
ENV.update(BEADS_ACTOR=ROOT.name, BD_NON_INTERACTIVE="1", BD_LAST_TOUCHED_FALLBACK="0")


def run(*args, cwd=PROJECT, ok=True):
    result = subprocess.run(args, cwd=cwd, env=ENV, text=True, capture_output=True)
    if ok and result.returncode:
        raise AssertionError((args, result.returncode, result.stdout, result.stderr))
    result.stdout = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout).strip()
    return result


def bd(*args, write=False):
    return json.loads(
        run("bd", "--sandbox" if write else "--readonly", *args, "--json").stdout
    )


def show(identifier):
    rows = bd("show", identifier, "--brief-deps")
    assert len(rows) == 1 and rows[0]["id"] == identifier
    return rows[0]


def create(kind, title, acceptance, parent=None):
    args = [
        "create",
        "--type",
        kind,
        "--title",
        title,
        "--description",
        "S4 synthetic contract",
        "--acceptance",
        acceptance,
    ]
    if parent:
        args += ["--parent", parent]
    return bd(*args, write=True)["id"]


print(f"Fixture: {ROOT}", flush=True)
run("git", "init", "-b", "main")
(PROJECT / "payload.txt").write_text("base\n")
run("git", "add", "payload.txt")
run("git", "commit", "-m", "Synthetic baseline")
run("git", "init", "--bare", str(ROOT / "git.git"))
run("git", "remote", "add", "origin", str(ROOT / "git.git"))
run("git", "push", "-u", "origin", "main")
run(
    "bd", "init", "--prefix", "s4", "--non-interactive", "--skip-agents", "--skip-hooks"
)
run("bd", "dolt", "remote", "add", "origin", f"file://{ROOT / 'dolt-remote'}")
(DB,) = [p.parent for p in (PROJECT / ".beads").rglob(".dolt")]
run("dolt", "push", "--silent", "origin", "main:main", cwd=DB)
epic = create(
    "epic",
    "Milestone with unmet own criterion",
    "Required external approval plus delivered child",
)
task = create("task", "Synthetic payload", "payload.txt contains delivered", epic)
bug = create(
    "bug",
    "Synthetic recovery bug",
    "Actual: absent marker. Expected: marker present. Repro: read payload.",
)
bd("update", task, "--claim", write=True)

# Git send succeeds, simulated lost acknowledgement: reconcile before any retry.
run("git", "switch", "-c", "contract-delivery")
(PROJECT / "payload.txt").write_text("delivered\n")
run("git", "add", "payload.txt")
run("git", "commit", "-m", "Synthetic checked payload (no review claim)")
sent = run("git", "rev-parse", "HEAD").stdout
tree = run("git", "rev-parse", "HEAD^{tree}").stdout
run("git", "push", "--quiet", "origin", f"{sent}:refs/heads/main")
run("git", "fetch", "--quiet", "origin")
remote = run("git", "ls-remote", "origin", "refs/heads/main").stdout.split()[0]
run("git", "merge-base", "--is-ancestor", sent, remote)
assert show(task)["status"] == "in_progress"  # interruption: Git yes / Beads open
assert run("git", "rev-parse", f"{sent}^{{tree}}").stdout == tree
note = f"Synthetic result; Git {sent} tree {tree}; contract checks only, no independent review claim."
bd(
    "update",
    task,
    "--append-notes",
    note,
    "--if-status",
    "in_progress",
    "--if-assignee",
    ROOT.name,
    write=True,
)
before = show(task)
assert not bd("dep", "list", task, "--type", "blocks", "--direction=down")
bd("close", task, "--reason", note, write=True)
closed = show(task)
assert closed["status"] == "closed" and closed["close_reason"] == note
for key in ("description", "acceptance_criteria", "notes", "assignee"):
    assert closed[key] == before[key]
children = bd(
    "list", "--parent", epic, "--all", "--limit", "0", "--max-rows", "0", "--brief"
)
assert [r["id"] for r in children] == [task] and all(
    r["status"] == "closed" for r in children
)
assert show(epic)["status"] == "open"  # own approval criterion is NOT proved
assert show(bug)["status"] == "open"  # no auto-advance/close of next work

# Beads is closed locally, but remote is still old. A failing push is not success.
required = run("dolt", "log", "-n", "1", "--oneline", cwd=DB).stdout.split()[0]
run("dolt", "fetch", "--silent", "origin", cwd=DB)
assert run("dolt", "merge-base", required, "origin/main", cwd=DB).stdout != required
failed = run(
    "dolt", "push", "--silent", "missing-remote", "main:main", cwd=DB, ok=False
)
assert failed.returncode != 0 and show(task) == closed
assert "nothing to commit" in run("dolt", "status", cwd=DB).stdout.lower()
run("dolt", "push", "--silent", "origin", "main:main", cwd=DB)
run("dolt", "fetch", "--silent", "origin", cwd=DB)
assert run("dolt", "merge-base", required, "origin/main", cwd=DB).stdout == required

# Read-only retry, then dirty Git state: confirmation of old S still valid.
inventory = bd("list", "--all", "--limit", "0", "--max-rows", "0", "--brief")
notes = show(task)["notes"]
local_before = run("dolt", "log", "-n", "1", "--oneline", cwd=DB).stdout
run("dolt", "fetch", "--silent", "origin", cwd=DB)
assert run("dolt", "merge-base", required, "origin/main", cwd=DB).stdout == required
assert bd("list", "--all", "--limit", "0", "--max-rows", "0", "--brief") == inventory
assert show(task)["notes"] == notes
assert run("dolt", "log", "-n", "1", "--oneline", cwd=DB).stdout == local_before
(PROJECT / "foreign.txt").write_text("preserve me\n")
run("git", "fetch", "--quiet", "origin")
run("git", "merge-base", "--is-ancestor", sent, "origin/main")
assert (PROJECT / "foreign.txt").read_text() == "preserve me\n"

# Divergent Git histories: non-force rejection, then explicit merge conflict.
OTHER = ROOT / "other"
run("git", "clone", "-b", "main", str(ROOT / "git.git"), str(OTHER))
(OTHER / "payload.txt").write_text("remote edit\n")
run("git", "add", "payload.txt", cwd=OTHER)
run("git", "commit", "-m", "Concurrent authorized change", cwd=OTHER)
run("git", "push", "origin", "main", cwd=OTHER)
remote_new = run("git", "ls-remote", "origin", "refs/heads/main").stdout.split()[0]
(PROJECT / "payload.txt").write_text("local edit\n")
run("git", "add", "payload.txt")
run("git", "commit", "-m", "Conflicting candidate; do not publish")
rejected = run("git", "push", "--quiet", "origin", "HEAD:refs/heads/main", ok=False)
assert rejected.returncode != 0
run("git", "fetch", "--quiet", "origin")
conflict = run("git", "merge", "origin/main", ok=False)
assert conflict.returncode != 0 and run("git", "ls-files", "-u").stdout
assert (
    run("git", "ls-remote", "origin", "refs/heads/main").stdout.split()[0] == remote_new
)
assert (PROJECT / "foreign.txt").read_text() == "preserve me\n"
# Confirm the prior delivery, not the conflicted tip; no reset/abort needed.
run("git", "merge-base", "--is-ancestor", sent, "origin/main")
assert show(task)["status"] == "closed" and show(epic)["status"] == "open"
print(
    json.dumps(
        {
            "result": "PASS (tool contracts only)",
            "fixture": str(ROOT),
            "task": task,
            "epic_left_open": epic,
            "untouched_bug": bug,
            "git_sent": sent,
            "tree": tree,
            "dolt_required": required,
            "recovery": [
                "Git published / Task open",
                "Task closed / Dolt absent",
                "confirmation-only",
            ],
            "conflict_preserved": True,
        },
        indent=2,
    )
)

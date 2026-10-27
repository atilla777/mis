"""Real CLI contract smoke, NOT a model-driven /mis-plan e2e.

Run: python -B tests/s2_beads_smoke.py
Creates only fresh fixtures below /tmp/opencode; retains them for inspection.
Init/remotes/close are test preparation, never MIS runtime behavior.
"""

import json
import os
import re
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(tempfile.mkdtemp(prefix="mis-s2-", dir="/tmp/opencode"))
PROJECT = ROOT / "consumer"
PROJECT.mkdir()
# Do not inherit a caller's database/server routing into an isolated test.
ENV = {k: v for k, v in os.environ.items() if not k.startswith(("BEADS_", "BD_"))}
ENV.update(BD_NON_INTERACTIVE="1", BD_LAST_TOUCHED_FALLBACK="0")


def run(*args, cwd=PROJECT, ok=True):
    result = subprocess.run(args, cwd=cwd, env=ENV, text=True, capture_output=True)
    if ok and result.returncode:
        raise AssertionError((args, result.returncode, result.stdout, result.stderr))
    result.stdout = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    return result


def bd(*args, write=False):
    result = run(
        "bd",
        "-C",
        str(PROJECT),
        "--sandbox" if write else "--readonly",
        *args,
        "--json",
    )
    return json.loads(result.stdout)


def show(identifier):
    rows = bd("show", identifier, "--brief-deps")
    assert len(rows) == 1 and rows[0]["id"] == identifier
    return rows[0]


def inventory(*extra):
    return bd(
        "list",
        "--all",
        "--limit",
        "0",
        "--max-rows",
        "0",
        "--include-gates",
        "--include-ephemeral",
        "--include-infra",
        "--include-templates",
        "--brief",
        *extra,
    )


def create(kind, title, description, acceptance, parent=None):
    # Fixed fixture content only, not a production identity/dedup algorithm.
    args = [
        "create",
        "--type",
        kind,
        "--title",
        title,
        "--description",
        description,
        "--acceptance",
        acceptance,
    ]
    if parent:
        assert show(parent)["issue_type"] == "epic"
        assert show(parent)["status"] == "open"
        args += ["--parent", parent]
    identifier = bd(*args, write=True)["id"]
    row = show(identifier)
    assert (
        row["issue_type"],
        row["title"],
        row["description"],
        row["acceptance_criteria"],
    ) == (kind, title, description, acceptance)
    if parent:
        assert row["parent"] == parent
        assert identifier in {r["id"] for r in inventory("--parent", parent)}
        edges = bd(
            "dep", "list", identifier, "--type", "parent-child", "--direction=down"
        )
        assert any(
            e["id"] == parent and e["dependency_type"] == "parent-child" for e in edges
        )
    return identifier


print(f"Fixture: {ROOT}", flush=True)
run("git", "init", "-b", "main")
for directory in ("docs/product", "docs/spec", "docs/rules"):
    (PROJECT / directory).mkdir(parents=True)
(PROJECT / "AGENTS.md").write_text(
    "Read docs/product/goals.md and docs/rules/checks.md. "
    "This disposable test authorizes its entire shared Dolt main history to origin.\n"
)
(PROJECT / "docs/product/goals.md").write_text(
    "# Goals\n## Technical\nProvide a runnable unittest check; no application feature.\n"
    "## Product\nCLI integer increment: 0 -> 1, -1 -> 0, 4 -> 5; reject non-integers. "
    "No network, storage or UI. Runtime prerequisite: approved integer parser.\n"
    "## Standalone\nDocument the local check command, no implementation changes.\n"
)
(PROJECT / "docs/rules/checks.md").write_text("Use Python unittest; standard mode.\n")
run("git", "add", "AGENTS.md", "docs")
run("git", "commit", "-m", "test fixture requirements")
run("git", "init", "--bare", str(ROOT / "git-remote.git"))
run("git", "remote", "add", "origin", str(ROOT / "git-remote.git"))
run("git", "push", "-u", "origin", "main")
run(
    "bd", "init", "--prefix", "s2", "--non-interactive", "--skip-agents", "--skip-hooks"
)
run("bd", "dolt", "remote", "add", "origin", f"file://{ROOT / 'dolt-remote'}")
print(run("bd", "context", "--json").stdout, flush=True)
print(run("bd", "dolt", "status").stdout, flush=True)
databases = list((PROJECT / ".beads").rglob(".dolt"))
assert len(databases) == 1, databases
database = databases[0].parent
run("dolt", "status", cwd=database)
run("dolt", "branch", "-av", cwd=database)
run("dolt", "remote", "-v", cwd=database)
# Establish the prepared remote before exercising the planning operations.
run("dolt", "push", "--silent", "origin", "main:main", cwd=database)
run("dolt", "fetch", "--silent", "origin", cwd=database)
before_files = {
    str(p.relative_to(PROJECT)): p.read_bytes()
    for p in PROJECT.rglob("*")
    if p.is_file() and not {".git", ".beads"}.intersection(p.relative_to(PROJECT).parts)
}
before_git = run("git", "rev-parse", "HEAD").stdout
before_worktrees = run("git", "worktree", "list", "--porcelain").stdout
assert inventory() == []

technical = create(
    "epic",
    "Checks are runnable",
    "docs/product/goals.md#technical",
    "A fresh checkout can run unittest; no product functionality required.",
)
check = create(
    "task",
    "Provide local unittest entry point",
    "docs/product/goals.md#technical",
    "The documented check command passes on a fresh checkout.",
    technical,
)
product = create(
    "epic",
    "Integer increment available",
    "docs/product/goals.md#product",
    "CLI 0 -> 1, -1 -> 0, 4 -> 5; reject non-integers; no network/storage/UI.",
)
parser = create(
    "task",
    "Approve integer parser contract",
    "Existing external prerequisite.",
    "Contract defines integer parsing and invalid-input errors.",
)
increment = create(
    "task",
    "Implement integer increment CLI",
    "docs/product/goals.md#product",
    "0 -> 1, -1 -> 0, 4 -> 5; reject non-integers; no network/storage/UI.",
    product,
)
standalone = create(
    "task",
    "Document local check",
    "docs/product/goals.md#standalone",
    "README names the local check command; no code changes.",
)
assert "parent" not in show(standalone)
assert not bd("dep", "list", standalone, "--type", "parent-child", "--direction=down")
bd("dep", "add", increment, parser, "--type", "blocks", write=True)
edges = bd("dep", "list", increment, "--type", "blocks", "--direction=down")
assert (
    len(edges) == 1
    and edges[0]["id"] == parser
    and edges[0]["dependency_type"] == "blocks"
)
assert not bd("dep", "list", parser, "--type", "blocks", "--direction=down")
assert increment not in {r["id"] for r in bd("ready", "--limit", "0")}
cycle = run(
    "bd", "--sandbox", "dep", "add", parser, increment, "--type", "blocks", ok=False
)
assert cycle.returncode != 0
assert not bd("dep", "list", parser, "--type", "blocks", "--direction=down")

# Bounded update preserves unrelated content and stops on a stale native guard.
before = show(standalone)
acceptance = (
    before["acceptance_criteria"] + " Include the expected successful exit code."
)
bd(
    "update",
    standalone,
    "--acceptance",
    acceptance,
    "--if-status",
    "open",
    "--if-assignee",
    "",
    write=True,
)
after = show(standalone)
for field in ("description", "title", "status", "issue_type", "notes", "assignee"):
    assert after.get(field) == before.get(field), field
assert after["acceptance_criteria"] == acceptance
stale = run(
    "bd",
    "--sandbox",
    "update",
    standalone,
    "--title",
    "Must not replace",
    "--if-status",
    "closed",
    "--json",
    ok=False,
)
assert stale.returncode == 13
assert show(standalone)["title"] == before["title"]

# Closed context belongs to fixture setup, not the planning workflow.
closed = create(
    "task",
    "Historical setup",
    "Pre-existing verified fixture setup.",
    "The fixture requirements are committed.",
)
bd("close", closed, "--reason", "Fixture requirements commit checked", write=True)
rows = inventory()
assert len(rows) == 7 and show(closed)["status"] == "closed"
# Reconcile fixed proposals by their full known content; same IDs, no writes.
snapshot = {r["id"]: show(r["id"]) for r in rows}
for identifier, expected in snapshot.items():
    matches = [
        show(r["id"]) for r in inventory() if r["issue_type"] == expected["issue_type"]
    ]
    matches = [
        r
        for r in matches
        if r["description"] == expected["description"]
        and r["acceptance_criteria"] == expected["acceptance_criteria"]
    ]
    assert [r["id"] for r in matches] == [identifier]
assert {r["id"]: show(r["id"]) for r in inventory()} == snapshot

status = run("dolt", "status", cwd=database).stdout
assert "nothing to commit" in status, status
required = run("dolt", "log", "-n", "1", "--oneline", cwd=database).stdout.split()[0]
run("dolt", "fetch", "--silent", "origin", cwd=database)
remote_before = run(
    "dolt", "merge-base", "main", "origin/main", cwd=database
).stdout.strip()
assert remote_before != required  # Sandbox did not auto-publish issue writes.
run("dolt", "push", "--silent", "origin", "main:main", cwd=database)
run("dolt", "fetch", "--silent", "origin", cwd=database)
assert (
    run("dolt", "merge-base", required, "origin/main", cwd=database).stdout.strip()
    == required
)
branches = run("dolt", "branch", "-av", cwd=database).stdout
assert required in branches
# Independent remote clone (test-only) confirms the published head.
run(
    "dolt",
    "clone",
    f"file://{ROOT / 'dolt-remote'}",
    str(ROOT / "remote-check"),
    cwd=ROOT,
)
remote_log = run(
    "dolt", "log", "-n", "1", "--oneline", cwd=ROOT / "remote-check"
).stdout
assert remote_log.split()[0] == required
# Confirmation-only recovery: fresh fetch/reachability, no duplicate writes/push.
run("dolt", "fetch", "--silent", "origin", cwd=database)
assert (
    run("dolt", "merge-base", required, "origin/main", cwd=database).stdout.strip()
    == required
)
assert len(inventory()) == 7
assert run("git", "rev-parse", "HEAD").stdout == before_git
assert run("git", "worktree", "list", "--porcelain").stdout == before_worktrees
after_files = {
    str(p.relative_to(PROJECT)): p.read_bytes()
    for p in PROJECT.rglob("*")
    if p.is_file() and not {".git", ".beads"}.intersection(p.relative_to(PROJECT).parts)
}
assert before_files == after_files and not list((PROJECT / "docs/spec").iterdir())
print(
    json.dumps(
        {
            "result": "PASS",
            "fixture": str(ROOT),
            "beads_revision": required,
            "ids": {
                "technical_epic": technical,
                "check": check,
                "product_epic": product,
                "parser": parser,
                "increment": increment,
                "standalone": standalone,
                "closed": closed,
            },
        },
        indent=2,
    )
)

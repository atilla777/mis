"""Real native OpenCode API/bd/Git contract smoke; NOT model-driven /mis-run e2e.

Run: python -B tests/s3_execution_smoke.py
Fresh disposable project, local remotes and idle sessions retained for inspection.
Fixed proposals/code/spec below are test data, not a runtime executor/planner.
Independent review of the retained candidates is a separate required check.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlencode


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = Path(tempfile.mkdtemp(prefix="mis-s3-", dir="/tmp/opencode"))
PROJECT = ROOT / "consumer"
PROJECT.mkdir()
ENV = {k: v for k, v in os.environ.items() if not k.startswith(("BEADS_", "BD_"))}
ACTOR = f"mis-s3-{ROOT.name}"
ENV.update(BD_NON_INTERACTIVE="1", BD_LAST_TOUCHED_FALLBACK="0", BEADS_ACTOR=ACTOR)


def run(*args, cwd=PROJECT, ok=True):
    result = subprocess.run(args, cwd=cwd, env=ENV, text=True, capture_output=True)
    if ok and result.returncode:
        raise AssertionError((args, result.returncode, result.stdout, result.stderr))
    result.stdout = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    return result


def api(method, path, data=None):
    args = ["opencode", "api", method, path]
    if data is not None:
        args += ["--data", json.dumps(data)]
    text = run(*args).stdout.strip()
    return json.loads(text) if text else None


def bd(*args, write=False, cwd=PROJECT):
    return json.loads(
        run(
            "bd",
            "-C",
            str(cwd),
            "--sandbox" if write else "--readonly",
            *args,
            "--json",
        ).stdout
    )


def show(identifier, cwd=PROJECT):
    rows = bd("show", identifier, "--brief-deps", cwd=cwd)
    assert len(rows) == 1 and rows[0]["id"] == identifier
    return rows[0]


def append(identifier, text):
    row = show(identifier)
    assert row["status"] == "in_progress" and row["assignee"] == ACTOR
    if text not in row.get("notes", ""):
        bd(
            "update",
            identifier,
            "--append-notes",
            text,
            "--if-status",
            "in_progress",
            "--if-assignee",
            ACTOR,
            write=True,
        )
    assert text in show(identifier)["notes"]


def create(title, acceptance):
    return bd(
        "create",
        "--type",
        "task",
        "--title",
        title,
        "--description",
        "Source: docs/product/goals.md",
        "--acceptance",
        acceptance,
        write=True,
    )["id"]


def fingerprint(path):
    # Include baseline tracked files plus WIP additions, modes, and deletion markers.
    names = set(run("git", "ls-files", "-z", cwd=path).stdout.split("\0"))
    names |= set(
        run(
            "git", "ls-files", "--others", "--exclude-standard", "-z", cwd=path
        ).stdout.split("\0")
    )
    digest = hashlib.sha256()
    for name in sorted(names - {""}):
        file = path / name
        digest.update(name.encode() + b"\0")
        if file.exists():
            digest.update(f"{file.stat().st_mode & 0o777:o}".encode() + b"\0")
            digest.update(file.read_bytes() + b"\0")
        else:
            digest.update(b"deleted\0")
    return digest.hexdigest()


print(f"Fixture: {ROOT}", flush=True)
run("git", "init", "-b", "main")
for folder in ("docs/product", "docs/spec", "docs/rules", "tests"):
    (PROJECT / folder).mkdir(parents=True)
(PROJECT / ".gitignore").write_text(".opencode/\n__pycache__/\n")
(PROJECT / "AGENTS.md").write_text(
    "Read docs/product/goals.md and docs/rules/checks.md. Disposable S3 fixture.\n"
    "Only local candidate/claim/notes are authorized, no completion/publication.\n"
)
(PROJECT / "docs/product/goals.md").write_text(
    "# Goals\nProduct: increment(value) accepts only Python int (not bool), returns value+1.\n"
    "Examples: 0→1, -1→0, 4→5. Other types raise TypeError. No I/O/network/UI.\n"
    "Technical: document an explicit unittest discovery command, no product changes.\n"
)
(PROJECT / "docs/rules/checks.md").write_text(
    "Python stdlib unittest. Product behavior requires TDD. Documentation-only: standard.\n"
    "Run python -B -m unittest discover -s tests -v. Independent read-only review required.\n"
)
(PROJECT / "docs/spec/index.md").write_text(
    "# Specifications\n\nNo product contracts implemented yet.\n"
)
(PROJECT / "increment.py").write_text("def increment(value):\n    return value\n")
(PROJECT / "tests/test_baseline.py").write_text(
    "import unittest\n\nclass Baseline(unittest.TestCase):\n"
    "    def test_harness(self):\n        self.assertEqual(2 + 2, 4)\n"
)
run("git", "add", ".")
run("git", "commit", "-m", "S3 fixture requirements and baseline")
base = run("git", "rev-parse", "HEAD").stdout.strip()
run("git", "init", "--bare", str(ROOT / "git-remote.git"))
run("git", "remote", "add", "origin", str(ROOT / "git-remote.git"))
run("git", "push", "-u", "origin", "main")
# Preparation only; runtime must never initialize a new workspace in a worktree.
run(
    "bd", "init", "--prefix", "s3", "--non-interactive", "--skip-agents", "--skip-hooks"
)
run("bd", "dolt", "remote", "add", "origin", f"file://{ROOT / 'dolt-remote'}")
(database,) = [p.parent for p in (PROJECT / ".beads").rglob(".dolt")]
run("dolt", "push", "--silent", "origin", "main:main", cwd=database)
dolt_remote_base = run(
    "dolt", "log", "-n", "1", "--oneline", cwd=database
).stdout.split()[0]
# Keep preparation artifacts in the base, so native worktrees have prepared routing.
run("git", "add", ".beads", ".gitignore")
if run("git", "diff", "--cached", "--quiet", ok=False).returncode:
    run("git", "commit", "-m", "Prepare Beads routing for native worktrees")
base = run("git", "rev-parse", "HEAD").stdout.strip()
run("git", "push", "origin", "main")
shutil.copytree(PACKAGE / "skills", PROJECT / ".opencode/skills")
shutil.copytree(PACKAGE / "commands/opencode", PROJECT / ".opencode/commands")
query = urlencode({"location[directory]": str(PROJECT)})
location = api("get", f"/api/location?{query}")
project_id = location["project"]["id"]
expected_skills = {p.parent.name for p in (PACKAGE / "skills").glob("*/SKILL.md")}
# Fresh-location discovery is asynchronous in 2.0.32 (also observed in S2).
for _ in range(5):
    skills = api("get", f"/api/skill?{query}")["data"]
    installed = {r["name"]: r for r in skills if r["name"].startswith("mis-")}
    if set(installed) == expected_skills:
        break
assert set(installed) == expected_skills, sorted(installed)
for name, row in installed.items():
    assert (
        Path(row["path"]).resolve()
        == (PROJECT / f".opencode/skills/{name}/SKILL.md").resolve()
    )
    source = (PACKAGE / f"skills/{name}/SKILL.md").read_text()
    assert row["content"] == source.split("---", 2)[2].removeprefix("\n")
    assert (PROJECT / f".opencode/skills/{name}/SKILL.md").read_bytes() == (
        PACKAGE / f"skills/{name}/SKILL.md"
    ).read_bytes()
commands = api("get", f"/api/command?{query}")["data"]
assert any(r["name"] == "mis-run" and "S3" in r["description"] for r in commands)

product = create(
    "Implement integer increment",
    "int only, not bool; +1; TypeError otherwise; no I/O.",
)
technical = create(
    "Document local unittest command",
    "README names explicit passing unittest discovery command; no behavior change.",
)
prerequisite = create(
    "External prerequisite", "An external contract must be approved first."
)
blocked = create(
    "Not executable yet", "Do not execute while external prerequisite is open."
)
bd("dep", "add", blocked, prerequisite, "--type", "blocks", write=True)
assert blocked not in {r["id"] for r in bd("ready", "--limit", "0")}
assert (
    bd("dep", "list", blocked, "--type", "blocks", "--direction=down")[0]["id"]
    == prerequisite
)
assert show(blocked)["status"] == "open" and not show(blocked).get("assignee")

candidates = []
for identifier in (product, technical):
    assert identifier in {r["id"] for r in bd("ready", "--limit", "0")}
    before = show(identifier)
    bd("update", identifier, "--claim", write=True)
    claimed = show(identifier)
    assert claimed["status"] == "in_progress" and claimed["assignee"] == ACTOR
    assert claimed["acceptance_criteria"] == before["acceptance_criteria"]
    assert not bd("dep", "list", identifier, "--type", "blocks", "--direction=down")
    # Another actor must not take a live claim.
    refused = run(
        "bd",
        "--sandbox",
        "--actor",
        "foreign-s3-reviewer",
        "update",
        identifier,
        "--claim",
        "--json",
        ok=False,
    )
    assert refused.returncode != 0 and show(identifier)["assignee"] == ACTOR
    session = api(
        "post",
        "/api/session",
        {"title": f"S3 fixture {identifier}", "location": {"directory": str(PROJECT)}},
    )["data"]
    existing = api("get", f"/api/worktree?{urlencode({'projectID': project_id})}")
    result = api(
        "post",
        "/api/worktree",
        {"projectID": project_id, "from": str(PROJECT), "name": identifier},
    )
    worktree = Path(result["directory"]).resolve()
    assert worktree != PROJECT and worktree.is_dir()
    common = run(
        "git", "rev-parse", "--path-format=absolute", "--git-common-dir", cwd=worktree
    ).stdout.strip()
    assert (
        common
        == run(
            "git", "rev-parse", "--path-format=absolute", "--git-common-dir"
        ).stdout.strip()
    )
    assert (
        Path(run("git", "rev-parse", "--show-toplevel", cwd=worktree).stdout.strip())
        == worktree
    )
    assert run("git", "rev-parse", "HEAD", cwd=worktree).stdout.strip() == base
    branch = run("git", "branch", "--show-current", cwd=worktree).stdout.strip()
    if not branch:
        assert not run("git", "status", "--porcelain", cwd=worktree).stdout.strip()
        branch = f"mis/{identifier}"
        assert (
            run(
                "git",
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{branch}",
                ok=False,
            ).returncode
            == 1
        )
        run("git", "switch", "-c", branch, cwd=worktree)
        assert (
            run("git", "branch", "--show-current", cwd=worktree).stdout.strip()
            == branch
        )
    assert branch and identifier in branch
    assert not run("git", "status", "--porcelain", cwd=worktree).stdout.strip()
    inventory = api("get", f"/api/worktree?{urlencode({'projectID': project_id})}")
    assert len(inventory) == len(existing) + 1
    assert str(worktree) in {r["directory"] for r in inventory}
    association = (
        f"Task {identifier}; worktree {worktree}; branch {branch}; base {base}"
    )
    append(identifier, association)
    api("post", f"/api/session/{session['id']}/move", {"directory": str(worktree)})
    # Separate request after the move boundary: never assume immediate path switching.
    moved = api("get", f"/api/session/{session['id']}")["data"]
    assert moved["location"]["directory"] == str(worktree)
    assert moved["projectID"] == project_id
    assert show(identifier, cwd=worktree)["assignee"] == ACTOR

    if identifier == product:
        (worktree / "tests/test_increment.py").write_text(
            "import unittest\nfrom increment import increment\n\n"
            "class Increment(unittest.TestCase):\n"
            "    def test_integers(self):\n"
            "        for source, expected in ((0, 1), (-1, 0), (4, 5)):\n"
            "            with self.subTest(source=source):\n"
            "                self.assertEqual(increment(source), expected)\n"
            "    def test_invalid_types(self):\n"
            "        for value in (True, False, 1.0, '1', None, []):\n"
            "            with self.subTest(value=value):\n"
            "                with self.assertRaises(TypeError):\n"
            "                    increment(value)\n"
        )
        red = run(
            "python",
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-v",
            cwd=worktree,
            ok=False,
        )
        assert (
            red.returncode != 0 and "FAIL:" in red.stderr and "ERROR:" not in red.stderr
        )
        (ROOT / "product-red.txt").write_text(red.stderr)
        (worktree / "increment.py").write_text(
            "def increment(value):\n    if type(value) is not int:\n"
            "        raise TypeError('expected int')\n    return value + 1\n"
        )
        (worktree / "docs/spec/integer-increment.md").write_text(
            "# Integer increment\n\nCandidate pending integration.\n\n"
            "`increment(value)` accepts Python int, excluding bool, and returns value + 1.\n"
            "Examples: 0→1, -1→0, 4→5. Non-int inputs raise TypeError. No I/O/network/UI.\n\n"
            f"Source: [product goals](../product/goals.md). Beads: `{identifier}`.\n"
        )
        (worktree / "docs/spec/index.md").write_text(
            "# Specifications\n\nCandidate pending integration: [Integer increment](integer-increment.md).\n"
        )
        append(
            identifier,
            "Spec candidate: docs/spec/integer-increment.md; pending integration.",
        )
    else:
        (worktree / "README.md").write_text(
            "# Local checks\n\nRun `python -B -m unittest discover -s tests -v`. Success exits 0.\n"
        )
        assert [p.name for p in (worktree / "docs/spec").glob("*.md")] == ["index.md"]
        append(
            identifier,
            "Spec no-op: documentation of existing test invocation; no durable product behavior change.",
        )
    green = run(
        "python", "-B", "-m", "unittest", "discover", "-s", "tests", "-v", cwd=worktree
    )
    assert "OK" in green.stderr
    (ROOT / f"{identifier}-green.txt").write_text(green.stderr)
    # Simulate interruption and recover from actual Bead association/native inventory.
    snapshot = fingerprint(worktree)
    before_notes = show(identifier)["notes"]
    before_inventory = api(
        "get", f"/api/worktree?{urlencode({'projectID': project_id})}"
    )
    assert association in before_notes
    assert str(worktree) in {r["directory"] for r in before_inventory}
    append(identifier, association)  # idempotent linkage, not repeated append
    bd("update", identifier, "--claim", write=True)  # native self-claim idempotence
    assert show(identifier)["notes"] == before_notes
    assert fingerprint(worktree) == snapshot
    assert (
        api("get", f"/api/worktree?{urlencode({'projectID': project_id})}")
        == before_inventory
    )
    # Foreign untracked data is preserved; ambiguity is not authorization to overwrite.
    (worktree / "foreign.txt").write_text("foreign data: do not edit\n")
    foreign = (worktree / "foreign.txt").read_bytes()
    assert "foreign.txt" in run("git", "status", "--porcelain", cwd=worktree).stdout
    assert (worktree / "foreign.txt").read_bytes() == foreign
    candidates.append(
        {
            "id": identifier,
            "worktree": str(worktree),
            "branch": branch,
            "session": session["id"],
            "base": base,
            "candidate_before_foreign_file": snapshot,
            "review_context_exclusion": "foreign.txt (untracked foreign data, not candidate)",
        }
    )

assert run("git", "rev-parse", "HEAD").stdout.strip() == base
assert run("git", "ls-remote", "origin", "refs/heads/main").stdout.split()[0] == base
assert all(show(i)["status"] == "in_progress" for i in (product, technical))
run("dolt", "fetch", "--silent", "origin", cwd=database)
local = run("dolt", "log", "-n", "1", "--oneline", cwd=database).stdout.split()[0]
assert local != dolt_remote_base
assert (
    run("dolt", "merge-base", "main", "origin/main", cwd=database).stdout.strip()
    == dolt_remote_base
)
receipt = {
    "result": "PASS (CLI/API contract only; independent review pending)",
    "fixture": str(ROOT),
    "project_id": project_id,
    "actor": ACTOR,
    "candidates": candidates,
    "blocked": blocked,
    "prerequisite": prerequisite,
    "git_remote_unchanged": base,
    "dolt_remote_unchanged": dolt_remote_base,
    "dolt_local": local,
    "skills": sorted(installed),
}
(ROOT / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))

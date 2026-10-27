"""Prepare two isolated S5 projects; does NOT plan or execute their tasks.

Run python -B tests/s5_prepare_pilots.py, then invoke real OpenCode commands in
fresh sessions at the printed paths. Local test remotes only; fixtures retained.
"""

import json
import os
from pathlib import Path
import subprocess
import tempfile


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = Path(tempfile.mkdtemp(prefix="mis-s5-", dir="/tmp/opencode"))
ENV = {k: v for k, v in os.environ.items() if not k.startswith(("BEADS_", "BD_"))}
ENV.update(BD_NON_INTERACTIVE="1", BD_LAST_TOUCHED_FALLBACK="0")


def run(*args, cwd):
    result = subprocess.run(args, cwd=cwd, env=ENV, text=True, capture_output=True)
    if result.returncode:
        raise AssertionError((args, result.returncode, result.stdout, result.stderr))
    return result.stdout.strip()


for kind in ("technical", "product"):
    home = ROOT / kind
    project = home / "consumer"
    project.mkdir(parents=True)
    run("git", "init", "-b", "main", cwd=project)
    for folder in ("docs/product", "docs/spec", "docs/rules", "tests"):
        (project / folder).mkdir(parents=True)
    (project / ".gitignore").write_text("__pycache__/\n")
    (project / "AGENTS.md").write_text(
        "# Disposable MIS S5 pilot\n"
        "Read docs/product/goals.md and docs/rules/checks.md.\n"
        "Git primary is main; origin is this fixture's local bare test remote.\n"
        "Full authority for this fixture's own Git history and shared Beads/Dolt history: "
        "ordinary commits, merge latest main, non-force direct push to origin/main, "
        "Task/Epic writes and independent Dolt origin/main publication. No external services.\n"
        "Use MIS workflows only when requested; one command then stop, no auto-next.\n"
        "Independent read-only reviewer delegation is explicitly authorized and required.\n"
        "No other writer uses this fixture. Preserve package files.\n"
    )
    goal = (
        "# Technical milestone: reproducible checks\n"
        "Provide README.md with the exact passing Python stdlib unittest discovery "
        "command, run from repository root, and its Python 3 prerequisite. "
        "One documentation Task suffices. Existing baseline must still pass. "
        "No product behavior, new dependencies, CI, application code or spec changes.\n"
        if kind == "technical"
        else "# Product milestone: integer tripling\n"
        "Implement triple(value) in triple.py: exact built-in Python int only "
        "(not bool or int subclasses); returns value * 3, including negative/zero/large ints. "
        "Examples: -2 -> -6, 0 -> 0, 7 -> 21. All other types raise TypeError. "
        "No I/O, network, storage, UI, dependencies or changes to requirements/rules. "
        "One implementation Task suffices; test boundaries and document implemented "
        "behavior in docs/spec/ with navigation and Beads linkage.\n"
    )
    (project / "docs/product/goals.md").write_text(goal)
    (project / "docs/spec/index.md").write_text(
        "# Specifications\n\nNo implemented product behavior yet.\n"
    )
    (project / "docs/rules/checks.md").write_text(
        "# Checks\nPython 3, stdlib unittest, no third-party dependencies.\n"
        "Run: python -B -m unittest discover -s tests -v\n"
        + (
            "Documentation-only work uses standard mode.\n"
            if kind == "technical"
            else "Product work requires TDD: observe assertion-failure RED before each behavioral slice, then GREEN.\n"
        )
        + "Independent read-only review covers the entire publication tree, including unchanged files, modes and package files.\n"
    )
    (project / "tests/test_baseline.py").write_text(
        "import unittest\n\nclass Baseline(unittest.TestCase):\n"
        "    def test_harness(self):\n        self.assertEqual(2 + 2, 4)\n"
    )
    if kind == "product":
        (project / "triple.py").write_text("def triple(value):\n    return value\n")
    run("python", "-B", str(PACKAGE / "scripts/install.py"), str(project), cwd=project)
    run("git", "add", ".", cwd=project)
    run(
        "git",
        "commit",
        "-m",
        "Prepare isolated S5 requirements and MIS installation",
        cwd=project,
    )
    run("git", "init", "--bare", str(home / "git-remote.git"), cwd=project)
    run("git", "remote", "add", "origin", str(home / "git-remote.git"), cwd=project)
    run("git", "push", "-u", "origin", "main", cwd=project)
    run(
        "bd",
        "init",
        "--prefix",
        "s5t" if kind == "technical" else "s5p",
        "--non-interactive",
        "--skip-agents",
        "--skip-hooks",
        cwd=project,
    )
    run(
        "bd",
        "dolt",
        "remote",
        "add",
        "origin",
        f"file://{home / 'dolt-remote'}",
        cwd=project,
    )
    (database,) = [p.parent for p in (project / ".beads").rglob(".dolt")]
    run("dolt", "push", "--silent", "origin", "main:main", cwd=database)
    run("git", "add", ".beads", ".gitignore", cwd=project)
    if run("git", "diff", "--cached", "--name-only", cwd=project):
        run(
            "git", "commit", "-m", "Prepare unique Beads workspace routing", cwd=project
        )
    run("git", "push", "origin", "main", cwd=project)
    assert not run("git", "status", "--porcelain", cwd=project)
    assert (
        json.loads(
            run(
                "bd",
                "--readonly",
                "list",
                "--all",
                "--limit",
                "0",
                "--json",
                cwd=project,
            )
        )
        == []
    )
    print(f"{kind}: {project}", flush=True)
print(f"Fixture: {ROOT}", flush=True)

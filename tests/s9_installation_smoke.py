"""Disposable real embedded Beads/Git-remote setup + fresh-clone restoration.

Tool contracts only, not a model-driven /mis-install pilot. Retains fixture.
"""

import json
import os
import re
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(tempfile.mkdtemp(prefix="mis-s9-", dir="/tmp/opencode"))
SOURCE = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "consumer"
REMOTE = ROOT / "origin.git"
ENV = {k: v for k, v in os.environ.items() if not k.startswith(("BD_", "BEADS_"))}
ENV.update(BD_NON_INTERACTIVE="1", BEADS_ACTOR="mis-s9-test")


def run(*args, cwd=PROJECT):
    result = subprocess.run(args, cwd=cwd, env=ENV, capture_output=True, text=True)
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return re.sub(r"\x1b\[[0-9;]*m", "", result.stdout).strip()


def bd(*args, cwd=PROJECT):
    return run("bd", "--sandbox", *args, cwd=cwd)


print(f"Fixture: {ROOT}", flush=True)
PROJECT.mkdir()
run("git", "init", "-b", "main")
run("git", "config", "user.name", "MIS test")
run("git", "config", "user.email", "mis@example.invalid")
(PROJECT / "AGENTS.md").write_text("Keep original instructions\n")
hook = PROJECT / ".git/hooks/pre-commit"
hook.write_text("#!/bin/sh\nexit 0\n")
hook.chmod(0o755)
run("git", "add", "AGENTS.md")
run("git", "commit", "-m", "baseline")
package_revision = run("git", "rev-parse", "HEAD", cwd=SOURCE)
install_command = (
    "python3",
    "-B",
    str(SOURCE / "scripts/install.py"),
    str(PROJECT),
    "--revision",
    package_revision,
)
run(*install_command)
assert not (PROJECT / ".opencode").exists()
run(*install_command, "--apply")
assert "Verified; no changes" in run(*install_command)
assert package_revision in (PROJECT / ".opencode/mis-installation").read_text()
run("git", "add", ".opencode")
run("git", "commit", "-m", "Install exact MIS package")
run("git", "init", "--bare", str(REMOTE))
run("git", "remote", "add", "origin", str(REMOTE))
run("git", "push", "-u", "origin", "main")
assert not run("git", "ls-remote", "origin", "refs/dolt/data")
git_primary_before_dolt = run("git", "ls-remote", "origin", "refs/heads/main")
bd("init", "--prefix", "s9", "--non-interactive", "--skip-agents", "--skip-hooks")
context = json.loads(bd("context", "--json"))
assert context["dolt_mode"] == "embedded" and Path(context["repo_root"]) == PROJECT
assert (PROJECT / "AGENTS.md").read_text() == "Keep original instructions\n"
assert hook.read_text() == "#!/bin/sh\nexit 0\n"
url = f"git+file://{REMOTE}"
bd("dolt", "remote", "add", "origin", url, "--allow-git-origin")
bd("config", "set", "sync.remote", url)
row = json.loads(
    bd(
        "create",
        "--type",
        "task",
        "--title",
        "Restoration sentinel",
        "--description",
        "Test fixture only",
        "--json",
    )
)
(database,) = [p.parent for p in (PROJECT / ".beads").rglob(".dolt")]
required = run("dolt", "log", "-n", "1", "--oneline", cwd=database).split()[0]
run("dolt", "push", "--silent", "origin", "main:main", cwd=database)
assert run("git", "ls-remote", "origin", "refs/dolt/data")
assert run("git", "ls-remote", "origin", "refs/heads/main") == git_primary_before_dolt
run("git", "add", ".beads", ".gitignore")
tracked = run("git", "diff", "--cached", "--name-only").splitlines()
assert not any("embeddeddolt/" in p or "/.dolt/" in p for p in tracked), tracked
if tracked:
    run("git", "commit", "-m", "Beads routing only")
run("git", "push", "origin", "main")
FRESH = ROOT / "fresh"
run("git", "clone", "--branch", "main", str(REMOTE), str(FRESH), cwd=ROOT)
assert not list((FRESH / ".beads").rglob(".dolt"))
plan = bd("bootstrap", "--dry-run", "--json", cwd=FRESH)
print("Bootstrap plan:", plan, flush=True)
proposal = json.loads(plan)
assert proposal["action"] == "sync" and proposal["sync_remote"] == url
assert proposal["has_existing"] is False and "clone" in proposal["reason"]
bd("bootstrap", "--non-interactive", cwd=FRESH)
restored = json.loads(bd("show", row["id"], "--json", cwd=FRESH))
assert len(restored) == 1 and restored[0]["title"] == "Restoration sentinel"
fresh_context = json.loads(bd("context", "--json", cwd=FRESH))
assert fresh_context["dolt_mode"] == "embedded"
assert (FRESH / "AGENTS.md").read_text() == "Keep original instructions\n"
(fresh_db,) = [p.parent for p in (FRESH / ".beads").rglob(".dolt")]
run("dolt", "fetch", "--silent", "origin", cwd=fresh_db)
assert run(
    "dolt", "merge-base", required, "remotes/origin/main", cwd=fresh_db
).startswith(required)
before = bd("show", row["id"], "--json", cwd=FRESH)
bd("bootstrap", "--non-interactive", cwd=FRESH)
assert bd("show", row["id"], "--json", cwd=FRESH) == before
print(
    json.dumps(
        {
            "result": "PASS (tool contracts only)",
            "fixture": str(ROOT),
            "restored_id": row["id"],
            "required_revision": required,
            "dolt_remote": url,
            "mode": "embedded",
        },
        indent=2,
    )
)

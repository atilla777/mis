"""First MIS package install; Beads preparation belongs to mis-proj-op-install."""

from pathlib import Path
import subprocess
import sys


if __name__ == "__main__":
    source = Path(__file__).resolve().parents[1]
    engine = source / "skills/mis-proj-op-update/scripts/update.py"
    # Same preflight/apply engine as /mis-update; revision is always explicit.
    result = subprocess.run(
        [
            sys.executable,
            str(engine),
            *sys.argv[1:],
            "--source",
            str(source),
            "--install",
        ]
    )
    sys.exit(result.returncode)

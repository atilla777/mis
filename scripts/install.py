"""Copy only MIS skills/resources/license and command facades into a project."""

import argparse
from pathlib import Path
import shutil


PACKAGE = Path(__file__).resolve().parents[1]


def install(project):
    project = project.resolve(strict=True)
    if not project.is_dir() or project == PACKAGE:
        raise ValueError("Choose a prepared consumer directory, not MIS itself")
    files = [(PACKAGE / "skills/LICENSE-RIS", Path("skills/LICENSE-RIS"))]
    for skill in sorted((PACKAGE / "skills").glob("mis-*")):
        for source in sorted(skill.rglob("*")):
            if source.is_file():
                files.append((source, source.relative_to(PACKAGE)))
    for name in ("mis-plan.md", "mis-run.md", "mis-status.md", "mis-update.md"):
        files.append((PACKAGE / "commands/opencode" / name, Path("commands") / name))
    target = project / ".opencode"
    # Preflight the entire copy: no partial install on a known conflict, no
    # traversal through destination symlinks, no replacement of user files.
    for source, relative in files:
        destination = target / relative
        for part in (destination, *destination.parents):
            if part == project:
                break
            if part.is_symlink():
                raise ValueError(f"Destination symlink: {part}")
            if part != destination and part.exists() and not part.is_dir():
                raise ValueError(f"Not a directory: {part}")
        if destination.exists() and (
            not destination.is_file() or destination.read_bytes() != source.read_bytes()
        ):
            raise ValueError(f"Conflicting file (not overwritten): {destination}")
    for source, relative in files:
        destination = target / relative
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    return len(files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    try:
        count = install(args.project)
    except (OSError, ValueError) as error:
        parser.exit(1, f"MIS install: {error}\n")
    print(f"MIS: {count} files verified in {args.project.resolve() / '.opencode'}")

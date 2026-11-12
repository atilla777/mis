#!/usr/bin/env python3
"""MIS desktop adapter. No scheduler, prompts, session writes or direct database access."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import termios
import time
from urllib.parse import urlencode


HERE = Path(__file__).resolve().parent
SESSION = re.compile(r"ses_[A-Za-z0-9_-]+\Z")
ADDRESS = re.compile(r"0x[0-9a-fA-F]+\Z")
KEY = "mis_dispatcher"


def run(args, *, cwd=None, timeout=35):
    # OpenCode 2.0.32 truncates large piped stdout. Use a private regular file.
    temp = os.environ.get("TMPDIR") or (
        "/tmp/opencode" if Path("/tmp/opencode").is_dir() else None
    )
    with tempfile.TemporaryFile(dir=temp) as output:
        result = subprocess.run(
            args,
            cwd=cwd,
            stdout=output,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(
                f"{args[0]}: {result.stderr.decode(errors='replace').strip()[:500]}"
            )
        output.seek(0)
        return output.read().decode()


def api(path):
    return json.loads(run(["opencode", "api", "get", path]))


def bd(root, *args):
    # Ambient redirects could read another project's DB, even with -C.
    for name in (
        "BEADS_DB",
        "BEADS_DIR",
        "BD_DB",
        "BEADS_DOLT_SERVER_DATABASE",
        "BEADS_DOLT_SERVER_HOST",
        "BEADS_DOLT_SERVER_PORT",
    ):
        if os.environ.get(name):
            raise RuntimeError(f"unset ambient {name}")
    return json.loads(run(["bd", "-C", root, "--readonly", "--json", *args]))


def identity(root):
    return hashlib.sha256(root.encode()).hexdigest()[:16]


def clean(text):
    return "".join(c for c in str(text) if c.isprintable())[:160]


def reservation(value):
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("unsupported dispatcher metadata")
    if not SESSION.fullmatch(value.get("session", "")):
        raise ValueError("invalid dispatcher session")
    if not os.path.isabs(value.get("project", "")) or not value.get("task"):
        raise ValueError("invalid dispatcher project/task")
    if value.get("phase") not in ("reserved", "submitted"):
        raise ValueError("invalid reservation phase")
    return value


def same(a, b):
    return all(a.get(k) == b.get(k) for k in ("version", "project", "task", "session"))


def inventory():
    result, seen = {}, set()
    cursor = None
    for _ in range(1000):
        query = {"limit": "100"}
        if cursor:
            query["cursor"] = cursor
        page = api("/api/session?" + urlencode(query))
        rows = page["data"]
        if not isinstance(rows, list):
            raise ValueError("invalid session inventory")
        for row in rows:
            if row["id"] in result:
                raise ValueError("duplicate session in inventory; retry snapshot")
            result[row["id"]] = row
        cursor = page.get("cursor", {}).get("next")
        if not cursor:
            return result
        if cursor in seen or not rows:
            raise ValueError("incomplete/repeated session pagination")
        seen.add(cursor)
    raise ValueError("session pagination exceeds 1000 pages")


def family(root_id, sessions):
    ids = {root_id}
    while True:
        more = {s["id"] for s in sessions.values() if s.get("parentID") in ids}
        if more <= ids:
            return ids
        ids |= more


def pending(sid):
    for kind in ("form", "permission"):
        rows = api(f"/api/session/{sid}/{kind}")["data"]
        if not isinstance(rows, list):
            raise ValueError("invalid pending request inventory")
        if rows:
            return True
    return False


def collect():
    sessions = inventory()
    active = api("/api/session/active")["data"]
    if not isinstance(active, dict):
        raise ValueError("invalid active session inventory")
    roots, projects, errors, checked = {}, {}, {}, []
    for sid, s in sessions.items():
        meta = s.get("metadata", {}).get(KEY)
        if meta is None:
            continue
        try:
            r = reservation(meta)
        except (ValueError, TypeError) as exc:
            root = (
                meta.get("project", "unknown") if isinstance(meta, dict) else "unknown"
            )
            errors[root] = clean(exc)
            continue
        if r["session"] == sid:
            roots[sid] = r
        elif r["session"] not in sessions or sid not in family(r["session"], sessions):
            raise ValueError("dispatcher metadata without confirmed native ancestry")
        elif not same(
            r, reservation(sessions[r["session"]].get("metadata", {}).get(KEY))
        ):
            raise ValueError("inconsistent inherited dispatcher metadata")

    needed = set().union(*(family(sid, sessions) for sid in roots)) if roots else set()
    with ThreadPoolExecutor(max_workers=4) as pool:
        waits = dict(zip(sorted(needed), pool.map(pending, sorted(needed))))
    for root in sorted({r["project"] for r in roots.values()}):
        if root in errors:
            continue
        try:
            project = collect_project(root, roots, sessions, active, waits)
            checked.append(root)
            if project:
                projects[root] = project
        except (
            RuntimeError,
            ValueError,
            KeyError,
            OSError,
            subprocess.SubprocessError,
        ) as exc:
            errors[root] = clean(exc)
    return {"projects": projects, "errors": errors, "checked": checked}


def collect_project(root, roots, sessions, active, waits):
    if str(Path(root).resolve(strict=True)) != root:
        raise ValueError(f"project path changed: {clean(root)}")
    where = bd(root, "where")
    if Path(where["path"]).resolve() != Path(root, ".beads").resolve():
        raise ValueError("Beads directory does not match project")
    issues = bd(root, "list", "--all", "--limit", "0", "--flat")
    tasks = {t["id"]: t for t in issues}
    if len(tasks) != len(issues):
        raise ValueError("duplicate Beads task")
    rows = []
    for sid, r in roots.items():
        if r["project"] != root:
            continue
        task = tasks.get(r["task"])
        if task is None or not same(r, reservation(task.get("metadata", {}).get(KEY))):
            raise ValueError(f"missing/mismatched Beads link: {clean(r['task'])}")
        ids = family(sid, sessions)
        running = any(i in active for i in ids)
        waiting = any(waits[i] for i in ids)
        if task["status"] == "closed" and not running and not waiting:
            continue
        state = (
            "WAITING_USER"
            if waiting
            else "RUNNING"
            if running
            else "FAILED"
            if any(sessions[i].get("outcome") == "failed" for i in ids)
            else "PAUSED"
        )
        if task["status"] == "closed":
            state = "INCONSISTENT"
        rows.append(
            {
                "session": sid,
                "task": r["task"],
                "title": clean(task.get("title", r["task"])),
                "state": state,
                "created": sessions[sid].get("time", {}).get("created", 0),
            }
        )
    if rows:
        return {
            "id": identity(root),
            "name": clean(Path(root).name),
            "path": root,
            "workspace": "mis-" + identity(root),
            "tasks": sorted(rows, key=lambda t: (t["created"], t["session"])),
        }
    return None


def choose_slots(old, tasks, selected=None, focused=None):
    valid = {t["session"] for t in tasks}
    slots = [(sid if sid in valid else None) for sid in old[:4]]
    slots += [None] * (4 - len(slots))
    if selected is not None:
        if selected not in valid:
            raise ValueError("session is no longer available")
        if selected not in slots:
            index = (
                slots.index(None)
                if None in slots
                else focused
                if focused in range(4)
                else 0
            )
            slots[index] = selected
    for t in tasks:
        sid = t["session"]
        if sid not in slots and None in slots:
            slots[slots.index(None)] = sid
    return slots


def selection_snapshot(state, sid):
    """Selection need not rescan thousands of historical sessions; revalidate its exact link."""
    if not SESSION.fullmatch(sid):
        raise ValueError("invalid selected session")
    projects = json.loads(json.dumps(state["projects"]))
    project = next(
        (p for p in projects.values() if any(t["session"] == sid for t in p["tasks"])),
        None,
    )
    if project is None or project.get("stale"):
        raise ValueError("selected session unavailable or stale")
    session = api("/api/session/" + sid)["data"]
    r = reservation(session.get("metadata", {}).get(KEY))
    if session["id"] != sid or r["session"] != sid or r["project"] != project["path"]:
        raise ValueError("selected session link changed")
    rows = bd(project["path"], "show", r["task"])
    if (
        len(rows) != 1
        or rows[0]["id"] != r["task"]
        or not same(r, reservation(rows[0].get("metadata", {}).get(KEY)))
    ):
        raise ValueError("selected Beads link changed")
    return {
        "projects": projects,
        "errors": state.get("errors", {}),
        "checked": list(projects),
    }


def runtime_dir():
    base = os.environ.get("XDG_RUNTIME_DIR")
    if not base:
        raise RuntimeError("XDG_RUNTIME_DIR is required")
    path = Path(base, "mis-sessions")
    path.mkdir(mode=0o700, exist_ok=True)
    if (
        path.is_symlink()
        or path.stat().st_uid != os.getuid()
        or path.stat().st_mode & 0o077
    ):
        raise RuntimeError("unsafe MIS Sessions runtime directory")
    return path


def read_state(path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {"projects": {}, "enabled": True}


def save(path, data):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".state-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def hypr(command):
    return json.loads(run(["hyprctl", "-j", command], timeout=8))


def dispatch(expr):
    result = run(["hyprctl", "dispatch", expr], timeout=8).strip()
    if result != "ok":
        raise RuntimeError("Hyprland: " + result[:500])


def window_class(project_id, slot):
    return f"mis.sessions.{project_id}.{slot}"


def owned_windows(project, clients):
    result = {}
    for c in clients:
        for slot in range(4):
            expected = window_class(project["id"], slot)
            if c.get("initialClass") == expected and c.get("class") == expected:
                try:
                    argv = (
                        Path(f"/proc/{int(c['pid'])}/cmdline").read_bytes().split(b"\0")
                    )
                except (OSError, ValueError, KeyError):
                    raise RuntimeError("cannot confirm pult window process")
                tail = [
                    str(HERE / "sessions.py").encode(),
                    b"viewer",
                    project["id"].encode(),
                    str(slot).encode(),
                    b"",
                ]
                if argv[-5:] != tail:
                    raise RuntimeError(
                        "window class matches but process is not a pult viewer"
                    )
                if slot in result:
                    raise RuntimeError(
                        "duplicate pult window; refusing ambiguous ownership"
                    )
                if not ADDRESS.fullmatch(c.get("address", "")):
                    raise ValueError("invalid window address")
                result[slot] = c
    return result


def reconcile(state, projects, clients, selected=None, selected_slot=None):
    old_projects = state.get("projects", {})
    active = next((c for c in clients if c.get("focusHistoryID") == 0), None)
    for root, project in projects.items():
        if project.get("stale"):
            continue
        old = old_projects.get(root, {})
        windows = owned_windows(project, clients)
        focused = old.get("focused", 0)
        for slot, c in windows.items():
            if active and c["address"] == active["address"]:
                focused = slot
        if selected_slot is not None and selected in {
            t["session"] for t in project["tasks"]
        }:
            focused = selected_slot
        picking = (
            selected if selected in {t["session"] for t in project["tasks"]} else None
        )
        project["slots"] = choose_slots(
            old.get("slots", []), project["tasks"], picking, focused
        )
        project["focused"] = project["slots"].index(picking) if picking else focused
        # Persist assignments before launching viewers; viewers never read task text as commands.
    state["projects"] = projects
    return state


def apply_windows(state, old_projects, clients, selected=None):
    # Missing setup must not scatter new windows over an arbitrary desktop layout.
    result = run(
        [
            "hyprctl",
            "eval",
            'assert(_G.mis_sessions_layout_loaded, "Load MIS Sessions layout.lua in Hyprland first")',
        ],
        timeout=8,
    ).strip()
    if result != "ok":
        raise RuntimeError("MIS Sessions layout is not loaded")
    for root, project in {**old_projects, **state["projects"]}.items():
        current = state["projects"].get(root)
        if current and current.get("stale"):
            continue
        windows = owned_windows(project, clients)
        slots = current["slots"] if current else [None] * 4
        for slot, sid in enumerate(slots):
            window = windows.get(slot)
            if sid and not window:
                # Launch rules prevent map-time focus stealing and target only this process.
                command = shlex.join(
                    [
                        "kitty",
                        "--class",
                        window_class(project["id"], slot),
                        "--title",
                        f"MIS · {project['name']} · {slot + 1}",
                        "--directory",
                        root,
                        "--session",
                        "none",
                        "/usr/bin/python3",
                        "-B",
                        str(HERE / "sessions.py"),
                        "viewer",
                        project["id"],
                        str(slot),
                    ]
                )
                rules = {
                    "workspace": "name:" + project["workspace"] + " silent",
                    "no_initial_focus": True,
                    "tile": True,
                    "group": "barred",
                }
                dispatch(
                    "hl.dsp.exec_cmd("
                    + lua_string(command)
                    + ", "
                    + lua_table(rules)
                    + ")"
                )
            elif not sid and window:
                dispatch(
                    "hl.dsp.window.close({window="
                    + lua_string("address:" + window["address"])
                    + "})"
                )
        if selected and current and selected in slots:
            slot = slots.index(selected)
            dispatch(
                "hl.dsp.focus({workspace="
                + lua_string("name:" + project["workspace"])
                + "})"
            )
            if slot in windows:
                dispatch(
                    "hl.dsp.focus({window="
                    + lua_string("address:" + windows[slot]["address"])
                    + "})"
                )


def lua_string(value):
    # JSON and Lua disagree about \u escapes; decimal byte escapes are unambiguous.
    return (
        '"'
        + "".join(
            chr(b) if 32 <= b < 127 and chr(b) not in '\\"' else f"\\{b:03d}"
            for b in value.encode()
        )
        + '"'
    )


def focus_project(state, project_id):
    project = next(
        (p for p in state["projects"].values() if p["id"] == project_id), None
    )
    if project is None:
        raise ValueError("project no longer available")
    windows = owned_windows(project, hypr("clients"))
    if not windows:
        raise ValueError("project has no viewer windows yet")
    window = windows.get(project.get("focused", 0), next(iter(windows.values())))
    dispatch(
        "hl.dsp.focus({workspace=" + lua_string("name:" + project["workspace"]) + "})"
    )
    dispatch(
        "hl.dsp.focus({window=" + lua_string("address:" + window["address"]) + "})"
    )


def lua_table(values):
    return (
        "{"
        + ",".join(
            k + "=" + ("true" if v is True else lua_string(v))
            for k, v in values.items()
        )
        + "}"
    )


def terminate_viewer_child(child):
    if child and child.poll() is None:
        # Never Ctrl+C, an API interrupt, or killpg: only this local TUI process.
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)


def viewer(project_id, slot):
    if not re.fullmatch(r"[0-9a-f]{16}", project_id) or slot not in range(4):
        raise ValueError("invalid viewer slot")
    path = runtime_dir() / "state.json"
    child, last = None, None
    original = termios.tcgetattr(sys.stdin.fileno())

    def stop(_signal, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)
    try:
        while True:
            state = read_state(path)
            project = next(
                (p for p in state["projects"].values() if p["id"] == project_id), None
            )
            sid = project["slots"][slot] if project else None
            if sid != last:
                terminate_viewer_child(child)
                child = None
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, original)
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.flush()
                if sid:
                    # --session creates unknown IDs, so always verify exact existing session first.
                    session = api("/api/session/" + sid)["data"]
                    r = reservation(session.get("metadata", {}).get(KEY))
                    if (
                        session["id"] != sid
                        or r["session"] != sid
                        or r["project"] != project["path"]
                    ):
                        raise ValueError("viewer session metadata changed")
                    child = subprocess.Popen(
                        ["opencode", project["path"], "--session", sid]
                    )
                last = sid
            if sid is None or (child and child.poll() is not None):
                return
            time.sleep(0.4)
    finally:
        terminate_viewer_child(child)
        try:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, original)
        except termios.error:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan", help="read-only snapshot, no windows or runtime state")
    sub.add_parser("tick", help="refresh snapshot and the four viewer slots")
    select = sub.add_parser(
        "select", help="show an existing session in the selected slot"
    )
    select.add_argument("session")
    project = sub.add_parser("project", help="focus an existing project's desktop")
    project.add_argument("project")
    sub.add_parser(
        "pause", help="pause automatic refresh; leave all sessions/windows running"
    )
    view = sub.add_parser("viewer", help=argparse.SUPPRESS)
    view.add_argument("project")
    view.add_argument("slot", type=int)
    args = parser.parse_args()
    if args.command == "viewer":
        viewer(args.project, args.slot)
        return
    if args.command == "scan":
        print(json.dumps(collect(), ensure_ascii=False))
        return
    directory = runtime_dir()
    lock = os.open(directory / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock)
        print(json.dumps({"busy": True}))
        return
    try:
        path = directory / "state.json"
        state = read_state(path)
        if args.command == "project":
            focus_project(state, args.project)
        elif args.command == "pause":
            state["enabled"] = False
            save(path, state)
        else:
            try:
                snapshot = (
                    selection_snapshot(state, args.session)
                    if args.command == "select"
                    else collect()
                )
                projects = snapshot["projects"]
                clients = hypr("clients")
                old = state["projects"]
                for root in old:
                    if root not in projects and root not in snapshot["checked"]:
                        snapshot["errors"].setdefault(
                            root, "dispatcher link is missing from snapshot"
                        )
                for root in snapshot["errors"]:
                    if root in old:
                        projects[root] = {**old[root], "stale": True}
                selected = args.session if args.command == "select" else None
                if selected and any(
                    p.get("stale") and selected in p.get("slots", [])
                    for p in projects.values()
                ):
                    raise ValueError("project snapshot is stale; selection disabled")
                if selected and not any(
                    selected == t["session"]
                    for p in projects.values()
                    for t in p["tasks"]
                ):
                    raise ValueError("selected session is unavailable")
                if not state.get("enabled", True) and not selected:
                    state["error"] = (
                        "Automatic windows paused; select a session to resume"
                    )
                else:
                    state = reconcile(state, projects, clients, selected)
                    state.update(
                        enabled=True,
                        error="",
                        errors=snapshot["errors"],
                        updated=time.time(),
                    )
                    save(path, state)
                    apply_windows(state, old, clients, selected)
            except (
                RuntimeError,
                ValueError,
                KeyError,
                OSError,
                subprocess.SubprocessError,
            ) as e:
                state["error"] = clean(e)
            save(path, state)
        print(json.dumps(state, ensure_ascii=False))
    finally:
        os.close(lock)


if __name__ == "__main__":
    try:
        main()
    except (
        RuntimeError,
        ValueError,
        KeyError,
        OSError,
        subprocess.SubprocessError,
    ) as exc:
        print(json.dumps({"error": clean(exc)}), file=sys.stderr)
        sys.exit(1)

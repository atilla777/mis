#!/usr/bin/env python3
"""Opt-in actual four-viewer/fifth-session switch. Disposable sessions, no model calls."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sessions", ROOT / "integrations/omarchy/mis.sessions/sessions.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def api_write(method, path, body=None):
    args = ["opencode", "api", method, path]
    if body is not None:
        args += ["--data", json.dumps(body)]
    text = m.run(args)
    return json.loads(text) if text.strip() else None


def wait_for(fn, description):
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        result = fn()
        if result:
            return result
        time.sleep(0.3)
    raise RuntimeError("timed out: " + description)


def descendant_args(pid):
    result = []
    try:
        children = Path(f"/proc/{pid}/task/{pid}/children").read_text().split()
    except FileNotFoundError:
        return result
    for child in children:
        try:
            result.append(Path(f"/proc/{child}/cmdline").read_bytes().split(b"\0"))
            result += descendant_args(child)
        except FileNotFoundError:
            pass
    return result


def main():
    directory = m.runtime_dir()
    state_path = directory / "state.json"
    if state_path.exists():
        raise RuntimeError(
            "refusing to overwrite existing pult state; run before installation"
        )
    created = []
    project = None
    previous = m.hypr("activewindow").get("address")
    with tempfile.TemporaryDirectory(
        prefix="mis-viewer-probe-", dir="/tmp/opencode"
    ) as root:
        subprocess.run(["git", "init", "-q", root], check=True)
        try:
            subprocess.run(
                [
                    "hyprctl",
                    "eval",
                    "dofile("
                    + m.lua_string(
                        str(ROOT / "integrations/omarchy/mis.sessions/layout.lua")
                    )
                    + ")",
                ],
                check=True,
                capture_output=True,
            )
            rows = []
            for i in range(5):
                sid = "ses_mis_probe_" + uuid.uuid4().hex
                metadata = {
                    "version": 1,
                    "project": root,
                    "task": "probe-" + str(i),
                    "session": sid,
                    "phase": "submitted",
                }
                api_write(
                    "post",
                    "/api/session",
                    {
                        "id": sid,
                        "title": "MIS disposable viewer probe",
                        "location": {"directory": root},
                        "metadata": {m.KEY: metadata},
                    },
                )
                created.append(sid)
                rows.append(
                    {
                        "session": sid,
                        "task": metadata["task"],
                        "title": "Probe",
                        "state": "PAUSED",
                        "created": i,
                    }
                )
            project = {
                "id": m.identity(root),
                "name": "Disposable MIS viewer probe",
                "path": root,
                "workspace": "mis-" + m.identity(root),
                "tasks": rows,
            }
            state = m.reconcile({"projects": {}}, {root: project}, [])
            m.save(state_path, state)
            m.apply_windows(state, {}, m.hypr("clients"))
            windows = wait_for(
                lambda: (
                    w
                    if len(w := m.owned_windows(project, m.hypr("clients"))) == 4
                    else None
                ),
                "four viewer windows",
            )
            for i, window in windows.items():
                wait_for(
                    lambda i=i, window=window: any(
                        created[i].encode() in args
                        for args in descendant_args(window["pid"])
                    ),
                    "attached slot " + str(i),
                )
            addresses = {i: w["address"] for i, w in windows.items()}
            old = json.loads(json.dumps(state["projects"]))
            state = m.reconcile(
                state, {root: {**project}}, m.hypr("clients"), created[4], 2
            )
            m.save(state_path, state)
            m.apply_windows(state, old, m.hypr("clients"), created[4])
            if m.hypr("activewindow").get("address") != windows[2]["address"]:
                raise RuntimeError("selection did not focus the selected slot")
            wait_for(
                lambda: any(
                    created[4].encode() in args
                    for args in descendant_args(windows[2]["pid"])
                ),
                "fifth session in slot three",
            )
            if any(
                created[2].encode() in args
                for args in descendant_args(windows[2]["pid"])
            ):
                raise RuntimeError("old TUI still occupies replaced slot")
            after = m.owned_windows(project, m.hypr("clients"))
            if addresses != {i: w["address"] for i, w in after.items()}:
                raise RuntimeError("replacement recreated desktop windows")
            for sid in created:
                if m.api("/api/session/" + sid)["data"]["id"] != sid:
                    raise RuntimeError("server session lost")
            # Confirm completed project removes only its own four windows.
            old = state["projects"]
            state["projects"] = {}
            m.save(state_path, state)
            m.apply_windows(state, old, m.hypr("clients"))
            wait_for(
                lambda: not m.owned_windows(project, m.hypr("clients")),
                "closed viewer windows",
            )
            print(
                "PASS: four real TUI viewers, fifth session replaces selected slot in-place, all five server sessions survive, empty project removes windows; no model calls"
            )
        finally:
            if project:
                m.save(state_path, {"projects": {}})
                for window in m.owned_windows(project, m.hypr("clients")).values():
                    m.dispatch(
                        "hl.dsp.window.close({window="
                        + m.lua_string("address:" + window["address"])
                        + "})"
                    )
                time.sleep(1)
            state_path.unlink(missing_ok=True)
            for sid in created:
                api_write("delete", "/api/session/" + sid)
            if previous and any(c["address"] == previous for c in m.hypr("clients")):
                m.dispatch(
                    "hl.dsp.focus({window=" + m.lua_string("address:" + previous) + "})"
                )


if __name__ == "__main__":
    main()

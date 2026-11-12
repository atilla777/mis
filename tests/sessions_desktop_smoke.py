#!/usr/bin/env python3
"""Opt-in four dummy Kitty windows on a disposable named workspace; no AI sessions."""

import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sessions", ROOT / "integrations/omarchy/mis.sessions/sessions.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def main():
    token = uuid.uuid4().hex[:12]
    workspace = "mis-probe-" + token
    prefix = "mis.probe." + token + "."
    previous = m.hypr("activewindow").get("address")
    subprocess.run(
        [
            "hyprctl",
            "eval",
            "dofile("
            + m.lua_string(str(ROOT / "integrations/omarchy/mis.sessions/layout.lua"))
            + ")",
        ],
        check=True,
        capture_output=True,
    )
    try:
        for i in range(4):
            command = shlex.join(
                [
                    "kitty",
                    "--class",
                    prefix + str(i),
                    "--title",
                    "MIS layout probe",
                    "--session",
                    "none",
                    "sh",
                    "-c",
                    "sleep 120",
                ]
            )
            m.dispatch(
                "hl.dsp.exec_cmd("
                + m.lua_string(command)
                + ", "
                + m.lua_table(
                    {
                        "workspace": "name:" + workspace + " silent",
                        "no_initial_focus": True,
                        "tile": True,
                        "group": "barred",
                    }
                )
                + ")"
            )
        deadline = time.monotonic() + 15
        clients = []
        while time.monotonic() < deadline:
            clients = [
                c
                for c in m.hypr("clients")
                if c.get("initialClass", "").startswith(prefix)
            ]
            if len(clients) == 4:
                break
            time.sleep(0.2)
        if len(clients) != 4:
            raise RuntimeError("four probe windows did not appear")
        time.sleep(1)
        clients = [
            c for c in m.hypr("clients") if c.get("initialClass", "").startswith(prefix)
        ]
        if (
            len({tuple(c["at"]) for c in clients}) != 4
            or len({c["at"][0] for c in clients}) != 2
            or len({c["at"][1] for c in clients}) != 2
        ):
            raise RuntimeError(
                "not a 2x2 grid: " + json.dumps([(c["at"], c["size"]) for c in clients])
            )
        if any(c["workspace"]["name"] != workspace for c in clients):
            raise RuntimeError("probe window escaped workspace")
        now = m.hypr("activewindow").get("address")
        if previous and now != previous:
            raise RuntimeError("background launch stole focus")
        target = "address:" + clients[0]["address"]
        m.dispatch(
            "hl.dsp.window.fullscreen({window="
            + m.lua_string(target)
            + ',mode="fullscreen",action="set"})'
        )
        time.sleep(0.4)
        full = next(
            c for c in m.hypr("clients") if c["address"] == clients[0]["address"]
        )
        if not full.get("fullscreen"):
            raise RuntimeError("fullscreen did not activate")
        m.dispatch(
            "hl.dsp.window.fullscreen({window="
            + m.lua_string(target)
            + ',mode="fullscreen",action="unset"})'
        )
        time.sleep(0.4)
        restored = next(
            c for c in m.hypr("clients") if c["address"] == clients[0]["address"]
        )
        if restored["size"] != clients[0]["size"]:
            raise RuntimeError("grid did not restore after fullscreen")
        print(
            "PASS: four native windows, 2x2 grid, fullscreen/restore, no launch-time focus stealing"
        )
    finally:
        for c in m.hypr("clients"):
            if c.get("initialClass", "").startswith(prefix):
                m.dispatch(
                    "hl.dsp.window.close({window="
                    + m.lua_string("address:" + c["address"])
                    + "})"
                )
        if previous and any(c["address"] == previous for c in m.hypr("clients")):
            m.dispatch(
                "hl.dsp.focus({window=" + m.lua_string("address:" + previous) + "})"
            )


if __name__ == "__main__":
    main()

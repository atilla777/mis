#!/usr/bin/env python3
"""Opt-in real OpenCode client-disconnect probe. Disposable session; no LLM calls."""

import fcntl
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import tempfile
import termios
import threading
import time


def api(method, path, body=None):
    args = ["opencode", "api", method, path]
    if body is not None:
        args += ["--data", json.dumps(body)]
    with tempfile.TemporaryFile(dir="/tmp/opencode") as f:
        subprocess.run(args, stdout=f, stderr=subprocess.PIPE, check=True, timeout=40)
        f.seek(0)
        text = f.read()
        return json.loads(text) if text.strip() else None


def main():
    with tempfile.TemporaryDirectory(
        prefix="mis-client-probe-", dir="/tmp/opencode"
    ) as root:
        subprocess.run(["git", "init", "-q", root], check=True)
        session = api(
            "post",
            "/api/session",
            {
                "title": "MIS disposable disconnect probe",
                "location": {"directory": root},
            },
        )["data"]["id"]
        marker = Path(root, "shell-finished")
        failures = []

        def shell():
            try:
                # Fixed command, disposable cwd. No prompt/model and no writes outside fixture.
                api(
                    "post",
                    f"/api/session/{session}/shell",
                    {"command": "sleep 12; printf finished > shell-finished"},
                )
            except Exception as exc:
                failures.append(str(exc))

        thread = threading.Thread(target=shell)
        child = None
        master, slave = pty.openpty()

        def setup():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        try:
            thread.start()
            child = subprocess.Popen(
                ["opencode", root, "--session", session],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                preexec_fn=setup,
            )
            os.close(slave)
            output = bytearray()
            until = time.monotonic() + 5
            while time.monotonic() < until:
                if select.select([master], [], [], 0.2)[0]:
                    output.extend(os.read(master, 65536))
            if child.poll() is not None or len(output) < 100:
                raise RuntimeError("TUI did not stay attached")
            if marker.exists():
                raise RuntimeError("probe shell finished before client termination")
            child.terminate()  # Same local-only termination used by the pult.
            child.wait(timeout=8)
            thread.join(timeout=25)
            if (
                thread.is_alive()
                or failures
                or not marker.exists()
                or marker.read_text() != "finished"
            ):
                raise RuntimeError(
                    "server-side shell did not survive TUI termination: "
                    + str(failures)
                )
            if api("get", f"/api/session/{session}")["data"]["id"] != session:
                raise RuntimeError("session disappeared")
            print(
                "PASS: attached TUI terminated; server-side shell completed; session retained; no LLM calls"
            )
        finally:
            if child and child.poll() is None:
                child.terminate()
                child.wait(timeout=8)
            os.close(master)
            thread.join(timeout=30)
            if not thread.is_alive():
                api("delete", f"/api/session/{session}")


if __name__ == "__main__":
    main()

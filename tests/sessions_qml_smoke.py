#!/usr/bin/env python3
"""Load plugin with the real Omarchy components, without enabling or running it."""

import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(
        prefix="mis-qml-", dir="/tmp/opencode"
    ) as directory:
        base = Path(directory)
        for name in ["Commons", "Ui"]:
            (base / name).symlink_to(
                Path("/usr/share/omarchy/shell", name), target_is_directory=True
            )
        (base / "shell.qml").write_text(
            """
import QtQuick
import Quickshell
ShellRoot {
  Item {
    id: holder
    Component.onCompleted: {
      var component = Qt.createComponent("file://SOURCE")
      if (component.status !== Component.Ready) throw new Error(component.errorString())
      var widget = component.createObject(holder, {settings: {automatic: false}})
      if (!widget) throw new Error("widget creation failed")
      widget.snapshot = {projects: {test: {name: "Test", path: "/test", slots: ["ses_test"], tasks: [{session: "ses_test", task: "p-1", title: "Тест", state: "WAITING_USER"}]}}, errors: {}}
      if (widget.projects.length !== 1 || widget.waiting !== 1) throw new Error("model failed")
      console.log("MIS_QML_PASS")
    }
  }
  Timer { interval: 1500; running: true; onTriggered: Qt.quit() }
}
""".replace("SOURCE", str(ROOT / "integrations/omarchy/mis.sessions/BarWidget.qml"))
        )
        env = {**os.environ, "QT_QPA_PLATFORM": "wayland"}
        result = subprocess.run(
            ["quickshell", "--no-color", "--path", str(base)],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15,
        )
        print(result.stdout)
        if (
            result.returncode
            or "MIS_QML_PASS" not in result.stdout
            or "Error:" in result.stdout
        ):
            raise RuntimeError("QML load/model smoke failed")


if __name__ == "__main__":
    main()

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
import qs.Commons
ShellRoot {
  Item {
    id: holder
    Component.onCompleted: {
      var component = Qt.createComponent("file://SOURCE")
      if (component.status !== Component.Ready) throw new Error(component.errorString())
      var widget = component.createObject(holder, {settings: {automatic: false}})
      if (!widget) throw new Error("widget creation failed")
      function assert(value, message) { if (!value) throw new Error(message) }
      function project(name, states, stale) {
        return {name: name, path: "/" + name, slots: [], stale: !!stale,
          tasks: states.map((state, i) => ({session: "ses_" + name + i, task: name + i, title: "Тест", state: state}))}
      }
      assert(widget.indicatorText === "MIS", "empty indicator")
      widget.snapshot = {projects: {one: project("one", ["RUNNING", "RUNNING"])}, errors: {}}
      assert(widget.running === 2 && widget.indicatorText === "MIS ▶ 2", "running indicator")
      assert(widget.indicatorColor.toString() === Color.accent.toString(), "running color")
      widget.snapshot = {projects: {one: project("one", ["PAUSED"])}, errors: {}}
      assert(widget.indicatorText === "MIS Ⅱ 1", "paused indicator")
      widget.snapshot = {projects: {
        one: project("one", ["RUNNING", "WAITING_USER", "FAILED", "INCONSISTENT"]),
        two: project("two", ["WAITING_USER", "PAUSED"])
      }, errors: {}}
      assert(widget.waiting === 2 && widget.failed === 2, "separate question/error counts")
      assert(widget.indicatorText === "MIS ? 2 ! 2 ▶ 1 Ⅱ 1", "combined indicator")
      assert(widget.indicatorColor.toString() === Color.urgent.toString(), "attention color priority")
      assert(widget.projectText(widget.projects[0]) === "one · 4 · ? 1", "project questions")
      assert(widget.stateText("WAITING_USER").indexOf("Ждёт вашего ответа") >= 0, "question label")
      assert(widget.indicatorTooltip.indexOf("ждут ответа: 2") >= 0, "question tooltip")
      widget.snapshot = {projects: {old: project("old", ["RUNNING", "WAITING_USER"], true)}, errors: {}}
      assert(widget.running === 0 && widget.waiting === 0 && widget.warning, "stale is not current")
      assert(widget.indicatorText === "MIS !" && widget.projectText(widget.projects[0]) === "old · 2 !", "stale indicator")
      widget.snapshot = {projects: {}, errors: {"/missing": "not found"}}
      assert(widget.indicatorText === "MIS !", "project error indicator")
      widget.snapshot = {projects: {one: project("one", ["RUNNING", "WAITING_USER"])}, errors: {}}
      widget.error = "disconnected"
      assert(widget.indicatorText === "MIS !" && widget.waiting === 0 && widget.running === 0, "global error is not current")
      widget.error = ""
      assert(widget.indicatorText === "MIS ? 1 ▶ 1", "global error recovery")
      widget.snapshot = {projects: {}, errors: {}}
      assert(widget.indicatorText === "MIS", "recovery indicator")
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

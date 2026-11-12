import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui as Ui

Ui.BarWidget {
  id: root
  moduleName: "mis.sessions"
  property var snapshot: ({projects: {}, errors: {}})
  property string error: ""
  property bool opened: false
  property string selectedProject: ""
  property int selectedTask: 0
  property var pendingAction: []
  readonly property string helper: decodeURIComponent(Qt.resolvedUrl("sessions.py").toString().replace(/^file:\/\//, ""))
  readonly property var projects: Object.values(snapshot.projects || {})
  readonly property var project: projects.find(p => p.path === selectedProject) || projects[0] || null
  readonly property var tasks: project ? project.tasks : []
  readonly property int waiting: countState("WAITING_USER")
  readonly property int running: countState("RUNNING")
  readonly property int paused: countState("PAUSED")
  readonly property int failed: countState("FAILED") + countState("INCONSISTENT")
  readonly property bool warning: error !== "" || Object.keys(snapshot.errors || {}).length > 0 || projects.some(p => p.stale)
  readonly property string indicatorText: "MIS"
    + (waiting ? " ? " + waiting : "")
    + (failed ? " ! " + failed : warning ? " !" : "")
    + (running ? " ▶ " + running : "")
    + (paused ? " Ⅱ " + paused : "")
  readonly property color indicatorColor: waiting || failed || warning ? Color.urgent
    : running ? Color.accent : root.bar ? root.bar.barForeground : Color.foreground
  readonly property string indicatorTooltip: "MIS Sessions · проектов: " + projects.length
    + " · работают: " + running + " · ждут ответа: " + waiting
    + " · на паузе: " + paused + " · ошибки задач: " + failed
    + (warning ? " · есть ошибки обновления; данные могут устареть" : "")

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  function projectCount(p, state) {
    return p && !p.stale && !root.error ? p.tasks.filter(t => t.state === state).length : 0
  }
  function countState(state) {
    return projects.reduce((n, p) => n + projectCount(p, state), 0)
  }
  function projectText(p) {
    var questions = projectCount(p, "WAITING_USER")
    return p.name + " · " + p.tasks.length + (questions ? " · ? " + questions : "") + (p.stale ? " !" : "")
  }
  function stateText(state) {
    switch (state) {
      case "WAITING_USER": return "? Ждёт вашего ответа или разрешения"
      case "RUNNING": return "▶ Работает"
      case "PAUSED": return "Ⅱ На паузе"
      case "FAILED": return "! Ошибка сессии"
      case "INCONSISTENT": return "! Состояние задачи и сессии не совпадает"
      default: return state
    }
  }

  function open() { opened = true; refresh() }
  function close() { opened = false }
  function toggle() { opened ? close() : open() }
  function refresh() { invoke(["tick"]) }
  function invoke(args) {
    if (worker.running) {
      if (args[0] !== "tick") pendingAction = args
      return
    }
    worker.command = ["/usr/bin/python3", "-B", helper].concat(args)
    worker.running = true
  }
  function selectSession(sid) {
    if (project && project.stale) return
    invoke(["select", sid])
    close()
  }
  function selectProject(p) {
    selectedProject = p.path
    selectedTask = 0
    invoke(["project", p.id])
  }

  Process {
    id: worker
    stdout: StdioCollector {
      onStreamFinished: {
        try {
          var result = JSON.parse(text)
          if (!result.busy) { root.snapshot = result; root.error = result.error || "" }
        } catch (e) { root.error = "Invalid helper response" }
      }
    }
    stderr: StdioCollector {
      onStreamFinished: if (text.trim()) root.error = text.trim().slice(0, 500)
    }
    onExited: function(code) {
      if (code !== 0 && !root.error) root.error = "MIS helper failed: " + code
      if (root.pendingAction.length) {
        var args = root.pendingAction
        root.pendingAction = []
        Qt.callLater(function() { root.invoke(args) })
      }
    }
  }

  Timer {
    interval: 15000
    repeat: true
    running: root.setting("automatic", true)
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  Ui.WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.indicatorText
    tooltipText: root.indicatorTooltip
    foreground: root.indicatorColor
    onPressed: function(b) {
      if (b === Qt.MiddleButton) root.refresh()
      else root.toggle()
    }
  }

  Ui.KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: catcher
    contentWidth: panel.fittedContentWidth(Style.space(540))
    contentHeight: panel.fittedContentHeight(Style.space(440))

    Ui.PanelKeyCatcher {
      id: catcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onMoveRequested: function(dx, dy) {
        if (dy && root.tasks.length) {
          root.selectedTask = Math.max(0, Math.min(root.tasks.length - 1, root.selectedTask + dy))
          taskList.positionViewAtIndex(root.selectedTask, ListView.Contain)
        }
        if (dx && root.projects.length) {
          var i = root.projects.findIndex(p => p.path === root.project.path)
          root.selectProject(root.projects[(i + dx + root.projects.length) % root.projects.length])
        }
      }
      onActivateRequested: if (root.tasks[root.selectedTask]) root.selectSession(root.tasks[root.selectedTask].session)
      onTextKey: function(t) { if (t === "r") root.refresh() }

      Column {
        anchors.fill: parent
        spacing: Style.space(10)
        Text {
          text: "MIS Sessions" + (worker.running ? " · обновление…" : "")
          color: Color.foreground
          font.pixelSize: Style.font.title
          font.bold: true
        }
        Text {
          width: parent.width
          visible: root.waiting > 0
          text: "? Ждут вашего ответа: " + root.waiting + ". Выберите проект с меткой ? и откройте задачу."
          color: Color.urgent
          wrapMode: Text.Wrap
        }
        Text {
          width: parent.width
          visible: root.warning || !root.projects.length
          text: root.error || (Object.keys(root.snapshot.errors || {}).length
            ? "Недоступные проекты: " + Object.keys(root.snapshot.errors).join(", ")
            : root.warning ? "Данные проектов устарели; дождитесь обновления"
            : "Нет незавершённых задач диспетчера")
          textFormat: Text.PlainText
          color: root.warning ? Color.urgent : Color.foreground
          wrapMode: Text.Wrap
          maximumLineCount: 3
          elide: Text.ElideRight
        }
        Flickable {
          width: parent.width
          height: Style.space(36)
          contentWidth: projectRow.width
          clip: true
          Row {
            id: projectRow
            spacing: Style.space(8)
            Repeater {
              model: root.projects
              delegate: Rectangle {
                required property var modelData
                width: projectLabel.implicitWidth + Style.space(18)
                height: Style.space(32)
                radius: Style.space(4)
                color: root.project && root.project.path === modelData.path ? Color.accent : Color.popups.background
                Text {
                  id: projectLabel
                  anchors.centerIn: parent
                  text: root.projectText(modelData)
                  textFormat: Text.PlainText
                  color: root.projectCount(modelData, "WAITING_USER") ? Color.urgent : Color.foreground
                  font.pixelSize: Style.font.body
                }
                MouseArea {
                  anchors.fill: parent
                  onClicked: root.selectProject(modelData)
                }
              }
            }
          }
        }
        Text {
          width: parent.width
          text: root.project ? root.project.path : ""
          textFormat: Text.PlainText
          elide: Text.ElideMiddle
          color: Color.foreground
          font.pixelSize: Style.font.caption
        }
        ListView {
          id: taskList
          width: parent.width
          height: Math.max(Style.space(80), catcher.height - y - Style.space(40))
          clip: true
          spacing: Style.space(4)
          model: root.tasks
          delegate: Rectangle {
            required property var modelData
            required property int index
            width: taskList.width
            height: Style.space(58)
            color: index === root.selectedTask ? Qt.darker(Color.accent, 1.8) : Color.popups.background
            radius: Style.space(4)
            Column {
              anchors.fill: parent
              anchors.margins: Style.space(6)
              Text {
                width: parent.width
                text: (root.project.slots.indexOf(modelData.session) >= 0 ? "▣ " : "○ ") + modelData.task + " · " + modelData.title
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: Color.foreground
                font.pixelSize: Style.font.body
              }
              Text {
                text: root.project.stale || root.error ? "! Данные устарели · " + root.stateText(modelData.state) : root.stateText(modelData.state)
                color: ["WAITING_USER", "FAILED", "INCONSISTENT"].indexOf(modelData.state) >= 0 ? Color.urgent : Color.foreground
                font.pixelSize: Style.font.caption
              }
            }
            MouseArea {
              anchors.fill: parent
              onClicked: { root.selectedTask = index; root.selectSession(modelData.session) }
            }
          }
        }
        Text {
          text: "Окна и полный экран — обычные сочетания Omarchy"
          color: Color.foreground
          font.pixelSize: Style.font.caption
        }
      }
    }
  }
}

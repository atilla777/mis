"""No desktop, Beads, OpenCode, model calls or user HOME writes."""

import copy
import contextlib
import importlib.util
import json
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "integrations/omarchy/mis.sessions/sessions.py"
)
spec = importlib.util.spec_from_file_location("sessions", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture(root, sid="ses_root", status="open"):
    r = dict(version=1, project=root, task="p-1", session=sid, phase="submitted")
    session = dict(id=sid, metadata={m.KEY: r}, time={"created": 1})
    task = dict(id="p-1", title="Task", status=status, metadata={m.KEY: json.dumps(r)})
    return session, task


class Slots(unittest.TestCase):
    def setUp(self):
        self.tasks = [{"session": "ses_" + str(i)} for i in range(6)]

    def test_first_four_and_stable_arrivals(self):
        slots = m.choose_slots([], self.tasks)
        self.assertEqual(slots, ["ses_0", "ses_1", "ses_2", "ses_3"])
        self.assertEqual(m.choose_slots(slots, list(reversed(self.tasks))), slots)

    def test_selection_replaces_focused_slot(self):
        slots = m.choose_slots([], self.tasks)
        self.assertEqual(
            m.choose_slots(slots, self.tasks, "ses_5", 2),
            ["ses_0", "ses_1", "ses_5", "ses_3"],
        )
        self.assertEqual(m.choose_slots(slots, self.tasks, "ses_1", 3), slots)

    def test_completed_fills_vacancy_and_empty_clears(self):
        old = m.choose_slots([], self.tasks)
        self.assertEqual(
            m.choose_slots(old, self.tasks[1:]), ["ses_4", "ses_1", "ses_2", "ses_3"]
        )
        self.assertEqual(m.choose_slots(old, []), [None] * 4)

    def test_missing_selection_rejected(self):
        with self.assertRaises(ValueError):
            m.choose_slots([], self.tasks, "ses_missing")


class Snapshot(unittest.TestCase):
    def collect(self, root, sessions, tasks, active=None, waits=None):
        def fake_bd(path, *args):
            self.assertEqual(root, path)
            return {"path": str(Path(root, ".beads"))} if args == ("where",) else tasks

        with (
            patch.object(m, "inventory", return_value=sessions),
            patch.object(m, "api", return_value={"data": active or {}}),
            patch.object(
                m, "pending", side_effect=lambda sid: (waits or {}).get(sid, False)
            ),
            patch.object(m, "bd", side_effect=fake_bd),
        ):
            return m.collect()

    def test_running_waiting_paused_failed_and_completion(self):
        with tempfile.TemporaryDirectory(dir="/tmp/opencode") as root:
            s, t = fixture(root)
            for state, active, waits, outcome in [
                ("RUNNING", {s["id"]: {}}, {}, None),
                ("WAITING_USER", {}, {s["id"]: True}, None),
                ("PAUSED", {}, {}, "succeeded"),
                ("FAILED", {}, {}, "failed"),
            ]:
                s["outcome"] = outcome
                snap = self.collect(root, {s["id"]: s}, [t], active, waits)
                self.assertEqual(snap["projects"][root]["tasks"][0]["state"], state)
            t["status"] = "closed"
            self.assertEqual(self.collect(root, {s["id"]: s}, [t])["projects"], {})
            snap = self.collect(root, {s["id"]: s}, [t], waits={s["id"]: True})
            self.assertEqual(
                snap["projects"][root]["tasks"][0]["state"], "INCONSISTENT"
            )

    def test_children_do_not_become_tiles(self):
        with tempfile.TemporaryDirectory(dir="/tmp/opencode") as root:
            s, t = fixture(root)
            child = {**s, "id": "ses_child", "parentID": s["id"]}
            snap = self.collect(
                root, {s["id"]: s, child["id"]: child}, [t], waits={child["id"]: True}
            )
            self.assertEqual(len(snap["projects"][root]["tasks"]), 1)
            self.assertEqual(
                snap["projects"][root]["tasks"][0]["state"], "WAITING_USER"
            )

    def test_bad_test_record_does_not_hide_working_project(self):
        with tempfile.TemporaryDirectory(dir="/tmp/opencode") as root:
            s, t = fixture(root)
            bad = {"id": "ses_oldtest", "metadata": {m.KEY: {"project": "/missing"}}}
            snap = self.collect(root, {s["id"]: s, bad["id"]: bad}, [t])
            self.assertIn(root, snap["projects"])
            self.assertIn("/missing", snap["errors"])

    def test_mismatched_beads_link_quarantines_project(self):
        with tempfile.TemporaryDirectory(dir="/tmp/opencode") as root:
            s, t = fixture(root)
            t["metadata"] = {}
            snap = self.collect(root, {s["id"]: s}, [t])
            self.assertFalse(snap["projects"])
            self.assertIn(root, snap["errors"])

    def test_orphan_metadata_is_not_trusted(self):
        s, _ = fixture("/project")
        s["id"] = "ses_orphan"
        with (
            patch.object(m, "inventory", return_value={s["id"]: s}),
            patch.object(m, "api", return_value={"data": {}}),
        ):
            with self.assertRaises(ValueError):
                m.collect()

    def test_cursor_failure_is_not_empty_success(self):
        pages = [
            {"data": [{"id": "ses_1"}], "cursor": {"next": "same"}},
            {"data": [{"id": "ses_2"}], "cursor": {"next": "same"}},
        ]
        with patch.object(m, "api", side_effect=pages):
            with self.assertRaises(ValueError):
                m.inventory()


class Safety(unittest.TestCase):
    def test_invalid_pending_shape_is_not_empty_success(self):
        with (
            patch.object(m, "api", return_value={"data": {}}),
            self.assertRaises(ValueError),
        ):
            m.pending("ses_root")

    def test_lookalike_window_is_not_owned(self):
        project = {"id": "a" * 16}
        name = m.window_class(project["id"], 0)
        client = {"class": name, "initialClass": name, "pid": 12345, "address": "0x123"}
        with (
            patch.object(Path, "read_bytes", return_value=b"kitty\0"),
            self.assertRaises(RuntimeError),
        ):
            m.owned_windows(project, [client])

    def test_bd_is_readonly_and_rejects_redirects(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(m, "run", return_value="[]") as run,
        ):
            m.bd("/project", "list")
            self.assertEqual(
                run.call_args.args[0],
                ["bd", "-C", "/project", "--readonly", "--json", "list"],
            )
        for key in ["BD_DB", "BEADS_DIR", "BEADS_DOLT_SERVER_DATABASE"]:
            with (
                patch.dict(os.environ, {key: "foreign"}),
                self.assertRaises(RuntimeError),
            ):
                m.bd("/project", "list")

    def test_api_only_gets(self):
        with patch.object(m, "run", return_value='{"data":[]}') as run:
            m.api("/api/session")
            self.assertEqual(
                run.call_args.args[0], ["opencode", "api", "get", "/api/session"]
            )

    def test_terminate_only_local_child(self):
        child = Mock()
        child.poll.return_value = None
        m.terminate_viewer_child(child)
        child.terminate.assert_called_once()
        child.kill.assert_not_called()

    def test_runtime_state_private_and_atomic(self):
        with (
            tempfile.TemporaryDirectory(dir="/tmp/opencode") as directory,
            patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}),
        ):
            runtime = m.runtime_dir()
            path = runtime / "state.json"
            m.save(path, {"projects": {}})
            self.assertEqual(m.read_state(path), {"projects": {}})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            runtime.chmod(0o755)
            with self.assertRaises(RuntimeError):
                m.runtime_dir()

    def test_lua_quotes_cannot_inject_commands(self):
        quoted = m.lua_string('русский"\\\n); malicious()')
        self.assertNotIn('"\\\n', quoted)
        self.assertIn("\\034", quoted)
        self.assertIn("\\010", quoted)

    def test_manual_window_not_owned(self):
        project = {"id": "a" * 16}
        self.assertEqual(
            m.owned_windows(project, [{"class": "kitty", "initialClass": "kitty"}]), {}
        )

    def test_projects_keep_separate_slots(self):
        projects = {
            "/a": {"id": "a", "tasks": [{"session": "ses_a"}]},
            "/b": {"id": "b", "tasks": [{"session": "ses_b"}]},
        }
        state = m.reconcile({"projects": {}}, projects, [], "ses_b")
        self.assertEqual(state["projects"]["/a"]["slots"], ["ses_a", None, None, None])
        self.assertEqual(state["projects"]["/b"]["slots"], ["ses_b", None, None, None])


class Refresh(unittest.TestCase):
    def setUp(self):
        self.project = {
            "id": "a" * 16,
            "path": "/project",
            "name": "project",
            "workspace": "mis-" + "a" * 16,
            "tasks": [{"session": "ses_root"}],
            "slots": ["ses_root", None, None, None],
            "focused": 0,
        }

    def call_main(self, snapshot=None, error=None, command=None):
        with tempfile.TemporaryDirectory(dir="/tmp/opencode") as directory:
            path = Path(directory, "state.json")
            m.save(
                path,
                {
                    "projects": {"/project": copy.deepcopy(self.project)},
                    "enabled": True,
                },
            )
            with (
                patch.object(m, "runtime_dir", return_value=Path(directory)),
                patch.object(m, "collect", return_value=snapshot, side_effect=error),
                patch.object(m, "hypr", return_value=[]),
                patch.object(m, "apply_windows") as apply,
                patch.object(m.sys, "argv", ["sessions.py", *(command or ["tick"])]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                m.main()
            return m.read_state(path), apply.call_args

    def test_global_error_preserves_assignments_and_does_not_touch_windows(self):
        state, call = self.call_main(error=RuntimeError("server unavailable"))
        self.assertEqual(state["projects"]["/project"]["slots"], self.project["slots"])
        self.assertIn("server unavailable", state["error"])
        self.assertIsNone(call)

    def test_project_error_keeps_stale_slots(self):
        state, _ = self.call_main(
            {"projects": {}, "errors": {"/project": "Beads unavailable"}, "checked": []}
        )
        self.assertTrue(state["projects"]["/project"]["stale"])
        self.assertEqual(state["projects"]["/project"]["slots"], self.project["slots"])

    def test_lost_dispatcher_link_is_not_completion(self):
        state, _ = self.call_main({"projects": {}, "errors": {}, "checked": []})
        self.assertTrue(state["projects"]["/project"]["stale"])

    def test_confirmed_completed_project_disappears(self):
        state, call = self.call_main(
            {"projects": {}, "errors": {}, "checked": ["/project"]}
        )
        self.assertEqual(state["projects"], {})
        self.assertIsNotNone(call)

    def test_pause_does_not_touch_windows(self):
        state, call = self.call_main(command=["pause"])
        self.assertFalse(state["enabled"])
        self.assertIsNone(call)

    def test_stale_project_never_launches_or_closes_windows(self):
        project = {**self.project, "stale": True}
        with (
            patch.object(m, "run", return_value="ok"),
            patch.object(m, "dispatch") as dispatch,
        ):
            m.apply_windows({"projects": {"/project": project}}, {}, [])
            dispatch.assert_not_called()

    def test_selection_revalidates_without_full_inventory(self):
        session, task = fixture("/project")
        state = {"projects": {"/project": self.project}}
        with (
            patch.object(m, "api", return_value={"data": session}),
            patch.object(m, "bd", return_value=[task]),
            patch.object(m, "inventory") as inventory,
        ):
            snap = m.selection_snapshot(state, "ses_root")
            self.assertIn("/project", snap["projects"])
            inventory.assert_not_called()


if __name__ == "__main__":
    unittest.main()

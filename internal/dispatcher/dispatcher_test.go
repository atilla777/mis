package dispatcher

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"
)

type fakeBeads struct {
	tasks   []Task
	blocked map[string]bool
	err     error
	saveErr bool
}

func (b *fakeBeads) List(context.Context) ([]Task, error) { return b.tasks, b.err }
func (b *fakeBeads) Ready(context.Context) ([]Task, error) {
	var ready []Task
	for _, t := range b.tasks {
		if t.Status == "open" && !b.blocked[t.ID] {
			ready = append(ready, t)
		}
	}
	return ready, b.err
}
func (b *fakeBeads) Get(_ context.Context, id string) (Task, error) {
	for _, t := range b.tasks {
		if t.ID == id {
			return t, b.err
		}
	}
	return Task{}, errors.New("missing task")
}
func (b *fakeBeads) Save(_ context.Context, t Task, r Reservation) error {
	if b.saveErr {
		return errors.New("lost metadata response")
	}
	for i := range b.tasks {
		if b.tasks[i].ID == t.ID {
			data, _ := json.Marshal(r)
			text, _ := json.Marshal(string(data))
			b.tasks[i].Metadata = map[string]json.RawMessage{MetadataKey: text}
			return nil
		}
	}
	return errors.New("missing task")
}

type fakeOpenCode struct {
	sessions                                       map[string]Session
	created, commands                              []string
	createErr, lostCreate, commandErr, snapshotErr bool
	onCommand                                      func()
}

func (o *fakeOpenCode) Snapshot(context.Context) (map[string]Session, error) {
	if o.snapshotErr {
		return nil, errors.New("offline")
	}
	return o.sessions, nil
}
func (o *fakeOpenCode) Create(_ context.Context, r Reservation) error {
	o.created = append(o.created, r.Task)
	if !o.createErr || o.lostCreate {
		data, _ := json.Marshal(r)
		o.sessions[r.Session] = Session{ID: r.Session, Metadata: map[string]json.RawMessage{MetadataKey: data}}
	}
	if o.createErr {
		return errors.New("lost create response")
	}
	return nil
}
func (o *fakeOpenCode) Lookup(_ context.Context, id string) (Session, error) {
	s, ok := o.sessions[id]
	if !ok {
		return s, errors.New("404")
	}
	return s, nil
}
func (o *fakeOpenCode) Command(_ context.Context, session, task string) error {
	o.commands = append(o.commands, task)
	if o.onCommand != nil {
		o.onCommand()
	}
	if o.commandErr {
		return errors.New("command response lost")
	}
	s := o.sessions[session]
	s.Running = true
	o.sessions[session] = s
	return nil
}

func fixture(count int) (*Dispatcher, *fakeBeads, *fakeOpenCode) {
	b := &fakeBeads{blocked: map[string]bool{}}
	for i := 0; i < count; i++ {
		b.tasks = append(b.tasks, Task{ID: fmt.Sprintf("test-%02d", i), Type: "task", Status: "open", Created: time.Unix(int64(i+1), 0)})
	}
	o := &fakeOpenCode{sessions: map[string]Session{}}
	i := 0
	d := &Dispatcher{Root: "/project", Beads: b, OpenCode: o, Out: io.Discard, NewID: func() (string, error) { i++; return fmt.Sprintf("ses_test%d", i), nil }}
	return d, b, o
}

var defaults = Config{60 * time.Second, 6, 12}

func TestScheduling(t *testing.T) {
	for _, count := range []int{0, 1, 9} {
		t.Run(fmt.Sprint(count), func(t *testing.T) {
			d, _, o := fixture(count)
			n, err := d.Cycle(context.Background(), defaults)
			if err != nil || n.Started != min(count, 6) {
				t.Fatalf("%+v %v", n, err)
			}
			_, err = d.Cycle(context.Background(), defaults)
			if err != nil || len(o.commands) != min(count, 6) {
				t.Fatalf("duplicate launch: %v %v", o.commands, err)
			}
		})
	}
}

func TestNativeDependenciesAndEligibility(t *testing.T) {
	d, b, o := fixture(6)
	b.blocked[b.tasks[0].ID] = true
	b.tasks[1].Assignee = "manual"
	b.tasks[2].Type = "epic"
	b.tasks[3].Created = time.Time{}
	b.tasks[4].Status = "deferred"
	_, err := d.Cycle(context.Background(), defaults)
	if err != nil || !reflect.DeepEqual(o.commands, []string{"test-05"}) {
		t.Fatalf("%v %v", o.commands, err)
	}
}

func TestOldestThenID(t *testing.T) {
	d, b, o := fixture(3)
	b.tasks[0].Created = time.Unix(10, 0)
	b.tasks[1].Created = time.Unix(1, 0)
	b.tasks[2].Created = time.Unix(1, 0)
	b.tasks[1], b.tasks[2] = b.tasks[2], b.tasks[1]
	_, err := d.Cycle(context.Background(), defaults)
	if err != nil || !reflect.DeepEqual(o.commands, []string{"test-01", "test-02", "test-00"}) {
		t.Fatalf("%v %v", o.commands, err)
	}
}

func TestCreateFailureAndLostResponse(t *testing.T) {
	for _, lost := range []bool{false, true} {
		t.Run(fmt.Sprint(lost), func(t *testing.T) {
			d, _, o := fixture(1)
			o.createErr = true
			o.lostCreate = lost
			_, err := d.Cycle(context.Background(), defaults)
			if (err == nil) != lost {
				t.Fatal(err)
			}
			// A fresh dispatcher recovers Beads/session linkage without local state.
			d2 := *d
			_, _ = d2.Cycle(context.Background(), defaults)
			if len(o.created) != 1 || len(o.commands) != map[bool]int{false: 0, true: 1}[lost] {
				t.Fatalf("duplicate/incorrect create: %+v", o)
			}
		})
	}
}

func TestAtMostOnceCommandAndReservationError(t *testing.T) {
	d, b, o := fixture(1)
	o.commandErr = true
	if _, err := d.Cycle(context.Background(), defaults); err == nil {
		t.Fatal("expected uncertain command")
	}
	_, _ = d.Cycle(context.Background(), defaults)
	if len(o.commands) != 1 || len(o.created) != 1 {
		t.Fatal("retried unknown command")
	}
	r, _ := b.tasks[0].Reservation()
	if r.Phase != "submitted" {
		t.Fatal(r)
	}
	d, b, o = fixture(1)
	b.saveErr = true
	if _, err := d.Cycle(context.Background(), defaults); err == nil || len(o.created) != 0 {
		t.Fatal("create without durable reservation")
	}
}

func TestInteractiveStatesAndManualResume(t *testing.T) {
	d, b, o := fixture(2)
	cfg := Config{time.Second, 1, 2}
	_, _ = d.Cycle(context.Background(), cfg)
	r, _ := b.tasks[0].Reservation()
	s := o.sessions[r.Session]
	s.Waiting = true
	o.sessions[s.ID] = s
	n, err := d.Cycle(context.Background(), cfg)
	if err != nil || n.Active != 1 || n.Open != 2 || n.Started != 1 {
		t.Fatalf("waiting slots: %+v %v", n, err)
	}
	s.Waiting = false
	s.Running = false
	s.Outcome = "succeeded"
	o.sessions[s.ID] = s
	state, active, err := classify(b.tasks[0], *r, o.sessions)
	if err != nil || state != Paused || active {
		t.Fatalf("idle is not completion: %s", state)
	}
	s.Running = true
	o.sessions[s.ID] = s
	n, err = d.Cycle(context.Background(), cfg)
	if err != nil || n.Active != 2 || n.Started != 0 {
		t.Fatalf("manual resume: %+v %v", n, err)
	}
	s.Running = false
	s.Outcome = "failed"
	o.sessions[s.ID] = s
	state, active, err = classify(b.tasks[0], *r, o.sessions)
	if err != nil || state != Failed || active {
		t.Fatal(state, active, err)
	}
	b.tasks[0].Status = "closed"
	state, _, err = classify(b.tasks[0], *r, o.sessions)
	if err != nil || state != Completed {
		t.Fatal(state, err)
	}
}

func TestOpenLimitAndConfigReload(t *testing.T) {
	d, b, o := fixture(4)
	cfg := Config{time.Second, 6, 1}
	_, _ = d.Cycle(context.Background(), cfg)
	for id, s := range o.sessions {
		s.Running = false
		o.sessions[id] = s
	}
	n, err := d.Cycle(context.Background(), cfg)
	if err != nil || n.Started != 0 || n.Open != 1 {
		t.Fatal(n, err)
	}
	cfg.Open = 2
	n, err = d.Cycle(context.Background(), cfg)
	if err != nil || n.Started != 1 || n.Open != 2 {
		t.Fatal(n, err)
	}
	cfg.Open = 0
	cfg.Concurrent = 0
	_, _ = d.Cycle(context.Background(), cfg)
	if len(o.commands) != 2 || b.tasks[0].Status != "open" {
		t.Fatal("lowered limits mutated tasks/sessions")
	}
}

func TestChildSessionStates(t *testing.T) {
	d, b, o := fixture(1)
	_, _ = d.Cycle(context.Background(), defaults)
	r, _ := b.tasks[0].Reservation()
	o.sessions["child"] = Session{ID: "child", Parent: r.Session, Running: true, Waiting: true}
	state, active, err := classify(b.tasks[0], *r, o.sessions)
	if err != nil || state != Running || !active {
		t.Fatal("running parent with waiting background child", state, active, err)
	}
	parent := o.sessions[r.Session]
	parent.Running = false
	o.sessions[r.Session] = parent
	state, active, err = classify(b.tasks[0], *r, o.sessions)
	if err != nil || state != Waiting || active {
		t.Fatal(state, active, err)
	}
	o.sessions["other"] = Session{ID: "other", Parent: r.Session, Running: true}
	state, active, err = classify(b.tasks[0], *r, o.sessions)
	if err != nil || state != Running || !active {
		t.Fatal(state, active, err)
	}
}

func TestInconsistentAndOrphanInventory(t *testing.T) {
	for _, mode := range []string{"missing", "metadata", "closed-active", "orphan", "invalid-reservation", "extra-session"} {
		t.Run(mode, func(t *testing.T) {
			d, b, o := fixture(2)
			_, _ = d.Cycle(context.Background(), Config{time.Second, 1, 12})
			r, _ := b.tasks[0].Reservation()
			s := o.sessions[r.Session]
			switch mode {
			case "missing":
				delete(o.sessions, r.Session)
			case "metadata":
				s.Metadata = nil
				o.sessions[r.Session] = s
			case "closed-active":
				b.tasks[0].Status = "closed"
			case "orphan":
				b.tasks[0].Metadata = nil
			case "invalid-reservation":
				b.tasks[0].Metadata[MetadataKey] = json.RawMessage(`false`)
			case "extra-session":
				extra := *r
				extra.Session = "ses_orphan"
				data, _ := json.Marshal(extra)
				o.sessions[extra.Session] = Session{ID: extra.Session, Running: true, Metadata: map[string]json.RawMessage{MetadataKey: data}}
				s.Running = false
				o.sessions[r.Session] = s
			}
			_, err := d.Cycle(context.Background(), defaults)
			if err == nil || len(o.commands) != 1 {
				t.Fatal(mode, err, o.commands)
			}
		})
	}
}

func TestTemporaryBackendFailure(t *testing.T) {
	d, b, o := fixture(1)
	b.err = errors.New("bd unavailable")
	if _, err := d.Cycle(context.Background(), defaults); err == nil {
		t.Fatal("expected error")
	}
	b.err = nil
	o.snapshotErr = true
	if _, err := d.Cycle(context.Background(), defaults); err == nil {
		t.Fatal("expected error")
	}
	o.snapshotErr = false
	if _, err := d.Cycle(context.Background(), defaults); err != nil || len(o.commands) != 1 {
		t.Fatal(err)
	}
}

func TestTemporaryPreflightFailure(t *testing.T) {
	d, _, o := fixture(1)
	d.Preflight = func(context.Context) error { return errors.New("bd where unavailable") }
	if _, err := d.Cycle(context.Background(), defaults); err == nil || len(o.created) != 0 {
		t.Fatal(err, o.created)
	}
	d.Preflight = nil
	if _, err := d.Cycle(context.Background(), defaults); err != nil || len(o.commands) != 1 {
		t.Fatal(err, o.commands)
	}
}

func TestExecLargeResponseAndCleanup(t *testing.T) {
	ctx := context.Background()
	data, err := Exec(ctx, "python3", "-c", "import sys; sys.stdout.write('x' * 400000)")
	if err != nil || len(data) != 400000 {
		t.Fatal(len(data), err)
	}
	ctx, cancel := context.WithCancel(ctx)
	cancel()
	if _, err := Exec(ctx, "python3", "-c", "import time;time.sleep(30)"); err == nil {
		t.Fatal("ignored cancellation")
	}
}

func TestManualSessionsExcluded(t *testing.T) {
	d, _, o := fixture(1)
	for i := 0; i < 50; i++ {
		id := fmt.Sprint(i)
		o.sessions[id] = Session{ID: id, Running: true, Waiting: true}
	}
	n, err := d.Cycle(context.Background(), defaults)
	if err != nil || n.Active != 1 || n.Open != 1 {
		t.Fatal(n, err)
	}
}

func TestRunCancelDoesNotStopSessions(t *testing.T) {
	d, _, o := fixture(1)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	o.onCommand = cancel
	d.Run(ctx, func() (Config, error) { return defaults, nil })
	if len(o.sessions) != 1 || len(o.commands) != 1 {
		t.Fatal("session lost on stop")
	}
}

func TestConfig(t *testing.T) {
	dir := t.TempDir()
	g := filepath.Join(dir, "global")
	p := filepath.Join(dir, "project")
	c, err := LoadConfig(g, p)
	if err != nil || c != defaults {
		t.Fatal(c, err)
	}
	os.WriteFile(g, []byte("scheduler:\n  interval: 2m\n  max_concurrent_tasks: 4\n"), 0600)
	os.WriteFile(p, []byte("scheduler:\n  max_open_tasks: 3\n"), 0600)
	c, err = LoadConfig(g, p)
	if err != nil || c != (Config{2 * time.Minute, 4, 3}) {
		t.Fatal(c, err)
	}
	os.WriteFile(p, []byte("scheduler:\n  max_concurrent_tasks: 0\n"), 0600)
	c, err = LoadConfig(g, p)
	if err != nil || c.Concurrent != 0 || c.Open != 12 {
		t.Fatal(c, err)
	}
	for _, text := range []string{"scheduler:\n  interval: -1s", "scheduler:\n  max_open_tasks: -1", "scheduler:\n  selection: random", "scheduler:\n  typo: 1", "scheduler:\n  interval: huh", "---\n{}\n---\n{}", "scheduler: ["} {
		os.WriteFile(p, []byte(text), 0600)
		if _, err := LoadConfig(g, p); err == nil {
			t.Fatalf("accepted %q", text)
		}
	}
	t.Setenv("XDG_CONFIG_HOME", dir)
	global, project, err := ConfigPaths("/project")
	if err != nil || global != filepath.Join(dir, "mis/dispatcher.yaml") || project != "/project/.mis/dispatcher.yaml" {
		t.Fatal(global, project, err)
	}
}

func TestLock(t *testing.T) {
	dir := t.TempDir()
	l, err := Lock("/one", dir)
	if err != nil {
		t.Fatal(err)
	}
	if other, err := Lock("/one", dir); err == nil {
		other.Close()
		t.Fatal("duplicate lock")
	}
	other, err := Lock("/two", dir)
	if err != nil {
		t.Fatal(err)
	}
	other.Close()
	l.Close()
	l, err = Lock("/one", dir)
	if err != nil {
		t.Fatal(err)
	}
	l.Close()
}

func TestLockHelper(t *testing.T) {
	if os.Getenv("MIS_LOCK_HELPER") == "" {
		return
	}
	l, err := Lock("/crash", os.Getenv("MIS_LOCK_DIR"))
	if err != nil {
		os.Exit(2)
	}
	defer l.Close()
	fmt.Println("locked")
	select {}
}

func TestLockReleasedAfterCrash(t *testing.T) {
	dir := t.TempDir()
	cmd := exec.Command(os.Args[0], "-test.run=^TestLockHelper$")
	cmd.Env = append(os.Environ(), "MIS_LOCK_HELPER=1", "MIS_LOCK_DIR="+dir)
	pipe, err := cmd.StdoutPipe()
	if err != nil {
		t.Fatal(err)
	}
	if err = cmd.Start(); err != nil {
		t.Fatal(err)
	}
	defer func() { cmd.Process.Kill(); cmd.Wait() }()
	var out [7]byte
	if _, err = io.ReadFull(pipe, out[:]); err != nil || string(out[:]) != "locked\n" {
		t.Fatal(string(out[:]), err)
	}
	if l, err := Lock("/crash", dir); err == nil {
		l.Close()
		t.Fatal("second process acquired lock")
	}
	cmd.Process.Kill()
	cmd.Wait()
	l, err := Lock("/crash", dir)
	if err != nil {
		t.Fatal(err)
	}
	l.Close()
}

func TestReservationStringAndObject(t *testing.T) {
	r := Reservation{1, "/project", "test-1", "ses_1", "submitted"}
	data, _ := json.Marshal(r)
	text, _ := json.Marshal(string(data))
	for _, value := range []json.RawMessage{data, text} {
		task := Task{ID: r.Task, Metadata: map[string]json.RawMessage{MetadataKey: value}}
		got, err := task.Reservation()
		if err != nil || *got != r {
			t.Fatal(got, err)
		}
	}
}

func TestCommandUsesNativeAPI(t *testing.T) {
	var args []string
	o := OpenCodeCLI{Run: func(_ context.Context, name string, a ...string) ([]byte, error) {
		if name != "opencode" {
			t.Fatal(name)
		}
		args = a
		return nil, nil
	}}
	if err := o.Command(context.Background(), "ses_1", "task-1"); err != nil {
		t.Fatal(err)
	}
	if len(args) != 5 || args[2] != "/api/session/ses_1/command" {
		t.Fatal(args)
	}
	var body map[string]string
	json.Unmarshal([]byte(args[4]), &body)
	if !reflect.DeepEqual(body, map[string]string{"name": "mis-run", "text": "task-1"}) {
		t.Fatal(body)
	}
}

func TestSnapshotPaginationAndPending(t *testing.T) {
	r := Reservation{1, "/project", "test-1", "ses_1", "submitted"}
	metadata, _ := json.Marshal(r)
	calls := []string{}
	o := OpenCodeCLI{Root: "/project", Project: "p", Run: func(_ context.Context, name string, args ...string) ([]byte, error) {
		path := args[2]
		calls = append(calls, path)
		switch {
		case strings.Contains(path, "/api/session?"):
			if strings.Contains(path, "cursor=") {
				return []byte(`{"data":[{"id":"ses_child","parentID":"ses_1"},{"id":"ses_manual"}],"cursor":{"next":null}}`), nil
			}
			return []byte(`{"data":[{"id":"ses_1","metadata":{"mis_dispatcher":` + string(metadata) + `}}],"cursor":{"next":"nextpage"}}`), nil
		case path == "/api/session/active":
			return []byte(`{"data":{"ses_1":{"type":"running"},"ses_child":{"type":"running"},"ses_manual":{"type":"running"}}}`), nil
		case path == "/api/session/ses_child/permission":
			return []byte(`{"data":[{"id":"perm"}]}`), nil
		default:
			if strings.Contains(path, "ses_manual/") {
				t.Fatal("inspected manual session")
			}
			return []byte(`{"data":[]}`), nil
		}
	}}
	s, err := o.Snapshot(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if !s["ses_child"].Waiting || !s["ses_1"].Running || s["ses_manual"].Running {
		t.Fatal(s)
	}
	if len(calls) != 7 {
		t.Fatal(calls)
	}
}

func TestBeadsSaveGuardAndReadback(t *testing.T) {
	r := Reservation{1, "/project", "test-1", "ses_1", "reserved"}
	var output bytes.Buffer
	b := BeadsCLI{Root: "/project", Run: func(_ context.Context, name string, args ...string) ([]byte, error) {
		if name != "bd" {
			t.Fatal(name)
		}
		fmt.Fprintln(&output, args)
		if args[4] == "update" {
			return []byte(`[]`), nil
		}
		data, _ := json.Marshal(r)
		text, _ := json.Marshal(string(data))
		return []byte(`[{"id":"test-1","status":"open","metadata":{"mis_dispatcher":` + string(text) + `}}]`), nil
	}}
	if err := b.Save(context.Background(), Task{ID: r.Task}, r); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(output.String(), "--if-status open --if-assignee ") || !strings.Contains(output.String(), "--sandbox") || !strings.Contains(output.String(), "--readonly") {
		t.Fatal(output.String())
	}
}

func TestCanonicalProjectFromNestedAndSymlink(t *testing.T) {
	root := t.TempDir()
	for _, path := range []string{"docs/product", "docs/rules", "docs/spec", ".beads", ".opencode"} {
		if err := os.MkdirAll(filepath.Join(root, path), 0700); err != nil {
			t.Fatal(err)
		}
	}
	for _, path := range []string{"AGENTS.md", ".opencode/mis-installation"} {
		os.WriteFile(filepath.Join(root, path), []byte("fixture"), 0600)
	}
	link := filepath.Join(t.TempDir(), "link")
	if err := os.Symlink(root, link); err != nil {
		t.Fatal(err)
	}
	run := func(_ context.Context, name string, args ...string) ([]byte, error) {
		if name == "git" {
			return []byte("worktree " + link + "\x00HEAD 123\x00\x00worktree /linked\x00"), nil
		}
		return json.Marshal(map[string]string{"path": filepath.Join(root, ".beads")})
	}
	for _, key := range []string{"BEADS_DIR", "BEADS_DB", "BD_DB", "BEADS_DOLT_SERVER_DATABASE", "BEADS_DOLT_SERVER_HOST", "BEADS_DOLT_SERVER_PORT"} {
		t.Setenv(key, "")
	}
	got, err := CanonicalProject(context.Background(), "/linked/nested", run)
	if err != nil || got != root {
		t.Fatal(got, err)
	}
	t.Setenv("BEADS_DIR", "/other")
	if _, err := CanonicalProject(context.Background(), root, run); err == nil {
		t.Fatal("accepted ambient redirect")
	}
}

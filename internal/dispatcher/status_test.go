package dispatcher

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

type statusFixture struct {
	root            string
	rows            []statusIssue
	parents, blocks map[string][]string
	fail, raw       map[string]string
	calls           []string
}

func newStatusFixture(t *testing.T) *statusFixture {
	t.Helper()
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, ".beads"), 0700); err != nil {
		t.Fatal(err)
	}
	for _, key := range []string{"BEADS_DIR", "BEADS_DB", "BD_DB", "BEADS_DOLT_SERVER_DATABASE", "BEADS_DOLT_SERVER_HOST", "BEADS_DOLT_SERVER_PORT"} {
		t.Setenv(key, "")
	}
	return &statusFixture{root: root, parents: map[string][]string{}, blocks: map[string][]string{}, fail: map[string]string{}, raw: map[string]string{}}
}

func issue(id, kind, status string) statusIssue {
	p := 2
	return statusIssue{ID: id, Title: "Title " + id, Type: kind, Status: status, Priority: &p}
}

func (f *statusFixture) run(_ context.Context, name string, args ...string) ([]byte, error) {
	if name == "git" {
		return []byte("worktree " + f.root + "\x00HEAD abc\x00\x00"), nil
	}
	if name != "bd" || len(args) < 5 || args[0] != "-C" || args[1] != f.root || args[2] != "--readonly" {
		return nil, fmt.Errorf("unexpected/non-readonly call %s %v", name, args)
	}
	if args[3] == "where" {
		return json.Marshal(map[string]string{"path": filepath.Join(f.root, ".beads")})
	}
	if args[3] != "--json" {
		return nil, fmt.Errorf("expected JSON: %v", args)
	}
	a := args[4:]
	key := strings.Join(a, " ")
	f.calls = append(f.calls, key)
	if message := f.fail[a[0]]; message != "" {
		return nil, fmt.Errorf("%s", message)
	}
	if data, ok := f.raw[a[0]]; ok {
		return []byte(data), nil
	}
	switch a[0] {
	case "list":
		for _, flag := range []string{"--all", "--limit 0", "--max-rows 0", "--include-gates", "--include-ephemeral", "--include-infra", "--include-templates"} {
			if !strings.Contains(key, flag) {
				return nil, fmt.Errorf("incomplete inventory flags: %s", key)
			}
		}
		rows := []statusIssue{}
		for _, row := range f.rows {
			if len(a) > 2 && a[1] == "--parent" {
				found := false
				for _, parent := range f.parents[row.ID] {
					if parent == a[2] {
						found = true
					}
				}
				if !found {
					continue
				}
			}
			rows = append(rows, row)
		}
		return json.Marshal(rows)
	case "show":
		for _, row := range f.rows {
			if row.ID == a[1] {
				return json.Marshal([]statusIssue{row})
			}
		}
		return nil, fmt.Errorf("missing %s", a[1])
	case "dep":
		if len(a) < 6 || a[len(a)-3] != "--type" || a[len(a)-1] != "--direction=down" {
			return nil, fmt.Errorf("wrong direction")
		}
		kind := a[len(a)-2]
		ids := a[2 : len(a)-3]
		rows := []map[string]string{}
		for _, id := range ids {
			targets := f.parents[id]
			if kind == "blocks" {
				targets = f.blocks[id]
			}
			for _, target := range targets {
				if len(ids) == 1 {
					rows = append(rows, map[string]string{"id": target, "dependency_type": kind})
				} else {
					rows = append(rows, map[string]string{"issue_id": id, "depends_on_id": target, "type": kind})
				}
			}
		}
		return json.Marshal(rows)
	}
	return nil, fmt.Errorf("unexpected call: %s", key)
}

func (f *statusFixture) show(id string) (string, error) {
	var out bytes.Buffer
	err := ShowStatus(context.Background(), f.root, id, f.run, &out)
	return out.String(), err
}

func TestStatusTree(t *testing.T) {
	f := newStatusFixture(t)
	f.rows = []statusIssue{issue("e", "epic", "open"), issue("unrelated-id", "task", "open"), issue("closed", "task", "closed"), issue("started", "bug", "in_progress"), issue("standalone", "task", "open"), issue("external", "task", "open")}
	f.parents["unrelated-id"] = []string{"e"}
	f.parents["closed"] = []string{"e"}
	f.parents["started"] = []string{"e"}
	f.blocks["started"] = []string{"external", "closed"}
	text, err := f.show("")
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"- 🔵 **Title e** · `e` · закрыто 1/3 задач", "  - 🐛 ▶ 🔒 `started` Title started · ждёт `external`", "  - ○ `unrelated-id`", "**Без вехи**", "Счётчики — статусы прямых дочерних записей"} {
		if !strings.Contains(text, want) {
			t.Errorf("missing %q:\n%s", want, text)
		}
	}
	if strings.Contains(text, "`closed`") {
		t.Fatal("closed task or prerequisite leaked")
	}
	again, err := f.show("")
	if err != nil || again != text {
		t.Fatal("nondeterministic output", err)
	}
}

func TestStatusSelectedSubtree(t *testing.T) {
	f := newStatusFixture(t)
	f.rows = []statusIssue{issue("ancestor", "epic", "closed"), issue("chosen", "epic", "open"), issue("child", "task", "open"), issue("sibling", "task", "open"), issue("external", "task", "open")}
	f.parents["chosen"] = []string{"ancestor"}
	f.parents["sibling"] = []string{"ancestor"}
	f.parents["child"] = []string{"chosen"}
	f.blocks["child"] = []string{"external"}
	text, err := f.show("chosen")
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"закрыта, контекст", "состав не проверен", "закрыто 0/1 задач", "ждёт `external` Title external"} {
		if !strings.Contains(text, want) {
			t.Fatalf("missing %q:\n%s", want, text)
		}
	}
	if strings.Contains(text, "sibling") || strings.Contains(text, "- ○ `external`") {
		t.Fatal("scope expanded", text)
	}
	for _, call := range f.calls {
		if strings.HasPrefix(call, "list ") && !strings.HasPrefix(call, "list --parent ") {
			t.Fatal("unscoped inventory", call)
		}
	}
}

func TestStatusClosedContextAndEmptyEpic(t *testing.T) {
	f := newStatusFixture(t)
	f.rows = []statusIssue{issue("closed-parent", "epic", "closed"), issue("child", "task", "open"), issue("empty", "epic", "open")}
	f.parents["child"] = []string{"closed-parent"}
	text, err := f.show("")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(text, "закрыта, контекст") || !strings.Contains(text, "закрыто 0/0 задач") || strings.Count(text, "`child`") != 1 {
		t.Fatal(text)
	}
	f.rows = []statusIssue{issue("done", "task", "closed")}
	f.parents = map[string][]string{}
	text, err = f.show("")
	if err != nil || text != "Незавершённых работ нет\n" {
		t.Fatal(text, err)
	}
	text, err = f.show("done")
	if err != nil || !strings.Contains(text, "закрыта, контекст") {
		t.Fatal(text, err)
	}
}

func TestStatusFailures(t *testing.T) {
	for _, mode := range []string{"null", "malformed", "duplicate", "missing-id", "missing-parent", "parent-cycle", "multiple-parents", "missing-blocker", "block-cycle", "edge-shape", "offline"} {
		t.Run(mode, func(t *testing.T) {
			f := newStatusFixture(t)
			f.rows = []statusIssue{issue("a", "task", "open"), issue("b", "task", "open")}
			id := ""
			switch mode {
			case "null":
				f.raw["list"] = "null"
			case "malformed":
				f.raw["list"] = "[{"
			case "duplicate":
				f.rows = append(f.rows, f.rows[0])
			case "missing-id":
				id = "absent"
			case "missing-parent":
				f.parents["a"] = []string{"absent"}
			case "parent-cycle":
				f.parents["a"] = []string{"b"}
				f.parents["b"] = []string{"a"}
			case "multiple-parents":
				f.parents["a"] = []string{"b", "absent"}
			case "missing-blocker":
				f.blocks["a"] = []string{"absent"}
			case "block-cycle":
				f.blocks["a"] = []string{"b"}
				f.blocks["b"] = []string{"a"}
			case "edge-shape":
				f.raw["dep"] = `[{"surprise":true}]`
			case "offline":
				f.fail["list"] = "offline"
			}
			text, err := f.show(id)
			if err == nil || strings.Contains(text, "Незавершённых работ нет") {
				t.Fatalf("masked failure: %v\n%s", err, text)
			}
			if mode == "parent-cycle" || mode == "missing-parent" {
				if !strings.Contains(text, "Связи не подтверждены") {
					t.Fatal(text)
				}
			}
		})
	}
}

func TestStatusExceptionalFields(t *testing.T) {
	f := newStatusFixture(t)
	a := issue("a", "gate", "deferred")
	a.Title = "unknown\n\x1btitle"
	a.Priority = nil
	a.Assignee = "owner"
	due := time.Now().Add(-24 * time.Hour)
	a.Due = &due
	b := issue("b", "bug", "blocked")
	priority := 0
	b.Priority = &priority
	f.rows = []statusIssue{a, b}
	text, err := f.show("")
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"тип: gate", "статус: deferred", "приоритет неизвестен", "исполнитель: owner", "просрочено", "🐛 🔒", "P0", "причина блокировки не установлена"} {
		if !strings.Contains(text, want) {
			t.Fatalf("missing %q:\n%s", want, text)
		}
	}
	if strings.ContainsRune(text, '\x1b') {
		t.Fatal("terminal escape leaked")
	}
}

func TestStatusExplicitEdgesAndRedirect(t *testing.T) {
	f := newStatusFixture(t)
	f.rows = []statusIssue{issue("a", "task", "open"), issue("b", "epic", "open")}
	run := func(ctx context.Context, name string, args ...string) ([]byte, error) {
		if name == "bd" && len(args) > 8 && args[4] == "dep" {
			if args[6] == "a" && args[len(args)-2] == "parent-child" {
				return []byte(`[{"issue_id":"a","depends_on_id":"b","type":"parent-child"}]`), nil
			}
			return []byte("[]"), nil
		}
		return f.run(ctx, name, args...)
	}
	var out bytes.Buffer
	if err := ShowStatus(context.Background(), f.root, "", run, &out); err != nil || !strings.Contains(out.String(), "  - ○ `a`") {
		t.Fatal(out.String(), err)
	}
	t.Setenv("BEADS_DIR", "/elsewhere")
	if err := ShowStatus(context.Background(), f.root, "", run, &out); err == nil {
		t.Fatal("accepted redirected DB")
	}
}

func TestStatusBatchedCalls(t *testing.T) {
	for _, count := range []int{1, 128, 129, 500} {
		t.Run(fmt.Sprint(count), func(t *testing.T) {
			f := newStatusFixture(t)
			f.rows = append(f.rows, issue("e", "epic", "open"))
			for i := 0; i < count; i++ {
				id := fmt.Sprintf("task-%04d", i)
				status := "closed"
				if i%10 == 0 {
					status = "open"
				}
				f.rows = append(f.rows, issue(id, "task", status))
				f.parents[id] = []string{"e"}
				if i%10 == 0 && i > 0 {
					f.blocks[id] = []string{"task-0000"}
				}
			}
			text, err := f.show("")
			if err != nil || !strings.Contains(text, fmt.Sprintf("закрыто %d/%d задач", count-(count+9)/10, count)) {
				t.Fatal(text, err)
			}
			parentCalls, blockCalls := 0, 0
			for _, call := range f.calls {
				switch {
				case strings.HasSuffix(call, "--type parent-child --direction=down"):
					parentCalls++
				case strings.HasSuffix(call, "--type blocks --direction=down"):
					blockCalls++
				}
			}
			if parentCalls != (count+1+127)/128 || blockCalls != 1 || len(f.calls) != 1+parentCalls+blockCalls {
				t.Fatalf("per-issue CLI reads returned: %d parent, %d blocks, %d total", parentCalls, blockCalls, len(f.calls))
			}
		})
	}
}

func TestStatusBatchEdgeValidation(t *testing.T) {
	for _, raw := range []string{
		`[{"id":"b","dependency_type":"parent-child"}]`,
		`[{"issue_id":"foreign","depends_on_id":"b","type":"parent-child"}]`,
		`[{"issue_id":"a","depends_on_id":"","type":"parent-child"}]`,
		`[{"issue_id":"a","depends_on_id":"b","type":"blocks"}]`,
	} {
		f := newStatusFixture(t)
		f.rows = []statusIssue{issue("a", "task", "open"), issue("b", "epic", "open")}
		f.raw["dep"] = raw
		text, err := f.show("")
		if err == nil || !strings.Contains(text, "Связи не подтверждены") || strings.Contains(text, "закрыто 0/") {
			t.Fatalf("accepted invalid batch %s: %s, %v", raw, text, err)
		}
	}
}

func TestStatusBatchFailureAndDuplicates(t *testing.T) {
	f := newStatusFixture(t)
	f.rows = []statusIssue{issue("a", "task", "open"), issue("b", "epic", "open")}
	f.parents["a"] = []string{"b", "b"}
	text, err := f.show("")
	if err != nil || !strings.Contains(text, "закрыто 0/1 задач") {
		t.Fatal(text, err)
	}
	f.fail["dep"] = "offline"
	text, err = f.show("")
	if err == nil || !strings.Contains(text, "offline") || strings.Contains(text, "Незавершённых работ нет") {
		t.Fatal(text, err)
	}
}

func TestStatusLockAndMixedChildren(t *testing.T) {
	f := newStatusFixture(t)
	f.rows = []statusIssue{issue("e", "epic", "open"), issue("gate", "gate", "closed"), issue("child", "bug", "open")}
	f.parents["gate"] = []string{"e"}
	f.parents["child"] = []string{"e"}
	lock, err := Lock(f.root, t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer lock.Close()
	text, err := f.show("")
	if err != nil || !strings.Contains(text, "закрыто 1/2 записей") {
		t.Fatal(text, err)
	}
	// An inventory parent field contradicting typed edges must not produce a
	// reassuring counter or silently place the issue in the standalone group.
	f.rows[2].Parent = "missing"
	text, err = f.show("")
	if err == nil || !strings.Contains(text, "состав не проверен") || strings.Contains(text, "закрыто 1/2") {
		t.Fatal(text, err)
	}
}

func TestStatusExternalBlockCycle(t *testing.T) {
	f := newStatusFixture(t)
	f.rows = []statusIssue{issue("a", "task", "open"), issue("outside", "task", "open")}
	f.blocks["a"] = []string{"outside"}
	f.blocks["outside"] = []string{"a"}
	text, err := f.show("a")
	if err == nil || !strings.Contains(text, "цикл блокировок") || strings.Contains(text, "- ○ `outside`") {
		t.Fatal(text, err)
	}
}

func TestStatusMultipleBlockBatches(t *testing.T) {
	f := newStatusFixture(t)
	for i := 0; i < 260; i++ {
		id := fmt.Sprintf("task-%03d", i)
		f.rows = append(f.rows, issue(id, "task", "open"))
		if i > 0 {
			f.blocks[id] = []string{"task-000"}
		}
	}
	text, err := f.show("")
	if err != nil || strings.Count(text, "ждёт `task-000`") != 259 {
		t.Fatal(text, err)
	}
	if len(f.calls) != 7 { // inventory + three parent batches + three block batches
		t.Fatal("unexpected call count", len(f.calls))
	}
}

func TestStatusExternalBlockFrontier(t *testing.T) {
	f := newStatusFixture(t)
	f.rows = []statusIssue{issue("root", "epic", "open"), issue("child", "task", "open"), issue("x", "task", "open"), issue("y", "task", "open"), issue("z", "task", "closed")}
	f.parents["child"] = []string{"root"}
	f.blocks["child"] = []string{"x", "y"}
	f.blocks["x"] = []string{"y", "z"}
	f.blocks["y"] = []string{"x"}
	text, err := f.show("root")
	if err == nil || !strings.Contains(text, "цикл блокировок") || !strings.Contains(text, "ждёт `x` Title x, `y` Title y") || strings.Contains(text, "- ○ `x`") {
		t.Fatal(text, err)
	}
}

func TestStatusFailedBatchKeepsOtherBatches(t *testing.T) {
	f := newStatusFixture(t)
	for i := 0; i < 130; i++ {
		f.rows = append(f.rows, issue(fmt.Sprintf("task-%03d", i), "task", "open"))
	}
	run := func(ctx context.Context, name string, args ...string) ([]byte, error) {
		if name == "bd" && len(args) > 8 && args[4] == "dep" && args[6] == "task-000" && args[len(args)-2] == "parent-child" {
			return nil, fmt.Errorf("batch unavailable")
		}
		return f.run(ctx, name, args...)
	}
	var out bytes.Buffer
	err := ShowStatus(context.Background(), f.root, "", run, &out)
	if err == nil || !strings.Contains(out.String(), "batch unavailable") || !strings.Contains(out.String(), "- ○ `task-129`") || !strings.Contains(out.String(), "Связи не подтверждены") {
		t.Fatal(out.String(), err)
	}
}

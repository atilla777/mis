package dispatcher

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"sort"
	"strings"
	"time"
)

type statusIssue struct {
	ID       string     `json:"id"`
	Title    string     `json:"title"`
	Type     string     `json:"issue_type"`
	Status   string     `json:"status"`
	Parent   string     `json:"parent"`
	Priority *int       `json:"priority"`
	Assignee string     `json:"assignee"`
	Due      *time.Time `json:"due_at"`
}

type statusPlan struct {
	b                    BeadsCLI
	rows                 map[string]statusIssue
	children             map[string][]string
	parents              map[string][]string
	blocks               map[string][]string
	scope                map[string]bool
	bad                  map[string]bool
	diagnostics          []string
	membershipIncomplete bool
}

var statusListArgs = []string{"--all", "--limit", "0", "--max-rows", "0", "--include-gates", "--include-ephemeral", "--include-infra", "--include-templates", "--brief", "--flat"}

func (p *statusPlan) read(ctx context.Context, out any, args ...string) error {
	var raw json.RawMessage
	if err := p.b.call(ctx, false, &raw, args...); err != nil {
		return err
	}
	if len(raw) == 0 || raw[0] != '[' {
		return fmt.Errorf("bd %s: expected JSON array", args[0])
	}
	return json.Unmarshal(raw, out)
}

// ShowStatus never enters the scheduler or contacts OpenCode. All Beads calls
// use its enforced readonly mode; multiple reads are not a transactional snapshot.
func ShowStatus(ctx context.Context, cwd, id string, run Runner, out io.Writer) error {
	root, err := canonicalGitRoot(ctx, cwd, run)
	if err != nil {
		return err
	}
	if err := CheckBeads(ctx, root, run); err != nil {
		return err
	}
	p := statusPlan{b: BeadsCLI{Root: root, Run: run}, rows: map[string]statusIssue{}, children: map[string][]string{}, parents: map[string][]string{}, blocks: map[string][]string{}, scope: map[string]bool{}, bad: map[string]bool{}}
	if err := p.load(ctx, id); err != nil {
		return err
	}
	text := p.render(id, time.Now())
	if _, err := io.WriteString(out, text); err != nil {
		return err
	}
	if len(p.diagnostics) != 0 {
		return fmt.Errorf("status incomplete or inconsistent; see diagnostics")
	}
	return nil
}

func (p *statusPlan) add(row statusIssue) error {
	if row.ID == "" || row.Title == "" || row.Type == "" || row.Status == "" {
		return fmt.Errorf("incomplete issue row: %q", row.ID)
	}
	if _, exists := p.rows[row.ID]; exists {
		return fmt.Errorf("duplicate issue ID %s", row.ID)
	}
	p.rows[row.ID] = row
	return nil
}

func (p *statusPlan) get(ctx context.Context, id string) error {
	if _, ok := p.rows[id]; ok {
		return nil
	}
	var rows []statusIssue
	if err := p.read(ctx, &rows, "show", id, "--brief-deps"); err != nil {
		return err
	}
	if len(rows) != 1 || rows[0].ID != id {
		return fmt.Errorf("unexpected bd show result for %s", id)
	}
	return p.add(rows[0])
}

// Bound argv size as well as the number of CLI startups. Multi-ID dep list
// returns explicit source/target records; the single-ID form may return issues.
const statusEdgeBatchSize = 128

func (p *statusPlan) edges(ctx context.Context, ids []string, kind string) (map[string][]string, error) {
	result := make(map[string][]string, len(ids))
	for _, id := range ids {
		result[id] = nil
	}
	var rows []struct {
		ID             string `json:"id"`
		DependencyType string `json:"dependency_type"`
		Issue          string `json:"issue_id"`
		DependsOn      string `json:"depends_on_id"`
		Type           string `json:"type"`
	}
	args := append([]string{"dep", "list"}, ids...)
	args = append(args, "--type", kind, "--direction=down")
	if err := p.read(ctx, &rows, args...); err != nil {
		return nil, err
	}
	seen := map[string]map[string]bool{}
	for _, edge := range rows {
		source, target := edge.Issue, edge.DependsOn
		if len(ids) == 1 && edge.DependencyType == kind && edge.ID != "" {
			source, target = ids[0], edge.ID
		} else if edge.Type != kind {
			return nil, fmt.Errorf("unknown %s edge shape", kind)
		}
		if _, ok := result[source]; !ok || target == "" {
			return nil, fmt.Errorf("unknown %s edge endpoints", kind)
		}
		if seen[source] == nil {
			seen[source] = map[string]bool{}
		}
		if !seen[source][target] {
			result[source] = append(result[source], target)
			seen[source][target] = true
		}
	}
	for _, targets := range result {
		sort.Strings(targets)
	}
	return result, nil
}

func (p *statusPlan) problem(id, message string) {
	p.bad[id] = true
	p.membershipIncomplete = true
	p.diagnostics = append(p.diagnostics, id+": "+message)
}

func (p *statusPlan) load(ctx context.Context, selected string) error {
	expectedParents := map[string]string{}
	if selected == "" {
		var rows []statusIssue
		if err := p.read(ctx, &rows, append([]string{"list"}, statusListArgs...)...); err != nil {
			return err
		}
		for _, row := range rows {
			if err := p.add(row); err != nil {
				return err
			}
			p.scope[row.ID] = true
		}
	} else {
		if err := p.get(ctx, selected); err != nil {
			return err
		}
		var visit func(string) error
		visit = func(id string) error {
			if p.scope[id] {
				return nil
			}
			p.scope[id] = true
			var children []statusIssue
			args := append([]string{"list", "--parent", id}, statusListArgs...)
			if err := p.read(ctx, &children, args...); err != nil {
				return err
			}
			seen := map[string]bool{}
			for _, child := range children {
				if seen[child.ID] {
					return fmt.Errorf("duplicate child %s", child.ID)
				}
				seen[child.ID] = true
				if parent, ok := expectedParents[child.ID]; ok && parent != id {
					return fmt.Errorf("%s: inconsistent child selections", child.ID)
				}
				expectedParents[child.ID] = id
				if _, ok := p.rows[child.ID]; !ok {
					if err := p.add(child); err != nil {
						return err
					}
				}
				if err := visit(child.ID); err != nil {
					return err
				}
			}
			return nil
		}
		if err := visit(selected); err != nil {
			return err
		}
	}
	// Resolve parents, including ancestors outside a selected subtree.
	processed := map[string]bool{}
	for {
		pending := []string{}
		for id := range p.rows {
			if !processed[id] {
				pending = append(pending, id)
			}
		}
		if len(pending) == 0 {
			break
		}
		sort.Strings(pending)
		if len(pending) > statusEdgeBatchSize {
			pending = pending[:statusEdgeBatchSize]
		}
		edges, edgeErr := p.edges(ctx, pending, "parent-child")
		for _, id := range pending {
			processed[id] = true
			if edgeErr != nil {
				p.problem(id, edgeErr.Error())
				continue
			}
			parents := edges[id]
			p.parents[id] = parents
			if expected, ok := expectedParents[id]; ok && (len(parents) != 1 || parents[0] != expected) {
				p.problem(id, "состав детей расходится со связью родителя")
			}
			if parent := p.rows[id].Parent; parent != "" && (len(parents) != 1 || parents[0] != parent) {
				p.problem(id, "поле parent расходится со связью родителя")
			}
			if len(parents) > 1 {
				p.problem(id, "несколько родителей")
			}
			for _, parent := range parents {
				if selected == "" {
					if _, ok := p.rows[parent]; !ok {
						p.problem(id, "родитель "+parent+" отсутствует в inventory")
						continue
					}
				} else if err := p.get(ctx, parent); err != nil {
					p.problem(id, "родитель "+parent+" не проверен")
					continue
				}
				p.children[parent] = append(p.children[parent], id)
			}
		}
	}
	// Mark every member of parent cycles, not just the first repeated endpoint.
	for id := range p.rows {
		path := []string{}
		positions := map[string]int{}
		for current := id; current != ""; {
			if at, ok := positions[current]; ok {
				for _, member := range path[at:] {
					if !p.bad[member] {
						p.problem(member, "цикл родителей")
					}
				}
				break
			}
			positions[current] = len(path)
			path = append(path, current)
			if len(p.parents[current]) != 1 {
				break
			}
			current = p.parents[current][0]
		}
	}
	ids := []string{}
	for id := range p.scope {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	checkedBlocks := map[string]bool{}
	for len(ids) > 0 {
		batch := []string{}
		for len(ids) > 0 && len(batch) < statusEdgeBatchSize {
			id := ids[0]
			ids = ids[1:]
			if checkedBlocks[id] || p.rows[id].Status == "closed" {
				continue
			}
			checkedBlocks[id] = true
			batch = append(batch, id)
		}
		if len(batch) == 0 {
			continue
		}
		edges, edgeErr := p.edges(ctx, batch, "blocks")
		for _, id := range batch {
			if edgeErr != nil {
				p.diagnostics = append(p.diagnostics, id+": "+edgeErr.Error())
				continue
			}
			p.blocks[id] = edges[id]
			for _, blocker := range edges[id] {
				if err := p.get(ctx, blocker); err != nil {
					p.diagnostics = append(p.diagnostics, id+": блокер "+blocker+" не проверен")
				} else {
					ids = append(ids, blocker)
				}
			}
		}
	}
	// DFS checks the directed active prerequisite graph, including external paths.
	state := map[string]int{}
	var checkBlocks func(string)
	checkBlocks = func(id string) {
		if state[id] == 1 {
			p.diagnostics = append(p.diagnostics, id+": цикл блокировок")
			return
		}
		if state[id] == 2 {
			return
		}
		state[id] = 1
		for _, target := range p.blocks[id] {
			if row, ok := p.rows[target]; ok && row.Status != "closed" {
				checkBlocks(target)
			}
		}
		state[id] = 2
	}
	blockIDs := []string{}
	for id := range p.blocks {
		blockIDs = append(blockIDs, id)
	}
	sort.Strings(blockIDs)
	for _, id := range blockIDs {
		checkBlocks(id)
	}
	for parent := range p.children {
		sort.Strings(p.children[parent])
	}
	return nil
}

func cleanStatusText(s string) string {
	return strings.Map(func(r rune) rune {
		if r < 32 || r == 127 {
			return ' '
		}
		return r
	}, s)
}

func (p *statusPlan) render(selected string, now time.Time) string {
	var out strings.Builder
	visible := map[string]bool{}
	for id := range p.scope {
		if p.rows[id].Status == "closed" && id != selected {
			continue
		}
		seen := map[string]bool{}
		for current := id; current != "" && !seen[current]; {
			seen[current] = true
			visible[current] = true
			if len(p.parents[current]) != 1 {
				break
			}
			current = p.parents[current][0]
		}
	}
	ids := []string{}
	for id := range visible {
		if _, ok := p.rows[id]; ok {
			ids = append(ids, id)
		}
	}
	sort.Strings(ids)
	palette := []string{"🔵", "🟢", "🟠", "🟣", "🟡", "🔴"}
	colors := map[string]string{}
	// Stable assignment for this inventory, independent of map iteration.
	epics := []string{}
	for id, row := range p.rows {
		if row.Type == "epic" {
			epics = append(epics, id)
		}
	}
	sort.Strings(epics)
	for i, id := range epics {
		colors[id] = palette[i%len(palette)]
	}
	used := map[string]bool{}
	printed := map[string]bool{}
	hasCounters := false
	var emit func(string, int)
	emit = func(id string, depth int) {
		if printed[id] || !visible[id] || p.bad[id] {
			return
		}
		printed[id] = true
		row := p.rows[id]
		var marks []string
		if row.Type == "epic" {
			marks = append(marks, colors[id])
		}
		if row.Type == "bug" {
			marks = append(marks, "🐛")
			used["🐛"] = true
		}
		if row.Status == "in_progress" {
			marks = append(marks, "▶")
			used["▶"] = true
		}
		var blockers []string
		for _, target := range p.blocks[id] {
			endpoint, ok := p.rows[target]
			if ok && endpoint.Status == "closed" {
				continue
			}
			label := "`" + cleanStatusText(target) + "`"
			if !ok {
				label += " не проверен"
			} else if !visible[target] {
				label += " " + cleanStatusText(endpoint.Title)
			}
			blockers = append(blockers, label)
		}
		if row.Status == "blocked" || len(blockers) > 0 {
			marks = append(marks, "🔒")
			used["🔒"] = true
		}
		if len(marks) == 0 && row.Type == "task" {
			marks = append(marks, "○")
			used["○"] = true
		}
		fmt.Fprintf(&out, "%s- %s ", strings.Repeat("  ", depth), strings.Join(marks, " "))
		if row.Type == "epic" {
			fmt.Fprintf(&out, "**%s** · `%s`", cleanStatusText(row.Title), cleanStatusText(id))
		} else {
			fmt.Fprintf(&out, "`%s` %s", cleanStatusText(id), cleanStatusText(row.Title))
		}
		if row.Type != "epic" && row.Type != "task" && row.Type != "bug" {
			fmt.Fprintf(&out, " · тип: %s", cleanStatusText(row.Type))
		}
		switch row.Status {
		case "open", "in_progress", "blocked":
		case "closed":
			out.WriteString(" · закрыта, контекст")
		default:
			fmt.Fprintf(&out, " · статус: %s", cleanStatusText(row.Status))
		}
		if row.Priority == nil || *row.Priority < 0 || *row.Priority > 4 {
			out.WriteString(" · приоритет неизвестен")
		} else if *row.Priority <= 1 {
			fmt.Fprintf(&out, " · P%d", *row.Priority)
		}
		if row.Assignee != "" {
			fmt.Fprintf(&out, " · исполнитель: %s", cleanStatusText(row.Assignee))
		}
		if row.Due != nil && row.Due.Before(now) && row.Status != "closed" {
			fmt.Fprintf(&out, " · просрочено %s", row.Due.Format("2006-01-02"))
		}
		if row.Type == "epic" {
			total, closed := 0, 0
			noun := "задач"
			for _, child := range p.children[id] {
				c := p.rows[child]
				total++
				if c.Status == "closed" {
					closed++
				}
				if c.Type != "task" && c.Type != "bug" {
					noun = "записей"
				}
			}
			if p.membershipIncomplete || (selected != "" && !p.scope[id]) {
				out.WriteString(" · состав не проверен")
			} else {
				fmt.Fprintf(&out, " · закрыто %d/%d %s", closed, total, noun)
				hasCounters = true
			}
		}
		if len(blockers) > 0 {
			out.WriteString(" · ждёт " + strings.Join(blockers, ", "))
		} else if row.Status == "blocked" {
			out.WriteString(" · причина блокировки не установлена")
		}
		out.WriteByte('\n')
		for _, child := range p.children[id] {
			emit(child, depth+1)
		}
	}
	// Epic roots first, then standalone records. A missing/invalid ancestor never
	// silently reparents its descendants into a valid milestone.
	for _, id := range ids {
		if len(p.parents[id]) == 0 && p.rows[id].Type == "epic" {
			emit(id, 0)
		}
	}
	standalone := false
	for _, id := range ids {
		if len(p.parents[id]) == 0 && p.rows[id].Type != "epic" && !p.bad[id] {
			if !standalone {
				out.WriteString("\n**Без вехи**\n")
				standalone = true
			}
			emit(id, 0)
		}
	}
	unresolved := false
	for _, id := range ids {
		if printed[id] {
			continue
		}
		if !unresolved {
			out.WriteString("\n**⚠️ Связи не подтверждены**\n")
			unresolved = true
		}
		row := p.rows[id]
		fmt.Fprintf(&out, "- `%s` %s · тип: %s · статус: %s\n", cleanStatusText(id), cleanStatusText(row.Title), cleanStatusText(row.Type), cleanStatusText(row.Status))
	}
	if len(ids) == 0 && len(p.diagnostics) == 0 {
		out.WriteString("Незавершённых работ нет\n")
	}
	var legend []string
	for _, item := range []struct{ mark, label string }{{"○", "задача"}, {"▶", "в работе (Beads)"}, {"🔒", "заблокирована"}, {"🐛", "ошибка"}} {
		if used[item.mark] {
			legend = append(legend, item.mark+" "+item.label)
		}
	}
	if len(legend) > 0 {
		out.WriteString("\n" + strings.Join(legend, " · ") + "\n")
	}
	if hasCounters {
		out.WriteString("Счётчики — статусы прямых дочерних записей, не достижение критериев вехи.\n")
	}
	if len(p.diagnostics) > 0 {
		sort.Strings(p.diagnostics)
		out.WriteString("\n⚠️ Неполные или несогласованные данные:\n")
		for _, message := range p.diagnostics {
			out.WriteString("- " + cleanStatusText(message) + "\n")
		}
	}
	return out.String()
}

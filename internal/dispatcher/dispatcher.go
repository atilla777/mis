package dispatcher

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"sort"
	"strings"
	"time"
)

const MetadataKey = "mis_dispatcher"
const Protocol = "MIS dispatcher reservation v1"

type Reservation struct {
	Version int    `json:"version"`
	Project string `json:"project"`
	Task    string `json:"task"`
	Session string `json:"session"`
	Phase   string `json:"phase"`
}

type Task struct {
	ID       string                     `json:"id"`
	Type     string                     `json:"issue_type"`
	Status   string                     `json:"status"`
	Assignee string                     `json:"assignee"`
	Created  time.Time                  `json:"created_at"`
	Metadata map[string]json.RawMessage `json:"metadata"`
}

func (t Task) Reservation() (*Reservation, error) {
	b, ok := t.Metadata[MetadataKey]
	if !ok {
		return nil, nil
	}
	// bd --set-metadata stores string values, not parsed JSON objects.
	var text string
	if json.Unmarshal(b, &text) == nil {
		b = []byte(text)
	}
	var r Reservation
	if err := json.Unmarshal(b, &r); err != nil {
		return nil, fmt.Errorf("%s: invalid reservation: %w", t.ID, err)
	}
	if r.Version != 1 || r.Task != t.ID || !strings.HasPrefix(r.Session, "ses_") || r.Project == "" || (r.Phase != "reserved" && r.Phase != "submitted") {
		return nil, fmt.Errorf("%s: unsupported/inconsistent reservation", t.ID)
	}
	return &r, nil
}

type Beads interface {
	List(context.Context) ([]Task, error)
	Ready(context.Context) ([]Task, error)
	Get(context.Context, string) (Task, error)
	Save(context.Context, Task, Reservation) error
}

type Session struct {
	ID               string                     `json:"id"`
	Parent           string                     `json:"parentID"`
	Outcome          string                     `json:"outcome"`
	Metadata         map[string]json.RawMessage `json:"metadata"`
	Running, Waiting bool
}

type OpenCode interface {
	Snapshot(context.Context) (map[string]Session, error)
	Create(context.Context, Reservation) error
	Lookup(context.Context, string) (Session, error)
	Command(context.Context, string, string) error
}

type State string

const (
	Running   State = "RUNNING"
	Waiting   State = "WAITING_USER"
	Paused    State = "PAUSED"
	Failed    State = "FAILED"
	Completed State = "COMPLETED"
)

func linked(s Session, r Reservation) bool {
	var other Reservation
	return s.ID == r.Session && json.Unmarshal(s.Metadata[MetadataKey], &other) == nil && other.Version == r.Version && other.Project == r.Project && other.Task == r.Task && other.Session == r.Session
}

func classify(t Task, r Reservation, sessions map[string]Session) (State, bool, error) {
	s, ok := sessions[r.Session]
	if !ok {
		return Paused, false, fmt.Errorf("%s: session %s missing; reservation retained", t.ID, r.Session)
	}
	if !linked(s, r) {
		return Paused, false, fmt.Errorf("%s: session metadata mismatch", t.ID)
	}
	// Native child agents belong to the same task, including forms/permissions.
	family := map[string]bool{r.Session: true}
	for changed := true; changed; {
		changed = false
		for id, child := range sessions {
			if !family[id] && family[child.Parent] {
				family[id] = true
				changed = true
			}
		}
	}
	active, waiting := false, false
	for id := range family {
		child := sessions[id]
		waiting = waiting || child.Waiting
		// A background child waiting does not prove its parent is waiting.
		// Without a native drain-wait signal, count the running parent safely.
		active = active || (child.Running && !child.Waiting)
	}
	if t.Status == "closed" {
		if active || waiting {
			return Paused, active, fmt.Errorf("%s: Beads closed but session still active/waiting", t.ID)
		}
		return Completed, false, nil
	}
	if active {
		return Running, true, nil
	}
	if waiting {
		return Waiting, false, nil
	}
	if s.Outcome == "failed" {
		return Failed, false, nil
	}
	return Paused, false, nil
}

type Dispatcher struct {
	Root      string
	Beads     Beads
	OpenCode  OpenCode
	Out       io.Writer
	NewID     func() (string, error)
	Preflight func(context.Context) error
}

type Counts struct{ Ready, Active, Open, Started int }

func newID() (string, error) {
	var b [16]byte
	_, err := rand.Read(b[:])
	return "ses_mis_" + hex.EncodeToString(b[:]), err
}

func (d *Dispatcher) warn(err error) { fmt.Fprintf(d.Out, "Warning: %v\n", err) }

func (d *Dispatcher) Cycle(ctx context.Context, cfg Config) (Counts, error) {
	var n Counts
	if d.Preflight != nil {
		if err := d.Preflight(ctx); err != nil {
			return n, err
		}
	}
	tasks, err := d.Beads.List(ctx)
	if err != nil {
		return n, err
	}
	sessions, err := d.OpenCode.Snapshot(ctx)
	if err != nil {
		return n, err
	}
	seen := make(map[string]bool)
	reservations := make(map[string]Reservation)
	consistent := true
	for _, t := range tasks {
		r, e := t.Reservation()
		if e != nil {
			d.warn(e)
			consistent = false
			continue
		}
		if r == nil {
			continue
		}
		seen[t.ID] = true
		reservations[t.ID] = *r
		if r.Project != d.Root {
			d.warn(fmt.Errorf("%s: reservation belongs to %s", t.ID, r.Project))
			consistent = false
			continue
		}
		state, active, e := classify(t, *r, sessions)
		if e != nil {
			d.warn(e)
			consistent = false
		}
		if state != Completed {
			n.Open++
		}
		if active {
			n.Active++
		}
		fmt.Fprintf(d.Out, "%s %s (%s)\n", t.ID, state, r.Session)
		if r.Phase == "reserved" {
			d.warn(fmt.Errorf("%s: launch incomplete; inspect existing session/reservation manually, no automatic resubmit", t.ID))
		}
	}
	for _, s := range sessions {
		var r Reservation
		if json.Unmarshal(s.Metadata[MetadataKey], &r) == nil && r.Project == d.Root {
			stored, ok := reservations[r.Task]
			if !ok || !linked(s, stored) {
				d.warn(fmt.Errorf("orphan/conflicting dispatcher session %s: exact Beads link for %s missing", s.ID, r.Task))
				consistent = false
			}
		}
	}
	ready, err := d.Beads.Ready(ctx)
	if err != nil {
		return n, err
	}
	var eligible []Task
	for _, t := range ready {
		if eligibleTask(t) && !seen[t.ID] {
			eligible = append(eligible, t)
		}
	}
	sort.Slice(eligible, func(i, j int) bool {
		if eligible[i].Created.Equal(eligible[j].Created) {
			return eligible[i].ID < eligible[j].ID
		}
		return eligible[i].Created.Before(eligible[j].Created)
	})
	n.Ready = len(eligible)
	// Contradictory/missing inventory must not undercount limits.
	if !consistent {
		return n, fmt.Errorf("inconsistent task/session inventory; no new launches this cycle")
	}
	for _, candidate := range eligible {
		if n.Active >= cfg.Concurrent || n.Open >= cfg.Open {
			break
		}
		if err := ctx.Err(); err != nil {
			return n, err
		}
		// Re-read native ready immediately before reserving; /mis-run rechecks graph.
		fresh, e := d.Beads.Ready(ctx)
		if e != nil {
			return n, e
		}
		found := false
		for _, t := range fresh {
			if t.ID == candidate.ID && eligibleTask(t) {
				found = true
			}
		}
		if !found {
			continue
		}
		t, e := d.Beads.Get(ctx, candidate.ID)
		if e != nil {
			return n, e
		}
		if !eligibleTask(t) {
			continue
		}
		idgen := d.NewID
		if idgen == nil {
			idgen = newID
		}
		id, e := idgen()
		if e != nil {
			return n, e
		}
		r := Reservation{1, d.Root, t.ID, id, "reserved"}
		// Durable intent precedes create. Unknown writes are never blindly retried.
		if e = d.Beads.Save(ctx, t, r); e != nil {
			return n, fmt.Errorf("%s: reservation uncertain: %w", t.ID, e)
		}
		n.Open++
		fmt.Fprintf(d.Out, "Starting %s (%s)...\n", t.ID, id)
		if e = d.OpenCode.Create(ctx, r); e != nil {
			s, lookupErr := d.OpenCode.Lookup(ctx, id)
			if lookupErr != nil || !linked(s, r) {
				return n, fmt.Errorf("%s: create uncertain (%v); lookup: %v; retained reservation, no retry", t.ID, e, lookupErr)
			}
		}
		// Re-read reservation/status before submission; never steal manual claims.
		t, e = d.Beads.Get(ctx, t.ID)
		if e != nil {
			return n, e
		}
		stored, e := t.Reservation()
		if e != nil || stored == nil || *stored != r || t.Status != "open" || t.Assignee != "" {
			return n, fmt.Errorf("%s: changed before submission; inspect reservation", t.ID)
		}
		r.Phase = "submitted"
		if e = d.Beads.Save(ctx, t, r); e != nil {
			return n, e
		}
		// At-most-once submission: durable marker BEFORE API, including crash window.
		if e = d.OpenCode.Command(ctx, id, t.ID); e != nil {
			return n, fmt.Errorf("%s: command result uncertain: %w; continue existing session in OpenCode, no automatic resubmit", t.ID, e)
		}
		n.Started++
		// Reserve an active slot this cycle even if the API has not projected it yet.
		n.Active++
	}
	return n, nil
}

func eligibleTask(t Task) bool {
	_, reserved := t.Metadata[MetadataKey]
	return !reserved && t.ID != "" && !strings.HasPrefix(t.ID, "-") && !strings.ContainsAny(t.ID, " \t\r\n") && (t.Type == "task" || t.Type == "bug") && t.Status == "open" && t.Assignee == "" && !t.Created.IsZero()
}

func (d *Dispatcher) Run(ctx context.Context, load func() (Config, error)) {
	interval := 60 * time.Second
	for ctx.Err() == nil {
		cfg, err := load()
		if err == nil {
			interval = cfg.Interval
			fmt.Fprintf(d.Out, "Interval: %s; concurrent limit: %d; open tasks limit: %d\n", cfg.Interval, cfg.Concurrent, cfg.Open)
			n, e := d.Cycle(ctx, cfg)
			fmt.Fprintf(d.Out, "Ready: %d Active: %d Open: %d Started: %d\n", n.Ready, n.Active, n.Open, n.Started)
			err = e
		}
		if ctx.Err() != nil {
			break
		}
		if err != nil {
			d.warn(err)
		}
		fmt.Fprintf(d.Out, "Next check in %s\n", interval)
		timer := time.NewTimer(interval)
		select {
		case <-ctx.Done():
			timer.Stop()
		case <-timer.C:
		}
	}
	fmt.Fprintln(d.Out, "Dispatcher stopped; OpenCode sessions continue.")
}

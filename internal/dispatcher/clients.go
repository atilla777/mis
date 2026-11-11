package dispatcher

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/url"
	"os"
	"os/exec"
	"strings"
	"time"
)

// CLI transport intentionally preserves OpenCode's native discovery/authentication.
// Killing an API client on timeout/SIGINT does not interrupt the server session.
type Runner func(context.Context, string, ...string) ([]byte, error)

func Exec(ctx context.Context, name string, args ...string) ([]byte, error) {
	ctx, cancel := context.WithTimeout(ctx, 45*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, name, args...)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	// OpenCode 2.0.32 may exit before its piped stdout drains (observed truncated
	// /openapi.json at 196608/229376 bytes). A regular file avoids that CLI bug.
	dir := ""
	if info, err := os.Stat("/tmp/opencode"); err == nil && info.IsDir() {
		dir = "/tmp/opencode"
	}
	output, err := os.CreateTemp(dir, "mis-dispatcher-response-*")
	if err != nil {
		return nil, err
	}
	defer os.Remove(output.Name())
	defer output.Close()
	cmd.Stdout = output
	err = cmd.Run()
	if err != nil {
		return nil, fmt.Errorf("%s: %w: %s", name, err, strings.TrimSpace(stderr.String()))
	}
	if _, err := output.Seek(0, 0); err != nil {
		return nil, err
	}
	return io.ReadAll(output)
}

type BeadsCLI struct {
	Root string
	Run  Runner
}

func (b BeadsCLI) call(ctx context.Context, write bool, out any, args ...string) error {
	mode := "--readonly"
	if write {
		mode = "--sandbox"
	}
	data, err := b.Run(ctx, "bd", append([]string{"-C", b.Root, mode, "--json"}, args...)...)
	if err != nil {
		return err
	}
	if out != nil {
		return json.Unmarshal(data, out)
	}
	return nil
}
func (b BeadsCLI) List(ctx context.Context) ([]Task, error) {
	var rows []Task
	err := b.call(ctx, false, &rows, "list", "--all", "--limit", "0", "--flat")
	return rows, err
}
func (b BeadsCLI) Ready(ctx context.Context) ([]Task, error) {
	var rows []Task
	err := b.call(ctx, false, &rows, "ready", "--limit", "0")
	return rows, err
}
func (b BeadsCLI) Get(ctx context.Context, id string) (Task, error) {
	var rows []Task
	err := b.call(ctx, false, &rows, "show", id)
	if err != nil {
		return Task{}, err
	}
	if len(rows) != 1 || rows[0].ID != id {
		return Task{}, fmt.Errorf("unexpected bd show result for %s", id)
	}
	return rows[0], nil
}
func (b BeadsCLI) Save(ctx context.Context, t Task, r Reservation) error {
	data, err := json.Marshal(r)
	if err != nil {
		return err
	}
	if err = b.call(ctx, true, nil, "update", t.ID, "--set-metadata", MetadataKey+"="+string(data), "--if-status", "open", "--if-assignee", ""); err != nil {
		return err
	}
	current, err := b.Get(ctx, t.ID)
	if err != nil {
		return err
	}
	stored, err := current.Reservation()
	if err != nil {
		return err
	}
	if stored == nil || *stored != r || current.Status != "open" || current.Assignee != "" {
		return fmt.Errorf("%s: reservation read-back mismatch", t.ID)
	}
	return nil
}

type OpenCodeCLI struct {
	Root, Project string
	Run           Runner
}

func (o OpenCodeCLI) api(ctx context.Context, method, path string, body, out any) error {
	args := []string{"api", method, path}
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return err
		}
		args = append(args, "--data", string(data))
	}
	data, err := o.Run(ctx, "opencode", args...)
	if err != nil {
		return err
	}
	if out != nil {
		return json.Unmarshal(data, out)
	}
	return nil
}

func (o OpenCodeCLI) Lookup(ctx context.Context, id string) (Session, error) {
	var result struct {
		Data Session `json:"data"`
	}
	err := o.api(ctx, "get", "/api/session/"+url.PathEscape(id), nil, &result)
	if err == nil && result.Data.ID != id {
		err = fmt.Errorf("session read-back ID mismatch")
	}
	return result.Data, err
}
func (o OpenCodeCLI) Create(ctx context.Context, r Reservation) error {
	var result struct {
		Data Session `json:"data"`
	}
	err := o.api(ctx, "post", "/api/session", map[string]any{
		"id": r.Session, "title": "MIS: " + r.Task,
		"location": map[string]string{"directory": o.Root},
		"metadata": map[string]any{MetadataKey: r},
	}, &result)
	if err == nil && !linked(result.Data, r) {
		err = fmt.Errorf("session create read-back mismatch")
	}
	return err
}
func (o OpenCodeCLI) Command(ctx context.Context, session, task string) error {
	return o.api(ctx, "post", "/api/session/"+url.PathEscape(session)+"/command", map[string]string{"name": "mis-run", "text": task}, nil)
}

func (o OpenCodeCLI) Snapshot(ctx context.Context) (map[string]Session, error) {
	sessions := make(map[string]Session)
	cursor := ""
	seen := make(map[string]bool)
	for {
		q := url.Values{"project": {o.Project}, "limit": {"100"}}
		if cursor != "" {
			q.Set("cursor", cursor)
		}
		var page struct {
			Data   []Session `json:"data"`
			Cursor struct {
				Next *string `json:"next"`
			} `json:"cursor"`
		}
		if err := o.api(ctx, "get", "/api/session?"+q.Encode(), nil, &page); err != nil {
			return nil, err
		}
		for _, s := range page.Data {
			sessions[s.ID] = s
		}
		if page.Cursor.Next == nil || *page.Cursor.Next == "" || len(page.Data) == 0 {
			break
		}
		cursor = *page.Cursor.Next
		if seen[cursor] {
			return nil, fmt.Errorf("OpenCode repeated pagination cursor")
		}
		seen[cursor] = true
	}
	// Only inspect dispatcher roots and their native descendants, not manual sessions.
	family := make(map[string]bool)
	for id, s := range sessions {
		var r Reservation
		if json.Unmarshal(s.Metadata[MetadataKey], &r) == nil && r.Project == o.Root && r.Session == id {
			family[id] = true
		}
	}
	for changed := true; changed; {
		changed = false
		for id, s := range sessions {
			if !family[id] && family[s.Parent] {
				family[id] = true
				changed = true
			}
		}
	}
	var active struct {
		Data map[string]json.RawMessage `json:"data"`
	}
	if err := o.api(ctx, "get", "/api/session/active", nil, &active); err != nil {
		return nil, err
	}
	for id := range family {
		s := sessions[id]
		_, s.Running = active.Data[id]
		for _, resource := range []string{"form", "permission"} {
			var pending struct {
				Data []json.RawMessage `json:"data"`
			}
			if err := o.api(ctx, "get", "/api/session/"+url.PathEscape(id)+"/"+resource, nil, &pending); err != nil {
				return nil, err
			}
			s.Waiting = s.Waiting || len(pending.Data) > 0
		}
		sessions[id] = s
	}
	return sessions, nil
}

// Preflight is read-only: never install/init or submit a prompt to test capabilities.
func (o *OpenCodeCLI) Preflight(ctx context.Context) error {
	var spec struct {
		Paths map[string]map[string]json.RawMessage `json:"paths"`
	}
	if err := o.api(ctx, "get", "/openapi.json", nil, &spec); err != nil {
		return err
	}
	for path, method := range map[string]string{
		"/api/session": "post", "/api/session/active": "get", "/api/session/{sessionID}": "get",
		"/api/session/{sessionID}/command": "post", "/api/session/{sessionID}/form": "get", "/api/session/{sessionID}/permission": "get",
	} {
		if spec.Paths[path][method] == nil {
			return fmt.Errorf("OpenCode API lacks %s %s", method, path)
		}
	}
	q := url.Values{"location[directory]": {o.Root}}.Encode()
	var location struct {
		Project struct {
			ID string `json:"id"`
		} `json:"project"`
	}
	if err := o.api(ctx, "get", "/api/location?"+q, nil, &location); err != nil {
		return err
	}
	if location.Project.ID == "" {
		return fmt.Errorf("OpenCode did not identify project")
	}
	o.Project = location.Project.ID
	var commands struct {
		Data []struct {
			Name string `json:"name"`
		} `json:"data"`
	}
	if err := o.api(ctx, "get", "/api/command?"+q, nil, &commands); err != nil {
		return err
	}
	found := false
	for _, c := range commands.Data {
		if c.Name == "mis-run" {
			found = true
		}
	}
	if !found {
		return fmt.Errorf("/mis-run is not available; install/update MIS first")
	}
	var skills struct {
		Data []struct{ Name, Content string } `json:"data"`
	}
	if err := o.api(ctx, "get", "/api/skill?"+q, nil, &skills); err != nil {
		return err
	}
	for _, s := range skills.Data {
		if s.Name == "mis-flow-run" && strings.Contains(s.Content, Protocol) {
			return nil
		}
	}
	return fmt.Errorf("installed MIS lacks %s; update project skills first", Protocol)
}

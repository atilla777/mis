package dispatcher

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"syscall"
)

func CanonicalProject(ctx context.Context, cwd string, run Runner) (string, error) {
	root, err := ProjectRoot(ctx, cwd, run)
	if err != nil {
		return "", err
	}
	return root, CheckBeads(ctx, root, run)
}

func ProjectRoot(ctx context.Context, cwd string, run Runner) (string, error) {
	// Git's first worktree is the canonical checkout, even from linked worktrees.
	data, err := run(ctx, "git", "-C", cwd, "worktree", "list", "--porcelain", "-z")
	if err != nil {
		return "", err
	}
	first := strings.SplitN(string(data), "\x00", 2)[0]
	if !strings.HasPrefix(first, "worktree ") {
		return "", fmt.Errorf("cannot determine canonical Git checkout")
	}
	root, err := filepath.EvalSymlinks(strings.TrimPrefix(first, "worktree "))
	if err != nil {
		return "", err
	}
	for _, path := range []string{"AGENTS.md", "docs/product", "docs/rules", "docs/spec", ".opencode/mis-installation"} {
		if _, err := os.Stat(filepath.Join(root, path)); err != nil {
			return "", fmt.Errorf("not a prepared MIS project: %s: %w", path, err)
		}
	}
	return root, nil
}

func CheckBeads(ctx context.Context, root string, run Runner) error {
	// Reject ambient redirects instead of accidentally scheduling a different DB.
	for _, key := range []string{"BEADS_DIR", "BEADS_DB", "BD_DB", "BEADS_DOLT_SERVER_DATABASE", "BEADS_DOLT_SERVER_HOST", "BEADS_DOLT_SERVER_PORT"} {
		if os.Getenv(key) != "" {
			return fmt.Errorf("unset %s: dispatcher requires canonical project Beads", key)
		}
	}
	data, err := run(ctx, "bd", "-C", root, "--readonly", "where", "--json")
	if err != nil {
		return err
	}
	var where struct {
		Path string `json:"path"`
	}
	if err := json.Unmarshal(data, &where); err != nil {
		return err
	}
	beads, err := filepath.EvalSymlinks(where.Path)
	if err != nil {
		return err
	}
	if beads != filepath.Join(root, ".beads") {
		return fmt.Errorf("Beads workspace %s is not canonical project .beads", beads)
	}
	return nil
}

// Lock file is never unlinked: deleting a locked inode permits split-brain locks.
func Lock(root, dir string) (*os.File, error) {
	if err := os.MkdirAll(dir, 0700); err != nil {
		return nil, err
	}
	sum := sha256.Sum256([]byte(root))
	path := filepath.Join(dir, hex.EncodeToString(sum[:])+".lock")
	fd, err := syscall.Open(path, syscall.O_CREAT|syscall.O_RDWR|syscall.O_CLOEXEC|syscall.O_NOFOLLOW, 0600)
	if err != nil {
		return nil, err
	}
	f := os.NewFile(uintptr(fd), path)
	if err := syscall.Flock(fd, syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		f.Close()
		return nil, fmt.Errorf("dispatcher already running for %s: %w", root, err)
	}
	return f, nil
}

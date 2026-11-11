package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"

	"github.com/atilla777/mis/internal/dispatcher"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "mis-dispatcher:", err)
		os.Exit(1)
	}
}

func run() error {
	args := os.Args[1:]
	if len(args) == 1 && (args[0] == "--help" || args[0] == "-h") {
		fmt.Println("usage: mis-dispatcher [--status [ID]]\nWithout arguments: run the scheduler. --status: print the read-only plan once.")
		return nil
	}
	status := len(args) >= 1 && args[0] == "--status"
	if len(args) != 0 && (!status || len(args) > 2 || (len(args) == 2 && (args[1] == "" || args[1][0] == '-'))) {
		return fmt.Errorf("usage: mis-dispatcher [--status [ID]]")
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	cwd, err := os.Getwd()
	if err != nil {
		return err
	}
	if status {
		id := ""
		if len(args) == 2 {
			id = args[1]
		}
		return dispatcher.ShowStatus(ctx, cwd, id, dispatcher.Exec, os.Stdout)
	}
	root, err := dispatcher.ProjectRoot(ctx, cwd, dispatcher.Exec)
	if err != nil {
		return err
	}
	cache, err := os.UserCacheDir()
	if err != nil {
		return err
	}
	lock, err := dispatcher.Lock(root, filepath.Join(cache, "mis", "dispatcher"))
	if err != nil {
		return err
	}
	defer lock.Close()
	global, project, err := dispatcher.ConfigPaths(root)
	if err != nil {
		return err
	}
	o := &dispatcher.OpenCodeCLI{Root: root, Run: dispatcher.Exec}
	d := dispatcher.Dispatcher{Root: root, Beads: dispatcher.BeadsCLI{Root: root, Run: dispatcher.Exec}, OpenCode: o, Out: os.Stdout}
	d.Preflight = func(ctx context.Context) error {
		if err := dispatcher.CheckBeads(ctx, root, dispatcher.Exec); err != nil {
			return err
		}
		return o.Preflight(ctx)
	}
	fmt.Printf("MIS Dispatcher\nProject: %s\nPress Ctrl+C to stop.\n", root)
	// Retry temporary preflight failures on the same bounded scheduling loop.
	d.Run(ctx, func() (dispatcher.Config, error) {
		return dispatcher.LoadConfig(global, project)
	})
	return nil
}

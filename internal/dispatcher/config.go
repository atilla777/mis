package dispatcher

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"time"

	"gopkg.in/yaml.v3"
)

type Config struct {
	Interval         time.Duration
	Concurrent, Open int
}

func LoadConfig(global, project string) (Config, error) {
	c := Config{60 * time.Second, 6, 12}
	for _, path := range []string{global, project} {
		f, err := os.Open(path)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			return c, err
		}
		var doc struct {
			Scheduler struct {
				Interval   *string `yaml:"interval"`
				Concurrent *int    `yaml:"max_concurrent_tasks"`
				Open       *int    `yaml:"max_open_tasks"`
				Selection  *string `yaml:"selection"`
			} `yaml:"scheduler"`
		}
		d := yaml.NewDecoder(f)
		d.KnownFields(true)
		err = d.Decode(&doc)
		if err == io.EOF {
			err = nil
		}
		if err == nil {
			var extra any
			if e := d.Decode(&extra); e != io.EOF {
				err = fmt.Errorf("expected one YAML document")
			}
		}
		f.Close()
		if err != nil {
			return c, fmt.Errorf("%s: %w", path, err)
		}
		s := doc.Scheduler
		if s.Interval != nil {
			c.Interval, err = time.ParseDuration(*s.Interval)
			if err != nil {
				return c, fmt.Errorf("%s: interval: %w", path, err)
			}
		}
		if s.Concurrent != nil {
			c.Concurrent = *s.Concurrent
		}
		if s.Open != nil {
			c.Open = *s.Open
		}
		if s.Selection != nil && *s.Selection != "oldest_ready_first" {
			return c, fmt.Errorf("%s: unsupported selection", path)
		}
	}
	if c.Interval <= 0 || c.Concurrent < 0 || c.Open < 0 {
		return c, fmt.Errorf("interval must be positive; limits must be nonnegative")
	}
	return c, nil
}

func ConfigPaths(root string) (string, string, error) {
	dir, err := os.UserConfigDir()
	return filepath.Join(dir, "mis", "dispatcher.yaml"), filepath.Join(root, ".mis", "dispatcher.yaml"), err
}

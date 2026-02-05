package main

import (
	"crypto/sha1"
	"encoding/hex"
	"os"
	"path/filepath"
	"strings"
)

func expandHome(path string) string {
	if strings.HasPrefix(path, "~/") {
		if home, err := os.UserHomeDir(); err == nil {
			return filepath.Join(home, path[2:])
		}
	}
	return path
}

func resolveBaseDir() string {
	if env := os.Getenv("JOBWORKFLOW_ROOT"); env != "" {
		return env
	}

	cwd, err := os.Getwd()
	if err != nil {
		return "."
	}
	if hasRepoLayout(cwd) {
		return cwd
	}
	parent := filepath.Dir(cwd)
	if hasRepoLayout(parent) {
		return parent
	}

	return cwd
}

func hasRepoLayout(dir string) bool {
	if _, err := os.Stat(filepath.Join(dir, "trackers")); err != nil {
		return false
	}
	if _, err := os.Stat(filepath.Join(dir, "data")); err != nil {
		return false
	}
	return true
}

func slugify(value string) string {
	value = strings.TrimSpace(strings.ToLower(value))
	if value == "" {
		return ""
	}
	var b strings.Builder
	lastUnderscore := false
	for _, r := range value {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			b.WriteRune(r)
			lastUnderscore = false
			continue
		}
		if !lastUnderscore {
			b.WriteRune('_')
			lastUnderscore = true
		}
	}
	slug := strings.Trim(b.String(), "_")
	return slug
}

func shortHash(value string) string {
	sum := sha1.Sum([]byte(value))
	return hex.EncodeToString(sum[:4])
}

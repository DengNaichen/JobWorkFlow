package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

func runInitializationWithJob(company, position, url, jd, jobID string) (string, error) {
	baseDir := resolveBaseDir()
	trackersDir := filepath.Join(baseDir, "trackers")
	slug := trackerSlug(company, jobID, url, position)
	appDir := filepath.Join(baseDir, "data", "applications", slug)

	dirs := []string{trackersDir, filepath.Join(appDir, "resume"), filepath.Join(appDir, "cover")}
	for _, d := range dirs {
		if err := os.MkdirAll(d, 0755); err != nil {
			return "", err
		}
	}

	dateStr := time.Now().Format("2006-01-02")
	fileName := fmt.Sprintf("%s-%s.md", dateStr, slug)
	filePath := uniqueFilePath(trackersDir, fileName)

	displayCompany := strings.TrimSpace(company)
	if displayCompany == "" {
		displayCompany = "Unknown Company"
	}
	displayPosition := strings.TrimSpace(position)
	if displayPosition == "" {
		displayPosition = "Unknown Position"
	}
	displayJD := strings.TrimSpace(jd)
	if displayJD == "" {
		displayJD = "(no description)"
	}

	content := fmt.Sprintf(`---
company: %s
position: %s
status: Reviewed
next_action:
  - Wait for feedback
salary: 0
application_date: %s
website: 
reference_link: %s
resume_path: "[[data/applications/%s/resume/resume.pdf]]"
cover_letter_path: "[[data/applications/%s/cover/cover-letter.pdf]]"
---

## Job Description
%s

## Notes
- Created via Kaka Go MCP Tool
`, displayCompany, displayPosition, dateStr, url, filepath.Base(appDir), filepath.Base(appDir), displayJD)

	return filePath, os.WriteFile(filePath, []byte(content), 0644)
}

func trackerSlug(company, jobID, url, title string) string {
	if slug := slugify(company); slug != "" {
		return slug
	}
	if jobID != "" {
		return "job_" + jobID
	}
	if slug := slugify(title); slug != "" {
		return "job_" + slug
	}
	if url != "" {
		return "job_" + shortHash(url)
	}
	return "job_unknown"
}

func uniqueFilePath(dir, filename string) string {
	path := filepath.Join(dir, filename)
	if _, err := os.Stat(path); err != nil {
		return path
	}
	base := strings.TrimSuffix(filename, filepath.Ext(filename))
	ext := filepath.Ext(filename)
	for i := 1; i < 1000; i++ {
		candidate := filepath.Join(dir, fmt.Sprintf("%s-%d%s", base, i, ext))
		if _, err := os.Stat(candidate); err != nil {
			return candidate
		}
	}
	return path
}

func updateTrackerStatus(trackerPath, status string, dryRun bool) (string, error) {
	baseDir := resolveBaseDir()
	trackerPath = expandHome(trackerPath)
	absTracker := trackerPath
	if !filepath.IsAbs(trackerPath) {
		absTracker = filepath.Join(baseDir, trackerPath)
	}

	contentBytes, err := os.ReadFile(absTracker)
	if err != nil {
		return "", err
	}
	content := string(contentBytes)
	if !strings.HasPrefix(content, "---") {
		return "", fmt.Errorf("missing frontmatter")
	}
	parts := strings.SplitN(content, "---", 3)
	if len(parts) < 3 {
		return "", fmt.Errorf("invalid frontmatter")
	}
	raw := strings.TrimSuffix(parts[1], "\n")
	lines := strings.Split(raw, "\n")
	found := false
	var updated []string
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "status:") {
			updated = append(updated, "status: "+status)
			found = true
			continue
		}
		updated = append(updated, line)
	}
	if !found {
		updated = append(updated, "status: "+status)
	}
	newFrontmatter := strings.Join(updated, "\n")
	newContent := strings.Join([]string{"---", newFrontmatter, "---"}, "\n") + parts[2]
	if dryRun {
		return absTracker, nil
	}
	if err := os.WriteFile(absTracker, []byte(newContent), 0644); err != nil {
		return "", err
	}
	return absTracker, nil
}
